# Phase 1 Data Model: PullSheet

**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md) | **Date**: 2026-09-05

Twelve tables in `schema.sql`. The four safety-critical tables come first and fit one screen; the
ingestion, menu, and monitor tables follow. No ORM — every query is hand-written SQL in the module
that owns it.

Two structural rules run through the whole schema:

1. **Machine output and human action are separate tables.** `matches` is written only by the
   matcher; `decisions` is written only by a route that requires an actor name. Nothing in the
   matcher can produce a cleared item, because clearing is not a column it can write.
2. **Nothing is deleted.** No table has a delete path. Supersession, amendment, and clearing are
   all recorded as new rows or status columns, so a pull sheet can always be reconstructed as it
   stood at any point.

---

## Safety-critical tables

### `inventory_records`

FR-002's fourteen fields, plus identity bookkeeping from FR-064.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `site` | TEXT NOT NULL | From the export (spec assumption: no separate site registry) |
| `storage_location` | TEXT | Freezer / cooler / dry store / shelf label |
| `raw_description` | TEXT NOT NULL | **Verbatim** from the source. Never rewritten |
| `normalized_description` | TEXT NOT NULL | Abbreviation-expanded, unit-stripped, token-sorted |
| `quantity` | REAL NOT NULL | |
| `unit` | TEXT | `case`, `lb`, `ea`, … |
| `pack_size` | TEXT | e.g. `6/5 lb` |
| `gtin` | TEXT | Digits only, or NULL |
| `upc` | TEXT | Digits only, or NULL |
| `lot_code` | TEXT | **Verbatim** from the source (R3). Normalization happens in the matcher |
| `brand` | TEXT | The label on the case: `High Liner`, `Simplot` |
| `manufacturer` | TEXT | Who made it. Joins to `recall_records.recalling_firm` |
| `manufacturer_item_code` | TEXT | The maker's catalog number, quoted in recall notices |
| `vendor_name` | TEXT | The distributor: `Sysco`, `US Foods` |
| `vendor_item_code` | TEXT | SUPC and equivalents. Never a matching key — see below |
| `unit_cost` | REAL | NULL when the source does not carry it |
| `received_date` | TEXT | ISO date, or NULL |
| `source_export_id` | INTEGER FK → `ingest_runs.id` | |
| `unpopulated_fields` | TEXT NOT NULL | JSON array of field names the adapter could not fill (FR-003) |
| `identity_key` | TEXT NOT NULL | Computed; see below |
| `merged_from` | TEXT | JSON array of source row numbers when this record absorbed others (FR-065) |
| `superseded_by` | INTEGER FK → `inventory_records.id` | Set when a later export replaces this row |

**The five supplier columns are the ordinary matching path, not a fallback (FR-069).** A district
item master is built around purchasing, so it always records who supplies a line — it has to, in
order to reorder it. Barcode and lot coverage is partial: 50 of the 56 rows in the committed
fixture carry no GTIN, and lot codes are captured only where someone scans at receiving.
`recalling_firm` meanwhile is populated on 100% of the openFDA corpus. Supplier is therefore the
channel most rows actually reach a recall through.

`vendor_item_code` is deliberately **not** a matching key. A distributor's SUPC never appears in
an FDA or FSIS notice, so it can join to nothing; it is carried because the distributor needs
their own code to process a credit (P3).

**Identity (FR-064)**: `identity_key = site ‖ storage_location ‖ product_identity ‖ lot_code`.
`product_identity` is `gtin` when present, else `manufacturer#manufacturer_item_code`, else
`normalized_description` — strongest thing the row actually carries. Rows sharing an identity
within one ingest merge, quantities sum, and every contributing source row number is retained in
`merged_from`.

**Validation**: `quantity >= 0`. `gtin`/`upc` digits only. A row missing `raw_description` is
still stored, with `raw_description = ''` and the field listed in `unpopulated_fields` — FR-007
forbids dropping unparseable rows.

