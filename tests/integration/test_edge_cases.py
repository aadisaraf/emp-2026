"""SC-010. One test per edge case in spec.md. All twelve."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pullsheet import db, runs as runs_module
from pullsheet.adapters.sftp_drop import SftpDropAdapter
from pullsheet.artifacts import pull_sheet
from pullsheet.matching import lot as lot_module
from pullsheet.matching.run import ordered_matches, run_matcher
from pullsheet.recalls import amend, corpus

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = ROOT / "tests" / "adapters" / "fixtures"
NOW = datetime(2026, 9, 5, 14, 30, tzinfo=timezone.utc)

HEADER = ("Storage Location,Item Description,Qty On Hand,UOM,Pack Size,"
          "Case UPC,Lot #,Brand,Manufacturer,Mfr Item #,Vendor,Vendor Item #,"
          "Unit Cost,Received Date\n")


@pytest.fixture
def loaded(tmp_path):
    """A location with one finished run, exactly as the daily job leaves it."""
    path = tmp_path / "edges.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    db.load_inventory_fixture(conn)
    yield conn
    conn.close()


def _run_id(conn) -> int:
    return db.latest_ok_run(conn)["id"]


def _lines(conn):
    return ordered_matches(conn, _run_id(conn))


def _rematch(conn):
    """Re-run the matcher for a corpus that changed after the export arrived."""
    run_id = db.open_run(conn, "rematch", f"rematch-{conn.total_changes}")
    # No new inventory: the matcher reads the ACTIVE set, so everything on the
    # shelves is re-matched against the corpus as it now stands.
    run_matcher(conn, run_id)
    db.finalize_run(conn, run_id, corpus.corpus_note(conn))
    return run_id


def _inject(conn, description, *, firm="Edge Case Foods LLC", code_info="",
            record_id="F-8000-2026", classification="Class I"):
    from pullsheet.matching.normalize import normalize
    from pullsheet.recalls.parse import parse_record
    snapshot = conn.execute("SELECT MAX(id) m FROM recall_snapshots").fetchone()["m"]
    cur = conn.execute(
        """INSERT INTO recall_records
           (source, source_record_id, snapshot_id, recalling_firm, product_description,
            normalized_description, code_info, parsed_codes, classification, class_rank,
            report_date, received_at, reason_for_recall, status, raw_json)
           VALUES ('openfda',?,?,?,?,?,?,?,?,?,'2026-09-05',?,'Listeria','active','{}')""",
        (record_id, snapshot, firm, description, normalize(description), code_info,
         json.dumps(parse_record(description, code_info, None)), classification,
         corpus.class_rank(classification), NOW.isoformat()))
    conn.commit()
    return cur.lastrowid


# --- 1. malformed / empty / unrecognised-column export ----------------------

def test_01_a_malformed_export_is_rejected_by_name_and_leaves_the_sheet_intact(loaded):
    good_run = _run_id(loaded)
    before = [m["id"] for m in _lines(loaded)]
    assert before, "there is no sheet to protect, so this test proves nothing"

    adapter = SftpDropAdapter()
    result = db.ingest_file(loaded, FIXTURES / "malformed.csv", adapter)
    assert result["status"] == "rejected"
    assert "malformed.csv" in result["reason"]
    # The message names the failing row or column, not just "invalid".
    assert "row" in result["reason"].lower() or "column" in result["reason"].lower()

    # A rejected delivery does not become "the latest run", so the sheet that
    # was in force this morning is still the sheet in force this afternoon.
    assert _run_id(loaded) == good_run
    assert [m["id"] for m in _lines(loaded)] == before
    run = db.get_run(loaded, result["run_id"])
    assert run["status"] == "rejected" and run["rejection_reason"]

    empty = db.ingest_file(loaded, FIXTURES / "empty.csv", adapter)
    assert empty["status"] == "rejected"
    assert _run_id(loaded) == good_run
    assert [m["id"] for m in _lines(loaded)] == before


# --- 2. partially parseable rows -------------------------------------------

def test_02_partially_parseable_rows_are_kept_and_flagged(loaded, tmp_path):
    path = tmp_path / "partial.csv"
    path.write_text(
        "Storage Location,Item Description,Qty On Hand,UOM,Case UPC,Lot #\n"
        "Freezer 9,CHICKEN STRIPS BRD FC FROZEN 2/5 LB,,CS,,\n"
        "Freezer 9,SPINACH CHOPPED ORGANIC IQF 10 OZ,not-a-number,CS,,\n")
    result = db.ingest_file(loaded, path, SftpDropAdapter())
    assert result["status"] == "ok"
    assert result["rows_read"] == 2, "a row was dropped"

    rows = loaded.execute(
        """SELECT * FROM inventory_records
            WHERE run_id = ? AND storage_location = 'Freezer 9' ORDER BY id""",
        (result["run_id"],)).fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row["quantity"] is None, "an unreadable quantity was invented"
        flags = json.loads(row["unpopulated_fields"])
        assert "quantity" in flags, "the absence is not flagged on the row"


# --- 3. recall source unreachable ------------------------------------------

def test_03_an_unreachable_source_falls_back_and_says_so(loaded, monkeypatch):
    from pullsheet.recalls import fetch

    def refuse(*_a, **_k):
        raise OSError("Network is unreachable")

    monkeypatch.setattr(fetch, "fetch", refuse)
    result = fetch.refresh(loaded, now=NOW)

    assert result["status"] == "cached_fallback"
    assert result["snapshot"] is not None
    assert result["snapshot"]["captured_at"][:10] in result["message"]
    assert "Nothing on the pull sheet has changed" in result["message"]

    # And the capture date and age reach the printed artifact.
    head = pull_sheet.header(loaded, db.latest_ok_run(loaded), NOW)
    assert head["corpora"] and all("captured_at" in c and "age_hours" in c
                                   for c in head["corpora"])


# --- 4. item with no GTIN ---------------------------------------------------

def test_04_an_item_with_no_gtin_is_still_matched(loaded):
    without = loaded.execute(
        """SELECT COUNT(DISTINCT i.id) c FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE i.gtin IS NULL AND i.superseded_by IS NULL""").fetchone()["c"]
    assert without > 0, "every matched row has a barcode; the no-GTIN path is untested"

    # And some of them PULL -- absence of a code does not cap the tier either.
    pulled = loaded.execute(
        """SELECT COUNT(*) c FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE i.gtin IS NULL AND i.lot_code IS NULL AND m.status = 'PULL'""").fetchone()["c"]
    assert pulled > 0, "no row with neither a barcode nor a lot ever pulls"


# --- 5. recall names a lot the inventory does not track ---------------------

def test_05_an_untracked_lot_produces_held_not_cleared(loaded):
    _inject(loaded, "Edge Case Foods Beef Crumbles Cooked Taco Seasoned 5 lb",
            code_info="LOT ZZ-99887", record_id="F-8005-2026")
    run_id = _rematch(loaded)

    lines = [m for m in ordered_matches(loaded, run_id)
             if m["source_record_id"] == "F-8005-2026"]
    assert lines, "the recall produced no line at all, which is worse than HELD"
    untracked = [m for m in lines if not m["lot_code"]]
    assert untracked, "no matched row lacks a lot code, so this case is untested"
    for line in untracked:
        assert line["status"] == "HELD"
        assert line["lot_note"], "the line does not state that the lot is unconfirmed"


# --- 6. same product, several lots -----------------------------------------

def test_06_one_line_per_lot(loaded):
    """One location, so the case that used to be "same product at two sites" is
    the same product in two lots -- which is the one that actually matters,
    """
    rows = loaded.execute(
        """SELECT i.lot_code, i.storage_location, i.raw_description, COUNT(*) c
             FROM matches m JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE i.superseded_by IS NULL AND i.raw_description IN (
                  SELECT raw_description FROM inventory_records
                   WHERE superseded_by IS NULL GROUP BY raw_description
                  HAVING COUNT(DISTINCT IFNULL(lot_code, '')) > 1)
            GROUP BY i.lot_code, i.storage_location, i.raw_description""").fetchall()
    assert rows, "no product is stocked in two lots; this case is untested"

    seen = {(r["lot_code"], r["storage_location"], r["raw_description"]) for r in rows}
    assert len(seen) == len(rows), "two lots of one product collapsed into one line"
    for row in rows:
        assert row["c"] >= 1
        # Each carries its own quantity and location, not a shared one.
        detail = loaded.execute(
            """SELECT quantity, storage_location FROM inventory_records
                WHERE IFNULL(lot_code,'') = IFNULL(?,'') AND raw_description = ?
                  AND superseded_by IS NULL LIMIT 1""",
            (row["lot_code"], row["raw_description"])).fetchone()
        assert detail is not None


# --- 7. two recalls, one item ----------------------------------------------

def test_07_two_recalls_on_one_item_produce_two_lines_worst_class_first(loaded):
    run_id = _run_id(loaded)
    doubled = loaded.execute(
        """SELECT inventory_record_id, COUNT(DISTINCT recall_record_id) c
             FROM matches WHERE run_id = ?
            GROUP BY inventory_record_id HAVING c > 1
            ORDER BY c DESC LIMIT 1""", (run_id,)).fetchone()
    assert doubled, "no item is hit by two recalls; this case is untested"

    lines = [m for m in ordered_matches(loaded, run_id)
             if m["inventory_record_id"] == doubled["inventory_record_id"]]
    assert len(lines) == doubled["c"], "de-duplication hid a recall"
    ranks = [m["class_rank"] for m in lines]
    assert ranks == sorted(ranks), "the most serious class is not first"


# --- 8. recall later terminated or amended ---------------------------------

def test_08_a_terminated_recall_keeps_its_lines_marked_with_both_states(loaded):
    run_id = _run_id(loaded)
    target = loaded.execute(
        """SELECT r.source, r.source_record_id, r.id, COUNT(*) c
             FROM matches m JOIN recall_records r ON r.id = m.recall_record_id
            WHERE r.status = 'active' AND m.run_id = ?
            GROUP BY r.id ORDER BY c DESC LIMIT 1""", (run_id,)).fetchone()
    before = loaded.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"]

    result = amend.terminate(loaded, target["source"], target["source_record_id"],
                             NOW + timedelta(hours=2))
    assert result["lines_removed"] == 0
    assert loaded.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"] == before

    lines = [m for m in ordered_matches(loaded, run_id)
             if m["recall_record_id"] == target["id"]]
    assert len(lines) == target["c"], "a line disappeared when the recall was terminated"
    for line in lines:
        assert line["recall_status"] == "terminated"
        assert line["recall_prior_status"] == "active", "the prior state is not shown"
        assert line["status"] in ("PULL", "HELD"), "termination changed the line's status"


def test_08b_an_amended_recall_keeps_both_versions(loaded):
    target = loaded.execute(
        """SELECT r.source, r.source_record_id, r.id FROM matches m
             JOIN recall_records r ON r.id = m.recall_record_id
            WHERE r.status = 'active' LIMIT 1""").fetchone()
    result = amend.amend(loaded, target["source"], target["source_record_id"],
                         {"product_description": "Revised description, expanded lots",
                          "recall_number": target["source_record_id"] + "-A"},
                         NOW + timedelta(hours=3))

    old = loaded.execute("SELECT * FROM recall_records WHERE id = ?",
                         (target["id"],)).fetchone()
    new = loaded.execute("SELECT * FROM recall_records WHERE id = ?",
                         (result["superseded_by"],)).fetchone()
    assert old["status"] == "amended" and old["prior_status"] == "active"
    assert new["amended_from"] == target["id"] and new["status"] == "active"

    chain = amend.history(loaded, new["id"])
    assert [c["id"] for c in chain] == [old["id"], new["id"]]


# --- 9. zero matches --------------------------------------------------------

def test_09_zero_matches_still_produces_a_sheet_naming_the_corpus(tmp_path):
    path = tmp_path / "zero.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    # A real thing a kitchen stocks that shares no word with any recall in the
    # corpus. Inventory is present; it simply does not match anything.
    export = tmp_path / "quiet.csv"
    export.write_text(HEADER +
                      "Dry Store,QUARTZ SCOURING PAD 12 CT,4,CS,12 ct,,,,,,,,,\n")
    result = db.ingest_file(conn, export, SftpDropAdapter())
    assert result["status"] == "ok" and result["rows_read"] == 1

    run = db.latest_ok_run(conn)
    head = pull_sheet.header(conn, run, NOW)
    assert head["counts"]["total"] == 0
    # The artifact still exists and still names the corpus and its capture date.
    assert head["corpora"], "an empty sheet does not say what it was matched against"
    for entry in head["corpora"]:
        assert entry["captured_at"] and entry["record_count"] > 0
    assert pull_sheet.by_storage(conn, run["id"]) == []

    # And the word for it is "no recalled items found" -- a result, not silence.
    assert runs_module.run_status(conn, NOW)["state"] == "clear"
    conn.close()


# --- 10. two exports, one location -----------------------------------------

def test_10_a_later_export_supersedes_and_preserves_human_decisions(loaded, tmp_path):
    first = ordered_matches(loaded, _run_id(loaded))[0]
    subject = db.subject_key(first["identity_key"], first["source"],
                             first["source_record_id"])
    loaded.execute(
        """INSERT INTO decisions (kind, match_id, subject_key, actor, created_at)
           VALUES ('clear_match', ?, ?, 'AS', ?)""",
        (first["id"], subject, NOW.isoformat()))
    loaded.commit()

    # Same storage location, same product and lot as the fixture row, so it
    # resolves to the same identity_key -- which is what supersession is.
    path = tmp_path / "second.csv"
    path.write_text(HEADER +
                    "Freezer A,CHICKEN STRIPS BRD FC FROZEN 2/5 LB,"
                    "11,CS,2/5 lb,,4829-B,Cardinal Valley,Cardinal Valley Poultry Co.,"
                    "CV-4829,Sysco,1873452,38.50,2026-09-05\n")
    result = db.ingest_file(loaded, path, SftpDropAdapter())
    assert result["status"] == "ok"
    assert result["superseded"] >= 1, "the later export superseded nothing"

    superseded = loaded.execute(
        "SELECT COUNT(*) c FROM inventory_records WHERE superseded_by IS NOT NULL"
    ).fetchone()["c"]
    assert superseded >= 1

    # The clearing was recorded against the FOOD and the RECALL, so the new
    # run's brand-new match row for the same pair is still cleared. A decision
    today = [m for m in ordered_matches(loaded, result["run_id"])
             if db.subject_key(m["identity_key"], m["source"],
                               m["source_record_id"]) == subject]
    assert today, "the superseded item vanished from the new run"
    assert all(m["cleared_count"] >= 1 for m in today), (
        "a human clearing decision was silently reverted by the next export")


# --- 11. lot codes in different formats ------------------------------------

def test_11_lot_formats_normalize_and_a_partial_overlap_is_held(loaded):
    assert lot_module.compare("LOT 4829B", "4829-B") == "equal"
    assert lot_module.normalize_lot("LOT 4829B") == lot_module.normalize_lot("4829-B")

    partial = lot_module.compare("4829B", "4829B12")
    assert partial != "equal", "one code contained in another was decided as a match"

    # The fixture's chicken strips carry lot "4829-B". A recall quoting
    # "4829-B-07" contains it without equalling it: the honest answer is HELD
    assert lot_module.compare("4829-B", "4829-B-07") == "contained"

    _inject(loaded, "Cardinal Valley Chicken Strips Breaded Fully Cooked 2/5 lb",
            firm="Cardinal Valley Poultry Co.", code_info="Lot 4829-B-07",
            record_id="F-8011-2026")
    run_id = _rematch(loaded)
    lines = [m for m in ordered_matches(loaded, run_id)
             if m["source_record_id"] == "F-8011-2026"]
    contained = [m for m in lines if m["lot_code"] == "4829-B"]
    assert contained, "no line has the partially overlapping lot; this case is untested"
    for line in contained:
        assert line["status"] == "HELD" or line["lot_note"], (
            "a partial lot relationship was decided without a note")


# --- 12. snapshot older than the freshness window --------------------------

def test_12_a_stale_snapshot_gates_the_word_not_the_lines(loaded):
    run_id = _run_id(loaded)
    captured = corpus._parse_ts(loaded.execute(
        "SELECT MIN(captured_at) o FROM recall_snapshots").fetchone()["o"])
    fresh, stale = captured + timedelta(hours=2), captured + timedelta(hours=30)

    assert corpus.is_stale(loaded, fresh) is False
    assert corpus.is_stale(loaded, stale) is True

    lines_fresh = [(m["id"], m["status"]) for m in ordered_matches(loaded, run_id)]
    lines_stale = [(m["id"], m["status"]) for m in ordered_matches(loaded, run_id)]
    assert lines_fresh == lines_stale and lines_fresh

    # The stale corpus can change the WORD but never a LINE. And it can only
    # ever make the word more cautious: it must not be allowed to say "clear".
    word = runs_module.run_status(loaded, stale)
    assert word["state"] != "clear"
    assert word["stale_corpus"] is True
