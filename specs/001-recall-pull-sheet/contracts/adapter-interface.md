# Contract: `InventoryAdapter`

**Plan**: [../plan.md](../plan.md) | Satisfies FR-002, FR-003, FR-005, FR-008

The single boundary between the outside world and the matcher. The matcher imports nothing from
`adapters/`, and no adapter imports anything from `matching/`. Adding a source means adding a file
here and nothing else (SC-012).

## Interface

```python
# adapters/base.py
class NormalizedRecord(NamedTuple):
    site: str
    storage_location: str | None
    raw_description: str          # verbatim from source, never rewritten
    quantity: float
    unit: str | None
    pack_size: str | None
    gtin: str | None              # digits only, or None
    upc: str | None               # digits only, or None
    lot_code: str | None          # VERBATIM. Adapters must not normalize it.

    # Supplier identity (FR-069). Present far more reliably than gtin or
    # lot_code: an item master has to know who supplies a line to reorder it.
    brand: str | None
    manufacturer: str | None             # joins to recall_records.recalling_firm
    manufacturer_item_code: str | None   # quoted in recall notices as "Item Number: ..."
    vendor_name: str | None
    vendor_item_code: str | None         # SUPC. Not a matching key; used for credit claims

    unit_cost: float | None
    received_date: str | None     # ISO 8601, or None
    source_row: int               # 1-based row number in the source
    unpopulated: frozenset[str]   # fields this adapter could not fill


class InventoryAdapter(ABC):
    name: str
    provenance: Literal["live", "dated-snapshot", "hand-authored"]

    @abstractmethod
    def declares(self) -> frozenset[str]:
        """Field names this adapter is capable of populating (FR-003)."""

    @abstractmethod
    def read(self, source) -> Iterator[NormalizedRecord]:
        """Yield one record per source row. See rules below."""
```

`normalized_description` and `identity_key` are **not** adapter outputs. They are computed
downstream by `matching/normalize.py`, so that normalization has exactly one implementation and a
new adapter cannot change matching behavior.

## Rules every adapter must obey

1. **Never drop a row.** A row that cannot be fully parsed is still yielded, with unreadable
   fields set to `None` and named in `unpopulated`. (FR-007)
2. **Never invent a value.** No defaulting a missing quantity to 1, no inferring a unit, no
   deriving a GTIN from a description. Absent means `None` plus an entry in `unpopulated`.
   (FR-003)
3. **Pass `lot_code` and the supplier names through verbatim.** Case, punctuation, and whitespace
   exactly as the source wrote them. Normalization is the matcher's job — `firm.agrees()` is the
   single implementation, so an adapter cannot change what matches by tidying a company name
   differently. (R3, FR-066, FR-069)
4. **`raw_description` is never rewritten.** It is what the pull sheet shows the operator, and it
   must match what they see in their own system.
5. **Reject loudly, not partially.** If the whole source is unusable, raise
   `AdapterRejection(filename, row_or_column, reason)`. A rejection is recorded in `ingest_runs`
   and leaves any existing pull sheet intact. (FR-006)
6. **`declares()` must be honest.** It is rendered in the UI as the adapter's field-coverage map.

## The four adapters

| Adapter | Source | Provenance | Notes |
|---|---|---|---|
| `WatchedFolderAdapter` | Directory poll, CSV/XLSX | `live` | Primary path and demo centerpiece. Polls on an interval, ingests new files, moves processed files to `data/archive/`. Archive-after-success only; a rejected file stays put so it is visible. |
| `SpreadsheetUploadAdapter` | Browser upload | `live` | Runs column detection; prompts once for ambiguous headers, then stores the mapping on `inventory_sources.column_map`. |
| `EmailDropAdapter` | Local mailbox file | `hand-authored` if stubbed | May be stubbed against a fixture mailbox. If stubbed, the UI label stays `hand-authored` — Principle V forbids presenting a stub as working. |
| `PasteAdapter` | Textarea, one item per line | `live` | **The floor. Must never raise.** Any line becomes a record: whole line as `raw_description`, quantity 1 if none is parseable, everything else `None` and in `unpopulated`. |

## Column detection

`adapters/column_map.py` holds one dict of header aliases per internal field — the only place in
the codebase that knows what PrimeroEdge, LINQ/Titan, and Meals Plus call their columns.

```
gtin            ← "gtin", "gtin-14", "case upc", "upc", "item upc", "barcode"
lot_code        ← "lot", "lot #", "lot code", "batch", "batch #"
quantity        ← "qty", "quantity", "on hand", "qty on hand", "count"
raw_desc        ← "item", "item name", "description", "product", "product description"
site            ← "site", "school", "location", "building"
brand           ← "brand", "brand name", "label", "mfr brand"
manufacturer    ← "manufacturer", "mfr", "mfr name", "maker", "producer", "packer"
mfr_item_code   ← "manufacturer product code", "mfr item #", "mfr code", "item code"
vendor_name     ← "vendor", "supplier", "distributor", "prime vendor"
vendor_item_code← "supc", "vendor item #", "distributor product code", "supplier code"
...
```

`tests/adapters/fixtures/` carries the same three rows in four vocabularies, and a test asserts
all four resolve to the identical set of internal fields — including the five supplier fields,
which every real district export carries because purchasing is what an item master is for.

Matching is case-insensitive on punctuation-stripped headers. When a required field has no
confident header match, the UI asks once and remembers the answer for that source. When a header
is unrecognized but not required, its column is retained in the source row record and ignored.

## Adding a fifth adapter

Write the class, add its fixture to `tests/adapters/fixtures/`, register it. No change to
`matching/`, `artifacts/`, or `rollup/`. That zero-diff property is SC-012 and is asserted by a
test that imports `matching` and fails if it can reach `adapters`.
