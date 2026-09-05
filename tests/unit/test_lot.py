"""SC-015. Every case here came out of the fixture or the committed corpus."""

from __future__ import annotations

import pytest

from pullsheet.matching.lot import compare, looks_like_a_window, normalize_lot


@pytest.mark.parametrize("raw,expected", [
    ("LOT 4829B", "4829B"),
    ("4829-B", "4829B"),
    ("  lot   4829 b  ", "4829B"),
    ("Lot L1300", "L1300"),
    ("Daycode: K10635", "K10635"),
    ("Lots: 25006", "25006"),
    ("", None),
    (None, None),
    ("###", None),
])
def test_normalize_lot(raw, expected):
    assert normalize_lot(raw) == expected


def test_the_flagship_mismatch_is_equal():
    """The district writes 4829-B; the agency writes LOT 4829B."""
    assert compare("4829-B", "LOT 4829B") == "equal"


def test_prefix_is_contained_not_equal():
    assert compare("4829B", "4829") == "contained"
    assert compare("6112A", "6112") == "contained"
    assert compare("L1300A", "Lot L1300") == "contained"


def test_different_lots_are_none():
    assert compare("4829B", "4830B") == "none"
    assert compare("25142", "25139") == "none"


def test_date_ranges_are_unparseable_not_none():
    """FR-067: failure to parse must widen. Returning `none` here would let the
    gate treat a window it could not read as a positive non-match."""
    assert compare("4829B", "BEST BY 03/12-04/02") == "unparseable"
    assert compare("4829B", "BEST BY 03/12–04/02") == "unparseable"
    assert compare("Sell Thru Dates: SEP 25 25 Thru OCT 4 25", "4829B") == "unparseable"
    assert compare("4829B", "Use By 04/22/2026") == "unparseable"


def test_missing_side_is_unparseable():
    assert compare(None, "4829B") == "unparseable"
    assert compare("4829B", "") == "unparseable"


def test_window_detection():
    assert looks_like_a_window("BEST BY 03/12-04/02")
    assert not looks_like_a_window("4829-B")


def test_compare_never_raises():
    junk = [None, "", "   ", "\x00", "🥕", "0" * 1000, "LOT", "-", "//"]
    for a in junk:
        for b in junk:
            assert compare(a, b) in {"equal", "contained", "none", "unparseable"}


def test_symmetric():
    pairs = [("4829-B", "LOT 4829B"), ("6112A", "6112"), ("25142", "25139")]
    for a, b in pairs:
        assert compare(a, b) == compare(b, a)
