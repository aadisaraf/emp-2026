from __future__ import annotations

from pullsheet.matching.normalize import tokens
from pullsheet.matching.similarity import dice


def test_the_flagship_pair():
    """3 shared words, 5 + 4 total: 6/9."""
    a = tokens("CHICKEN STRIPS BRD FC FROZEN 2/5 LB")
    b = tokens("Frozen Chicken Strips, breaded")
    assert len(a & b) == 3
    assert round(dice(a, b), 3) == 0.667


def test_identical_sets_score_one():
    a = tokens("CHICKEN STRIPS BRD FC FROZEN 2/5 LB")
    assert dice(a, a) == 1.0


def test_disjoint_sets_score_zero():
    assert dice(tokens("CHICKEN STRIPS BRD FC FROZEN"), tokens("APPLES FRESH 125 CT")) == 0.0


def test_empty_is_zero_not_one():
    """Two unreadable descriptions are not evidence of a match."""
    assert dice(frozenset(), frozenset()) == 0.0
    assert dice(tokens("CHICKEN STRIPS BRD FC FROZEN"), frozenset()) == 0.0


def test_symmetric():
    a, b = tokens("GROUND BEEF 80/20 COARSE 10 LB CHUB"), tokens("Ground Beef, 80/20, 10 lb chubs")
    assert dice(a, b) == dice(b, a)


def test_bounded():
    pairs = [("CHICKEN STRIPS BRD FC FROZEN 2/5 LB", "Frozen Chicken Strips, breaded"),
             ("MOZZARELLA CHEESE SHREDDED LMPS 5 LB", "Mozzarella Sticks"),
             ("APPLES FRESH 125 CT", "Golden delicious whole fresh apples")]
    for x, y in pairs:
        assert 0.0 <= dice(tokens(x), tokens(y)) <= 1.0
