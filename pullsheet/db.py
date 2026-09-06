"""SQLite connection, schema load, reset, and fixture loading."""

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
    """Delete and recreate the database from schema.sql."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = connect(path)
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Runs
#


class DuplicateDelivery(Exception):
    """The same delivery has already been ingested."""

    def __init__(self, delivery_ref: str, run_id: int):
        super().__init__(f"already ingested as run {run_id}: {delivery_ref}")
        self.delivery_ref = delivery_ref
        self.run_id = run_id


def business_date(timestamp: str) -> str:
    """Which local day a run belongs to."""
    from zoneinfo import ZoneInfo

    from pullsheet import location

    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(location.TIMEZONE_NAME)).date().isoformat()


def open_run(conn: sqlite3.Connection, channel: str, delivery_ref: str | None = None,
             column_map: dict | None = None, now: str | None = None) -> int:
    """Start a run. It stays 'running' until it is finalized or rejected."""
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
    """FR-006, FR-009. A rejection is a recorded run, not a silence."""
    conn.execute(
        """UPDATE runs SET status = 'rejected', rejection_reason = ?, finalized_at = ?
            WHERE id = ?""",
        (reason, now or _now(), run_id),
    )
    conn.commit()
    return run_id


def previous_ok_run(conn: sqlite3.Connection, run_id: int) -> int | None:
    """The last run before this one that actually produced a sheet."""
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
    """Every run, newest first -- rejections included."""
    return conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


# The unit separator, used to join key components. Chosen because it cannot
# appear in a product description, a firm name or an agency record id.
SEP = "\u241f"

# What a human decision is ABOUT: this food, and this recall record.
#
def subject_key(identity_key: str, recall_source: str, recall_source_record_id: str) -> str:
    return SEP.join([identity_key, recall_source, recall_source_record_id])


# The same key, computed in SQL. The two must agree exactly; if they drift, a
# cleared line silently comes back. tests/unit/test_clearing_audit.py checks it.
SUBJECT_KEY_SQL = (
    "(i.identity_key || char(9247) || r.source || char(9247) || r.source_record_id)"
)


def previously_matched_pairs(conn: sqlite3.Connection, run_id: int) -> set[tuple[str, int]]:
    """What the previous good run already knew, as (item identity, recall id)."""
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
    """Freeze a run's counts and mark it good."""
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
    """FR-064. Product identity is the strongest thing the row actually carries."""
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
    """Load the committed inventory fixture through the real ingestion path."""
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
    """Recalls FIRST, then inventory."""
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


# Ingestion persistence (T036, T037)

def persist_records(conn: sqlite3.Connection, run_id: int, records: list) -> dict:
    """Write one delivery's rows into an open run: merges, then supersession.
    FR-064/FR-065 (merge): rows sharing an identity within a single export are
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
    """Read one file through an adapter and carry it through a whole run."""
    from pullsheet.adapters.base import AdapterRejection
    from pullsheet.matching.run import run_matcher
    from pullsheet.recalls.corpus import corpus_note

    ref = delivery_ref(path)
    try:
        run_id = open_run(conn, adapter.channel, ref, column_map, now)
    except DuplicateDelivery as dup:
        # Not an error and not a new run. Re-reading a file already ingested
        # would make it the baseline tomorrow's "new since" diff is measured
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
    """What was delivered, identified well enough to recognise a redelivery."""
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"{path.name}#{digest}"


if __name__ == "__main__":
    sys.exit(main())
