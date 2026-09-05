"""Normalization is the one place a food description is rewritten. If it is
wrong, every downstream comparison is wrong in the same direction and nothing
else in the system will notice."""

from __future__ import annotations

from pullsheet.matching.normalize import normalize, tokens


def test_abbreviated_inventory_description():
    assert tokens("chkn strips froz") == {"chicken", "strips", "frozen"}


def test_recall_side_of_the_same_product():
    assert tokens("Frozen Chicken Strips, breaded") == {"frozen", "chicken", "strips", "breaded"}


def test_the_two_sides_overlap_only_because_of_expansion():
    """Without the abbreviation dictionary these two share nothing at all.
    This is the whole reason abbreviations.py is hand-authored."""
    raw_overlap = set("chkn strips froz".split()) & set("frozen chicken strips breaded".split())
    assert raw_overlap == {"strips"}
    assert len(tokens("chkn strips froz") & tokens("Frozen Chicken Strips, breaded")) == 3


def test_multiword_expansion():
    assert tokens("chkn nuggets wg froz") == {"chicken", "nuggets", "whole", "grain", "frozen"}
    assert tokens("mozz shred lm") == {"mozzarella", "shredded", "low", "moisture"}


def test_pack_sizes_and_units_are_stripped():
    assert tokens("spinach froz org 10oz") == {"spinach", "frozen", "organic"}
    assert tokens("peas & carrots froz 2lb") == {"peas", "carrots", "frozen"}
    assert tokens("grnd bf 80/20") == {"ground", "beef"}
    assert tokens("salsa mild #10") == {"salsa", "mild"}
    assert tokens("chkn broth ns 32oz") == {"chicken", "broth", "no", "salt"}


def test_empty_and_missing_input_do_not_raise():
    assert tokens(None) == frozenset()
    assert tokens("") == frozenset()
    assert tokens("   ") == frozenset()
    assert tokens("###") == frozenset()


def test_normalize_is_stable_and_sorted():
    assert normalize("chkn strips froz") == "chicken frozen strips"
    assert normalize("froz chkn strips") == normalize("chkn strips froz")


def test_normalization_is_deterministic():
    first = normalize("Frozen Chicken Strips, breaded")
    for _ in range(100):
        assert normalize("Frozen Chicken Strips, breaded") == first
