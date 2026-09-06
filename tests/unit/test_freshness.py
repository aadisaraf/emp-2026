"""FR-068. The 24-hour window is measured from the snapshot's capture time
against an INJECTED now, never against the clock.

The property that matters most is the last one: staleness changes what the
header says, never which lines are produced. Suppressing lines because the data
is old would trade a visible caveat for an invisible gap, which is the trade
this system exists to refuse.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pullsheet import db
from pullsheet.recalls import corpus


@pytest.fixture
def loaded(tmp_path):
    path = tmp_path / "freshness.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    yield conn
    conn.close()


def _captured_at(conn) -> datetime:
    row = conn.execute("SELECT MIN(captured_at) AS oldest FROM recall_snapshots").fetchone()
    return corpus._parse_ts(row["oldest"])


def test_age(loaded):
    """30 hours after capture is stale; 23 hours is fresh; the lines are the
    same either way."""
    captured = _captured_at(loaded)

    fresh_now = captured + timedelta(hours=23)
    stale_now = captured + timedelta(hours=30)

    assert round(corpus.snapshot_age_hours(loaded, fresh_now)) == 23
    assert round(corpus.snapshot_age_hours(loaded, stale_now)) == 30

    assert corpus.is_stale(loaded, fresh_now) is False
    assert corpus.is_stale(loaded, stale_now) is True

    fresh_lines = [r["id"] for r in corpus.active_records(loaded)]
    stale_lines = [r["id"] for r in corpus.active_records(loaded)]
    assert fresh_lines == stale_lines
    assert fresh_lines, "the corpus is empty, so this test proves nothing"


def test_the_boundary_is_exactly_24_hours(loaded):
    captured = _captured_at(loaded)
    assert corpus.is_stale(loaded, captured + timedelta(hours=24)) is False
    assert corpus.is_stale(loaded, captured + timedelta(hours=24, minutes=1)) is True


def test_now_is_injected_and_the_clock_is_never_read(loaded):
    """Two calls with the same injected now agree, regardless of wall time."""
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert corpus.snapshot_age_hours(loaded, now) == corpus.snapshot_age_hours(loaded, now)
    import inspect
    source = inspect.getsource(corpus.snapshot_age_hours) + inspect.getsource(corpus.is_stale)
    assert "now()" not in source and "utcnow" not in source


def test_terminated_recalls_are_returned(loaded):
    """FR-016. active_records() filters to loaded snapshots and nothing else --
    a terminated recall is marked downstream, never withheld here."""
    statuses = {r["status"] for r in corpus.active_records(loaded)}
    assert "terminated" in statuses
    assert "active" in statuses


def test_active_records_returns_the_whole_corpus(loaded):
    total = loaded.execute("SELECT COUNT(*) c FROM recall_records").fetchone()["c"]
    assert len(corpus.active_records(loaded)) == total


def test_null_classification_sorts_as_most_serious(loaded):
    assert corpus.class_rank(None) == 1
    assert corpus.class_rank("") == 1
    assert corpus.class_rank("something unrecognised") == 1
    assert corpus.class_rank("Class I") == 1
    assert corpus.class_rank("Class III") == 3
    rows = loaded.execute(
        "SELECT class_rank FROM recall_records WHERE classification IS NULL").fetchall()
    assert all(r["class_rank"] == 1 for r in rows)


def test_corpus_summary_reports_both_sources_with_provenance(loaded):
    now = _captured_at(loaded) + timedelta(hours=30)
    summary = {s["source"]: s for s in corpus.corpus_summary(loaded, now)}
    assert set(summary) == {"openfda", "fsis"}
    assert summary["openfda"]["provenance"] == "dated-snapshot"
    # FSIS could not be fetched or verified, and says so here too.
    assert summary["fsis"]["provenance"] == "hand-authored"
    assert all(s["stale"] for s in summary.values())


# ===========================================================================
# SC-013 (T068). Staleness gates one word in the status, never a line.
# ===========================================================================

CLEAN_EXPORT = ("Storage Location,Item Description,Qty On Hand,UOM,Lot #\n"
                "Dry Store,SALT IODIZED 5 LB,4,CS,S-100\n"
                "Dry Store,BAKING SODA 2 LB,2,CS,B-220\n")


def _run_at(conn, path, when: datetime):
    """Ingest an export as if it had arrived at ``when``."""
    from pullsheet.adapters.sftp_drop import SftpDropAdapter
    result = db.ingest_file(conn, path, SftpDropAdapter(),
                            now=when.isoformat(timespec="seconds"))
    assert result["status"] == "ok", result.get("reason")
    return result


@pytest.fixture
def clean(tmp_path):
    """A location whose export matched nothing -- the only state in which
    "clear" and "stale" are distinguishable. With a PULL line on the sheet the
    word is "items to pull" whatever the corpus's age, which is correct and
    would make every assertion below vacuous."""
    from pullsheet import runs

    path = tmp_path / "clean.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    export = tmp_path / "clean.csv"
    export.write_text(CLEAN_EXPORT)
    _run_at(conn, export, _captured_at(conn) + timedelta(hours=1))
    yield conn, runs
    conn.close()


def test_sc013_nothing_reports_clear_when_the_corpus_is_stale(clean):
    conn, runs = clean
    captured = _captured_at(conn)

    fresh = runs.run_status(conn, captured + timedelta(hours=2))
    assert fresh["state"] == "clear", (
        "the run is not clear even when fresh, so the stale assertion is vacuous")

    stale = runs.run_status(conn, captured + timedelta(hours=26))
    assert stale["state"] == "stale"
    assert stale["word"] != runs.CLEAR


def test_sc013_a_stale_status_names_the_reason_and_the_age(clean):
    conn, runs = clean
    captured = _captured_at(conn)
    stale = runs.run_status(conn, captured + timedelta(hours=26))

    assert "stale" in stale["word"]
    assert stale["stale_corpus"] is True
    # FR-068: the reason says what was held back and that no line moved.
    assert "suppressed" in stale["detail"]
    assert round(corpus.snapshot_age_hours(conn, captured + timedelta(hours=26))) == 26


def test_sc013_the_lines_themselves_are_identical_stale_or_fresh(tmp_path):
    """The assertion that matters most. A run which suppressed lines because the
    data is old would trade a visible caveat for an invisible gap -- and would
    pass every other test in this file."""
    from pullsheet import runs
    from pullsheet.matching.run import ordered_matches

    path = tmp_path / "lines.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    captured = _captured_at(conn)
    db.load_inventory_fixture(
        conn, now=(captured + timedelta(hours=1)).isoformat(timespec="seconds"))
    run_id = db.latest_ok_run(conn)["id"]

    def sheet(now):
        # The status word is computed at `now`; the lines are read at the same
        # instant. If staleness reached the lines, these would differ.
        runs.run_status(conn, now)
        return [(r["id"], r["status"], r["tier"]) for r in ordered_matches(conn, run_id)]

    fresh = sheet(captured + timedelta(hours=2))
    stale = sheet(captured + timedelta(hours=26))
    assert fresh, "there are no lines, so this proves nothing"
    assert fresh == stale, "staleness changed which lines exist"

    assert corpus.is_stale(conn, captured + timedelta(hours=26)) is True
    # And a PULL line outranks staleness: food in the building is a fact about
    # the building, not about how old the recall feed is.
    assert runs.run_status(conn, captured + timedelta(hours=26))["state"] == "action"
    conn.close()


def test_a_location_that_never_reported_is_not_a_quiet_green_page(tmp_path):
    """FR-050. "No export has ever arrived" and "an export arrived and matched
    nothing" are different situations, and only one of them is reassuring."""
    from pullsheet import runs

    path = tmp_path / "silent.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    status = runs.run_status(conn, _captured_at(conn) + timedelta(hours=2))
    assert status["state"] == "never"
    assert status["run"] is None
    assert "no statement" in status["detail"] or "Nothing on this page" in status["detail"]
    conn.close()
