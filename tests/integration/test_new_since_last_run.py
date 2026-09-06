"""US5, FR-055 to FR-058. "What is new since the last run", and nothing else."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pullsheet import db, runs
from pullsheet.adapters.sftp_drop import SftpDropAdapter
from pullsheet.matching.run import ordered_matches, run_matcher
from pullsheet.recalls import corpus

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"
NOW = datetime(2026, 9, 5, 6, 0, tzinfo=timezone.utc)

HEADER = ("Storage Location,Item Description,Qty On Hand,UOM,Pack Size,"
          "Case UPC,Lot #,Brand,Manufacturer,Mfr Item #,Vendor,Vendor Item #,"
          "Unit Cost,Received Date\n")

# An overnight delivery of a product that is genuinely recalled in the
# committed corpus -- the same case already sitting in Freezer A, arriving into
RECALLED_ROW = ("Cooler 1,BEEF CRUMBLES COOKED TACO SEASONED 5 LB,6,CS,4/5 lb,,,"
                "Prairie Line,Prairie Line Beef LLC,PL-0904,US Foods,6612034,"
                "33.90,2026-09-04\n")

# A second arrival that touches the corpus only by a word in an ingredient
# list. It is flagged new too -- it genuinely was not on the shelf yesterday --
WEAK_ROW = ("Dry Store,SALT IODIZED 5 LB,4,CS,12 CT,,S-100,House,House Brand,"
            "HB-1,Sysco,SY-1,3.10,2026-09-01\n")


@pytest.fixture
def kitchen(tmp_path):
    """One location, corpus loaded, no run yet."""
    path = tmp_path / "new.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    yield conn, tmp_path
    conn.close()


def _export(tmp_path, name: str, extra_rows: str = "", *, drop: str = "") -> Path:
    """Tomorrow's export: the committed fixture, optionally with rows added or
    one description dropped. A new file name, because a delivery is identified by
    """
    lines = FIXTURE.read_text().splitlines(keepends=True)
    if drop:
        lines = [ln for ln in lines if drop not in ln]
    path = tmp_path / name
    path.write_text("".join(lines) + extra_rows)
    return path


def _deliver(conn, path: Path, when: datetime) -> dict:
    result = db.ingest_file(conn, path, SftpDropAdapter(),
                            now=when.isoformat(timespec="seconds"))
    assert result["status"] == "ok", result.get("reason")
    return result


def _new_lines(conn, run_id):
    return runs.new_since_previous(conn, run_id)


# --- Scenario 1: the first run has nothing to be new against ----------------

def test_the_first_run_flags_nothing_as_new(kitchen):
    """A first run with every line marked "new" would bury the one line that
    matters on every run after it. There is no previous run, so nothing is new
    """
    conn, tmp = kitchen
    result = _deliver(conn, _export(tmp, "day1.csv"), NOW)
    run_id = result["run_id"]

    assert result["matches"]["matches"] > 0, "no lines at all, so this proves nothing"
    assert result["matches"]["new"] == 0
    assert _new_lines(conn, run_id) == []
    assert runs.run_status(conn, NOW + timedelta(hours=1))["new_count"] == 0


# --- Scenario 2: a quiet run is still a run ---------------------------------

def test_an_unchanged_shelf_produces_a_recorded_run_with_zero_new_lines(kitchen):
    """FR-058. The day nothing happened must be visible in the history. A run
    that only appears when it found something turns silence into ambiguity:
    """
    conn, tmp = kitchen
    _deliver(conn, _export(tmp, "day1.csv"), NOW)
    day2 = _deliver(conn, _export(tmp, "day2.csv"), NOW + timedelta(days=1))

    assert day2["matches"]["new"] == 0
    assert _new_lines(conn, day2["run_id"]) == []

    history = runs.history(conn)
    assert len(history) == 2, "the quiet run was not recorded"
    assert [h["status"] for h in history] == ["ok", "ok"]
    assert history[0]["new_count"] == 0
    # And it still produced a full sheet -- quiet is not empty.
    assert len(ordered_matches(conn, day2["run_id"])) > 0


# --- Scenario 3: a newly arrived recalled item ------------------------------

def test_a_recalled_item_arriving_on_the_shelf_is_flagged_and_nothing_else_is(kitchen):
    conn, tmp = kitchen
    _deliver(conn, _export(tmp, "day1.csv"), NOW)
    day2 = _deliver(conn, _export(tmp, "day2.csv", RECALLED_ROW + WEAK_ROW),
                    NOW + timedelta(days=1))

    new = _new_lines(conn, day2["run_id"])
    assert new, "the newly delivered recalled item was not flagged"
    # Exactly the two rows that arrived overnight, and nothing else on the shelf.
    assert {row["raw_description"] for row in new} == {
        "BEEF CRUMBLES COOKED TACO SEASONED 5 LB", "SALT IODIZED 5 LB"}

    # One arrival produces one line per recall record it touches, so group.
    by_item: dict[str, set[str]] = {}
    for row in new:
        by_item.setdefault(row["raw_description"], set()).add(row["status"])
    assert "PULL" in by_item["BEEF CRUMBLES COOKED TACO SEASONED 5 LB"]
    # The salt shares only the word "iodized" with an ingredient list on a
    # recalled can of beans. New, and held for a person -- never auto-cleared.
    assert by_item["SALT IODIZED 5 LB"] == {"HELD"}

    # Every other line on the sheet was there yesterday and says so.
    all_lines = ordered_matches(conn, day2["run_id"])
    assert sum(1 for m in all_lines if m["is_new"]) == len(new)
    assert len(all_lines) > len(new), "the whole sheet was flagged new"


# --- Scenario 4: a new recall against an unchanged shelf --------------------

def _inject_recall(conn, description, *, record_id, firm="Overnight Foods LLC"):
    from pullsheet.matching.normalize import normalize
    from pullsheet.recalls.parse import parse_record
    snapshot = conn.execute("SELECT MAX(id) m FROM recall_snapshots").fetchone()["m"]
    conn.execute(
        """INSERT INTO recall_records
           (source, source_record_id, snapshot_id, recalling_firm, product_description,
            normalized_description, code_info, parsed_codes, classification, class_rank,
            report_date, received_at, reason_for_recall, status, raw_json)
           VALUES ('openfda',?,?,?,?,?,'',?,'Class I',1,'2026-09-06',?,'Listeria','active','{}')""",
        (record_id, snapshot, firm, description, normalize(description),
         json.dumps(parse_record(description, "", None)),
         (NOW + timedelta(days=1)).isoformat()))
    conn.commit()


def test_a_recall_published_overnight_is_new_on_the_next_run(kitchen):
    """The other direction, and the reason `python -m pullsheet.match` exists:
    the corpus changed and the inventory did not. The shelf is re-matched, so an
    """
    conn, tmp = kitchen
    _deliver(conn, _export(tmp, "day1.csv"), NOW)

    # Bananas match nothing in the committed corpus, so any new line here is
    # unambiguously the record that was published overnight.
    _inject_recall(conn, "Fresh Bananas, 40 lb case", record_id="F-9100-2026")

    run_id = db.open_run(conn, "rematch", "corpus refreshed overnight")
    stats = run_matcher(conn, run_id)
    db.finalize_run(conn, run_id, corpus.corpus_note(conn))

    new = _new_lines(conn, run_id)
    assert stats["new"] == len(new) > 0
    assert "F-9100-2026" in {row["source_record_id"] for row in new}
    # No delivery arrived, and the history says so rather than inventing one.
    assert runs.history(conn)[0]["channel"] == "rematch"


# --- Scenario 5: the assertion the whole design turns on --------------------

def test_a_carried_over_item_is_not_new_every_single_morning(kitchen):
    """Five days, same shelf. A carried-over item is re-recorded under a fresh
    inventory_records id every morning, so a diff on row ids would report the
    """
    conn, tmp = kitchen
    counts = []
    for day in range(5):
        result = _deliver(conn, _export(tmp, f"day{day}.csv"), NOW + timedelta(days=day))
        counts.append(result["matches"]["new"])

    assert counts == [0, 0, 0, 0, 0], f"a stable shelf reported new lines: {counts}"
    # And the sheet was genuinely full on every one of those days.
    for run in runs.history(conn):
        assert run["pull_count"] > 0


def test_an_item_that_drops_off_one_export_and_returns_is_not_new(kitchen):
    """Inventory is superseded by a later export, never by silence. An item
    missing from one morning's file was never removed from the shelf, so it was
    """
    conn, tmp = kitchen
    _deliver(conn, _export(tmp, "day1.csv"), NOW)
    day2 = _deliver(conn, _export(tmp, "day2.csv", drop="BEEF CRUMBLES"),
                    NOW + timedelta(days=1))

    assert day2["matches"]["new"] == 0, "silence was read as an arrival"
    day3 = _deliver(conn, _export(tmp, "day3.csv"), NOW + timedelta(days=2))
    assert day3["matches"]["new"] == 0, "the item came back and was called new"


# --- Scenario 6: it survives a restart --------------------------------------

def test_new_survives_a_restart_because_it_is_a_column_and_not_a_cache(kitchen):
    """There is no in-memory high-water mark to lose. `is_new` was written by
    the matcher and finalized with the run.
    """
    conn, tmp = kitchen
    _deliver(conn, _export(tmp, "day1.csv"), NOW)
    day2 = _deliver(conn, _export(tmp, "day2.csv", RECALLED_ROW), NOW + timedelta(days=1))
    before = [row["id"] for row in _new_lines(conn, day2["run_id"])]
    path = Path(conn.execute("PRAGMA database_list").fetchone()["file"])
    conn.close()

    reopened = db.connect(path)
    try:
        assert [row["id"] for row in _new_lines(reopened, day2["run_id"])] == before
        assert before
    finally:
        reopened.close()


def test_the_new_flag_is_never_edited_after_the_run_is_written(kitchen):
    """`matches` is written once. If `is_new` could be patched afterwards, a
    line could become un-new without anybody watching it happen.
    """
    conn, tmp = kitchen
    _deliver(conn, _export(tmp, "day1.csv"), NOW)
    day2 = _deliver(conn, _export(tmp, "day2.csv", RECALLED_ROW), NOW + timedelta(days=1))

    first = [(row["id"], row["status"]) for row in _new_lines(conn, day2["run_id"])]
    # Two more ordinary days pass.
    _deliver(conn, _export(tmp, "day3.csv", RECALLED_ROW), NOW + timedelta(days=2))
    _deliver(conn, _export(tmp, "day4.csv", RECALLED_ROW), NOW + timedelta(days=3))

    assert [(row["id"], row["status"]) for row in _new_lines(conn, day2["run_id"])] == first
    assert first, "nothing was flagged, so this proves nothing"
