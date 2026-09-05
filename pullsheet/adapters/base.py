"""The single boundary between the outside world and the matcher.

``matching/`` imports nothing from here, and nothing here imports from
``matching/`` -- ``tests/unit/test_boundaries.py`` fails the build if that ever
stops being true. Adding a source means adding one file in this package and
changing nothing else (SC-012).

The six rules every adapter obeys are in
``specs/001-recall-pull-sheet/contracts/adapter-interface.md``. The two that
cost the most to get wrong:

* **Never drop a row.** A row that will not parse is still yielded, with the
  unreadable fields ``None`` and named in ``unpopulated``.
* **Never invent a value.** No defaulting a quantity to 1, no inferring a unit,
  no deriving a GTIN from a description. Absent means ``None``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Literal, NamedTuple

Provenance = Literal["live", "dated-snapshot", "hand-authored"]


class NormalizedRecord(NamedTuple):
    """One inventory row, as an adapter saw it.

    ``normalized_description`` and ``identity_key`` are deliberately NOT fields.
    They are computed downstream by ``matching/normalize.py``, so normalization
    has exactly one implementation and a new adapter cannot change matching
    behaviour by normalizing differently.
    """

    site: str
    storage_location: str | None
    raw_description: str          # verbatim from source, never rewritten
    quantity: float | None
    unit: str | None
    pack_size: str | None
    gtin: str | None              # digits only, or None
    upc: str | None               # digits only, or None
    lot_code: str | None          # VERBATIM. Adapters must not normalize it (R3)

    # Supplier identity (FR-069). Districts run on purchasing systems, so these
    # are present far more reliably than gtin or lot_code: an item master has to
    # know who supplies a line in order to reorder it.
    brand: str | None                    # the label on the case
    manufacturer: str | None             # who made it. Joins to recalling_firm
    manufacturer_item_code: str | None   # the maker's catalog number, quoted in recall notices
    vendor_name: str | None              # the distributor
    vendor_item_code: str | None         # SUPC and equivalents. Not a recall key; used for credit claims

    unit_cost: float | None
    received_date: str | None     # ISO 8601, or None
    source_row: int               # 1-based row number in the source
    unpopulated: frozenset[str]   # fields this adapter could not fill


class AdapterRejection(Exception):
    """The whole source is unusable.

    Raised instead of returning a partial read. A rejection is recorded in
    ``ingest_runs`` with the failing row or column named, and it leaves any
    existing pull sheet intact (FR-006, FR-009). Rejecting loudly is safer than
    ingesting half a file, because half a file looks exactly like a district
    with fewer items in it.
    """

    def __init__(self, filename: str, row_or_column: str | int | None, reason: str):
        self.filename = filename
        self.row_or_column = row_or_column
        self.reason = reason
        where = f" at {row_or_column}" if row_or_column is not None else ""
        super().__init__(f"{filename}{where}: {reason}")


class InventoryAdapter(ABC):
    """One source of inventory."""

    name: str
    provenance: Provenance

    @abstractmethod
    def declares(self) -> frozenset[str]:
        """Field names this adapter is capable of populating (FR-003).

        Rendered in the UI as this adapter's field-coverage map, so it must be
        honest: declaring a field this adapter cannot fill misrepresents the
        data to the person deciding what to pull.
        """

    @abstractmethod
    def read(self, source) -> Iterator[NormalizedRecord]:
        """Yield one record per source row. Never fewer."""


#: The field names an adapter may declare. Anything outside this set is a typo.
DECLARABLE: frozenset[str] = frozenset(NormalizedRecord._fields) - {"source_row", "unpopulated"}
