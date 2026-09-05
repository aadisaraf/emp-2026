"""The adapter interface is frozen at this point in the build; every adapter
after it is written against these shapes. A change here is a change to every
adapter at once, so it should be hard to make by accident."""

from __future__ import annotations

import inspect

import pytest

from pullsheet.adapters.base import (
    DECLARABLE,
    AdapterRejection,
    InventoryAdapter,
    NormalizedRecord,
)

CONTRACT_FIELDS = (
    "site", "storage_location", "raw_description", "quantity", "unit", "pack_size",
    "gtin", "upc", "lot_code",
    # Supplier identity (FR-069). Ordered next to the other identifiers because
    # that is what they are: for most district rows they are the ONLY identifiers,
    # since barcode and lot coverage in item masters is partial.
    "brand", "manufacturer", "manufacturer_item_code", "vendor_name", "vendor_item_code",
    "unit_cost", "received_date", "source_row", "unpopulated",
)


def test_field_names_match_the_contract_exactly():
    assert NormalizedRecord._fields == CONTRACT_FIELDS


def test_eighteen_fields():
    assert len(NormalizedRecord._fields) == 18


def test_normalized_description_is_not_an_adapter_output():
    """Normalization has one implementation, in matching/normalize.py. An adapter
    that could supply its own would be able to change matching behaviour."""
    assert "normalized_description" not in NormalizedRecord._fields
    assert "identity_key" not in NormalizedRecord._fields


def test_the_abc_cannot_be_instantiated():
    with pytest.raises(TypeError):
        InventoryAdapter()


def test_a_subclass_missing_a_method_cannot_be_instantiated():
    class Incomplete(InventoryAdapter):
        name = "incomplete"
        provenance = "live"

        def declares(self):
            return frozenset()

    with pytest.raises(TypeError):
        Incomplete()


def test_declares_and_read_are_abstract():
    assert InventoryAdapter.declares.__isabstractmethod__
    assert InventoryAdapter.read.__isabstractmethod__


def test_rejection_names_the_file_and_the_place():
    err = AdapterRejection("malformed.csv", 2, "unterminated quote")
    assert err.filename == "malformed.csv"
    assert err.row_or_column == 2
    assert "malformed.csv" in str(err) and "2" in str(err) and "unterminated quote" in str(err)


def test_declarable_excludes_bookkeeping_fields():
    assert "source_row" not in DECLARABLE
    assert "unpopulated" not in DECLARABLE
    assert "lot_code" in DECLARABLE and "gtin" in DECLARABLE
    for field in ("brand", "manufacturer", "manufacturer_item_code",
                  "vendor_name", "vendor_item_code"):
        assert field in DECLARABLE


def test_base_does_not_import_from_matching():
    """SC-012: the boundary is one-directional."""
    assert "pullsheet.matching" not in inspect.getsource(
        __import__("pullsheet.adapters.base", fromlist=["base"])
    )
