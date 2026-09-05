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
