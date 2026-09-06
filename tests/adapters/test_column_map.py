"""Four vendors, four vocabularies, one set of internal fields (SC-012)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pullsheet.adapters.column_map import (
    ALIASES,
    apply,
    canonical,
    detect,
    required_missing,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VENDORS = ["headers_primeroedge.csv", "headers_linq_titan.csv",
           "headers_mealsplus.csv", "headers_adhoc.csv"]


def _headers(name):
    with (FIXTURES / name).open() as f:
        return csv.DictReader(f).fieldnames


def test_all_four_layouts_map_to_identical_internal_fields():
    resolved = {}
    for name in VENDORS:
        mapping, ambiguous = detect(_headers(name))
        fields = set(mapping.values())
        # The operator answers the ambiguous header once; after that all four
        # vocabularies describe exactly the same ten internal fields.
        for header, candidates in ambiguous.items():
            fields.add("lot_code" if "lot_code" in candidates else candidates[0])
        resolved[name] = fields

    reference = resolved[VENDORS[0]]
    for name, fields in resolved.items():
        assert fields == reference, f"{name} maps to {fields ^ reference} differently"
    assert reference == set(ALIASES)


def test_the_ambiguous_header_is_asked_about_not_guessed():
    mapping, ambiguous = detect(_headers("headers_adhoc.csv"))
    assert "Code" in ambiguous, "the deliberately ambiguous header was guessed"
    assert set(ambiguous["Code"]) == {"lot_code", "gtin"}
    assert "Code" not in mapping


def test_the_unambiguous_layouts_ask_nothing():
    for name in VENDORS[:3]:
        _mapping, ambiguous = detect(_headers(name))
        assert ambiguous == {}, f"{name} should need no question, got {ambiguous}"


@pytest.mark.parametrize("name", VENDORS)
def test_required_fields_are_always_found(name):
    mapping, _ = detect(_headers(name))
    assert required_missing(mapping) == set()


def test_detection_is_case_and_punctuation_insensitive():
    for spelling in ["Lot #", "LOT#", "lot  #", "Lot Number", "lot_no", "  Lot   "]:
        mapping, _ = detect([spelling])
        assert mapping.get(spelling) == "lot_code", spelling


def test_canonical():
    assert canonical("Qty On Hand") == "qty on hand"
    assert canonical("GTIN-14") == "gtin 14"
    assert canonical("$/unit") == "cost unit"
    assert canonical(None) == ""


def test_unrecognised_columns_are_kept_not_dropped():
    mapping, _ = detect(["Storage Location", "Item Description", "Vendor Notes"])
    row = {"Storage Location": "Freezer A",
           "Item Description": "CHICKEN STRIPS BRD FC FROZEN",
           "Vendor Notes": "substitute approved"}
    out = apply(mapping, row)
    assert out["storage_location"] == "Freezer A"
    assert out["_extra"] == {"Vendor Notes": "substitute approved"}


def test_a_field_is_never_claimed_twice():
    mapping, _ = detect(["Storage Location", "Storage Area", "Item Description"])
    assert list(mapping.values()).count("storage_location") == 1


def test_a_building_column_never_becomes_the_storage_location():
    """"Location" is a storage_location alias, so a "Location Name" column
    naming the school would land in the Storage column of the pull sheet and
    """
    for header in ["Site", "School", "Building", "Bldg", "Location Name", "Campus"]:
        mapping, ambiguous = detect([header, "Storage Location", "Item Description"])
        assert header not in mapping, f"{header} was mapped to {mapping.get(header)}"
        assert header not in ambiguous, f"{header} was asked about rather than ignored"
        assert mapping["Storage Location"] == "storage_location"
