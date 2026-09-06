# Phase 1 Data Model: PullSheet

**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md) | **Date**: 2026-09-05

Ten tables in `schema.sql`. The four safety-critical tables come first and fit one screen; the
run, corpus, and menu tables follow. No ORM — every query is hand-written SQL in the module that
owns it.

There were twelve. Amendment 3 removed the site roster and the monitor: `inventory_sources` and
`ingest_runs` collapsed into one `runs` table, and `monitor_runs` went with the alert queue it
existed to feed. A run either has new lines on it or it does not, and `matches.is_new` says which
— one column where there used to be a table and a foreign key.

Three structural rules run through the whole schema:

1. **Machine output and human action are separate tables.** `matches` is written only by the
   matcher; `decisions` is written only by a route that requires an actor name. Nothing in the
   matcher can produce a cleared item, because clearing is not a column it can write.
2. **Nothing is deleted.** No table has a delete path. Supersession, amendment, and clearing are
   all recorded as new rows or status columns, so a pull sheet can always be reconstructed as it
   stood at any point.
3. **A run is written once and frozen.** Counts and the corpus note are stamped at finalize, so
   opening last Tuesday's page prints last Tuesday's numbers against last Tuesday's corpus. A
   page that recomputed would put tonight's snapshot date above yesterday's lines — a document
   that looks sourced and is not.

---

## Safety-critical tables

### `inventory_records`

FR-002's fields, plus identity bookkeeping from FR-064. Twenty-one columns; there is no `site`.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `storage_location` | TEXT | Freezer / cooler / dry store / shelf label. **The cooler, not the building** — one deployment is one location |
| `raw_description` | TEXT NOT NULL | **Verbatim** from the source. Never rewritten |
| `normalized_description` | TEXT NOT NULL | Abbreviation-expanded, unit-stripped, token-sorted |
| `quantity` | REAL NOT NULL | |
| `unit` | TEXT | `case`, `lb`, `ea`, … |
| `pack_size` | TEXT | e.g. `6/5 lb` |
| `gtin` | TEXT | Digits only, or NULL. Carries UPCs too — a UPC is a GTIN with leading zeros, and two columns for one number is two places to look |
| `lot_code` | TEXT | **Verbatim** from the source (R3). Normalization happens in the matcher |
| `brand` | TEXT | The label on the case: `High Liner`, `Simplot` |
| `manufacturer` | TEXT | Who made it. Joins to `recall_records.recalling_firm` |
| `manufacturer_item_code` | TEXT | The maker's catalog number, quoted in recall notices |
| `vendor_name` | TEXT | The distributor: `Sysco`, `US Foods` |
| `vendor_item_code` | TEXT | SUPC and equivalents. Never a matching key — see below |
| `unit_cost` | REAL | NULL when the source does not carry it |
| `received_date` | TEXT | ISO date, or NULL |
| `run_id` | INTEGER FK → `runs.id` | The delivery this row arrived in |
| `unpopulated_fields` | TEXT NOT NULL | JSON array of field names the adapter could not fill (FR-003) |
| `identity_key` | TEXT NOT NULL | Computed; see below |
| `merged_from` | TEXT | JSON array of source row numbers when this record absorbed others (FR-065) |
| `superseded_by` | INTEGER FK → `inventory_records.id` | Set when a later export replaces this row. Nothing is deleted |

**`superseded_by IS NULL` is the active set, and it is what the matcher reads (FR-056).** Not one
run's rows. An item delivered on Monday and still in the freezer on Friday is re-matched into
Friday's run, so an item that drops out of one export does not drop off the sheet. Scoping the
sheet on which run an inventory row arrived in is the single most dangerous mistake available in
this schema, and it would look correct in every screenshot.

**The five supplier columns are the ordinary matching path, not a fallback (FR-069).** A kitchen's
item master is built around purchasing, so it always records who supplies a line — it has to, in
order to reorder it. Barcode and lot coverage is partial: 50 of the 56 rows in the committed
fixture carry no GTIN, and lot codes are captured only where someone scans at receiving.
`recalling_firm` meanwhile is populated on 100% of the openFDA corpus. Supplier is therefore the
channel most rows actually reach a recall through.

