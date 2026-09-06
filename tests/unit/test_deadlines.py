"""FR-052, FR-053. The two USDA clocks, and what happens after zero.

The verify in T065 is written as a single instant, so it is asserted as one:
at received_at + 25h the 24-hour clock reads 1h overrun and the 48-hour clock
reads 23h remaining.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from pullsheet import db
from pullsheet.recalls import corpus
from pullsheet import deadlines


@pytest.fixture
def loaded(tmp_path):
    path = tmp_path / "clocks.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    db.load_inventory_fixture(conn)
    yield conn
    conn.close()


@pytest.fixture
def run_id(loaded):
    return db.latest_ok_run(loaded)["id"]


def _received(conn):
    return corpus._parse_ts(conn.execute(
        """SELECT MIN(r.received_at) AS a FROM matches m
             JOIN recall_records r ON r.id = m.recall_record_id""").fetchone()["a"])


def test_both_clocks_exist_and_run_from_receipt_not_report_date(loaded, run_id):
    clocks = {c["key"]: c for c in deadlines.clocks(loaded, run_id, _received(loaded))}
    assert set(clocks) == {"distributor_notification", "inventory_assessment"}
    assert clocks["distributor_notification"]["hours"] == 24
    assert clocks["inventory_assessment"]["hours"] == 48

    # The due time is receipt + the window exactly, whatever the agency's own
    # report_date says. A recall published weeks ago that a district learns of
    # this morning starts its clock this morning.
    received = _received(loaded)
    assert clocks["distributor_notification"]["due_at"] == \
        (received + timedelta(hours=24)).isoformat(timespec="seconds")
    assert clocks["inventory_assessment"]["due_at"] == \
        (received + timedelta(hours=48)).isoformat(timespec="seconds")


def test_at_25_hours_one_clock_has_overrun_and_the_other_has_not(loaded, run_id):
    """T065's verify, asserted at the instant it names."""
    clocks = {c["key"]: c for c in deadlines.clocks(
        loaded, run_id, _received(loaded) + timedelta(hours=25))}

    notify = clocks["distributor_notification"]
    assert notify["overrun"] is True
    assert notify["text"] == "1h 00m OVERRUN"
    assert notify["remaining_hours"] == -1.0

    assess = clocks["inventory_assessment"]
    assert assess["overrun"] is False
    assert assess["text"] == "23h 00m remaining"
    assert assess["remaining_hours"] == 23.0


def test_an_elapsed_deadline_never_hides_or_resets(loaded, run_id):
    """FR-053. The overrun keeps growing; it does not wrap, blank, or turn green."""
    received = _received(loaded)
    a = deadlines.clocks(loaded, run_id, received + timedelta(hours=30))[0]
    b = deadlines.clocks(loaded, run_id, received + timedelta(hours=100))[0]
    assert a["overrun"] and b["overrun"]
    assert b["remaining_hours"] < a["remaining_hours"]
    assert "OVERRUN" in a["text"] and "OVERRUN" in b["text"]
    assert deadlines.clocks(loaded, run_id, received + timedelta(days=30)), \
        "the clocks disappeared once the deadline was far enough past"


def test_the_clock_reads_in_whole_minutes_not_sixty(loaded, run_id):
    """A remainder of 59.7 minutes rounded on its own prints "23h 60m", which
    reads like a broken clock on the one screen that has to look trustworthy."""
    received = _received(loaded)
    for offset in (timedelta(hours=1, seconds=18), timedelta(hours=24, seconds=3),
                   timedelta(seconds=31), timedelta(hours=47, minutes=59, seconds=45)):
        for clock in deadlines.clocks(loaded, run_id, received + offset):
            minutes = clock["text"].split("h ")[1][:2]
            assert int(minutes) < 60, clock["text"]


def test_now_is_injected(loaded):
    import inspect
    source = inspect.getsource(deadlines)
    assert "utcnow" not in source and "datetime.now(" not in source


def test_no_matches_means_no_clocks(tmp_path):
    """A run with nothing on its sheet is not against a deadline."""
    path = tmp_path / "empty.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    from datetime import datetime, timezone
    run_id = db.open_run(conn, "sftp_drop", "nothing.csv")
    assert deadlines.clocks(conn, run_id, datetime(2026, 9, 5, tzinfo=timezone.utc)) == []
    conn.close()
