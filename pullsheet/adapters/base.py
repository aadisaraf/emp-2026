"""The single boundary between the outside world and the matcher.
changing nothing else (SC-012).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Literal, NamedTuple

Provenance = Literal["live", "dated-snapshot", "hand-authored"]


class NormalizedRecord(NamedTuple):
    """One inventory row, as an adapter saw it."""

    storage_location: str | None  # the cooler, not the building -- one deployment
                                  # is one location, so there is no site field
    raw_description: str          # verbatim from source, never rewritten
    quantity: float | None
    unit: str | None
    pack_size: str | None
    gtin: str | None              # digits only, or None
    lot_code: str | None          # VERBATIM. Adapters must not normalize it (R3)

    # Supplier identity (FR-069). Kitchens run on purchasing systems, so these
    # are present far more reliably than gtin or lot_code: an item master has to
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
    existing pull sheet intact (FR-006, FR-009). Rejecting loudly is safer than
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
    # How a delivery through this adapter arrives. Stored on every run, so the
    # history can say whether last Tuesday came in over SFTP or by mail.
    channel: str

    @abstractmethod
    def declares(self) -> frozenset[str]:
        """Field names this adapter is capable of populating (FR-003)."""

    @abstractmethod
    def read(self, source) -> Iterator[NormalizedRecord]:
        """Yield one record per source row. Never fewer."""


# The field names an adapter may declare. Anything outside this set is a typo.
DECLARABLE: frozenset[str] = frozenset(NormalizedRecord._fields) - {"source_row", "unpopulated"}