`vendor_item_code` is deliberately **not** a matching key. A distributor's SUPC never appears in
an FDA or FSIS notice, so it can join to nothing; it is carried because the distributor needs
their own code to process a credit (P3).

**Identity (FR-064)**: `identity_key = storage_location ‖ product_identity ‖ lot_code`.
`product_identity` is `gtin` when present, else `manufacturer#manufacturer_item_code`, else
`normalized_description` — strongest thing the row actually carries. Rows sharing an identity
within one ingest merge, quantities sum, and every contributing source row number is retained in
`merged_from`.

**Validation**: `quantity >= 0`, and NULL where the source said nothing — never defaulted to 1,
which would invent a case of food. `gtin` digits only. A row missing `raw_description` is
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
| `received_at` | TEXT NOT NULL | When this location first saw it — drives the deadline clock (FR-051). Never re-stamped on a refresh: a deadline does not reset (FR-053) |
| `reason_for_recall` | TEXT | |
| `status` | TEXT NOT NULL | `active` \| `terminated` \| `amended` |
| `prior_status` | TEXT | What it was before it changed (FR-016) |
| `status_changed_at` | TEXT | When the change was first seen |
| `amended_from` | INTEGER FK → `recall_records.id` | Prior state, retained (FR-016) |
| `raw_json` | TEXT NOT NULL | The complete source record |

### `matches`

One row per candidate. Written only by the matcher, never edited afterwards.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `run_id` | INTEGER FK NOT NULL → `runs.id` | **The only thing the sheet is scoped on** |
| `inventory_record_id` | INTEGER FK NOT NULL | |
| `recall_record_id` | INTEGER FK NOT NULL | |
| `tier` | TEXT NOT NULL | `CONFIRMED` \| `PROBABLE` \| `POSSIBLE` — CHECK-constrained |
| `status` | TEXT NOT NULL | `PULL` \| `HELD` — CHECK-constrained to exactly these two |
| `evidence_kind` | TEXT NOT NULL | `gtin` \| `upc` \| `mfr_item` \| `lot` \| `secondary_code` \| `firm_and_name` \| `name` |
| `trigger_inventory_text` | TEXT NOT NULL | Exact substring from the inventory side (FR-023) |
| `trigger_recall_text` | TEXT NOT NULL | Exact substring from the recall side |
| `score` | REAL | Populated for `POSSIBLE` only; ordering, never status |
| `lot_note` | TEXT | e.g. `lot unconfirmed — recall lot not tracked in inventory` (FR-027, FR-067) |
| `is_new` | INTEGER NOT NULL | 1 when this (item, recall) pair appears on no earlier run (FR-057). Computed at INSERT, because `matches` is never updated. Always 0 on the first run — there is no predecessor to be new against, and flagging a whole first sheet would bury the one line that matters on every run after it |
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
| `kind` | TEXT NOT NULL | `clear_match` \| `confirm_pulled`. Two human actions, two writers — audited by qualname in `tests/unit/test_clearing_audit.py` |
| `match_id` | INTEGER FK → `matches.id` | The line as it stood when the decision was taken |
| `subject_key` | TEXT NOT NULL | `identity_key ␟ recall_source ␟ source_record_id` — the FOOD and the RECALL, not the row |
| `actor` | TEXT NOT NULL | Name or initials, entered at the point of decision |
| `note` | TEXT | Free text reason, optional |
| `created_at` | TEXT NOT NULL | |

**Validation**: `actor` must be non-empty. Spec assumption — no accounts in this build, so the
actor is typed, not authenticated. That is enough for an auditable record and is what FR-022
requires.

**`subject_key` is why a clearing survives the night.** Every run creates new `matches` rows, so a
decision pointing only at `match_id` would expire at the next delivery and the same judgement
would have to be taken again every morning. Keyed on the food and the recall, it still applies to
tomorrow's line for the same pair. `match_id` is kept alongside it so the decision can still be
read against the exact line the person was looking at.

---

## The run table

### `runs`

