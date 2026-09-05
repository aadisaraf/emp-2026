from __future__ import annotations

from pullsheet.matching.normalize import tokens
from pullsheet.matching.similarity import dice


def test_the_flagship_pair():
    """3 shared tokens, 3 + 4 total: 6/7."""
    a = tokens("chkn strips froz")
    b = tokens("Frozen Chicken Strips, breaded")
    assert round(dice(a, b), 3) == 0.857


def test_identical_sets_score_one():
    a = tokens("chkn strips froz")
    assert dice(a, a) == 1.0


def test_disjoint_sets_score_zero():
    assert dice(tokens("chkn strips froz"), tokens("apples fresh")) == 0.0


def test_empty_is_zero_not_one():
    """Two unreadable descriptions are not evidence of a match."""
    assert dice(frozenset(), frozenset()) == 0.0
    assert dice(tokens("chkn strips froz"), frozenset()) == 0.0


def test_symmetric():
    a, b = tokens("grnd bf 80/20"), tokens("Ground Beef, 80/20, 10 lb chubs")
    assert dice(a, b) == dice(b, a)


def test_bounded():
    pairs = [("chkn strips froz", "Frozen Chicken Strips, breaded"),
             ("mozz shred lm", "Mozzarella Sticks"),
             ("apples fresh 125ct", "Golden delicious whole fresh apples")]
    for x, y in pairs:
        assert 0.0 <= dice(tokens(x), tokens(y)) <= 1.0