### `recall_records`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `source` | TEXT NOT NULL | `openfda` \| `fsis` |
| `source_record_id` | TEXT NOT NULL | The agency's own id, for verbatim display (FR-015) |
| `snapshot_id` | INTEGER FK → `recall_snapshots.id` | |
| `recalling_firm` | TEXT | |
| `product_description` | TEXT NOT NULL | |
| `normalized_description` | TEXT NOT NULL | |
| `code_info` | TEXT | Raw free text, retained verbatim |
| `parsed_codes` | TEXT NOT NULL | JSON: `{gtins:[], upcs:[], lots:[], date_codes:[], unparsed:bool}` |
| `classification` | TEXT | `Class I` \| `Class II` \| `Class III` \| NULL |
| `class_rank` | INTEGER NOT NULL | 1/2/3; **NULL classification sorts as 1** (spec assumption) |
| `report_date` | TEXT | Agency publication date |
| `received_at` | TEXT NOT NULL | When this district first saw it — drives the deadline clock (FR-051) |
| `reason_for_recall` | TEXT | |
| `status` | TEXT NOT NULL | `active` \| `terminated` \| `amended` |
| `amended_from` | INTEGER FK → `recall_records.id` | Prior state, retained (FR-016) |
| `raw_json` | TEXT NOT NULL | The complete source record |

### `matches`

One row per candidate. Written only by the matcher, never edited afterwards.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `inventory_record_id` | INTEGER FK NOT NULL | |
| `recall_record_id` | INTEGER FK NOT NULL | |
| `tier` | TEXT NOT NULL | `CONFIRMED` \| `PROBABLE` \| `POSSIBLE` — CHECK-constrained |
| `status` | TEXT NOT NULL | `PULL` \| `HELD` — CHECK-constrained to exactly these two |
| `evidence_kind` | TEXT NOT NULL | `gtin` \| `upc` \| `mfr_item` \| `lot` \| `secondary_code` \| `firm_and_name` \| `name` |
| `trigger_inventory_text` | TEXT NOT NULL | Exact substring from the inventory side (FR-023) |
| `trigger_recall_text` | TEXT NOT NULL | Exact substring from the recall side |
| `score` | REAL | Populated for `POSSIBLE` only; ordering, never status |
| `lot_note` | TEXT | e.g. `lot unconfirmed — recall lot not tracked in inventory` (FR-027, FR-067) |
| `first_seen_run_id` | INTEGER FK → `monitor_runs.id` | NULL for the initial ingest; set when a monitor diff surfaces it (FR-057) |
| `created_at` | TEXT NOT NULL | |

**The status column has no third value.** There is no `CLEARED`. A cleared line is a match that
has a `decisions` row pointing at it — which means clearing is always a join away from an actor
and a timestamp, and can never be an absence of data.

**Deterministic ordering** (FR-032): `ORDER BY class_rank, tier_rank, score DESC NULLS LAST, id`,
where `tier_rank` is CONFIRMED=1, PROBABLE=2, POSSIBLE=3. The trailing `id` guarantees a total
order, so two runs cannot differ on ties (SC-011).

### `decisions`

Every human action in the system, in one auditable table.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `kind` | TEXT NOT NULL | `clear_match` \| `confirm_site_pulled` \| `acknowledge_alert` |
| `target_type` | TEXT NOT NULL | `match` \| `site` |
| `target_id` | TEXT NOT NULL | |
| `actor` | TEXT NOT NULL | Name or initials, entered at the point of decision |
| `note` | TEXT | Free text reason, optional |
| `created_at` | TEXT NOT NULL | |

**Validation**: `actor` must be non-empty. Spec assumption — no accounts in this build, so the
actor is typed, not authenticated. That is enough for an auditable record and is what FR-022
requires.

---

## Ingestion tables

### `inventory_sources`

| Column | Notes |
|---|---|
| `id` | INTEGER PK |
| `name` | Human label, e.g. `Lincoln Elementary — watched folder` |
| `adapter` | `watched_folder` \| `spreadsheet_upload` \| `email_drop` \| `paste` |
| `column_map` | JSON, the remembered header mapping for this source |
| `provenance` | `live` \| `dated-snapshot` \| `hand-authored` |

The remembered `column_map` is what makes "ask the user once" work: detection runs first, and only
ambiguous columns prompt. The answer is stored here and reused for that source.

### `ingest_runs`

`id`, `source_id`, `filename`, `arrived_at`, `row_count`, `rows_parsed`, `rows_partial`,
`status` (`ok` | `rejected`), `rejection_reason`, `adapter`. FR-006 and FR-009: a rejection is
recorded with the failing row or column named, and it never replaces a prior good sheet.

### `recall_snapshots`

