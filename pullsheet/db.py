"""SQLite connection, schema load, reset, and fixture loading.

No ORM. Every query is hand-written SQL in the module that owns it; this file
owns connection handling, the reset path, and loading the committed fixtures
that a demo starts from.

``--reset`` and ``--load-fixtures`` together put the database in a known state.
``scripts/demo_reset.sh`` (T053) is the operator-facing wrapper around them.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from pullsheet.matching.normalize import normalize

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "pullsheet" / "schema.sql"
DB_PATH = ROOT / "data" / "pullsheet.db"
FIXTURES = ROOT / "data" / "fixtures"


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """A connection with row access by name and foreign keys enforced."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def reset(path: Path = DB_PATH) -> None:
    """Delete and recreate the database from schema.sql.

    This is a development and rehearsal path only. It is not reachable from the
    application, and it is not how anything is removed at run time -- nothing in
    PullSheet deletes rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = connect(path)
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ===========================================================================
# Runs
# ===========================================================================
#
# One run is one delivery, from arrival to a finalized sheet. Everything the
# dashboard shows is scoped to a run, and only a run that reached 'ok' is ever
# shown as the current picture -- a rejected or half-finished delivery must not
# be able to blank a good sheet (FR-009).


class DuplicateDelivery(Exception):
    """The same delivery has already been ingested.

    Raised rather than silently re-ingested. A file dropped twice would
    otherwise become the baseline that tomorrow's "new since the last run" diff
    is measured against, and the day would report nothing new while hiding the
    real change.
    """

    def __init__(self, delivery_ref: str, run_id: int):
        super().__init__(f"already ingested as run {run_id}: {delivery_ref}")
        self.delivery_ref = delivery_ref
        self.run_id = run_id


def business_date(timestamp: str) -> str:
    """Which local day a run belongs to.

    "Every day" is a calendar question, and the calendar is the kitchen's, not
    UTC's. An export that lands at 6 p.m. Pacific is that day's export; grouping
    it by UTC date would file it under tomorrow and make the day it belongs to
    look like a day nothing arrived.
    """
    from zoneinfo import ZoneInfo

    from pullsheet import location

    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(location.TIMEZONE_NAME)).date().isoformat()


def open_run(conn: sqlite3.Connection, channel: str, delivery_ref: str | None = None,
             column_map: dict | None = None, now: str | None = None) -> int:
    """Start a run. It stays 'running' until it is finalized or rejected.

    The 'running' state is not bookkeeping. Rows are committed before the
    matcher is called, so without it a crash in between leaves a database full
    of inventory and no matches -- an empty sheet that looks like good news.
    """
    now = now or _now()
    if delivery_ref:
        prior = conn.execute(
            "SELECT id FROM runs WHERE delivery_ref = ?", (delivery_ref,)
        ).fetchone()
        if prior:
            raise DuplicateDelivery(delivery_ref, prior["id"])
    cur = conn.execute(
        """INSERT INTO runs (channel, delivery_ref, column_map, business_date,
                             started_at, status)
           VALUES (?,?,?,?,?,'running')""",
        (channel, delivery_ref, json.dumps(column_map) if column_map else None,
         business_date(now), now),
    )
    conn.commit()
    return cur.lastrowid


def reject_run(conn: sqlite3.Connection, run_id: int, reason: str,
               now: str | None = None) -> int:
    """FR-006, FR-009. A rejection is a recorded run, not a silence.

    It never touches inventory_records, so any existing pull sheet is left
    exactly as it was. A bad export must not be able to empty a good sheet.
    """
    conn.execute(
        """UPDATE runs SET status = 'rejected', rejection_reason = ?, finalized_at = ?
            WHERE id = ?""",
        (reason, now or _now(), run_id),
    )
    conn.commit()
    return run_id


def previous_ok_run(conn: sqlite3.Connection, run_id: int) -> int | None:
    """The last run before this one that actually produced a sheet.

    Not ``id - 1``. Diffing against a rejected or half-finished run would make
    every line read as new the following morning, which is how a real alert
    stops being worth reading.
    """
    row = conn.execute(
        "SELECT id FROM runs WHERE status = 'ok' AND id < ? ORDER BY id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    return row["id"] if row else None


def latest_ok_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """The current picture. Deliberately ignores 'running' and 'rejected'."""
    return conn.execute(
        "SELECT * FROM runs WHERE status = 'ok' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def get_run(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def recent_runs(conn: sqlite3.Connection, limit: int = 30) -> list[sqlite3.Row]:
    """Every run, newest first -- rejections included.

    A rejected delivery is part of the history an operator needs to see. Showing
    only the good ones would make a week of failed drops look like a quiet week.
    """
    return conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


#: The unit separator, used to join key components. Chosen because it cannot
#: appear in a product description, a firm name or an agency record id.
SEP = "\u241f"

#: What a human decision is ABOUT: this food, and this recall record.
#:
#: Deliberately not the match row id. A nightly run writes fresh match rows for
#: inventory that has not moved, so a clearing keyed to a row id would stop
#: applying the next morning -- and an operator would have to clear the same
#: false positive every day until they stopped reading the sheet.
def subject_key(identity_key: str, recall_source: str, recall_source_record_id: str) -> str:
    return SEP.join([identity_key, recall_source, recall_source_record_id])


#: The same key, computed in SQL. The two must agree exactly; if they drift, a
#: cleared line silently comes back. tests/unit/test_clearing_audit.py checks it.
SUBJECT_KEY_SQL = (
    "(i.identity_key || char(9247) || r.source || char(9247) || r.source_record_id)"
)


def previously_matched_pairs(conn: sqlite3.Connection, run_id: int) -> set[tuple[str, int]]:
    """What the previous good run already knew, as (item identity, recall id).

    Identity rather than row id, deliberately: a carried-over item is re-recorded
    every morning under a fresh inventory_records id, so a diff on ids would
    report the entire sheet as new every single day and the word would stop
    meaning anything.
    """
    previous = previous_ok_run(conn, run_id)
    if previous is None:
        return set()
    return {
        (r["identity_key"], r["recall_record_id"])
        for r in conn.execute(
            """SELECT i.identity_key AS identity_key, m.recall_record_id
                 FROM matches m JOIN inventory_records i ON i.id = m.inventory_record_id
                WHERE m.run_id = ?""",
            (previous,),
        )
    }


def finalize_run(conn: sqlite3.Connection, run_id: int, corpus_note: str | None = None,
                 now: str | None = None) -> dict:
    """Freeze a run's counts and mark it good.

    The counts are stored rather than derived on read because a past run's page
    must show the totals THAT run produced. Reading them live would print
    tonight's numbers above yesterday's lines, which is the kind of quietly
    wrong answer Principle V exists to prevent.

    Nothing here touches `matches`. Whether a match is new was decided by the
    matcher at the moment it wrote the row, so this never has to go back and
    edit a machine judgement after the fact.
    """
    counts = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(status = 'PULL') AS pulls,
                  SUM(status = 'HELD') AS helds,
                  SUM(is_new) AS news
             FROM matches WHERE run_id = ?""",
        (run_id,),
    ).fetchone()
    conn.execute(
        """UPDATE runs SET status = 'ok', finalized_at = ?, corpus_note = ?,
                           match_count = ?, pull_count = ?, held_count = ?
            WHERE id = ?""",
        (now or _now(), corpus_note, counts["total"] or 0,
         counts["pulls"] or 0, counts["helds"] or 0, run_id),
    )
    conn.commit()
    return {"run_id": run_id, "previous_run_id": previous_ok_run(conn, run_id),
            "match_count": counts["total"] or 0, "pull_count": counts["pulls"] or 0,
            "held_count": counts["helds"] or 0, "new_count": counts["news"] or 0}


