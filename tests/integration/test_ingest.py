"""End to end: a file lands, rows are persisted, and the counts reconcile."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pullsheet import db
from pullsheet.adapters.watched_folder import WatchedFolderAdapter

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"
ADAPTER_FIXTURES = ROOT / "tests" / "adapters" / "fixtures"


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "ingest.db"
    db.reset(path)
    connection = db.connect(path)
    yield connection
    connection.close()


@pytest.fixture
def adapter():
    return WatchedFolderAdapter()


def test_row_counts_reconcile(conn, adapter):
    result = db.ingest_file(conn, FIXTURE, adapter, "Lincoln USD watched folder")
    run = conn.execute("SELECT * FROM ingest_runs WHERE id = ?", (result["run_id"],)).fetchone()
    written = conn.execute(
        "SELECT COUNT(*) c FROM inventory_records WHERE source_export_id = ?",
        (result["run_id"],)).fetchone()["c"]
    assert run["status"] == "ok"
    assert run["row_count"] == written == result["records_written"]


def test_every_partially_parsed_row_is_present_and_flagged(conn, adapter):
    db.ingest_file(conn, FIXTURE, adapter, "Lincoln USD watched folder")
    rows = conn.execute("SELECT raw_description, quantity, unpopulated_fields "
                        "FROM inventory_records").fetchall()
    partial = [r for r in rows if json.loads(r["unpopulated_fields"])]
    assert partial, "the fixture has no partial rows, so this test proves nothing"
    for row in partial:
        assert json.loads(row["unpopulated_fields"]), row["raw_description"]

    blank = [r for r in rows if r["quantity"] is None]
    assert len(blank) == 1
    assert "quantity" in json.loads(blank[0]["unpopulated_fields"])


def test_normalized_description_is_computed_downstream(conn, adapter):
    db.ingest_file(conn, FIXTURE, adapter, "Lincoln USD watched folder")
    row = conn.execute(
        "SELECT normalized_description FROM inventory_records "
        "WHERE raw_description = 'CHICKEN STRIPS BRD FC FROZEN 2/5 LB'").fetchone()
    assert row["normalized_description"] == "brd chicken fc frozen strips"


def test_a_rejection_is_recorded_and_leaves_the_sheet_intact(conn, adapter):
    """FR-006, FR-009. A bad export must not be able to empty a good sheet."""
    db.ingest_file(conn, FIXTURE, adapter, "Lincoln USD watched folder")
    before = conn.execute("SELECT COUNT(*) c FROM inventory_records").fetchone()["c"]

    result = db.ingest_file(conn, ADAPTER_FIXTURES / "malformed.csv", adapter,
                            "Lincoln USD watched folder")
    after = conn.execute("SELECT COUNT(*) c FROM inventory_records").fetchone()["c"]

    assert result["status"] == "rejected"
    assert after == before, "a rejected export changed the inventory"

    run = conn.execute("SELECT * FROM ingest_runs WHERE status = 'rejected'").fetchone()
    assert run["rejection_reason"]
    assert "malformed.csv" in run["rejection_reason"]
    assert "row 1" in run["rejection_reason"], "the failing row is not named"
    assert "Item Description" in run["rejection_reason"], "the failing column is not named"


def test_an_empty_file_is_rejected_by_name(conn, adapter):
    result = db.ingest_file(conn, ADAPTER_FIXTURES / "empty.csv", adapter, "test source")
    assert result["status"] == "rejected"
    assert "empty" in result["reason"]


def test_ingest_never_raises_past_the_caller(conn, adapter, tmp_path):
    """A folder poller that dies on a bad file stops watching the folder."""
    for name, content in [("junk.csv", "\x00\x01\x02"),
                          ("headers_only.csv", "Site,Item Description\n"),
                          ("one_column.csv", "Whatever\nvalue\n")]:
        path = tmp_path / name
        path.write_text(content)
        result = db.ingest_file(conn, path, adapter, "test source")
        assert result["status"] in {"ok", "rejected"}


def test_the_source_and_its_provenance_are_recorded(conn, adapter):
    db.ingest_file(conn, FIXTURE, adapter, "Lincoln USD watched folder")
    source = conn.execute("SELECT * FROM inventory_sources").fetchone()
    assert source["adapter"] == "watched_folder"
    assert source["provenance"] == "live"
    assert source["name"] == "Lincoln USD watched folder"
