"""Tolerant header detection."""

from __future__ import annotations

import re
from typing import Iterable

# internal field -> header spellings seen in the wild
ALIASES: dict[str, set[str]] = {
    "storage_location": {"storage location", "storage", "location", "where",
                         "storage area", "area", "room"},
    "raw_description": {"item description", "product description", "description",
                        "item", "product", "item name", "product name", "food item"},
    "quantity": {"qty on hand", "quantity on hand", "on hand", "qty", "quantity",
                 "count", "cases on hand", "inventory"},
    "unit": {"uom", "unit", "units", "u m", "unit of measure", "uom code"},
    "pack_size": {"pack size", "pack", "size", "case pack", "packsize"},
    "gtin": {"case upc", "gtin", "gtin 14", "gtin14", "item upc", "upc", "barcode",
             "case gtin", "upc code", "case code"},
    "lot_code": {"lot", "lot code", "lot no", "lot number", "batch", "batch no",
                 "batch number", "lot batch"},
    # Supplier identity (FR-069). Purchasing is what an item master is FOR, so
    # these columns are present in real exports far more reliably than gtin
    "brand": {"brand", "brand name", "label", "mfr brand", "manufacturer brand"},
    "manufacturer": {"manufacturer", "mfr", "mfr name", "manufacturer name",
                     "maker", "producer", "packer", "processor"},
    "manufacturer_item_code": {"manufacturer product code", "mfr item", "mfr item no",
                               "mfr item number", "manufacturer item code", "mfr code",
                               "mfr no", "manufacturer code", "mfr product code",
                               "item code", "product code", "manufacturer item"},
    "vendor_name": {"vendor", "vendor name", "supplier", "supplier name",
                    "distributor", "distributor name", "prime vendor"},
    "vendor_item_code": {"vendor item", "vendor item no", "vendor item number",
                         "supc", "vendor product code", "distributor product code",
                         "vendor code", "supplier item", "supplier code",
                         "distributor item", "vendor item code"},
    # "$/unit" and "$ per case" are common. The dollar sign is the signal, so
    # canonical() turns it into the word `cost` rather than stripping it -- which
    "unit_cost": {"unit cost", "cost per unit", "unit price", "price", "cost",
                  "per unit", "cost unit", "cost per case", "cost case",
                  "case cost", "case price", "extended cost", "value"},
    "received_date": {"received date", "date received", "rcv date", "date in",
                      "receipt date", "delivered", "delivery date"},
}

# Headers that name the BUILDING, deliberately recognised and then ignored.
#
IGNORED: frozenset[str] = frozenset({
    "site", "school", "building", "bldg", "location name", "site name",
    "facility", "campus", "site id", "school name",
})

# Headers that genuinely could be two things. We ask; we do not guess.
# "Code" is the common one -- half the operators mean the lot code by it and
AMBIGUOUS: dict[str, tuple[str, ...]] = {
    "code": ("lot_code", "gtin"),
    "number": ("lot_code", "gtin"),
    "no": ("lot_code", "gtin"),
    # Bare "item" is the description in PrimeroEdge and the catalog number in
    # some LINQ exports. Guessing wrong puts a number where a name belongs.
    "item no": ("manufacturer_item_code", "vendor_item_code"),
    "item number": ("manufacturer_item_code", "vendor_item_code"),
}

_PUNCT = re.compile(r"[^a-z0-9]+")


def canonical(header: str | None) -> str:
    """Lowercase, punctuation-stripped, whitespace-collapsed."""
    if not header:
        return ""
    return _PUNCT.sub(" ", header.lower().replace("$", " cost ")).strip()


_REVERSE: dict[str, str] = {}
for _field, _spellings in ALIASES.items():
    for _spelling in _spellings:
        _REVERSE[canonical(_spelling)] = _field


def detect(headers: Iterable[str]) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """Map source headers to internal fields."""
    mapping: dict[str, str] = {}
    ambiguous: dict[str, tuple[str, ...]] = {}
    taken: set[str] = set()

    for header in headers:
        key = canonical(header)
        if not key:
            continue
        if key in IGNORED:
            # Recognised, and deliberately not mapped. See IGNORED.
            continue
        if key in AMBIGUOUS:
            ambiguous[header] = AMBIGUOUS[key]
            continue
        field = _REVERSE.get(key)
        if field and field not in taken:
            mapping[header] = field
            taken.add(field)

    # An ambiguous header whose candidates are ALL already confidently mapped
    # from other columns is no longer a question worth asking.
    for header in list(ambiguous):
        if all(f in taken for f in ambiguous[header]):
            del ambiguous[header]

    return mapping, ambiguous


def required_missing(mapping: dict[str, str]) -> set[str]:
    """Fields without which a row cannot be matched at all."""
    return {"raw_description"} - set(mapping.values())


def apply(mapping: dict[str, str], row: dict[str, str]) -> dict[str, str | None]:
    """Rewrite one source row into internal field names."""
    out: dict[str, str | None] = {field: None for field in ALIASES}
    extra: dict[str, str] = {}
    for header, value in row.items():
        field = mapping.get(header)
        if field:
            out[field] = value
        elif header:
            extra[header] = value
    out["_extra"] = extra or None
    return out
