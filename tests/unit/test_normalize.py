"""Normalization is the one place a food description is rewritten. If it is
wrong, every downstream comparison is wrong in the same direction and nothing
else in the system will notice.
"""

from __future__ import annotations

from pullsheet.matching.normalize import normalize, tokens


def test_a_district_catalog_description():
    assert tokens("CHICKEN STRIPS BRD FC FROZEN 2/5 LB") == {
        "chicken", "strips", "brd", "fc", "frozen"}


def test_the_recall_side_of_the_same_product():
    assert tokens("Frozen Chicken Strips, breaded") == {
        "frozen", "chicken", "strips", "breaded"}


def test_the_two_sides_overlap_on_the_words_they_share():
    """No expansion, no spelling correction: three words agree because both
    catalogs wrote the same three words.
    """
    shared = tokens("CHICKEN STRIPS BRD FC FROZEN 2/5 LB") & tokens("Frozen Chicken Strips, breaded")
    assert shared == {"chicken", "strips", "frozen"}


def test_an_abbreviation_is_not_expanded():
    """``BRD`` and ``breaded`` are different words and stay different words."""
    assert "brd" in tokens("CHICKEN STRIPS BRD FC FROZEN 2/5 LB")
    assert "breaded" not in tokens("CHICKEN STRIPS BRD FC FROZEN 2/5 LB")


def test_pack_sizes_and_units_are_stripped():
    assert tokens("SPINACH CHOPPED ORGANIC IQF 10 OZ") == {"spinach", "chopped", "organic", "iqf"}
    assert tokens("PEAS & CARROTS BLEND IQF 2 LB") == {"peas", "carrots", "blend", "iqf"}
    assert tokens("GROUND BEEF 80/20 COARSE 10 LB CHUB") == {"ground", "beef", "coarse", "chub"}
    assert tokens("SALSA MILD #10 CAN") == {"salsa", "mild"}
    assert tokens("HFS 10/6lb Crunchy Row Breaded Cod Rectangles 3 oz.") == {
        "hfs", "crunchy", "row", "breaded", "cod", "rectangles"}


def test_empty_and_missing_input_do_not_raise():
    assert tokens(None) == frozenset()
    assert tokens("") == frozenset()
    assert tokens("   ") == frozenset()
    assert tokens("###") == frozenset()


def test_normalize_is_stable_and_sorted():
    assert normalize("CHICKEN STRIPS BRD FC FROZEN 2/5 LB") == "brd chicken fc frozen strips"
    assert normalize("FROZEN BRD CHICKEN STRIPS FC") == normalize("CHICKEN STRIPS BRD FC FROZEN")


def test_normalization_is_deterministic():
    first = normalize("Frozen Chicken Strips, breaded")
    for _ in range(100):
        assert normalize("Frozen Chicken Strips, breaded") == first


def test_there_is_no_abbreviation_dictionary():
    """A regression guard on the decision, not just on its effects."""
    import pullsheet.matching as matching
    from pathlib import Path
    assert not (Path(matching.__file__).parent / "abbreviations.py").exists()
