"""The floor. One item per line, typed or pasted into a box.

**This adapter must never raise.** Every other path can fail: a folder can be
unmounted, an upload can be the wrong file, an email integration can quietly
stop. When all of that has failed at 6am with a recall notice on the screen, a
nutrition director can still type item names into a box and get a pull sheet.

So there is no such thing as input this adapter rejects. Any line becomes a
record: the whole line as ``raw_description``, a quantity only when one is
genuinely parseable, and everything else ``None`` and named in ``unpopulated``.
"""

from __future__ import annotations

import re
from typing import Iterator

from pullsheet.adapters.base import InventoryAdapter, NormalizedRecord

#: A leading or trailing count: "12 CHICKEN STRIPS BRD FC FROZEN", "CHICKEN STRIPS BRD FC FROZEN x 12",
#: "CHICKEN STRIPS BRD FC FROZEN, 12 cases". Anything less obvious is left alone -- inventing
#: a quantity is worse than not having one.
_LEADING = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:x\s*)?(?=\D)")
_TRAILING = re.compile(r"[\s,;]+(?:x\s*)?(\d+(?:\.\d+)?)\s*"
                       r"(cs|case|cases|ea|each|lb|lbs|bag|bags|box|boxes)?\s*$", re.I)

MAX_LINE = 4000


class PasteAdapter(InventoryAdapter):
    name = "paste"
    provenance = "live"

    def declares(self) -> frozenset[str]:
        """Honest and small. A typed line carries a description and sometimes a
        count. It does not carry a barcode, a lot, or a cost, and this adapter
        never pretends otherwise."""
        return frozenset({"site", "raw_description", "quantity"})

    def read(self, source, site: str = "Pasted inventory") -> Iterator[NormalizedRecord]:
        """Yield one record per non-empty line. Never raises, for any input."""
        try:
            text = source if isinstance(source, str) else str(source or "")
        except Exception:                      # noqa: BLE001
            text = ""

        source_row = 0
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue                        # a blank line is not an item
            source_row += 1
            yield self._record(line[:MAX_LINE], site, source_row)

    @staticmethod
    def _record(line: str, site: str, source_row: int) -> NormalizedRecord:
        quantity = None
        description = line

        match = _LEADING.match(line)
        if match:
            quantity = float(match.group(1))
            description = line[match.end():].strip() or line
        else:
            match = _TRAILING.search(line)
            if match:
                quantity = float(match.group(1))
                description = line[:match.start()].strip() or line

        unpopulated = {"storage_location", "unit", "pack_size", "gtin", "upc",
                       "lot_code", "brand", "manufacturer", "manufacturer_item_code",
                       "vendor_name", "vendor_item_code", "unit_cost", "received_date"}
        if quantity is None:
            unpopulated.add("quantity")

        return NormalizedRecord(
            site=site,
            storage_location=None,
            # The whole line is kept as the description even when a quantity was
            # split off it, so nothing a person typed is ever lost.
            raw_description=description or line,
            quantity=quantity,
            unit=None, pack_size=None, gtin=None, upc=None, lot_code=None,
            brand=None, manufacturer=None, manufacturer_item_code=None,
            vendor_name=None, vendor_item_code=None,
            unit_cost=None, received_date=None,
            source_row=source_row,
            unpopulated=frozenset(unpopulated),
        )
