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
                recalling_firm=r.get("recalling_firm") or "",
            ))
    return out


def _inventory() -> list[SimpleNamespace]:
    rows = []
    with (FIXTURES / "inventory_lincoln.csv").open() as f:
        for source_row, r in enumerate(csv.DictReader(f), start=1):
            gtin = "".join(c for c in r["Case UPC"] if c.isdigit()) or None
            rows.append(SimpleNamespace(
                source_row=source_row,
                storage_location=r["Storage Location"],
                raw_description=r["Item Description"],
                normalized_description=normalize(r["Item Description"]),
                gtin=gtin, lot_code=r["Lot #"] or None,
                brand=r["Brand"] or None,
                manufacturer=r["Manufacturer"] or None,
                manufacturer_item_code=r["Mfr Item #"] or None,
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
    desc = "CHICKEN STRIPS BRD FC FROZEN 2/5 LB"
    assert "frozen" in tokens(desc)
    assert "frozen" not in significant_tokens(desc)
    assert significant_tokens(desc) == {"chicken", "strips", "brd", "fc"}


def test_item_key_agrees_with_tiers():
    """``screen`` defines its own copy because ``tiers`` imports from it. Two
    implementations of one key is exactly the kind of thing that drifts."""
    from pullsheet.matching.screen import _item_key
    from pullsheet.matching.tiers import item_key
    for code in ("02075", "2075", "B-1133", "473015", "", None, "0", "  53374 "):
        assert _item_key(code) == item_key(code), code


def test_a_row_that_normalizes_to_nothing_is_still_reachable_by_code():
    row = SimpleNamespace(normalized_description="", gtin="10073803048293",
                          lot_code=None)
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
    candidates = generate_candidates(inv, INDEXES)
    assert seed["recall_source_record_id"] in candidates, (
        f"{inv.raw_description!r} in {inv.storage_location} no longer reaches "
        f"{seed['recall_source_record_id']} -- the screening floor has risen"
    )


def test_an_unrelated_pair_is_not_generated():
    """A row sharing no significant token, no lot, and no barcode fragment with
    a recall is never evaluated. That is the floor, stated as a test."""
    row = SimpleNamespace(normalized_description=normalize("zzqx widget assembly"),
                          gtin=None, lot_code=None)
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


def test_a_single_common_word_is_not_enough_on_its_own():
    """'milk' reaches every milk recall there has ever been. Admitting a pair on
    that alone produces a sheet nobody can read, which is its own way of missing
    a recall. Sharing a SECOND word still admits it."""
    from pullsheet.matching.screen import COMMON_TOKEN_SHARE
    common = [t for t, n in INDEXES.doc_freq.items()
              if n > COMMON_TOKEN_SHARE * INDEXES.record_count]
    assert common, "no token is common enough for this test to mean anything"
    token = max(common, key=lambda t: INDEXES.doc_freq[t])
    assert not INDEXES.is_distinctive(token)

    only_common = SimpleNamespace(normalized_description=token,
                                  gtin=None, lot_code=None)
    assert generate_candidates(only_common, INDEXES) == set()


def test_two_common_words_together_are_enough():
    """Take a real record, keep only its COMMON tokens, and check the pair still
    reaches it. Neither word would admit it alone."""
    for rec in CORPUS:
        common = [t for t in significant_tokens(rec.normalized_description)
                  if not INDEXES.is_distinctive(t)]
        if len(common) >= 2:
            row = SimpleNamespace(normalized_description=" ".join(common[:2]),
                                  gtin=None, lot_code=None)
            assert rec.id in generate_candidates(row, INDEXES)
            for word in common[:2]:
                alone = SimpleNamespace(normalized_description=word,
                                        gtin=None, lot_code=None)
                assert rec.id not in generate_candidates(alone, INDEXES)
            return
    pytest.skip("no record carries two common tokens")


def test_one_distinctive_word_is_enough():
    """'mozzarella' appears in 6 of 1012 records. One is plenty."""
    row = SimpleNamespace(normalized_description="mozzarella",
                          gtin=None, lot_code=None)
    assert INDEXES.is_distinctive("mozzarella")
    assert generate_candidates(row, INDEXES)


def test_the_screening_rule_is_stated_in_prose():
    """T045 renders this string verbatim on the sheet. It must answer 'what does
    your system throw away?' without the reader opening a file."""
    assert "significant product words" in SCREENING_RULE
    assert "never evaluated" in SCREENING_RULE
    assert "barcode" in SCREENING_RULE and "lot code" in SCREENING_RULE
    # The supplier channel is how most district rows reach a recall at all, so a
    # rule that does not mention it is not describing this system.
    assert "supplier" in SCREENING_RULE


# --------------------------------------------------------------------------
# The supplier channels (FR-069, FR-070)
# --------------------------------------------------------------------------

def _firm_record_id():
    """The id of the High Liner record carrying item number 53374."""
    for rec in CORPUS:
        if "53374" in (rec.parsed_codes.get("item_codes") or []):
            return rec.id
    raise AssertionError("the corpus no longer contains High Liner item 53374")


def _any_high_liner_id():
    for rec in CORPUS:
        if "high liner" in (rec.recalling_firm or "").lower():
            return rec.id
    raise AssertionError("the corpus no longer contains a High Liner record")


def test_a_row_with_no_barcode_and_no_lot_is_reachable_by_its_supplier():
    """The ordinary case, not the exception: most district rows carry neither a
    barcode nor a lot, and the supplier is the only identifier they have."""
    row = SimpleNamespace(normalized_description="", gtin=None, lot_code=None,
                          brand="High Liner", manufacturer=None, manufacturer_item_code=None)
    assert _any_high_liner_id() in generate_candidates(row, INDEXES)


def test_a_catalog_number_only_reaches_its_own_manufacturer():
    """FR-070. Item 53374 is a pollock wedge at High Liner and is nothing at all
    at any other company, so it is indexed under the firm rather than alone."""
    ours = SimpleNamespace(normalized_description="", gtin=None, lot_code=None,
                           brand="High Liner", manufacturer=None, manufacturer_item_code="53374")
    assert _firm_record_id() in generate_candidates(ours, INDEXES)

    theirs = SimpleNamespace(normalized_description="", gtin=None, lot_code=None,
                             brand="Simplot", manufacturer=None, manufacturer_item_code="53374")
    assert _firm_record_id() not in generate_candidates(theirs, INDEXES)


def test_a_row_with_no_supplier_at_all_is_unaffected():
    """The paste adapter supplies a description and nothing else. Adding supplier
    channels must not have made that row harder to match."""
    bare = SimpleNamespace(normalized_description="mozzarella", gtin=None,
                           lot_code=None)
    assert generate_candidates(bare, INDEXES)
