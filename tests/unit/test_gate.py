"""The most heavily tested function in the codebase.

Written BEFORE gate.decide() exists and observed failing. Constitution
Principle I is the one place in this build where that ceremony earns its keep:
a gate implemented before its tests cannot be said to have been driven by them.

The ladder (contracts/hold-gate.md):

    normalized gtin or upc equality      CONFIRMED  PULL
    lot agreement or secondary code      PROBABLE   PULL
    name similarity only, ANY score      POSSIBLE   HELD
"""

from __future__ import annotations

import itertools

import pytest

from pullsheet.matching.gate import TIER_STATUS, Decision, decide
from pullsheet.matching.tiers import Evidence


class Row:
    """A stand-in for an inventory or recall record. decide() reads nothing off
    these beyond what Evidence already carries -- if a test passes with these
    and fails with the real rows, decide() is reaching for something it should
    not have."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


INV = Row(id=1, raw_description="CHICKEN STRIPS BRD FC FROZEN", gtin=None, lot_code="4829-B")
REC = Row(id=1, product_description="Frozen Chicken Strips, breaded",
          source_record_id="FSIS-RC-018-2026", status="active")


# --------------------------------------------------------------------------
# The ladder: three rows, three tests
# --------------------------------------------------------------------------

def test_ladder_gtin_equality_is_confirmed_and_pulls():
    d = decide(INV, REC, Evidence("gtin", "10073803110075", "10073803110075"))
    assert (d.tier, d.status) == ("CONFIRMED", "PULL")


def test_ladder_upc_equality_is_confirmed_and_pulls():
    d = decide(INV, REC, Evidence("upc", "041220273355", "41220273355"))
    assert (d.tier, d.status) == ("CONFIRMED", "PULL")


def test_ladder_lot_agreement_is_probable_and_pulls():
    d = decide(INV, REC, Evidence(
        "lot", "4829-B", "LOT 4829B",
        lot_comparison="equal", recall_lot_present=True, inventory_lot_present=True))
    assert (d.tier, d.status) == ("PROBABLE", "PULL")


def test_ladder_secondary_code_is_probable_and_pulls():
    d = decide(INV, REC, Evidence(
        "secondary_code", "K10635", "Daycode: K10635",
        lot_comparison="equal", recall_lot_present=True, inventory_lot_present=True))
    assert (d.tier, d.status) == ("PROBABLE", "PULL")


def test_ladder_name_only_is_possible_and_holds():
    d = decide(INV, REC, Evidence("name", "CHICKEN STRIPS BRD FC FROZEN",
                                  "Frozen Chicken Strips, breaded", score=0.857))
    assert (d.tier, d.status) == ("POSSIBLE", "HELD")


# --------------------------------------------------------------------------
# The seven widening rules. Every one of them produces or retains a line.
# --------------------------------------------------------------------------

def test_widen_recall_names_a_lot_the_inventory_does_not_track():
    """FR-027. The district does not record lots for this item, so we cannot
    rule it out -- and not being able to rule it out means it stays visible."""
    d = decide(INV, REC, Evidence(
        "name", "peas & carrots froz 2lb", "Deep-brand PREMIUM Select Peas and Carrots",
        score=0.6, recall_lot_present=True, inventory_lot_present=False))
    assert d.status == "HELD"
    assert d.lot_note and "not tracked" in d.lot_note.lower()


def test_widen_lot_range_or_date_code_cannot_be_parsed():
    """FR-067. 'BEST BY 03/12-04/02' is not a lot code we can compare. Failure
    to parse widens; it must never narrow."""
    d = decide(INV, REC, Evidence(
        "name", "beef crumbles ckd", "Beef Crumbles, cooked and seasoned",
        score=0.7, lot_comparison="unparseable",
        recall_lot_present=True, inventory_lot_present=True))
    assert d.status == "HELD"
    assert d.lot_note and "could not be" in d.lot_note.lower()


def test_widen_lot_codes_overlap_partially():
    """FR-066. Recall lot 6112, inventory lot 6112A. Related, not equal."""
    d = decide(INV, REC, Evidence(
        "lot", "6112A", "6112", lot_comparison="contained",
        recall_lot_present=True, inventory_lot_present=True))
    assert d.status == "HELD"
    assert d.tier == "POSSIBLE"
    assert d.lot_note and "unconfirmed" in d.lot_note.lower()


def test_widen_inventory_has_no_gtin():
    """FR-026. Produce and USDA commodity foods carry no barcode. Absence of a
    code is not evidence of absence of a recall."""
    inv = Row(id=2, raw_description="APPLES FRESH 125 CT", gtin=None, lot_code=None)
    d = decide(inv, REC, Evidence("name", "APPLES FRESH 125 CT",
                                  "Golden delicious whole fresh apples", score=0.5))
    assert d.status == "HELD"
    assert d.evidence_kind == "name"


def test_widen_recall_code_info_unparsed():
    d = decide(INV, REC, Evidence(
        "name", "POTATO WEDGE CRINKLE CUT SAVORY 6 CUT 5 LB", "Crinkle Cut Wedge, Frozen Potatoes",
        score=0.55, recall_codes_unparsed=True))
    assert (d.tier, d.status) == ("POSSIBLE", "HELD")


def test_widen_any_field_absent_or_malformed_still_produces_a_line():
    """FR-025. Empty strings, None, and nonsense all still produce a Decision."""
    for bad in ("", "   ", None):
        d = decide(Row(id=3, raw_description=bad, gtin=None, lot_code=bad), REC,
                   Evidence("name", bad or "", "something", score=None))
        assert d.status in {"PULL", "HELD"}


def test_widen_terminated_or_amended_recall_is_retained_and_marked():
    """FR-016. A terminated recall is still a recall that was in this kitchen."""
    for status in ("terminated", "amended"):
        d = decide(INV, Row(id=4, status=status),
                   Evidence("gtin", "10073803110075", "10073803110075",
                            recall_status=status))
        assert d.status == "PULL"
        assert d.lot_note and status in d.lot_note.lower()


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_same_triple_yields_an_identical_decision_across_100_calls():
    ev = Evidence("lot", "4829-B", "LOT 4829B", score=0.9,
                  lot_comparison="equal", recall_lot_present=True, inventory_lot_present=True)
    first = decide(INV, REC, ev)
    for _ in range(100):
        assert decide(INV, REC, ev) == first


# --------------------------------------------------------------------------
# SC-003: the explicit auto-clear assertion
# --------------------------------------------------------------------------

def test_no_input_can_auto_clear():
    """Two parts, and between them they are what makes "there is no pull
    threshold" a testable claim rather than a slogan.

    (a) A property sweep over generated triples -- every combination of null,
        empty, malformed, and contradictory fields -- asserting that the status
        is always PULL or HELD, that nothing else is ever produced, and that
        nothing raises.

    (b) A score sweep on name-only evidence from 0.00 to 1.00 in 0.01 steps.
        All 101 values must yield HELD. If any score anywhere promotes a line,
        this fails, and a threshold has appeared in a codebase that claims not
        to have one.
    """
    # --- (a) property sweep -------------------------------------------------
    kinds = ["gtin", "upc", "lot", "secondary_code", "name"]
    texts = ["", "   ", "4829-B", "\x00\x01", "NULL", "0" * 500, "🥕"]
    scores = [None, -1.0, 0.0, 0.5, 1.0, 2.0, float("nan"), float("inf")]
    comparisons = [None, "equal", "contained", "none", "unparseable"]
    statuses = ["active", "terminated", "amended", "", "bogus"]

    checked = 0
    for kind, text, score, comparison, rstatus, rlot, ilot, unparsed in itertools.product(
        kinds, texts, scores, comparisons, statuses, (True, False), (True, False), (True, False)
    ):
        ev = Evidence(kind, text, text[::-1], score, comparison, rlot, ilot, unparsed, rstatus)
        inv = Row(id=0, raw_description=text, gtin=None, lot_code=text)
        rec = Row(id=0, product_description=text, status=rstatus)
        d = decide(inv, rec, ev)                       # must not raise, ever
        assert isinstance(d, Decision)
        assert d.status in {"PULL", "HELD"}, f"{d.status!r} from {ev!r}"
        assert d.tier in TIER_STATUS
        assert TIER_STATUS[d.tier] == d.status, f"tier/status disagree: {d.tier} {d.status}"
        checked += 1

    assert checked > 10_000, f"property sweep only covered {checked} inputs"

    # --- (b) score sweep ----------------------------------------------------
    for step in range(101):
        score = step / 100.0
        d = decide(INV, REC, Evidence("name", "CHICKEN STRIPS BRD FC FROZEN",
                                      "Frozen Chicken Strips, breaded", score=score))
        assert d.status == "HELD", f"score {score} promoted a name-only match to {d.status}"
        assert d.tier == "POSSIBLE", f"score {score} promoted a name-only match to {d.tier}"


def test_status_literal_admits_exactly_two_values():
    """There is no third status. Not 'CLEARED', not None, not ''."""
    assert set(TIER_STATUS.values()) == {"PULL", "HELD"}
