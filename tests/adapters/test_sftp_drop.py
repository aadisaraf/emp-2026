"""The primary ingestion path. Two rules carry most of the weight: never drop a
row, and never invent a value."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pullsheet.adapters.base import AdapterRejection, NormalizedRecord
from pullsheet.adapters.sftp_drop import SftpDropAdapter

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"
ADAPTER_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def adapter():
    return SftpDropAdapter()


def _source_rows():
    with FIXTURE.open() as f:
        return list(csv.DictReader(f))


def test_every_source_row_becomes_a_record(adapter):
    records = list(adapter.read(FIXTURE))
    assert len(records) == len(_source_rows())
    assert all(isinstance(r, NormalizedRecord) for r in records)


def test_the_blank_quantity_row_survives_with_the_field_flagged(adapter):
    """FR-007. Defaulting it to 1 would invent a case of food that may not
    exist, and nobody downstream could tell."""
    records = [r for r in adapter.read(FIXTURE) if r.quantity is None]
    assert len(records) == 1
    record = records[0]
    assert record.raw_description == "CORN DOGS CHICKEN & PORK 4 OZ 72 CT"
    assert "quantity" in record.unpopulated


def test_lot_codes_pass_through_verbatim(adapter):
    """R3. Normalization is the matcher's job; an adapter that upper-cased a lot
    here would destroy the only string there is to compare against."""
    source = [r["Lot #"] for r in _source_rows() if r["Lot #"]]
    read = [r.lot_code for r in adapter.read(FIXTURE) if r.lot_code]
    assert read == source
    assert "4829-B" in read


def test_missing_barcodes_are_none_and_flagged_not_invented(adapter):
    records = list(adapter.read(FIXTURE))
    without = [r for r in records if r.gtin is None]
    assert len(without) >= 5
    assert all("gtin" in r.unpopulated for r in without)


def test_missing_unit_costs_are_flagged(adapter):
    records = list(adapter.read(FIXTURE))
    without = [r for r in records if r.unit_cost is None]
    assert len(without) >= 2
    assert all("unit_cost" in r.unpopulated for r in without)


def test_source_rows_are_numbered_from_one(adapter):
    records = list(adapter.read(FIXTURE))
    assert [r.source_row for r in records] == list(range(1, len(records) + 1))


def test_descriptions_are_never_rewritten(adapter):
    source = [r["Item Description"] for r in _source_rows()]
    assert [r.raw_description for r in adapter.read(FIXTURE)] == source


@pytest.mark.parametrize("name,expected_in_message", [
    ("empty.csv", "empty"),
    ("malformed.csv", "unterminated quote"),
])
def test_an_unusable_source_is_rejected_loudly(adapter, name, expected_in_message):
    with pytest.raises(AdapterRejection) as err:
        list(adapter.read(ADAPTER_FIXTURES / name))
    assert expected_in_message in str(err.value)
    assert err.value.filename == name


def test_a_missing_required_column_names_the_column(adapter, tmp_path):
    """Exactly one column is required: the one naming the food. Without it there
    is nothing to match, and the run is rejected naming what was absent."""
    path = tmp_path / "no_description.csv"
    path.write_text("Storage Location,Qty On Hand\nFreezer A,14\n")
    with pytest.raises(AdapterRejection) as err:
        list(adapter.read(path))
    assert "raw_description" in str(err.value)
    assert "Storage Location" in str(err.value), "the headers actually seen are not shown"


def test_a_building_column_is_ignored_rather_than_read_as_storage(adapter, tmp_path):
    """One deployment is one location, so a school-name column carries nothing.
    Letting it drift into storage_location would print a building on the sheet
    and send someone to the wrong place looking for a freezer."""
    path = tmp_path / "with_site.csv"
    path.write_text("Site,Storage Location,Item Description,Qty On Hand\n"
                    "Lincoln Elementary,Freezer A,CHICKEN STRIPS BRD FC FROZEN,14\n")
    record = list(adapter.read(path))[0]
    assert record.storage_location == "Freezer A"


@pytest.mark.parametrize("name", ["headers_primeroedge.csv", "headers_linq_titan.csv",
                                  "headers_mealsplus.csv"])
def test_every_vendor_layout_yields_the_same_internal_records(adapter, name):
    """SC-012: adding a source changes no behaviour downstream."""
    reference = list(adapter.read(ADAPTER_FIXTURES / "headers_primeroedge.csv"))
    got = list(adapter.read(ADAPTER_FIXTURES / name))
    assert [r.storage_location for r in got] == [r.storage_location for r in reference]
    assert [r.raw_description for r in got] == [r.raw_description for r in reference]
    assert [r.lot_code for r in got] == [r.lot_code for r in reference]
    assert [r.gtin for r in got] == [r.gtin for r in reference]


def test_xlsx_reads_the_same_as_csv(adapter, tmp_path):
    from openpyxl import Workbook

    rows = _source_rows()
    wb = Workbook()
    sheet = wb.active
    sheet.append(list(rows[0].keys()))
    for row in rows:
        sheet.append(list(row.values()))
    path = tmp_path / "inventory.xlsx"
    wb.save(path)

    from_xlsx = list(adapter.read(path))
    from_csv = list(adapter.read(FIXTURE))
    assert len(from_xlsx) == len(from_csv)
    assert [r.raw_description for r in from_xlsx] == [r.raw_description for r in from_csv]
    assert [r.lot_code for r in from_xlsx] == [r.lot_code for r in from_csv]


def test_declares_is_honest(adapter):
    from pullsheet.adapters.base import DECLARABLE
    assert adapter.declares() <= DECLARABLE
    records = list(adapter.read(FIXTURE))
    populated = {f for r in records for f in adapter.declares()
                 if getattr(r, f, None) is not None}
    assert populated == adapter.declares(), "a declared field is never populated"


def test_an_unsupported_file_type_is_rejected(adapter, tmp_path):
    path = tmp_path / "inventory.pdf"
    path.write_bytes(b"%PDF-1.4")
    with pytest.raises(AdapterRejection):
        list(adapter.read(path))
