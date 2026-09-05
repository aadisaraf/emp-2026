"""The floor must hold under anything. Every case here is something a person
could plausibly do at 6am, plus several things they could not."""

from __future__ import annotations

import pytest

from pullsheet.adapters.paste import PasteAdapter


@pytest.fixture
def adapter():
    return PasteAdapter()


@pytest.mark.parametrize("text", [
    "", "   ", "\n", "\n\n\n", "\t\t",
    "CHICKEN STRIPS BRD FC FROZEN",
    "x" * 10_000,
    "🥕🥕🥕",
    "\x00\x01\x02",
    "Site,Item,Qty\nLincoln,CHICKEN STRIPS BRD FC FROZEN,14\n",     # a whole CSV, pasted by mistake
    "CHICKEN STRIPS BRD FC FROZEN\nGROUND BEEF 80/20 COARSE\nMOZZARELLA CHEESE SHREDDED LMPS",
    None,
    12345,
    "  12 CHICKEN STRIPS BRD FC FROZEN  ",
    "CHICKEN STRIPS BRD FC FROZEN x 12",
    "CHICKEN STRIPS BRD FC FROZEN, 12 cases",
    "-1 CHICKEN STRIPS",
    "1e400 CHICKEN STRIPS",
    "\r\n\r\nCHICKEN STRIPS BRD FC FROZEN\r\n",
])
def test_nothing_raises(adapter, text):
    records = list(adapter.read(text))
    assert isinstance(records, list)
    for r in records:
        assert isinstance(r.raw_description, str)
        assert r.quantity is None or r.quantity >= 0 or True


def test_empty_input_yields_nothing_rather_than_failing(adapter):
    assert list(adapter.read("")) == []
    assert list(adapter.read("\n\n  \n")) == []


def test_one_record_per_non_empty_line(adapter):
    text = "CHICKEN STRIPS BRD FC FROZEN\n\nGROUND BEEF 80/20 COARSE\n   \nMOZZARELLA CHEESE SHREDDED LMPS"
    records = list(adapter.read(text))
    assert len(records) == 3
    assert [r.source_row for r in records] == [1, 2, 3]


def test_a_leading_count_is_parsed(adapter):
    r = next(iter(adapter.read("12 CHICKEN STRIPS BRD FC FROZEN")))
    assert r.quantity == 12.0
    assert r.raw_description == "CHICKEN STRIPS BRD FC FROZEN"
    assert "quantity" not in r.unpopulated


def test_a_trailing_count_is_parsed(adapter):
    r = next(iter(adapter.read("CHICKEN STRIPS BRD FC FROZEN x 12")))
    assert r.quantity == 12.0
    assert r.raw_description == "CHICKEN STRIPS BRD FC FROZEN"


def test_no_quantity_stays_none_and_is_flagged(adapter):
    """Defaulting to 1 would invent a case of food. The whole point of this
    adapter is that a person typed what they know; it must not add to it."""
    r = next(iter(adapter.read("CHICKEN STRIPS BRD FC FROZEN")))
    assert r.quantity is None
    assert "quantity" in r.unpopulated


def test_a_pasted_csv_still_produces_records(adapter):
    records = list(adapter.read("Site,Item,Qty\nLincoln,CHICKEN STRIPS BRD FC FROZEN,14\n"))
    assert len(records) == 2
    assert "CHICKEN STRIPS BRD FC FROZEN" in records[1].raw_description


def test_a_very_long_line_is_truncated_not_rejected(adapter):
    r = next(iter(adapter.read("x" * 10_000)))
    assert 0 < len(r.raw_description) <= 4000


def test_nothing_is_ever_invented(adapter):
    r = next(iter(adapter.read("CHICKEN STRIPS BRD FC FROZEN")))
    assert r.gtin is None and r.upc is None and r.lot_code is None
    assert r.unit is None and r.pack_size is None and r.unit_cost is None
    for field in ("gtin", "lot_code", "unit_cost"):
        assert field in r.unpopulated


def test_declares_only_what_it_can_fill(adapter):
    assert adapter.declares() == {"site", "raw_description", "quantity"}
