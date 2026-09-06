"""FR-049, FR-050. One word per site, and `unconfirmed` is the default.

The property under test is not "the words are right". It is that a building
which never reported cannot be made to look like a building that reported and
came back empty. Every other assertion here supports that one.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from pullsheet import db
from pullsheet.matching.run import run_matcher
from pullsheet.recalls import corpus
from pullsheet.rollup import status


@pytest.fixture
def loaded(tmp_path):
    path = tmp_path / "rollup.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    db.load_inventory_fixture(conn)
    run_matcher(conn)
    yield conn
    conn.close()


def _captured(conn):
    return corpus._parse_ts(conn.execute(
        "SELECT MIN(captured_at) AS o FROM recall_snapshots").fetchone()["o"])


def _fresh(conn):
    return _captured(conn) + timedelta(hours=2)


def test_every_site_has_exactly_one_status(loaded):
    rows = status.site_statuses(loaded, _fresh(loaded))
    assert rows
    for row in rows:
        assert row["status"] in status.STATUS_WORDS
        assert row["reason"], f"{row['site']} has a status but no stated reason"


def test_a_site_with_lines_is_holding(loaded):
    rows = {r["site"]: r for r in status.site_statuses(loaded, _fresh(loaded))}
    for site in ("Lincoln Elementary", "Roosevelt Middle School", "Central High School"):
        assert rows[site]["status"] == "holding"
        assert rows[site]["pull"] + rows[site]["held"] > 0


def test_a_site_that_never_reported_is_unconfirmed_and_says_so(loaded):
    """The reason this module reads a roster instead of inventory_records."""
    rows = {r["site"]: r for r in status.site_statuses(loaded, _fresh(loaded))}
    silent = [s for s in status.roster() if s not in
              {"Lincoln Elementary", "Roosevelt Middle School", "Central High School"}]
    assert silent, "the roster has no unreported site, so this test proves nothing"
    for site in silent:
        assert rows[site]["status"] == "unconfirmed"
        assert "no export" in rows[site]["reason"]
        assert rows[site]["reported"] is False


def test_an_empty_export_inside_the_window_is_clear(loaded):
    """`clear` is reachable -- otherwise `unconfirmed` would be meaningless."""
    site = "Washington Elementary"
    source_id = db.ensure_source(loaded, "Washington export", "watched_folder", "live")
    run = loaded.execute(
        """INSERT INTO ingest_runs (source_id, filename, arrived_at, row_count,
                                    rows_parsed, rows_partial, status, adapter)
           VALUES (?,?,?,0,0,0,'ok','watched_folder')""",
        (source_id, "washington.csv", "2026-09-05T06:00:00+00:00")).lastrowid
    loaded.execute(
        """INSERT INTO inventory_records
           (site, raw_description, normalized_description, source_export_id,
            identity_key, created_at)
           VALUES (?, 'SALT IODIZED 5 LB', 'iodized salt', ?, 'w1', '2026-09-05T06:00:00+00:00')""",
        (site, run))
    loaded.commit()

    rows = {r["site"]: r for r in status.site_statuses(loaded, _fresh(loaded))}
    assert rows[site]["status"] == "clear"
    assert rows[site]["pull"] == 0 and rows[site]["held"] == 0


def test_a_rejected_export_does_not_make_a_site_look_answered(loaded):
    """FR-009. A bad file must not be able to answer for a building."""
    site = "Jefferson Early Learning Center"
    source_id = db.ensure_source(loaded, "Jefferson export", "watched_folder", "live")
    db.record_rejection(loaded, source_id, "jefferson.xlsx", "watched_folder",
                        "no recognisable header row")
    rows = {r["site"]: r for r in status.site_statuses(loaded, _fresh(loaded))}
    assert rows[site]["status"] == "unconfirmed"


def test_status_is_derived_not_stored(loaded):
    """No table holds a site status, so none can disagree with the rows."""
    schema = (db.SCHEMA).read_text().lower()
    assert "site_status" not in schema and "site_statuses" not in schema
    a = status.site_statuses(loaded, _fresh(loaded))
    b = status.site_statuses(loaded, _fresh(loaded))
    assert a == b


def test_confirming_one_site_changes_only_that_site(loaded):
    """FR-054."""
    before = {r["site"]: r["status"] for r in status.site_statuses(loaded, _fresh(loaded))}
    loaded.execute(
        """INSERT INTO decisions (kind, target_type, target_id, actor, created_at)
           VALUES ('confirm_site_pulled', 'site', 'Lincoln Elementary', 'AS', '2026-09-05T15:00:00+00:00')""")
    loaded.commit()

    rows = {r["site"]: r for r in status.site_statuses(loaded, _fresh(loaded))}
    assert rows["Lincoln Elementary"]["confirmed"]["actor"] == "AS"
    for site, row in rows.items():
        assert row["status"] == before[site], "confirming one site moved another"
        if site != "Lincoln Elementary":
            assert row["confirmed"] is None
