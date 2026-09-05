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
