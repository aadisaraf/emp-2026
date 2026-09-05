"""Screening is the only place a pair can fail to exist. Every test here exists
to make that floor visible and to keep it from quietly rising.

The build-stopping assertion is
``test_every_seeded_pair_survives_screening``: if a hand-seeded correspondence
is screened out, no amount of correct gate logic downstream will put it back on
the sheet.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pullsheet.matching.normalize import normalize
from pullsheet.matching.screen import (
    SCREENING_RULE,
    STOPLIST,
    ScreenRecord,
    build_indexes,
    code_key,
    generate_candidates,
    significant_tokens,
)
from pullsheet.recalls.parse import parse_record

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOTS = ROOT / "pullsheet" / "recalls" / "snapshots"
FIXTURES = ROOT / "data" / "fixtures"


def _corpus() -> list[ScreenRecord]:
    out = []
    for name in ("openfda-2026-09-05.json", "fsis-2026-09-05.json"):
        for r in json.loads((SNAPSHOTS / name).read_text())["results"]:
            out.append(ScreenRecord(
                id=r["recall_number"],
                normalized_description=normalize(r["product_description"]),
                parsed_codes=parse_record(r["product_description"], r.get("code_info"), r.get("more_code_info")),
            ))
    return out


def _inventory() -> list[SimpleNamespace]:
    rows = []
    with (FIXTURES / "inventory_lincoln.csv").open() as f:
        for source_row, r in enumerate(csv.DictReader(f), start=1):
            gtin = "".join(c for c in r["Case UPC"] if c.isdigit()) or None
            rows.append(SimpleNamespace(
                source_row=source_row,
                site=r["Site"],
                raw_description=r["Item Description"],
                normalized_description=normalize(r["Item Description"]),
                gtin=gtin, upc=gtin, lot_code=r["Lot #"] or None,
            ))
    return rows


CORPUS = _corpus()
INDEXES = build_indexes(CORPUS)
INVENTORY = _inventory()
SEEDS = json.loads((FIXTURES / "expected_matches.json").read_text())["matches"]


# --------------------------------------------------------------------------
# T027: the indexes
# --------------------------------------------------------------------------

def test_indexes():
    """A GTIN-14 and its UPC-12 form land on the same code key, and stoplisted
    words never enter the token index."""
    # Same case, printed two ways. The check digits differ; the key does not.
    assert code_key("10073803048293") == code_key("073803048296") == "07380304829"
    assert code_key("10041220273352") == code_key("041220273355")

    for word in ("frozen", "case", "fresh", "packaged", "brand"):
        assert word in STOPLIST
        assert word not in INDEXES.by_token, f"{word!r} leaked into the token index"

    assert INDEXES.record_count == len(CORPUS)
    assert INDEXES.by_code and INDEXES.by_lot and INDEXES.by_token


def test_code_key_ignores_unusable_input():
    for junk in (None, "", "   ", "abc", "12", "🥕"):
        assert code_key(junk) is None


def test_significant_tokens_drop_the_stoplist_but_normalization_keeps_it():
    from pullsheet.matching.normalize import tokens
    assert "frozen" in tokens("chkn strips froz")
    assert "frozen" not in significant_tokens("chkn strips froz")
    assert significant_tokens("chkn strips froz") == {"chicken", "strips"}


def test_a_row_that_normalizes_to_nothing_is_still_reachable_by_code():
    row = SimpleNamespace(normalized_description="", gtin="10073803048293",
                          upc=None, lot_code=None)
    assert generate_candidates(row, INDEXES), "a barcode-only row was screened out"


# --------------------------------------------------------------------------
# T028: generate_candidates
# --------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"row{s['source_row']}->{s['recall_source_record_id']}")
def test_every_seeded_pair_survives_screening(seed):
    """A seeded pair screened out is a build-stopping failure: nothing
    downstream can recover a pair that was never generated."""
    inv = INVENTORY[seed["source_row"] - 1]
    assert inv.raw_description == seed["item_description"]
    assert inv.site == seed["site"]
    candidates = generate_candidates(inv, INDEXES)
    assert seed["recall_source_record_id"] in candidates, (
        f"{inv.raw_description!r} at {inv.site} no longer reaches "
        f"{seed['recall_source_record_id']} -- the screening floor has risen"
    )


def test_an_unrelated_pair_is_not_generated():
    """A row sharing no significant token, no lot, and no barcode fragment with
    a recall is never evaluated. That is the floor, stated as a test."""
    row = SimpleNamespace(normalized_description=normalize("zzqx widget assembly"),
                          gtin=None, upc=None, lot_code=None)
    assert generate_candidates(row, INDEXES) == set()


def test_screening_narrows_substantially():
    """If screening returned everything it would not be a floor, it would be a
    no-op dressed as one."""
    total = len(CORPUS)
    sizes = [len(generate_candidates(inv, INDEXES)) for inv in INVENTORY]
    assert max(sizes) < total, "some row is compared against the entire corpus"
    assert sum(sizes) / len(sizes) < total / 2


def test_no_inventory_row_is_screened_out_entirely_without_reason():
    """Report which rows reach nothing. Zero candidates is legitimate -- it means
    that item genuinely matches no recall -- but it should be a small minority,
    and a sudden jump here means the floor moved."""
    empty = [inv.raw_description for inv in INVENTORY
             if not generate_candidates(inv, INDEXES)]
    assert len(empty) < len(INVENTORY) / 2, f"{len(empty)} rows reach nothing: {empty[:5]}"


def test_the_screening_rule_is_stated_in_prose():
    """T045 renders this string verbatim on the sheet. It must answer 'what does
    your system throw away?' without the reader opening a file."""
    assert "significant name token" in SCREENING_RULE
    assert "never evaluated" in SCREENING_RULE