def identity_key(location: str | None, gtin: str | None,
                 normalized_description: str, lot_code: str | None,
                 manufacturer: str | None = None,
                 manufacturer_item_code: str | None = None) -> str:
    """FR-064. Product identity is the strongest thing the row actually carries.

    GTIN first. Failing that, the manufacturer's own catalog number -- which is
    what a kitchen orders by, and is a far more stable identity than a
    description string that a catalog refresh can reword. The normalized
    description is the floor, so a row with neither still has a stable identity
    instead of being treated as unique every time.

    ``location`` is the storage location -- the freezer, not the building. One
    deployment is one location, so the building is not part of an identity; the
    cooler still is, because the same case in two coolers is two things to walk
    to.
    """
    if gtin:
        product_identity = gtin
    elif manufacturer and manufacturer_item_code:
        product_identity = f"{manufacturer.strip().lower()}#{manufacturer_item_code.strip().upper()}"
    else:
        product_identity = normalized_description
    return SEP.join([location or "", product_identity, lot_code or ""])


def _digits(value: str | None) -> str | None:
    if not value:
        return None
    kept = "".join(c for c in value if c.isdigit())
    return kept or None


def load_inventory_fixture(conn: sqlite3.Connection, now: str | None = None) -> int:
    """Load the committed inventory fixture through the real ingestion path.

    Not a second reader. It opens a run, hands the file to the drop adapter, and
    persists it exactly as a scheduled delivery would -- so a rehearsal database
    and a demo database contain the same rows, merged the same way, with the
    same counts. Two readers for one file is two places for the demo's headline
    numbers to disagree with the demo.

    ``data/fixtures/unit_costs.csv`` fills in the handful of rows whose export
    left the cost column blank. It is a supplement to what arrived, applied
    after the fact and only where the source said nothing -- never an override.
    """
    from pullsheet.adapters.sftp_drop import SftpDropAdapter

    path = FIXTURES / "inventory_lincoln.csv"
    result = ingest_file(conn, path, SftpDropAdapter(), now=now)
    if result["status"] != "ok":
        raise RuntimeError(f"fixture load failed: {result.get('reason')}")

    cost_file = FIXTURES / "unit_costs.csv"
    if cost_file.exists():
        with cost_file.open() as f:
            for row in csv.DictReader(f):
                if not row["unit_cost"].strip():
                    continue
                conn.execute(
                    """UPDATE inventory_records SET unit_cost = ?
                        WHERE raw_description = ? AND unit_cost IS NULL""",
                    (float(row["unit_cost"]), row["item_description"]),
                )
        conn.commit()
    return result["records_written"]


