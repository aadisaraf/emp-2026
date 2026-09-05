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


def identity_key(site: str, location: str | None, gtin: str | None,
                 normalized_description: str, lot_code: str | None) -> str:
    """FR-064. ``product_identity`` is the GTIN when there is one and the
    normalized description otherwise, so a row without a barcode still has a
    stable identity instead of being treated as unique every time."""
    product_identity = gtin or normalized_description
    return "␟".join([site, location or "", product_identity, lot_code or ""])


def _digits(value: str | None) -> str | None:
    if not value:
        return None
    kept = "".join(c for c in value if c.isdigit())
    return kept or None


def load_inventory_fixture(conn: sqlite3.Connection) -> int:
    """Load the committed inventory fixture directly.

    This is the fixture path, not the ingestion path: the adapters in
    ``pullsheet/adapters/`` are how inventory arrives at run time. This exists so
    a rehearsal can start from a known database without waiting on a folder poll.
    """
    path = FIXTURES / "inventory_lincoln.csv"
    costs = {}
    cost_file = FIXTURES / "unit_costs.csv"
    if cost_file.exists():
        with cost_file.open() as f:
            for row in csv.DictReader(f):
                if row["unit_cost"].strip():
                    costs[row["item_description"]] = float(row["unit_cost"])

    now = _now()
    n = 0
    with path.open() as f:
        for source_row, row in enumerate(csv.DictReader(f), start=1):
            desc = row["Item Description"]
            unpopulated = []
            qty = row["Qty On Hand"].strip()
            if not qty:
                unpopulated.append("quantity")          # FR-007: kept, flagged, never dropped
            gtin = _digits(row["Case UPC"])
            if not gtin:
                unpopulated.append("gtin")
            lot = row["Lot #"] or None                   # verbatim (R3)
            if not lot:
                unpopulated.append("lot_code")
            raw_cost = row["Unit Cost"].strip()
            cost = float(raw_cost) if raw_cost else costs.get(desc)
            if cost is None:
                unpopulated.append("unit_cost")

            norm = normalize(desc)
            conn.execute(
                """INSERT INTO inventory_records
                   (site, storage_location, raw_description, normalized_description,
                    quantity, unit, pack_size, gtin, upc, lot_code, unit_cost,
                    received_date, unpopulated_fields, identity_key, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (row["Site"], row["Storage Location"] or None, desc, norm,
                 float(qty) if qty else None, row["UOM"] or None, row["Pack Size"] or None,
                 gtin, gtin, lot, cost, row["Received Date"] or None,
                 json.dumps(unpopulated),
                 identity_key(row["Site"], row["Storage Location"], gtin, norm, lot),
                 now),
            )
            n += 1
    conn.commit()
    return n


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
            "INSERT INTO service_days (date, site, recipe_id, planned_meals) VALUES (?,?,?,?)",
            [(r["date"], r["site"], r["recipe_id"], int(r["planned_meals"])) for r in rows],
        )
        counts["service_days"] = len(rows)

    conn.commit()
    return counts


def load_fixtures(path: Path = DB_PATH) -> dict[str, int]:
    conn = connect(path)
    counts = {"inventory_records": load_inventory_fixture(conn)}
    counts.update(load_menu_fixtures(conn))

    from pullsheet.recalls.corpus import load_snapshots
    counts["recall_records"] = sum(load_snapshots(conn).values())

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


if __name__ == "__main__":
    sys.exit(main())


# ===========================================================================
# Ingestion persistence (T036, T037)
# ===========================================================================

def ensure_source(conn: sqlite3.Connection, name: str, adapter: str,
                  provenance: str = "live",
                  column_map: dict | None = None) -> int:
    """Find or create an inventory source, remembering its column mapping."""
    row = conn.execute(
        "SELECT id, column_map FROM inventory_sources WHERE name = ? AND adapter = ?",
        (name, adapter),
    ).fetchone()
    if row:
        if column_map is not None:
            conn.execute("UPDATE inventory_sources SET column_map = ? WHERE id = ?",
                         (json.dumps(column_map), row["id"]))
            conn.commit()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO inventory_sources (name, adapter, column_map, provenance) VALUES (?,?,?,?)",
        (name, adapter, json.dumps(column_map) if column_map else None, provenance),
    )
    conn.commit()
    return cur.lastrowid


def record_rejection(conn: sqlite3.Connection, source_id: int, filename: str,
                     adapter: str, reason: str) -> int:
    """FR-006, FR-009. A rejection is a recorded run, not a silence.

    It never touches inventory_records, so any existing pull sheet is left
    exactly as it was. A bad export must not be able to empty a good sheet.
    """
    cur = conn.execute(
        """INSERT INTO ingest_runs
           (source_id, filename, arrived_at, row_count, rows_parsed, rows_partial,
            status, rejection_reason, adapter)
           VALUES (?,?,?,0,0,0,'rejected',?,?)""",
        (source_id, filename, _now(), reason, adapter),
    )
    conn.commit()
    return cur.lastrowid


def persist_records(conn: sqlite3.Connection, source_id: int, filename: str,
                    adapter: str, records: list) -> dict:
    """Write one successful ingest: the run, its rows, merges, and supersession.

    FR-064/FR-065 (merge): rows sharing an identity within a single export are
    one record with summed quantities, and every contributing source row number
    is retained in ``merged_from`` -- so a total can always be traced back to the
    lines that produced it.
    """
    merged: dict[str, dict] = {}
    for rec in records:
        norm = normalize(rec.raw_description)
        key = identity_key(rec.site, rec.storage_location, rec.gtin, norm, rec.lot_code)
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

    cur = conn.execute(
        """INSERT INTO ingest_runs
           (source_id, filename, arrived_at, row_count, rows_parsed, rows_partial,
            status, adapter)
           VALUES (?,?,?,?,?,?,'ok',?)""",
        (source_id, filename, _now(), len(records), len(records),
         sum(1 for r in records if r.unpopulated), adapter),
    )
    run_id = cur.lastrowid
    now = _now()

    sites = {r.site for r in records}
    new_ids: dict[str, int] = {}

    for key, item in merged.items():
        rec = item["rec"]
        cur = conn.execute(
            """INSERT INTO inventory_records
               (site, storage_location, raw_description, normalized_description,
                quantity, unit, pack_size, gtin, upc, lot_code, unit_cost,
                received_date, source_export_id, unpopulated_fields, identity_key,
                merged_from, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rec.site, rec.storage_location, rec.raw_description, item["norm"],
             item["quantity"], rec.unit, rec.pack_size, rec.gtin, rec.upc,
             rec.lot_code, rec.unit_cost, rec.received_date, run_id,
             json.dumps(sorted(rec.unpopulated)), key,
             json.dumps(item["rows"]) if len(item["rows"]) > 1 else None, now),
        )
        new_ids[key] = cur.lastrowid

    # Supersession. A later export for a site replaces the rows it has a
    # counterpart for, and the old rows are RETAINED with superseded_by set --
    # so a pull sheet can still be reconstructed as it stood, and any decisions
    # taken against those rows still resolve.
    #
    # A row with no counterpart in the new export is deliberately left ACTIVE.
    # An item vanishing from an export is not proof it left the freezer; the
    # export may simply be incomplete, and quietly dropping it would be the one
    # kind of disappearance this system exists to prevent.
    superseded = 0
    for site in sites:
        for old in conn.execute(
            """SELECT id, identity_key FROM inventory_records
                WHERE site = ? AND superseded_by IS NULL AND source_export_id IS NOT ?""",
            (site, run_id),
        ).fetchall():
            replacement = new_ids.get(old["identity_key"])
            if replacement:
                conn.execute("UPDATE inventory_records SET superseded_by = ? WHERE id = ?",
                             (replacement, old["id"]))
                superseded += 1

    conn.commit()
    return {"run_id": run_id, "rows_read": len(records), "records_written": len(merged),
            "merged_away": len(records) - len(merged), "superseded": superseded}


def ingest_file(conn: sqlite3.Connection, path: Path, adapter, source_name: str | None = None,
                column_map: dict | None = None) -> dict:
    """Read one file through an adapter and persist the outcome, success or not.

    Always returns a result and never raises past the caller: a folder poller
    that dies on a bad file stops watching the folder.
    """
    from pullsheet.adapters.base import AdapterRejection

    source_id = ensure_source(conn, source_name or f"{adapter.name} source",
                              adapter.name, adapter.provenance, column_map)
    try:
        records = list(adapter.read(path, column_map) if column_map else adapter.read(path))
    except AdapterRejection as rejection:
        run_id = record_rejection(conn, source_id, path.name, adapter.name, str(rejection))
        return {"status": "rejected", "run_id": run_id, "reason": str(rejection),
                "filename": path.name}

    result = persist_records(conn, source_id, path.name, adapter.name, records)
    result["status"] = "ok"
    result["filename"] = path.name
    return result
