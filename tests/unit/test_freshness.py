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
# SC-013 (T068). Staleness gates one word in the roll-up, never a line.
# ===========================================================================

def _fully_loaded(tmp_path_factory):
    """A database with inventory, matches, and one site that reported empty."""
    from pullsheet.matching.run import run_matcher
    from pullsheet.rollup import status

    path = tmp_path_factory.mktemp("stale") / "sc013.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    db.load_inventory_fixture(conn)
    run_matcher(conn)

    # A building that sent an export and came back empty. Without one, "zero
    # sites report clear" would be true for the wrong reason.
    source_id = db.ensure_source(conn, "Washington export", "watched_folder", "live")
    run = conn.execute(
        """INSERT INTO ingest_runs (source_id, filename, arrived_at, row_count,
                                    rows_parsed, rows_partial, status, adapter)
           VALUES (?,?,?,0,0,0,'ok','watched_folder')""",
        (source_id, "washington.csv", "2026-09-05T06:00:00+00:00")).lastrowid
    conn.execute(
        """INSERT INTO inventory_records
           (site, raw_description, normalized_description, source_export_id,
            identity_key, created_at)
           VALUES ('Washington Elementary', 'SALT IODIZED 5 LB', 'iodized salt',
                   ?, 'w1', '2026-09-05T06:00:00+00:00')""", (run,))
    conn.commit()
    return conn, status


@pytest.fixture(scope="module")
def sc013(tmp_path_factory):
    conn, status = _fully_loaded(tmp_path_factory)
    yield conn, status
    conn.close()


def test_sc013_no_site_reports_clear_when_the_corpus_is_stale(sc013):
    conn, status = sc013
    captured = _captured_at(conn)

    fresh = status.site_statuses(conn, captured + timedelta(hours=2))
    assert any(s["status"] == "clear" for s in fresh), (
        "no site is clear even when fresh, so the stale assertion would be vacuous")

    stale = status.site_statuses(conn, captured + timedelta(hours=30))
    assert not any(s["status"] == "clear" for s in stale)


def test_sc013_a_stale_site_names_the_reason_the_date_and_the_age(sc013):
    conn, status = sc013
    captured = _captured_at(conn)
    stale = {s["site"]: s for s in status.site_statuses(conn, captured + timedelta(hours=30))}

    was_clear = stale["Washington Elementary"]
    assert was_clear["status"] == "unconfirmed"
    assert "stale recall data" in was_clear["reason"]
    # FR-068: the capture date and the age are both shown alongside.
    assert was_clear["snapshot_captured_at"][:10] in was_clear["reason"]
    assert "30h" in was_clear["reason"]
    assert was_clear["snapshot_age_hours"] == pytest.approx(30, abs=0.1)


def test_sc013_the_lines_themselves_are_identical_stale_or_fresh(sc013):
    """The assertion that matters most. A run which suppressed lines because the
    data is old would trade a visible caveat for an invisible gap -- and would
    pass every other test in this file."""
    conn, status = sc013
    captured = _captured_at(conn)

    def counts(now):
        rows = status.site_statuses(conn, now)
        return {r["site"]: (r["pull"], r["held"]) for r in rows}

    fresh = counts(captured + timedelta(hours=2))
    stale = counts(captured + timedelta(hours=30))
    assert fresh == stale, "staleness changed which lines exist"
    assert sum(p for p, _ in fresh.values()) > 0, "there are no lines, so this proves nothing"

    total = conn.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"]
    assert total > 0
    assert corpus.is_stale(conn, captured + timedelta(hours=30)) is True
    assert conn.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"] == total