`id`, `source` (`openfda` | `fsis`), `captured_at`, `record_count`, `provenance`, `file_path`,
`fetch_status` (`live` | `cached_fallback` | `committed`). `captured_at` is the timestamp the
freshness window measures from (R0-5).

---

## Menu tables (P2)

All hand-authored and labeled as such.

- **`recipes`** — `id`, `name`, `provenance`.
- **`recipe_ingredients`** — `recipe_id`, `ingredient_name`, `normalized_name`. Joined to
  inventory by the same normalization the matcher uses, so a recalled item traverses to recipes
  through one code path rather than two.
- **`recipe_components`** — `recipe_id`, `component` (`grain` | `meat_or_alternate` | `fruit` |
  `vegetable` | `milk`). Set containment against this table is how FR-041's "no substitute exists"
  is proven rather than asserted.
- **`service_days`** — `id`, `date`, `site`, `recipe_id`, `planned_meals`. `planned_meals` is the
  sole input to the affected meal count (FR-039), and is presented as planned, never measured.

---

## Monitor table (P5)

**`monitor_runs`** — `id`, `ran_at`, `snapshot_id`, `records_evaluated`, `new_records`,
`new_matches`, `zero_hit` (BOOLEAN). FR-058 requires a zero-hit run to be recorded as a run, so
`zero_hit` is stored rather than inferred from an absence of rows.

Alerts are not a separate table. An alert *is* a match carrying a `first_seen_run_id`, and it is
acknowledged by a `decisions` row of kind `acknowledge_alert`. One less table, one less place for
state to disagree with itself.

---

## State transitions

**Match status** — set once by `gate.decide()`, never mutated:

```
   gtin / upc / mfr_item ────── CONFIRMED ─┐
                                           ├──→ PULL
   lot / secondary_code / firm_and_name ── PROBABLE ─┘

   name ───────────────────── POSSIBLE ──→ HELD ──(decisions row, actor required)──→ cleared
```

Two rungs depend on a second condition and fall to POSSIBLE without it: a lot-based kind whose
codes are not equal (FR-066), and a supplier-based kind whose firm does not actually agree
(FR-070). Demotion moves a line from PULL to HELD. It never removes one.

`cleared` is not a status value. It is the existence of a `decisions` row. There is no arrow back
into the matcher, and no arrow that any automatic process can take.

**Site status** (`rollup/status.py`, derived — never stored):

| Condition | Status |
|---|---|
| No successful ingest run for the site | `unconfirmed` |
| Snapshot in use older than 24h (FR-068) | `unconfirmed (stale recall data)` |
| Successful ingest, zero matches, fresh snapshot | `clear` |
| Any match rows for the site | `holding` |
| `holding` plus a `confirm_site_pulled` decision | `holding — pull confirmed by {actor}` |

Deriving rather than storing site status means it cannot drift out of date with the underlying
matches, and the stale gate is applied at read time by construction.

---

## Requirements traceability

| Requirement | Where it lives |
|---|---|
| FR-002 / FR-003 | `inventory_records` columns, `unpopulated_fields` |
| FR-007 | Unparseable rows stored, flagged, never dropped |
| FR-015 / FR-016 | `recall_records.raw_json`, `status`, `amended_from` |
| FR-018 / FR-019 | `matches.status` CHECK — two values only; `tier` CHECK |
| FR-022 | `decisions` table, non-empty `actor` |
| FR-023 | `trigger_inventory_text`, `trigger_recall_text` |
| FR-027 / FR-067 | `matches.lot_note` |
| FR-032 | Deterministic ORDER BY with trailing `id` |
| FR-039 | `service_days.planned_meals` |
| FR-046 / FR-047 | `inventory_records.unit_cost` nullable; claim excludes NULLs and says so |
| FR-051 | `recall_records.received_at` |
| FR-058 | `monitor_runs.zero_hit` |
| FR-064 / FR-065 | `identity_key`, `merged_from` |
| FR-069 | `inventory_records.brand`, `manufacturer`, `manufacturer_item_code`, `vendor_name`, `vendor_item_code` |
| FR-070 | `matching/screen.py` item index keyed `firm\|code`; `matching/gate.py` `_NEEDS_FIRM` |
| FR-071 | `matching/firm.py::agrees`, `matches.evidence_kind = 'firm_and_name'` |
| FR-068 | `recall_snapshots.captured_at` vs injected `now` |
