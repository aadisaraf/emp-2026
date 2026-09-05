"""SC-005. Every hand-seeded correspondence must reach the pull sheet.

The asymmetry is the point: a seeded pair that is ABSENT is a failure. A seeded
pair that lands HELD rather than PULL is not -- the gate is allowed to be more
cautious than this file, never less.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pullsheet import db
from pullsheet.adapters.watched_folder import WatchedFolderAdapter
from pullsheet.matching.run import ordered_matches, run_matcher
from pullsheet.recalls.corpus import load_snapshots

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"
SEEDS = json.loads((ROOT / "data" / "fixtures" / "expected_matches.json").read_text())["matches"]


@pytest.fixture(scope="module")
def sheet(tmp_path_factory):
    path = tmp_path_factory.mktemp("sc005") / "sheet.db"
    db.reset(path)
    conn = db.connect(path)
    load_snapshots(conn)
    db.ingest_file(conn, FIXTURE, WatchedFolderAdapter(), "Lincoln USD watched folder")
    run_matcher(conn)
    rows = ordered_matches(conn)
    conn.close()
    return rows


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"{s['item_description']}->{s['recall_source_record_id']}")
def test_every_seeded_correspondence_reaches_the_sheet(seed, sheet):
    found = [r for r in sheet
             if r["raw_description"] == seed["item_description"]
             and r["site"] == seed["site"]
             and r["source_record_id"] == seed["recall_source_record_id"]]
    assert found, (
        f"{seed['item_description']!r} at {seed['site']} never reached "
        f"{seed['recall_source_record_id']}. {seed['why']}")

    line = found[0]
    assert line["status"] in {"PULL", "HELD"}
    assert line["evidence_kind"] == seed["expected_evidence_kind"], seed["why"]


def test_the_abbreviation_cases_specifically(sheet):
    """The three descriptions the whole abbreviation dictionary exists for."""
    for abbreviated in ("chkn strips froz", "grnd bf 80/20", "mozz shred lm"):
        lines = [r for r in sheet if r["raw_description"] == abbreviated]
        assert lines, f"{abbreviated!r} produced no line at all"


def test_a_row_with_no_barcode_still_reaches_a_recall(sheet):
    """FR-026. Produce and USDA commodity foods carry no barcode, and absence of
    a code is not evidence of absence of a recall."""
    lines = [r for r in sheet if r["raw_description"] == "apples fresh 125ct"]
    assert lines
    assert all(r["evidence_kind"] == "name" for r in lines)


def test_the_blank_quantity_row_still_reaches_a_recall(sheet):
    lines = [r for r in sheet if r["raw_description"] == "corn dogs chkn prk"]
    assert lines, "a missing quantity suppressed a match"
    assert lines[0]["quantity"] is None


def test_no_seeded_pair_was_lost_between_screening_and_the_sheet(sheet):
    on_sheet = {(r["site"], r["raw_description"], r["source_record_id"]) for r in sheet}
    missing = [s for s in SEEDS
               if (s["site"], s["item_description"], s["recall_source_record_id"]) not in on_sheet]
    assert not missing, f"{len(missing)} seeded pairs vanished: {missing[:3]}"


def test_held_lines_are_in_the_same_ordering_as_pull_lines(sheet):
    """HELD is never a separate section: the two statuses interleave in one
    order. A held line an operator has to go looking for is one they will not
    see."""
    statuses = [r["status"] for r in sheet]
    assert "PULL" in statuses and "HELD" in statuses
    first_held = statuses.index("HELD")
    assert "PULL" in statuses[first_held:], (
        "every PULL line precedes every HELD line -- the sheet is grouped by "
        "status rather than by seriousness")