One row per day's answer. This is the table `inventory_sources` and `ingest_runs` became.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `channel` | TEXT NOT NULL | `sftp_drop` \| `email_drop` \| `spreadsheet_upload` \| `rematch` — CHECK-constrained |
| `delivery_ref` | TEXT | `filename#sha256[:16]`. Name AND content, so the same file twice is one delivery (FR-072) and two different files with identical bytes are two |
| `column_map` | TEXT | JSON. The ANSWERS this location gave about ambiguous headers — never a whole mapping |
| `business_date` | TEXT | The day this run is the answer for |
| `started_at` / `finalized_at` | TEXT | |
| `status` | TEXT NOT NULL | `running` \| `ok` \| `rejected` — CHECK-constrained |
| `rejection_reason` | TEXT | CHECK: a rejected run without one is not a record (FR-006) |
| `corpus_note` | TEXT | The corpus this run was matched against, rendered at finalize. Frozen text, not a foreign key: a snapshot is taken per source and there are always two, so a single FK could only ever name one |
| `rows_read`, `rows_partial` | INTEGER | |
| `match_count`, `pull_count`, `held_count` | INTEGER | Frozen at finalize, for the same reason as `corpus_note` |

**`delivery_ref` is the duplicate guard.** The drop folder can hand back the same file after a
retry. Ingesting it again would make it the baseline tomorrow's new-since diff is measured
against, and that day would report nothing new while hiding the change.

**`column_map` stores answers, never a mapping.** Detection runs on every single file. Only
headers detection finds genuinely ambiguous — "Code", which half of kitchens mean as a lot and
half as a product code — are filled in from what this location already answered. Replaying a
whole remembered mapping onto a differently-shaped file silently drops the columns the new file
spells differently, and the sheet comes out short with nothing on screen to say so.

A `rematch` run has no delivery behind it: it is what `python -m pullsheet.match` produces when
the corpus changed and the inventory did not. It is named rather than disguised as an SFTP drop,
so the run history never claims a file arrived on a morning when none did.

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
- **`service_days`** — `id`, `date`, `recipe_id`, `planned_meals`. `planned_meals` is the sole
  input to the affected meal count (FR-039), and is presented as planned, never measured. The
  headline number counts each service day once however many recalled items land on it.

The menu tables are K-12-specific. `/impact` renders the money half always and the menu half only
where the location runs a meal program; a restaurant deployment simply never populates them.

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

**Location status** (`runs.py::run_status`, derived at read time — never stored). Exactly one
word, evaluated in this order, and the order is not arbitrary:

| Condition | Word |
|---|---|
| No successful run has ever finished | `no inventory has ever been received` |
| The latest good run is older than 30h | `no inventory received recently` |
| The newest delivery of any outcome was rejected | `the most recent delivery was rejected` |
| The latest run has PULL lines | `items to pull` |
| Snapshot in use older than 24h (FR-068) | `recall data is stale` |
| Otherwise | `no recalled items found` |

Absence outranks everything: a system reporting "clear" on data it never received is worse than
one reporting nothing at all. A stale corpus outranks "clear" for the same reason, and cannot
outrank "items to pull" — food in the building is a fact about the building, regardless of how old
the recall feed is.

Deriving rather than storing means the word cannot drift out of date with the underlying matches,
and the stale gate is applied at read time by construction. **What the gate touches is this
string and nothing else.** Not one line is suppressed, re-ranked, or altered (SC-013).

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
| FR-050 | `runs.py::run_status` — a run that never happened has its own word |
| FR-051 | `recall_records.received_at` |
| FR-056 | `inventory_records.superseded_by IS NULL` is what the matcher reads |
| FR-057 | `matches.is_new`, computed at INSERT from earlier runs' pairs |
| FR-058 | Every run is a `runs` row whatever its outcome, including rejections |
| FR-072 | `runs.delivery_ref` — name plus content hash |
| FR-064 / FR-065 | `identity_key`, `merged_from` |
| FR-069 | `inventory_records.brand`, `manufacturer`, `manufacturer_item_code`, `vendor_name`, `vendor_item_code` |
| FR-070 | `matching/screen.py` item index keyed `firm\|code`; `matching/gate.py` `_NEEDS_FIRM` |
| FR-071 | `matching/firm.py::agrees`, `matches.evidence_kind = 'firm_and_name'` |
| FR-068 | `recall_snapshots.captured_at` vs injected `now` |
