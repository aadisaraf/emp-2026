"""SC-005. Every hand-seeded correspondence must reach the pull sheet."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pullsheet import db
from pullsheet.adapters.sftp_drop import SftpDropAdapter
from pullsheet.matching.run import ordered_matches
from pullsheet.recalls.corpus import load_snapshots

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"
ORACLE = json.loads((ROOT / "data" / "fixtures" / "expected_matches.json").read_text())
SEEDS = ORACLE["matches"]
NEGATIVES = ORACLE["must_not_pull"]


def _export_rows() -> list[dict]:
    import csv
    with FIXTURE.open() as f:
        return list(csv.DictReader(f))


EXPORT = _export_rows()


def _identifies(line, seed) -> bool:
    """Is this sheet line the export row the oracle names?"""
    row = EXPORT[seed["source_row"] - 1]
    return (line["raw_description"] == row["Item Description"]
            and (line["lot_code"] or "") == row["Lot #"]
            and (line["storage_location"] or "") == row["Storage Location"])


@pytest.fixture(scope="module")
def sheet(tmp_path_factory):
    path = tmp_path_factory.mktemp("sc005") / "sheet.db"
    db.reset(path)
    conn = db.connect(path)
    load_snapshots(conn)
    result = db.ingest_file(conn, FIXTURE, SftpDropAdapter())
    assert result["status"] == "ok"
    rows = ordered_matches(conn, result["run_id"])
    conn.close()
    return rows


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"{s['item_description']}->{s['recall_source_record_id']}")
def test_every_seeded_correspondence_reaches_the_sheet(seed, sheet):
    assert EXPORT[seed["source_row"] - 1]["Item Description"] == seed["item_description"], (
        "the fixture rows have shifted; the oracle's row numbers are stale")
    found = [r for r in sheet
             if _identifies(r, seed)
             and r["source_record_id"] == seed["recall_source_record_id"]]
    assert found, (
        f"row {seed['source_row']} ({seed['item_description']!r}) never reached "
        f"{seed['recall_source_record_id']}. {seed['why']}")

    line = found[0]
    assert line["status"] in {"PULL", "HELD"}
    assert line["evidence_kind"] == seed["expected_evidence_kind"], seed["why"]


@pytest.mark.parametrize("neg", NEGATIVES, ids=lambda n: n["item_description"])
def test_a_recalled_supplier_alone_never_pulls(neg, sheet):
    """FR-071, end to end. These rows are bought from a firm that IS being
    recalled. They must appear -- suppressing them would be the one thing the
    """
    lines = [r for r in sheet if r["raw_description"] == neg["item_description"]]
    assert lines, f"{neg['item_description']!r} produced no line at all"
    pulled = [r["evidence_kind"] for r in lines if r["status"] == "PULL"]
    assert not pulled, f"{neg['item_description']} pulled on {pulled}: {neg['why']}"


def test_most_rows_carry_no_barcode_which_is_the_point(sheet):
    """FR-026. Barcode and lot coverage in a kitchen's item master is partial;
    the fixture reflects that. If most rows had barcodes, the paths that matter
    """
    without = [r for r in EXPORT if not r["Case UPC"]]
    assert len(without) > len(EXPORT) * 0.75, (
        "the fixture has become unrealistically well-barcoded")


def test_a_row_with_no_barcode_still_reaches_a_recall(sheet):
    """FR-026. Produce and USDA commodity foods carry no barcode, and absence of
    a code is not evidence of absence of a recall.
    """
    lines = [r for r in sheet if r["raw_description"] == "APPLES FRESH 125 CT"]
    assert lines
    assert all(r["evidence_kind"] == "name" for r in lines)


def test_a_row_with_neither_barcode_nor_lot_still_pulls(sheet):
    """The case the supplier channels exist for: no barcode, no lot code, and a
    CONFIRMED pull anyway, off the manufacturer's own catalog number.
    """
    lines = [r for r in sheet
             if r["raw_description"] == "POLLOCK WEDGE BRD WG OVEN READY 3.4 OZ"]
    assert lines
    confirmed = [r for r in lines if r["evidence_kind"] == "mfr_item"]
    assert confirmed, "the manufacturer item code produced no line"
    assert confirmed[0]["tier"] == "CONFIRMED" and confirmed[0]["status"] == "PULL"
    assert confirmed[0]["lot_code"] is None


def test_the_blank_quantity_row_still_reaches_a_recall(sheet):
    lines = [r for r in sheet if r["raw_description"] == "CORN DOGS CHICKEN & PORK 4 OZ 72 CT"]
    assert lines, "a missing quantity suppressed a match"
    assert lines[0]["quantity"] is None


def test_no_seeded_pair_was_lost_between_screening_and_the_sheet(sheet):
    missing = [s for s in SEEDS
               if not any(_identifies(r, s)
                          and r["source_record_id"] == s["recall_source_record_id"]
                          for r in sheet)]
    assert not missing, f"{len(missing)} seeded pairs vanished: {missing[:3]}"


def test_held_lines_are_in_the_same_ordering_as_pull_lines(sheet):
    """HELD is never a separate section: the two statuses interleave in one
    order. A held line an operator has to go looking for is one they will not
    """
    statuses = [r["status"] for r in sheet]
    assert "PULL" in statuses and "HELD" in statuses
    first_held = statuses.index("HELD")
    assert "PULL" in statuses[first_held:], (
        "every PULL line precedes every HELD line -- the sheet is grouped by "
        "status rather than by seriousness")
