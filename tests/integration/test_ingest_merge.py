"""Identity, merging, and supersession (FR-064, FR-065, SC-014).

The property that matters: a quantity on the pull sheet can always be traced
back to the source rows that produced it, and re-ingesting an export replaces
rather than duplicates -- without destroying anything a human already decided.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pullsheet import db
from pullsheet.adapters.sftp_drop import SftpDropAdapter

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"

HEADER = ["Storage Location", "Item Description", "Qty On Hand", "UOM",
          "Pack Size", "Case UPC", "Lot #", "Unit Cost", "Received Date"]


def _copy(tmp_path, name: str) -> Path:
    """The same export under a new name.

    A delivery is identified by name AND content hash, so handing the drop the
    identical file twice is refused as a duplicate. Tomorrow's export is a new
    file, which is what supersession is actually about.
    """
    target = tmp_path / name
    target.write_bytes(FIXTURE.read_bytes())
    return target


def _write(path: Path, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    return path


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "merge.db"
    db.reset(path)
    connection = db.connect(path)
    yield connection
    connection.close()


@pytest.fixture
def adapter():
    return SftpDropAdapter()


def test_same_identity_rows_merge_with_summed_quantity(conn, adapter, tmp_path):
    """SC-014. Two lines for the same product, same storage, same lot are one
    record -- and both contributing source rows are named."""
    path = _write(tmp_path / "dupes.csv", [
        ["Freezer A", "CHICKEN STRIPS BRD FC FROZEN", "14", "CS",
         "2/5 lb", "", "4829-B", "38.50", "2026-08-24"],
        ["Freezer A", "CHICKEN STRIPS BRD FC FROZEN", "9", "CS",
         "2/5 lb", "", "4829-B", "38.50", "2026-08-26"],
        ["Cooler 1", "CHICKEN STRIPS BRD FC FROZEN", "3", "CS",
         "2/5 lb", "", "4829-B", "38.50", "2026-08-26"],
    ])
    db.ingest_file(conn, path, adapter)

    rows = conn.execute(
        "SELECT * FROM inventory_records ORDER BY id").fetchall()
    # Two records: Freezer A (merged from rows 1 and 2) and Cooler 1 (row 3).
    # A different storage location is a different identity -- you walk to a
    # different place to pull it.
    assert len(rows) == 2

    freezer = next(r for r in rows if r["storage_location"] == "Freezer A")
    assert freezer["quantity"] == 23.0
    assert json.loads(freezer["merged_from"]) == [1, 2]

    cooler = next(r for r in rows if r["storage_location"] == "Cooler 1")
    assert cooler["quantity"] == 3.0
    assert cooler["merged_from"] is None


def test_a_missing_quantity_does_not_become_zero_when_merging(conn, adapter, tmp_path):
    path = _write(tmp_path / "blank.csv", [
        ["Freezer A", "CHICKEN STRIPS BRD FC FROZEN", "", "CS",
         "2/5 lb", "", "4829-B", "38.50", "2026-08-24"],
        ["Freezer A", "CHICKEN STRIPS BRD FC FROZEN", "5", "CS",
         "2/5 lb", "", "4829-B", "38.50", "2026-08-26"],
    ])
    db.ingest_file(conn, path, adapter)
    row = conn.execute("SELECT * FROM inventory_records").fetchone()
    assert row["quantity"] == 5.0
    assert json.loads(row["merged_from"]) == [1, 2]


def test_different_lots_in_the_same_freezer_stay_separate(conn, adapter, tmp_path):
    path = _write(tmp_path / "lots.csv", [
        ["Freezer A", "CHICKEN STRIPS BRD FC FROZEN", "14", "CS",
         "2/5 lb", "", "4829-B", "38.50", "2026-08-24"],
        ["Freezer A", "CHICKEN STRIPS BRD FC FROZEN", "9", "CS",
         "2/5 lb", "", "4831A", "38.50", "2026-08-26"],
    ])
    db.ingest_file(conn, path, adapter)
    rows = conn.execute("SELECT * FROM inventory_records").fetchall()
    assert len(rows) == 2, "two lots were merged into one -- a recall on one lot "\
                           "would now be indistinguishable from a recall on the other"


def test_reingesting_supersedes_rather_than_duplicating(conn, adapter, tmp_path):
    first = db.ingest_file(conn, _copy(tmp_path, "monday.csv"), adapter)
    second = db.ingest_file(conn, _copy(tmp_path, "tuesday.csv"), adapter)

    active = conn.execute(
        "SELECT COUNT(*) c FROM inventory_records WHERE superseded_by IS NULL").fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) c FROM inventory_records").fetchone()["c"]

    assert active == first["records_written"], "the active sheet doubled"
    assert total == first["records_written"] * 2, "the earlier rows were destroyed"
    assert second["superseded"] == first["records_written"]


def test_superseded_rows_point_at_their_replacement(conn, adapter, tmp_path):
    db.ingest_file(conn, _copy(tmp_path, "monday.csv"), adapter)
    db.ingest_file(conn, _copy(tmp_path, "tuesday.csv"), adapter)
    rows = conn.execute(
        """SELECT o.identity_key AS old_key, n.identity_key AS new_key
             FROM inventory_records o
             JOIN inventory_records n ON n.id = o.superseded_by
            WHERE o.superseded_by IS NOT NULL""").fetchall()
    assert rows
    assert all(r["old_key"] == r["new_key"] for r in rows)


def test_a_prior_clearing_decision_still_resolves_after_reingest(conn, adapter, tmp_path):
    """Nothing is deleted, so a decision taken against yesterday's sheet is still
    an auditable record today -- and it still applies to today's line."""
    from pullsheet.matching.run import ordered_matches
    from pullsheet.recalls.corpus import load_snapshots

    load_snapshots(conn)
    first = db.ingest_file(conn, _copy(tmp_path, "monday.csv"), adapter)
    line = ordered_matches(conn, first["run_id"])[0]
    subject = db.subject_key(line["identity_key"], line["source"],
                             line["source_record_id"])
    conn.execute(
        """INSERT INTO decisions (kind, match_id, subject_key, actor, note, created_at)
           VALUES ('clear_match',?,?,'AS','verified empty','2026-09-05T10:00:00+00:00')""",
        (line["id"], subject))
    conn.commit()

    second = db.ingest_file(conn, _copy(tmp_path, "tuesday.csv"), adapter)

    decision = conn.execute("SELECT * FROM decisions").fetchone()
    assert decision["actor"] == "AS"
    still_there = conn.execute("SELECT * FROM inventory_records WHERE id = ?",
                               (line["inventory_record_id"],)).fetchone()
    assert still_there is not None, "the row a decision points at was destroyed"
    assert still_there["superseded_by"] is not None

    # And the decision reaches TODAY's line, which is a different match row for
    # the same food and the same recall. A clearing that expired overnight would
    # have to be taken again every morning.
    today = [m for m in ordered_matches(conn, second["run_id"])
             if db.subject_key(m["identity_key"], m["source"],
                               m["source_record_id"]) == subject]
    assert today and all(m["cleared_count"] >= 1 for m in today)


def test_identity_uses_the_gtin_when_there_is_one(conn):
    with_code = db.identity_key("Freezer A", "10073803110075", "chicken nuggets", "L1")
    no_code = db.identity_key("Freezer A", None, "chicken nuggets", "L1")
    assert "10073803110075" in with_code
    assert "chicken nuggets" in no_code
    assert with_code != no_code


def test_identity_falls_back_to_the_manufacturer_catalog_number(conn):
    """No barcode, but a maker and their own item number -- which is a stronger
    identity than a product name, and is what most kitchen exports carry."""
    catalog = db.identity_key("Freezer A", None, "pollock wedge", "L1",
                              "High Liner Foods", "HL-2261")
    name_only = db.identity_key("Freezer A", None, "pollock wedge", "L1")
    assert "HL-2261" in catalog
    assert catalog != name_only