def load_menu_fixtures(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {}

    with (FIXTURES / "recipes.csv").open() as f:
        rows = list(csv.DictReader(f))
        conn.executemany(
            "INSERT OR REPLACE INTO recipes (id, name, provenance) VALUES (?,?,?)",
            [(r["recipe_id"], r["name"], r["provenance"]) for r in rows],
        )
        counts["recipes"] = len(rows)

    with (FIXTURES / "recipe_ingredients.csv").open() as f:
        rows = list(csv.DictReader(f))
        conn.executemany(
            """INSERT INTO recipe_ingredients (recipe_id, ingredient_name, normalized_name)
               VALUES (?,?,?)""",
            # Normalized by the SAME function the matcher uses, so a recalled item
            # reaches recipes through one code path rather than two.
            [(r["recipe_id"], r["ingredient_name"], normalize(r["ingredient_name"])) for r in rows],
        )
        counts["recipe_ingredients"] = len(rows)

    with (FIXTURES / "recipe_components.csv").open() as f:
        rows = list(csv.DictReader(f))
        conn.executemany(
            "INSERT INTO recipe_components (recipe_id, component) VALUES (?,?)",
            [(r["recipe_id"], r["component"]) for r in rows],
        )
        counts["recipe_components"] = len(rows)

    with (FIXTURES / "service_days.csv").open() as f:
        rows = list(csv.DictReader(f))
        conn.executemany(
            "INSERT INTO service_days (date, recipe_id, planned_meals) VALUES (?,?,?)",
            [(r["date"], r["recipe_id"], int(r["planned_meals"])) for r in rows],
        )
        counts["service_days"] = len(rows)

    conn.commit()
    return counts


def load_fixtures(path: Path = DB_PATH) -> dict[str, int]:
    """Recalls FIRST, then inventory.

    Order is load-bearing now that ingesting an export runs the matcher and
    finalizes a run in one step: an inventory loaded before the corpus would be
    matched against nothing and finalize a run reading "no recalled items found"
    -- the exact false all-clear this whole application exists to prevent.
    """
    conn = connect(path)
    from pullsheet.recalls.corpus import load_snapshots
    counts = {"recall_records": sum(load_snapshots(conn).values())}
    counts.update(load_menu_fixtures(conn))
    counts["inventory_records"] = load_inventory_fixture(conn)

    conn.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pullsheet.db", description=__doc__)
    ap.add_argument("--reset", action="store_true", help="delete and recreate the database")
    ap.add_argument("--load-fixtures", action="store_true", help="load committed fixtures")
    args = ap.parse_args(argv)

    if not (args.reset or args.load_fixtures):
        ap.print_help()
        return 1
    if args.reset:
        reset()
        print(f"reset {DB_PATH.relative_to(ROOT)}")
    if args.load_fixtures:
        for table, n in load_fixtures().items():
            print(f"  {table}: {n}")
    return 0



# ===========================================================================
# Ingestion persistence (T036, T037)
# ===========================================================================

def persist_records(conn: sqlite3.Connection, run_id: int, records: list) -> dict:
    """Write one delivery's rows into an open run: merges, then supersession.

    FR-064/FR-065 (merge): rows sharing an identity within a single export are
    one record with summed quantities, and every contributing source row number
    is retained in ``merged_from`` -- so a total can always be traced back to the
    lines that produced it.
    """
    merged: dict[str, dict] = {}
    for rec in records:
        norm = normalize(rec.raw_description)
        key = identity_key(rec.storage_location, rec.gtin, norm, rec.lot_code,
                           rec.manufacturer, rec.manufacturer_item_code)
        existing = merged.get(key)
        if existing is None:
            merged[key] = {"rec": rec, "norm": norm, "rows": [rec.source_row],
                           "quantity": rec.quantity}
            continue
        existing["rows"].append(rec.source_row)
        # A missing quantity does not become zero and does not swallow a known
        # one: None + 5 is 5, and None + None stays None.
        if rec.quantity is not None:
            existing["quantity"] = (existing["quantity"] or 0) + rec.quantity

    new_ids: dict[str, int] = {}
    for key, item in merged.items():
        rec = item["rec"]
        cur = conn.execute(
            """INSERT INTO inventory_records
               (run_id, storage_location, raw_description, normalized_description,
                quantity, unit, pack_size, gtin, lot_code,
                brand, manufacturer, manufacturer_item_code, vendor_name,
                vendor_item_code, unit_cost,
                received_date, unpopulated_fields, identity_key, merged_from)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, rec.storage_location, rec.raw_description, item["norm"],
             item["quantity"], rec.unit, rec.pack_size, rec.gtin,
             rec.lot_code, rec.brand, rec.manufacturer, rec.manufacturer_item_code,
             rec.vendor_name, rec.vendor_item_code,
             rec.unit_cost, rec.received_date,
             json.dumps(sorted(rec.unpopulated)), key,
             json.dumps(item["rows"]) if len(item["rows"]) > 1 else None),
        )
        new_ids[key] = cur.lastrowid

    # Supersession. A later export replaces the rows it has a counterpart for,
    # and the old rows are RETAINED with superseded_by set -- so a pull sheet can
    # still be reconstructed as it stood, and any decisions taken against those
    # rows still resolve.
    #
    # A row with no counterpart in the new export is deliberately left ACTIVE.
    # An item vanishing from an export is not proof it left the freezer; the
    # export may simply be incomplete, and quietly dropping it would be the one
    # kind of disappearance this system exists to prevent. This is why the pull
    # sheet is never scoped by which run delivered a row -- see matching/run.py,
    # which re-matches the whole active set into every run.
    superseded = 0
    for old in conn.execute(
        """SELECT id, identity_key FROM inventory_records
            WHERE superseded_by IS NULL AND run_id IS NOT ?""",
        (run_id,),
    ).fetchall():
        replacement = new_ids.get(old["identity_key"])
        if replacement:
            conn.execute("UPDATE inventory_records SET superseded_by = ? WHERE id = ?",
                         (replacement, old["id"]))
            superseded += 1

    conn.execute(
        "UPDATE runs SET rows_read = ?, rows_partial = ? WHERE id = ?",
        (len(records), sum(1 for r in records if r.unpopulated), run_id),
    )
    conn.commit()
    return {"run_id": run_id, "rows_read": len(records), "records_written": len(merged),
            "merged_away": len(records) - len(merged), "superseded": superseded}


def ingest_file(conn: sqlite3.Connection, path: Path, adapter,
                column_map: dict | None = None, now: str | None = None) -> dict:
    """Read one file through an adapter and carry it through a whole run.

    Always returns a result and never raises past the caller: a folder poller
    that dies on a bad file stops watching the folder.
    """
    from pullsheet.adapters.base import AdapterRejection
    from pullsheet.matching.run import run_matcher
    from pullsheet.recalls.corpus import corpus_note

    ref = delivery_ref(path)
    try:
        run_id = open_run(conn, adapter.channel, ref, column_map, now)
    except DuplicateDelivery as dup:
        # Not an error and not a new run. Re-reading a file already ingested
        # would make it the baseline tomorrow's "new since" diff is measured
        # against, and the day would report nothing new while hiding the change.
        return {"status": "duplicate", "run_id": dup.run_id, "filename": path.name,
                "reason": str(dup)}

    try:
        records = list(adapter.read(path, column_map) if column_map else adapter.read(path))
    except AdapterRejection as rejection:
        reject_run(conn, run_id, str(rejection), now)
        return {"status": "rejected", "run_id": run_id, "reason": str(rejection),
                "filename": path.name}

    result = persist_records(conn, run_id, records)
    result["matches"] = run_matcher(conn, run_id, now=now)
    result.update(finalize_run(conn, run_id, corpus_note(conn), now))
    result["status"] = "ok"
    result["filename"] = path.name
    return result


def delivery_ref(path: Path) -> str:
    """What was delivered, identified well enough to recognise a redelivery.

    Filename AND content hash. Filename alone would refuse a genuine second
    export that happens to reuse a name; the hash alone would accept the same
    file dropped twice under two names.
    """
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"{path.name}#{digest}"


if __name__ == "__main__":
    sys.exit(main())
