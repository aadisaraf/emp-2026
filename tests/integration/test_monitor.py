"""US5 acceptance scenarios 1-4. The standing monitor.

Scenario 4 is the one that is easy to pass badly. "No alert was raised" is
trivially satisfiable by not running -- so it is asserted as a positive: a
``monitor_runs`` row exists, it is marked ``zero_hit``, and it names how many
records it looked at. Nothing found and nobody looked must not produce the same
picture, because only one of them is safe.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from pullsheet import db, monitor
from pullsheet.matching.run import run_matcher
from pullsheet.recalls import corpus

NOW = datetime(2026, 9, 5, 14, 30, tzinfo=timezone.utc)


@pytest.fixture
def dbpath(tmp_path):
    """A file-backed database, so 'restart' means what it says."""
    path = tmp_path / "monitor.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    db.load_inventory_fixture(conn)
    run_matcher(conn)
    conn.close()
    return path


def _inject(conn, description, firm, code_info="", record_id="F-9001-2026"):
    """Add one recall record, as a later snapshot load would."""
    from pullsheet.matching.normalize import normalize
    from pullsheet.recalls.parse import parse_record
    snapshot = conn.execute("SELECT MAX(id) m FROM recall_snapshots").fetchone()["m"]
    cur = conn.execute(
        """INSERT INTO recall_records
           (source, source_record_id, snapshot_id, recalling_firm, product_description,
            normalized_description, code_info, parsed_codes, classification, class_rank,
            report_date, received_at, reason_for_recall, status, raw_json)
           VALUES ('openfda',?,?,?,?,?,?,?,'Class I',1,'2026-09-05',?,'Listeria','active','{}')""",
        (record_id, snapshot, firm, description, normalize(description), code_info,
         json.dumps(parse_record(description, code_info, None)), NOW.isoformat()))
    conn.commit()
    return cur.lastrowid


def test_scenario_1_inventory_survives_a_restart(dbpath):
    first = db.connect(dbpath)
    rows = first.execute(
        "SELECT COUNT(*) c FROM inventory_records WHERE superseded_by IS NULL").fetchone()["c"]
    matches = first.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"]
    first.close()

    # A new process, a new connection. Nothing re-imported.
    second = db.connect(dbpath)
    assert second.execute(
        "SELECT COUNT(*) c FROM inventory_records WHERE superseded_by IS NULL"
    ).fetchone()["c"] == rows > 0
    assert second.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"] == matches > 0
    # And it is immediately usable for matching without an import step.
    assert monitor.run(second, NOW)["records_evaluated"] == 0
    second.close()


def test_scenario_2_only_unseen_records_are_evaluated(dbpath):
    conn = db.connect(dbpath)
    total = conn.execute("SELECT COUNT(*) c FROM recall_records").fetchone()["c"]

    first = monitor.run(conn, NOW)
    assert first["records_evaluated"] == 0, (
        "the first run re-evaluated the whole corpus, which the initial matcher "
        "pass had already covered")

    _inject(conn, "Simplot Potato Wedges 5 lb", "JR Simplot Company")
    _inject(conn, "Bolthouse Baby Carrots 5 lb", "Bolthouse Farms", record_id="F-9002-2026")

    second = monitor.run(conn, NOW)
    assert second["records_evaluated"] == 2
    assert second["new_records"] == 2
    assert conn.execute("SELECT COUNT(*) c FROM recall_records").fetchone()["c"] == total + 2

    # And a third run sees nothing again -- the mark advanced.
    assert monitor.run(conn, NOW)["records_evaluated"] == 0
    conn.close()


def test_scenario_3_a_matching_record_raises_an_alert_naming_sites_and_record(dbpath):
    conn = db.connect(dbpath)
    monitor.run(conn, NOW)
    before = len(monitor.open_alerts(conn))

    _inject(conn, "Bolthouse Farms Baby Carrots, peeled, 5 lb bags",
            "Bolthouse Farms", record_id="F-9010-2026")
    result = monitor.run(conn, NOW)
    assert result["new_matches"] > 0
    assert result["zero_hit"] is False

    alerts = monitor.open_alerts(conn)
    assert len(alerts) == before + result["new_matches"]

    triggered = [a for a in alerts if a["source_record_id"] == "F-9010-2026"]
    assert triggered, "the alert does not name the triggering recall record"
    for alert in triggered:
        assert alert["site"], "the alert does not name an affected site"
        assert alert["first_seen_run_id"] == result["run_id"]
        assert alert["recalling_firm"] == "Bolthouse Farms"

    # Exactly the affected sites, no more: every named site really holds the item.
    for alert in triggered:
        held = conn.execute(
            """SELECT 1 FROM inventory_records
                WHERE site = ? AND raw_description = ? AND superseded_by IS NULL""",
            (alert["site"], alert["raw_description"])).fetchone()
        assert held
    conn.close()


def test_scenario_4_a_record_matching_nothing_is_still_a_recorded_run(dbpath):
    """A quiet run is still a run (FR-058). Asserted positively."""
    conn = db.connect(dbpath)
    monitor.run(conn, NOW)
    runs_before = len(monitor.runs(conn))

    _inject(conn, "Zorbium Wafers, unflavoured, 900 g tin", "Zorbium Confectionery GmbH",
            record_id="F-9099-2026")
    result = monitor.run(conn, NOW)

    assert result["records_evaluated"] == 1, "the record was not evaluated at all"
    assert result["new_matches"] == 0
    assert result["zero_hit"] is True

    runs = monitor.runs(conn)
    assert len(runs) == runs_before + 1
    row = runs[0]
    assert row["zero_hit"] == 1
    assert row["records_evaluated"] == 1
    assert row["ran_at"] == NOW.isoformat(timespec="seconds")
    conn.close()


def test_an_alert_persists_across_a_restart_until_acknowledged(dbpath):
    conn = db.connect(dbpath)
    monitor.run(conn, NOW)
    _inject(conn, "Bolthouse Farms Baby Carrots, peeled, 5 lb bags",
            "Bolthouse Farms", record_id="F-9020-2026")
    monitor.run(conn, NOW)
    open_before = [a["id"] for a in monitor.open_alerts(conn)]
    assert open_before
    conn.close()

    restarted = db.connect(dbpath)
    assert [a["id"] for a in monitor.open_alerts(restarted)] == open_before

    restarted.execute(
        """INSERT INTO decisions (kind, target_type, target_id, actor, created_at)
           VALUES ('acknowledge_alert', 'match', ?, 'AS', ?)""",
        (str(open_before[0]), NOW.isoformat(timespec="seconds")))
    restarted.commit()

    after = [a["id"] for a in monitor.open_alerts(restarted)]
    assert open_before[0] not in after
    assert len(after) == len(open_before) - 1
    # Acknowledging says a person looked. The LINE is untouched.
    assert restarted.execute(
        "SELECT COUNT(*) c FROM matches WHERE id = ?", (open_before[0],)).fetchone()["c"] == 1
    restarted.close()


def test_the_monitor_never_writes_a_decision(dbpath):
    """The monitor runs unattended, so it must not be able to reach the table
    that means a human acted. It READS decisions -- open_alerts has to know what
    was acknowledged -- and may never write one."""
    import inspect
    import re
    source = inspect.getsource(monitor)
    writes = re.findall(r"(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+decisions", source, re.I)
    assert not writes, f"monitor.py writes to decisions: {writes}"

    # And a run really does not add one, however many times it runs.
    conn = db.connect(dbpath)
    before = conn.execute("SELECT COUNT(*) c FROM decisions").fetchone()["c"]
    _inject(conn, "Bolthouse Farms Baby Carrots, peeled, 5 lb bags", "Bolthouse Farms",
            record_id="F-9030-2026")
    monitor.run(conn, NOW)
    monitor.run(conn, NOW)
    assert conn.execute("SELECT COUNT(*) c FROM decisions").fetchone()["c"] == before
    conn.close()


def test_a_monitor_pass_does_not_duplicate_existing_matches(dbpath):
    conn = db.connect(dbpath)
    total = conn.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"]
    for _ in range(3):
        monitor.run(conn, NOW)
    assert conn.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"] == total
    conn.close()


def test_every_run_is_recorded_even_when_the_corpus_did_not_change(dbpath):
    conn = db.connect(dbpath)
    for i in range(1, 4):
        monitor.run(conn, NOW + timedelta(hours=i))
    runs = monitor.runs(conn)
    assert len(runs) == 3
    assert all(r["zero_hit"] == 1 for r in runs)
    assert len({r["ran_at"] for r in runs}) == 3
    conn.close()
