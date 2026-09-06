"""End to end: a file lands, rows are persisted, and the counts reconcile."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pullsheet import db
from pullsheet.adapters.sftp_drop import SftpDropAdapter

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
    return SftpDropAdapter()


def test_row_counts_reconcile(conn, adapter):
    result = db.ingest_file(conn, FIXTURE, adapter)
    run = db.get_run(conn, result["run_id"])
    written = conn.execute(
        "SELECT COUNT(*) c FROM inventory_records WHERE run_id = ?",
        (result["run_id"],)).fetchone()["c"]
    assert run["status"] == "ok"
    # rows READ is the file's row count; records WRITTEN is lower when two rows
    # of one export are the same item (FR-065). Both are on the run, and the
    assert run["rows_read"] == result["rows_read"]
    assert written == result["records_written"] <= run["rows_read"]


def test_every_partially_parsed_row_is_present_and_flagged(conn, adapter):
    db.ingest_file(conn, FIXTURE, adapter)
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
    db.ingest_file(conn, FIXTURE, adapter)
    row = conn.execute(
        "SELECT normalized_description FROM inventory_records "
        "WHERE raw_description = 'CHICKEN STRIPS BRD FC FROZEN 2/5 LB'").fetchone()
    assert row["normalized_description"] == "brd chicken fc frozen strips"


def test_a_rejection_is_recorded_and_leaves_the_sheet_intact(conn, adapter):
    """FR-006, FR-009. A bad export must not be able to empty a good sheet."""
    db.ingest_file(conn, FIXTURE, adapter)
    before = conn.execute("SELECT COUNT(*) c FROM inventory_records").fetchone()["c"]

    result = db.ingest_file(conn, ADAPTER_FIXTURES / "malformed.csv", adapter)
    after = conn.execute("SELECT COUNT(*) c FROM inventory_records").fetchone()["c"]

    assert result["status"] == "rejected"
    assert after == before, "a rejected export changed the inventory"

    run = db.get_run(conn, result["run_id"])
    assert run["status"] == "rejected"
    assert run["rejection_reason"]
    assert "malformed.csv" in run["rejection_reason"]
    assert "row 1" in run["rejection_reason"], "the failing row is not named"
    assert "Item Description" in run["rejection_reason"], "the failing column is not named"


def test_an_empty_file_is_rejected_by_name(conn, adapter):
    result = db.ingest_file(conn, ADAPTER_FIXTURES / "empty.csv", adapter)
    assert result["status"] == "rejected"
    assert "empty" in result["reason"]


def test_ingest_never_raises_past_the_caller(conn, adapter, tmp_path):
    """A folder poller that dies on a bad file stops watching the folder."""
    for name, content in [("junk.csv", "\x00\x01\x02"),
                          ("headers_only.csv", "Site,Item Description\n"),
                          ("one_column.csv", "Whatever\nvalue\n")]:
        path = tmp_path / name
        path.write_text(content)
        result = db.ingest_file(conn, path, adapter)
        assert result["status"] in {"ok", "rejected"}


def test_the_delivery_and_its_channel_are_recorded(conn, adapter):
    """A run names the channel it arrived on and the delivery it came from, so
    "which file produced this sheet" is answerable a week later.
    """
    result = db.ingest_file(conn, FIXTURE, adapter)
    run = db.get_run(conn, result["run_id"])
    assert run["channel"] == "sftp_drop"
    assert FIXTURE.name in run["delivery_ref"]
    assert run["business_date"] and run["finalized_at"]
    assert run["corpus_note"] is not None


def test_the_same_delivery_twice_is_refused_rather_than_double_counted(conn, adapter):
    """The drop folder can hand the same file back after a retry. Ingesting it
    again would make it the baseline tomorrow's "new since" diff is measured
    """
    first = db.ingest_file(conn, FIXTURE, adapter)
    again = db.ingest_file(conn, FIXTURE, adapter)
    assert first["status"] == "ok"
    assert again["status"] == "duplicate"
    assert again["run_id"] == first["run_id"]
    assert conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"] == 1
