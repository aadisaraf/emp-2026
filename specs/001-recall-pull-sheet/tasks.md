---
description: "Task list for PullSheet — food-recall response for K-12 nutrition departments"
---

# Tasks: PullSheet — Food-Recall Response for K-12 Nutrition Departments

**Input**: Design documents from `/specs/001-recall-pull-sheet/`

**Parallel build**: [parallel-plan.md](./parallel-plan.md) — branch and file-ownership plan for building these tasks concurrently.

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Test tasks are included and are **not optional here**. The constitution requires
test-first for the deterministic core (Development Workflow), and SC-003 is only provable by a
test. Where a task says "write the test first", the test must be seen to fail before the
implementation task begins.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: `[US1]`…`[US5]`, mapping to the priority-ordered stories in spec.md
- **⚠️**: Task is estimated **over ~45 minutes**. A suggested split follows on the next line.
- **Verify**: every task states the command to run and the observable result that means "done"

## Path conventions

Single Python package at repository root: `pullsheet/` for source, `tests/` for tests,
`data/` for fixtures and runtime folders, `scripts/` for operator scripts. Paths follow the
source tree in [plan.md](./plan.md#source-code-repository-root).

---

## Phase 1: Setup

**Purpose**: The skeleton, so every later task has somewhere to put its file.

- [X] T001 Create the package skeleton — every directory and `__init__.py` from the plan's source tree under `pullsheet/` (`adapters/`, `recalls/`, `recalls/snapshots/`, `matching/`, `menu/`, `artifacts/`, `rollup/`, `templates/`, `static/`), plus `tests/unit/`, `tests/adapters/`, `tests/integration/`, and `data/{fixtures,watched,archive}` with `.gitkeep` files. **Verify**: `python -c "import pullsheet, pullsheet.adapters, pullsheet.recalls, pullsheet.matching, pullsheet.menu, pullsheet.artifacts, pullsheet.rollup"` → exits 0 with no output.
- [X] T002 [P] Write `requirements.txt` pinning exactly seven dependencies: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `httpx`, `openpyxl`, `pytest`. **Verify**: `pip install -r requirements.txt && python -c "import fastapi, uvicorn, jinja2, multipart, httpx, openpyxl, pytest"` → exits 0. An eighth dependency appearing later needs a Complexity Tracking row in plan.md first.
- [X] T003 [P] Write `pytest.ini` with `testpaths = tests` and `-q` default in `addopts`. **Verify**: `pytest --collect-only` → exits 5 ("no tests ran") with zero import errors.
- [X] T004 [P] Write `tests/conftest.py` with shared fixtures: `tmp_db` (fresh SQLite from `schema.sql`), `fixed_now` (a frozen `datetime` for injection), and `fixture_path(name)`. **Verify**: `pytest --fixtures | grep -c 'tmp_db\|fixed_now\|fixture_path'` → 3.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data first, then the shapes everything else is written against.

**⚠️ CRITICAL**: No matcher work begins until T005–T012 exist. The whole point of fixtures-first
is that no later task is ever blocked on the network, and that the matcher is written against
data whose right answers are already known.

### Fixtures and snapshots (nothing is blocked on the network after this)

- [X] T005 Capture the openFDA snapshot to `pullsheet/recalls/snapshots/openfda-2026-09-05.json` via `curl -s 'https://api.fda.gov/food/enforcement.json?limit=1000' -o <path>` and commit it. **This is the only step in the entire build that requires the network.** Record the capture timestamp in a sibling `openfda-2026-09-05.meta.json` (`{source, captured_at, record_count, provenance: "dated-snapshot"}`). **Verify**: `python -c "import json;print(len(json.load(open('pullsheet/recalls/snapshots/openfda-2026-09-05.json'))['results']))"` → ≥ 500, and `git status --short` shows both files staged.
- [X] T006 [P] Hand-transcribe the FSIS meat/poultry snapshot into `pullsheet/recalls/snapshots/fsis-2026-09-05.json`, matching openFDA's field names so one loader handles both, with a `.meta.json` marked `provenance: "hand-authored"` and a `transcription_note`. FSIS returns 403 to server-side requests (verified 2026-09-05), so this cannot be fetched **or verified against published notices** — the records are authored in FSIS notice format and must carry the `hand-authored` label everywhere. Calling them a dated snapshot would claim a capture that never happened, which is exactly what Principle V forbids. **Verify**: `python -c "import json;d=json.load(open('pullsheet/recalls/snapshots/fsis-2026-09-05.json'));print(len(d['results']), all(r['source']=='fsis' for r in d['results']))"` → ≥ 10 and `True`. ⚠️ **Over 45 min** — transcription is slow and detail-critical.
  - *Split*: T006a transcribe 5 records and lock the field shape; T006b transcribe the remaining records against that shape (parallelizable across two people once the shape is fixed).
- [X] T007 Author `data/fixtures/inventory_lincoln.csv` — the ~50-line hand-authored district inventory. Must contain: ≥ 3 sites; deliberately abbreviated descriptions (`chkn strips froz`, `grnd bf 80/20`, `mozz shred lm`); ≥ 5 rows with no GTIN (produce and USDA commodity foods); ≥ 2 rows with no unit cost; the same product at two sites with different lots; lot codes in mismatched formats (`4829-B` where the recall says `LOT 4829B`); one row with a blank quantity; PrimeroEdge-style headers. **Verify**: `python -c "import csv;r=list(csv.DictReader(open('data/fixtures/inventory_lincoln.csv')));print(len(r), len({x['Site'] for x in r}))"` → ≥ 50 rows, ≥ 3 sites. ⚠️ **Over 45 min** — this is authored data whose correctness the whole demo rests on.
  - *Split*: T007a author the header row and 17 rows for site 1, fixing the CSV shape; T007b and T007c author sites 2 and 3 in parallel against that shape.
- [X] T008 Author `data/fixtures/expected_matches.json` — the seeded correspondence map, and the oracle for SC-005. One entry per inventory row that must reach a recall: `{source_row, recall_source_record_id, expected_evidence_kind, expected_tier}`. Cover all five evidence kinds and both lot outcomes (equal, contained). **Verify**: `python scripts/check_fixtures.py --seeds` → `True` and ≥ 12. (Seeds must resolve against **both** snapshots, not openFDA alone: the corpus spans two agencies and the seed set exercises both.)
- [X] T009 [P] Author the menu fixtures in `data/fixtures/`: `recipes.csv`, `recipe_ingredients.csv`, `recipe_components.csv` (`grain`/`meat_or_alternate`/`fruit`/`vegetable`/`milk`), `service_days.csv` (`date, site, recipe_id, planned_meals`), transcribed from a real published district menu and labeled `hand-authored`. At least one recipe must use a seeded recalled ingredient, and at least one broken recipe must have **no** viable substitute in stock so FR-041 is demonstrable rather than theoretical. **Verify**: `python scripts/check_fixtures.py --menu` → prints ≥ 1 recipe reachable from `expected_matches.json` and ≥ 1 recipe with an unsatisfiable component.
- [X] T010 [P] Author `data/fixtures/unit_costs.csv` — hand-authored plausible per-unit costs keyed to inventory rows, deliberately **absent** for ≥ 2 items so FR-047's quantity-only path is exercised. **Verify**: `python -c "import csv;r=list(csv.DictReader(open('data/fixtures/unit_costs.csv')));print(sum(1 for x in r if not x['unit_cost'].strip()))"` → ≥ 2.
- [X] T011 [P] Author four header-layout fixtures in `tests/adapters/fixtures/`: `headers_primeroedge.csv`, `headers_linq_titan.csv`, `headers_mealsplus.csv`, `headers_adhoc.csv` — same five inventory rows, four different column vocabularies, one deliberately ambiguous header that detection cannot resolve. Also `malformed.csv` (broken quoting) and `empty.csv`. **Verify**: `ls tests/adapters/fixtures/ | wc -l` → 6, and each of the four loads under `csv.DictReader` with a different header tuple.
- [X] T012 Write `pullsheet/provenance.py` (one dict: source key → `live` | `dated-snapshot` | `hand-authored`, plus `label_for(key)`), the committed table `data/PROVENANCE.md` listing every source with its label, capture date, file path, and how to regenerate it, and `tests/unit/test_provenance.py` asserting the two agree and that every path named in the table exists on disk. **Verify**: `pytest tests/unit/test_provenance.py -v` → passes; deleting a snapshot file or adding a source to `provenance.py` without a table row makes it fail.

### Schema and shared shapes

- [X] T013 Write the four safety-critical tables at the **top** of `pullsheet/schema.sql`: `inventory_records`, `recall_records`, `matches`, `decisions`, exactly per [data-model.md](./data-model.md). `matches.status` is `CHECK(status IN ('PULL','HELD'))` and `matches.tier` is `CHECK(tier IN ('CONFIRMED','PROBABLE','POSSIBLE'))`; `decisions.actor` is `CHECK(length(trim(actor)) > 0)`. **Verify**: `sqlite3 :memory: < pullsheet/schema.sql` exits 0, and `sqlite3 :memory: ".read pullsheet/schema.sql" "insert into matches(...,status) values(...,'CLEARED')"` → `CHECK constraint failed`. That failure is the schema enforcing Principle I.
- [X] T014 Append the remaining eight tables to `pullsheet/schema.sql`: `inventory_sources`, `ingest_runs`, `recall_snapshots`, `recipes`, `recipe_ingredients`, `recipe_components`, `service_days`, `monitor_runs`. No table gets a delete path. **Verify**: `sqlite3 /tmp/t.db ".read pullsheet/schema.sql" ".tables"` → exactly 12 table names.
- [X] T015 Write `pullsheet/db.py` — `connect()` with `sqlite3.Row`, `--reset` (delete and recreate `data/pullsheet.db` from `schema.sql`), and `--load-fixtures` loading inventory, unit costs, and menu fixtures. Recall snapshot loading is added later by T030 — leave a named `TODO(T030)` rather than a stub that silently loads nothing. **Verify**: `python -m pullsheet.db --reset && python -m pullsheet.db --load-fixtures && sqlite3 data/pullsheet.db "select count(*) from inventory_records"` → ≥ 50.
- [X] T016 [P] ~~Write `pullsheet/matching/abbreviations.py` — the hand-authored kitchen abbreviation dictionary.~~ **SUPERSEDED 2026-09-05.** Written, then removed. Both sides of the comparison are catalog strings from the same industry, not freehand text, so nothing needed recovering from `chkn`; every entry was a place a wrong guess could change what matched. Replaced by `pullsheet/matching/firm.py` — supplier identity, which is what district rows actually carry (FR-069). **Verify**: `python -c "from pullsheet.matching.firm import agrees;print(agrees('Simplot','JR Simplot Company'), agrees('Sun World','World Food LLC.'))"` → `True False`.
- [X] T017 Write `pullsheet/matching/normalize.py` — `normalize(text) -> str` and `tokens(text) -> frozenset[str]`: lowercase, strip pack sizes and units (`6/5 lb`, `#10 can`, `oz`), drop punctuation, split. **Words are compared as written** — no expansion, no spelling correction (amended 2026-09-05, see T016). This is the single normalization implementation; the menu cascade joins through it too, so a recalled item reaches recipes by the same code path it reaches inventory. Write `tests/unit/test_normalize.py` alongside. **Verify**: `pytest tests/unit/test_normalize.py -v` → `tokens("CHICKEN STRIPS BRD FC FROZEN 2/5 LB") & tokens("Frozen Chicken Strips, breaded")` == `{chicken, strips, frozen}`.
- [X] T018 Write `pullsheet/adapters/base.py` — the `NormalizedRecord` NamedTuple (13 fields), the `InventoryAdapter` ABC with `name`, `provenance`, `declares()`, `read()`, and the `AdapterRejection(filename, row_or_column, reason)` exception, exactly per [contracts/adapter-interface.md](./contracts/adapter-interface.md). Plus `tests/unit/test_adapter_contract.py` asserting the field names match the contract and the ABC cannot be instantiated. **Verify**: `pytest tests/unit/test_adapter_contract.py -v` → passes. **This task fixes the adapter interface; every adapter task after it is parallelizable.**
- [X] T019 Write `tests/unit/test_boundaries.py` — walks the AST of every module under `pullsheet/matching/` and fails if any of them imports from `pullsheet.adapters`; a second test asserts `lot_code` reaches the matcher byte-identical to the source string. **Verify**: `pytest tests/unit/test_boundaries.py -v` → passes now, and adding `from pullsheet.adapters import ...` to any matching module makes it fail.

**Checkpoint**: fixtures exist with known right answers, the schema refuses to represent a cleared match, normalization has one implementation, and the adapter interface is frozen. Adapters are now parallelizable.

---

## Phase 3: User Story 1 — Automatic recall detection from an inventory export (Priority: P1) 🎯 MVP

**Goal**: An export lands in a watched folder with nobody touching anything, and a printable pull
sheet appears — grouped by site, most serious class first, uncertain matches HELD and visible.

**Independent Test**: With the network disconnected, drop `data/fixtures/inventory_lincoln.csv`
into `data/watched/`. A complete pull sheet appears with no further human action, and every line
traces to a specific recall record and a specific triggering field value.

**If the build stops here, this is a complete product.** Everything after this phase decorates it.

### The Fail-Safe Hold gate — tests first (constitutional requirement)

> Write T021 and T022 **before** T023. They must be seen to fail. A gate implemented before its
> tests cannot be said to have been driven by them, and Principle I is the one place in this
> codebase where that distinction is worth the ceremony.

- [X] T020 [US1] Declare the value types with no logic: `Evidence` in `pullsheet/matching/tiers.py`, and `Decision` + `decide()` raising `NotImplementedError` in `pullsheet/matching/gate.py`. `Decision.status` is typed `Literal["PULL", "HELD"]` — there is no third value, so an auto-cleared item is unrepresentable rather than merely forbidden. **Verify**: `pytest tests/unit/test_gate.py --collect-only` → collects without `ImportError`.
- [X] T021 [US1] Write the ladder and widening tests in `tests/unit/test_gate.py` — one test per ladder row (3) and one per widening rule (7) from [contracts/hold-gate.md](./contracts/hold-gate.md), plus the determinism test (same triple, 100 calls, identical Decision). **Verify**: `pytest tests/unit/test_gate.py -v` → 11 tests collected, **all fail** with `NotImplementedError`.
- [X] T022 [US1] Write `tests/unit/test_gate.py::test_no_input_can_auto_clear` — **the explicit auto-clear assertion (SC-003)**. Two parts: (a) a property sweep over generated `(inv, rec, evidence)` triples — including every combination of null, empty-string, malformed, and contradictory fields — asserting `decide(...).status in {"PULL", "HELD"}` for every one, with zero inputs producing anything else and zero inputs raising; (b) a score sweep on name-only evidence from 0.0 to 1.0 in 0.01 steps asserting `HELD` at all 101 values, which is what makes "there is no pull threshold" a testable claim rather than a slogan. **Verify**: `pytest tests/unit/test_gate.py -k auto_clear -v` → **fails now**; passes after T023 and never again fails.
- [X] T023 [US1] Implement `decide()` in `pullsheet/matching/gate.py` — the three-row ladder and the seven widening rules. No clock, no config, no database handle, no I/O. Carries the Principle I justification comment naming FR-018 and this test. **Verify**: `pytest tests/unit/test_gate.py -v` → all 12 pass, including the 101-value score sweep.

### The matcher

- [X] T024 [P] [US1] Implement `pullsheet/matching/similarity.py` — Dice coefficient on normalized token sets, `2·|A∩B| / (|A|+|B|)`, written by hand, plus `tests/unit/test_similarity.py`. **Verify**: `pytest tests/unit/test_similarity.py -v` → `dice(tokens("chkn strips froz"), tokens("Frozen Chicken Strips, breaded")) == 0.857` to three decimals, `dice(A, A) == 1.0`, `dice(A, ∅) == 0.0`.
- [X] T025 [P] [US1] Implement `pullsheet/matching/lot.py` — `normalize_lot()` (uppercase, strip non-alphanumerics, collapse whitespace) and `compare(a, b) -> Literal["equal","contained","none","unparseable"]`, plus `tests/unit/test_lot.py`. **Verify**: `pytest tests/unit/test_lot.py -v` → `LOT 4829B` vs `4829-B` → `equal`; `4829B` vs `4829` → `contained`; `4829B` vs `4830B` → `none`; a date range like `BEST BY 03/12–04/02` → `unparseable`. This is SC-015.
- [X] T026 [P] [US1] Implement `pullsheet/recalls/parse.py` — the documented regex table extracting GTINs, UPCs, lot codes, and date codes from openFDA's free-text `code_info`, returning `{gtins, upcs, lots, date_codes, unparsed: bool}`. Every pattern carries a comment with an example string it matches. **Verify**: `pytest tests/unit/test_parse.py -v` → extracts correctly from ≥ 10 real `code_info` strings pulled from the committed snapshot, and an unparseable string yields empty lists with `unparsed: True` rather than raising.
- [X] T027 [US1] Write the hand-authored stoplist and `build_indexes()` in `pullsheet/matching/screen.py` — two in-memory inverted indexes: a code index (GTIN keyed by its right-most 11 digits so packaging-indicator and check-digit variants collide, plus UPCs and lots) and a token index over significant tokens. **Verify**: `pytest tests/unit/test_screen.py::test_indexes -v` → a GTIN-14 and its UPC-12 form land under the same code key; stoplisted words (`frozen`, `case`, `fresh`) are absent from the token index.
- [X] T028 [US1] Implement `generate_candidates()` in `pullsheet/matching/screen.py` — union of code-index and token-index hits. **This is the one narrowing operation in the system**; it carries the Principle I justification comment naming FR-020 and its covering test, and its rule is rendered verbatim in the UI later (T045). Stoplisted tokens still count in *scoring* — they are excluded only from *candidate generation*, and the comment must say so. **Verify**: `pytest tests/unit/test_screen.py -v` → every pair in `expected_matches.json` survives screening (a seeded pair screened out is a build-stopping failure), and a pair sharing neither a significant token nor a code fragment is not generated.
- [X] T029 [US1] Implement `build_evidence()` in `pullsheet/matching/tiers.py` — inspect a candidate pair and return `Evidence` naming the kind (`gtin`/`upc`/`lot`/`secondary_code`/`name`) and the exact triggering substring **from both sides**. **Verify**: `pytest tests/unit/test_tiers.py -v` → each of the five kinds is produced from a fixture pair, and both trigger substrings appear verbatim in their source strings (`assert trigger in source`).
- [X] T030 [US1] Load the recall snapshots: implement `pullsheet/recalls/corpus.py::load_snapshots()` writing `recall_snapshots` and `recall_records` rows, including `parsed_codes` from T026, `class_rank` (with NULL classification sorting as 1), and `received_at`. Wire it into `db.py --load-fixtures`, replacing the `TODO(T030)` marker. **Verify**: `python -m pullsheet.db --reset && python -m pullsheet.db --load-fixtures && sqlite3 data/pullsheet.db "select source, count(*) from recall_records group by 1"` → both `openfda` and `fsis` present, ≥ 500 total.
- [X] T031 [US1] Implement `corpus.py::active_records()` (filters to loaded snapshots — the third and last justified clearing path, with its comment) and `snapshot_age_hours(now)` / `is_stale(now)` measured from `captured_at` against the 24-hour window, with `now` injected and never read from the clock. **Verify**: `pytest tests/unit/test_freshness.py::test_age -v` → 30 hours after capture reports stale, 23 hours reports fresh, and both return the same lines either way.
- [X] T032 [US1] Implement `pullsheet/matching/run.py` — the orchestration: for each inventory record, `generate_candidates` → `build_evidence` → `decide` → insert `matches`, ordered `class_rank, tier_rank, score DESC NULLS LAST, id`. (This module is an addition to the plan's source tree; it exists so that `gate.py` stays pure and orchestration is not smuggled into it.) **Verify**: `python -m pullsheet.match --all && sqlite3 data/pullsheet.db "select tier, status, count(*) from matches group by 1,2"` → only `CONFIRMED|PULL`, `PROBABLE|PULL`, `POSSIBLE|HELD` appear. Any other combination is a gate bypass.

### Ingestion — the watched folder (demo centerpiece)

> T033–T037 come before the upload and paste adapters deliberately: the watched folder is the
> story the demo tells. All adapter tasks are marked `[P]` because the interface froze at T018 —
> the ordering here is demo priority, not a dependency.

- [X] T033 [P] [US1] Implement `pullsheet/adapters/column_map.py` — one alias dict per internal field and `detect(headers) -> (mapping, ambiguous)`, case-insensitive on punctuation-stripped headers. The only file in the codebase that knows what PrimeroEdge, LINQ/Titan, and Meals Plus call their columns. **Verify**: `pytest tests/adapters/test_column_map.py -v` → all four T011 header fixtures map to identical internal fields, and the deliberately ambiguous header is returned in `ambiguous` rather than guessed.
- [X] T034 [P] [US1] Implement `pullsheet/adapters/watched_folder.py::read()` — CSV and XLSX (via `openpyxl`) through `column_map`, yielding `NormalizedRecord`. Never drops a row, never invents a value, passes `lot_code` verbatim. **Verify**: `pytest tests/adapters/test_watched_folder.py -v` → the 50-row fixture yields exactly 50 records; the blank-quantity row yields a record with `quantity` unset and `"quantity"` in `unpopulated`, not a dropped row.
- [X] T035 [US1] Implement the poll loop and archive-on-success in `watched_folder.py`, plus `pullsheet/main.py` starting it alongside uvicorn in one process. A rejected file **stays put** so it remains visible. **Verify**: start the app, `cp data/fixtures/inventory_lincoln.csv data/watched/` → within one poll interval the file is in `data/archive/`, and `sqlite3 data/pullsheet.db "select status, row_count from ingest_runs"` → one `ok` row with 50.
- [X] T036 [US1] Implement ingest persistence in `db.py`/`watched_folder.py` — write `ingest_runs` (origin, arrival, row count, parsed, partial, status, rejection reason) and insert `inventory_records` with `unpopulated_fields` and `normalized_description` computed by T017. **Verify**: `pytest tests/integration/test_ingest.py -v` → row counts in `ingest_runs` equal rows in `inventory_records` for that run, and every partially-parsed row is present with a non-empty `unpopulated_fields`.
- [X] T037 [US1] Implement identity merge and supersession — `identity_key` from `(site, storage_location, product_identity, lot_code)` where `product_identity` is `gtin` or else `normalized_description`; matching identities merge with summed quantities and every contributing source row retained in `merged_from`; a later export for a site sets `superseded_by` on the earlier rows without destroying them, and preserves existing `decisions`. **Verify**: `pytest tests/integration/test_ingest_merge.py -v` → two same-identity rows become one record with summed quantity and both source rows in `merged_from` (SC-014); re-ingesting supersedes rather than duplicating, and a prior `clear_match` decision still resolves.
- [X] T038 [US1] Implement rejection handling (FR-006) — a malformed, empty, or unmapped-column export raises `AdapterRejection`, is recorded in `ingest_runs` with the failing file and row or column named, leaves any existing pull sheet intact, and returns HTTP 200 with a visible panel rather than a 4xx a folder poller would swallow. **Verify**: `cp tests/adapters/fixtures/malformed.csv data/watched/` → `/` shows a rejection panel naming file, column, and reason; `/sheet` is unchanged; the file is still in `data/watched/`.

### The pull sheet

- [X] T039 [US1] Write `pullsheet/app.py` — the FastAPI skeleton, `GET /` placeholder, and `GET /api/status` returning `{sheet_generated_at, pull_count, held_count, sites, corpus:{source, provenance, captured_at, age_hours, stale}, last_ingest}`. **Verify**: `curl -s localhost:8000/api/status | python -m json.tool` → all six top-level keys present, `corpus.captured_at` matching the committed snapshot meta.
- [X] T040 [US1] Write `pullsheet/templates/base.html` and `pullsheet/static/app.css`, including the **provenance-label Jinja macro** — one macro, used everywhere a source is displayed, on screen and in print. Provenance labels are load-bearing UI under Principle V and may not be styled into invisibility. **Verify**: `curl -s localhost:8000/ | grep -c 'data-provenance'` → ≥ 1, and the macro is the only place the three label strings appear in `templates/`.
- [X] T041 [US1] Implement `pullsheet/artifacts/pull_sheet.py` — the query and grouping: by site, ordered `class_rank, tier_rank, score DESC NULLS LAST, id`, returning PULL and HELD interleaved in that single order (HELD is never a separate section and never behind a toggle). **Verify**: `pytest tests/unit/test_pull_sheet_order.py -v` → for a fixture with mixed classes and tiers, the returned order matches the expected sequence exactly, and no HELD row is absent.
- [X] T042 [US1] Write `templates/sheet.html` and wire `GET /sheet` and `GET /sheet/{site}` — item description (verbatim `raw_description`), quantity with unit, storage location, lot, tier badge, status, recall class, and the triggering value. HELD rows visually distinct. Header carries district, site, generation timestamp, corpus source, provenance label, and capture date. Zero matches still renders the sheet stating zero lines matched and against which corpus and date. **Verify**: open `/sheet` → sections per site, Class I first, HELD rows distinct at a glance; `sqlite3 data/pullsheet.db "delete from matches"` then reload → the sheet still renders with the zero-line statement. ⚠️ **Over 45 min** — this is the demo's primary screen.
  - *Split*: T042a the table markup and grouping loop; T042b the header block, tier badges, and HELD styling.
- [X] T043 [US1] Write `pullsheet/static/print.css` and link it — every column survives standard Letter portrait, provenance labels and the capture date print, site sections break cleanly. **Verify**: print-preview `/sheet/lincoln` → all columns visible, nothing clipped at the right margin, provenance label present on the printed page (SC-008, FR-035).
- [X] T044 [US1] Implement `GET /match/{id}` — both source records rendered verbatim with the triggering substrings highlighted on each side, the tier, the evidence kind, and any `lot_note`. **Verify**: click any line on `/sheet` → both records render in full and the highlighted substring on each side is the value stored in `trigger_inventory_text` / `trigger_recall_text` (SC-002).
- [X] T045 [US1] Render the screening rule verbatim on `/sheet` (a footer line stating what a pair must share to become a candidate at all) and the `code_info` parser coverage count from T026. Both answer the hostile question "what does your system throw away?" before it is asked. **Verify**: `curl -s localhost:8000/sheet | grep -c 'shares no significant name token'` → 1, and the coverage count matches `select count(*) from recall_records where json_extract(parsed_codes,'$.unparsed')`.
- [X] T046 [US1] Implement `POST /match/{id}/clear` — requires a non-empty actor, writes a `decisions` row, **never deletes the match**. Cleared lines remain on the sheet rendered as cleared-by-actor-at-timestamp. Carries the second Principle I justification comment. **Verify**: `curl -si -X POST -d 'actor=' localhost:8000/match/1/clear` → 400; with `actor=AS` → 200, `select count(*) from matches` unchanged, and the line still visible on `/sheet` marked cleared.

### The manual floor

- [X] T047 [P] [US1] Implement `pullsheet/adapters/paste.py` and `POST /ingest/paste` — the floor. Any line becomes a record: whole line as `raw_description`, quantity 1 only if one is genuinely parseable, everything else `None` and in `unpopulated`. **Must never raise.** **Verify**: `pytest tests/adapters/test_paste.py -v` → empty string, a single blank line, 10,000 characters on one line, emoji, and a whole CSV pasted by mistake all produce records or an empty result; nothing raises.
- [X] T048 [P] [US1] Implement `pullsheet/adapters/spreadsheet_upload.py`, `GET /ingest`, and `POST /ingest/upload` — browser upload running `column_map.detect()`. **Verify**: upload `headers_linq_titan.csv` → records land with the same internal fields as the PrimeroEdge fixture produced (SC-012).
- [X] T049 [US1] Implement the column-mapping step — when `detect()` returns ambiguous fields, prompt once, then store the answer on `inventory_sources.column_map` and reuse it silently for that source. **Verify**: upload `headers_adhoc.csv` → mapping prompt appears for the ambiguous header only; submit it; upload the same file again → no prompt, and `select column_map from inventory_sources` shows the stored mapping.

### Proving User Story 1

- [X] T050 [US1] Write `tests/integration/test_seeded_correspondences.py` (SC-005) — every seeded correspondence in `expected_matches.json` appears on the sheet as PULL or HELD. A seeded pair that is **absent** is a failure; a seeded pair appearing as HELD rather than PULL is not. **Verify**: `pytest tests/integration/test_seeded_correspondences.py -v` → all seeded pairs present with the expected evidence kind.
- [X] T051 [US1] Write `tests/unit/test_determinism.py` (SC-011) — ingest the same fixture into two fresh databases and diff the match rows on tier, status, score, and order. **Verify**: `pytest tests/unit/test_determinism.py -v` → the diff is empty.
- [X] T052 [US1] Write `tests/unit/test_clearing_audit.py` (SC-003) — walk the AST of the whole `pullsheet/` package, find every function that filters, removes, or excludes a record, and assert there are **exactly three**: `screen.generate_candidates`, `app.clear_match`, `corpus.active_records` — each carrying a justification comment naming a requirement id and a test. **Verify**: `pytest tests/unit/test_clearing_audit.py -v` → passes and prints the three paths; adding a fourth filtering function without a comment fails the build.
- [X] T053 [US1] Write `scripts/demo_reset.sh` — the between-rehearsals reset: stop nothing, drop and recreate `data/pullsheet.db`, reload fixtures and snapshots, empty `data/watched/` and `data/archive/`, leave the app running and the browser refreshable. Idempotent. **Verify**: `./scripts/demo_reset.sh && curl -s localhost:8000/api/status | python -c "import json,sys;d=json.load(sys.stdin);print(d['pull_count'], d['held_count'])"` → `0 0`; `ls data/watched data/archive` → both empty; running it twice in a row produces identical output.
- [X] T054 [US1] **Network-off rehearsal (SC-004, FR-060).** Physically disconnect the network, run `./scripts/demo_reset.sh`, start the app, and `cp data/fixtures/inventory_lincoln.csv data/watched/`. **Verify**: the full pull sheet appears with no human interaction; the header names the cached snapshot with its capture date and age; the server log contains zero exceptions and zero outbound connection attempts (`sudo lsof -i -a -p $(pgrep -f uvicorn)` → empty). Do this at least once before the demo — the constitution's Delivery Constraints require it, and the freshness banner is intended behavior to narrate, not a defect to apologize for.

**Checkpoint**: 🎯 **MVP complete.** A watched folder, a matcher nobody can auto-clear, a printable
pull sheet, a manual floor, and a rehearsed offline demo. Stop here and you have a product.

---

## Phase 4: User Story 2 — Menu-break cascade and substitution (Priority: P2)

**Goal**: Which planned meals just became impossible, on which dates, for how many meals — and
what to serve instead, or a plain statement that nothing works.

**Independent Test**: With a pull sheet already produced, each recalled item resolves to the
recipes using it, those recipes resolve to dated service days with planned meal counts, and a
substitution is either proposed with its satisfied components named, or plainly declined with the
unmet component named.

**Depends on**: Phase 3 (needs match results). Nothing depends on this phase.

- [X] T055 [US2] Load the menu fixtures into `recipes`, `recipe_ingredients`, `recipe_components`, and `service_days` in `db.py --load-fixtures`, normalizing `ingredient_name` through T017 so recipes are reached by the same code path as inventory. **Verify**: `sqlite3 data/pullsheet.db "select count(*) from recipes, recipe_ingredients, recipe_components, service_days"` → all four non-zero, and `select count(*) from recipe_ingredients where normalized_name = ''` → 0.
- [X] T056 [US2] Implement `pullsheet/menu/cascade.py` — recalled item → recipes using it → scheduled service dates and sites → planned meal count summed from `service_days.planned_meals`. The count is **planned**, never measured, and carries a `hand-authored` provenance label. **Verify**: `pytest tests/unit/test_cascade.py -v` → a seeded recalled ingredient reaches the expected recipe set and the expected date/site/count rows, with the count equal to the hand-summed fixture value.
- [X] T057 [US2] Implement `pullsheet/menu/substitute.py` — set containment over `recipe_components`. A substitute is proposed only when the candidate's component set contains the broken recipe's required set; otherwise the function returns the **named unmet component**. "No substitute exists" is a proof, not a failure to find one. **Verify**: `pytest tests/unit/test_substitute.py -v` → the satisfiable recipe gets a proposal naming which components it covers; the deliberately unsatisfiable one from T009 returns a named unmet component and **no** approximate proposal.
- [X] T058 [US2] Implement `GET /menu` and `templates/menu.html` — broken items, affected dates, planned counts, proposals or declines, and the revised menu as a printable artifact under `print.css`. **Verify**: open `/menu` → each broken item lists its recipes, dates, sites, and planned counts labeled as planned; print-preview produces a clean revised menu (FR-042).
- [X] T059 [US2] Write `tests/integration/test_menu_cascade.py` covering US2 acceptance scenarios 1–5. **Verify**: `pytest tests/integration/test_menu_cascade.py -v` → 5 tests pass.

**Checkpoint**: US1 and US2 both demoable; US1 still works unchanged.

---

## Phase 5: User Story 3 — Compliance artifacts (Priority: P3)

**Goal**: The paperwork generates itself — hold record, state report, credit claim.

**Independent Test**: From an existing pull sheet, generate all three artifacts; each is complete,
itemized, printable, and traceable to the pull-sheet lines behind it.

**Depends on**: Phase 3.

- [ ] T060 [US3] Implement `pullsheet/artifacts/hold_record.py` and `GET /artifacts/hold/{site}` — per-site listing of every held item with quantity, lot, and location, signature and date fields left **blank for a human**. **Verify**: print-preview `/artifacts/hold/lincoln` → every HELD and PULL line for that site is listed, signature and date fields are empty, provenance labels present.
- [ ] T061 [US3] Implement `pullsheet/artifacts/credit_claim.py` and `GET /artifacts/credit-claim` — itemized quantity and extended value per line, district total, computed as plain `quantity × unit_cost` arithmetic. Lines with no unit cost appear **quantity-only**, and the claim states that the total excludes them. No price is ever estimated. **Verify**: `pytest tests/unit/test_credit_claim.py -v` → the total equals the hand-computed value for the costed lines; the two costless fixture items appear with quantity only and are named in the exclusion statement (FR-047).
- [ ] T062 [US3] Implement `pullsheet/artifacts/state_report.py` and `GET /artifacts/state-report` — every derivable field pre-filled, every non-derivable field visibly marked as requiring human entry rather than guessed (FR-045). Modelled on the USDA FNS district report and labeled `hand-authored`, per the spec's Open Questions interim default for FR-044. **Verify**: open `/artifacts/state-report` → derived fields populated from the database, undeliverable fields rendered with the "requires human entry" marker, zero fields silently blank. ⚠️ **Over 45 min** — form-shaped work with many fields.
  - *Split*: T062a the derived-field query and data assembly; T062b the form template and the unfillable-field marker treatment.
- [ ] T063 [US3] Apply the provenance macro to all four artifacts and write `tests/integration/test_artifacts.py` covering US3 acceptance scenarios 1–5. **Verify**: `pytest tests/integration/test_artifacts.py -v` → 5 pass, including an assertion that every artifact response contains a provenance label for each source it drew on (FR-048).

**Checkpoint**: US1–US3 demoable independently.

---

## Phase 6: User Story 4 — District roll-up and deadline clock (Priority: P4)

**Goal**: The whole district on one screen, with the USDA clock running.

**Independent Test**: With pull sheets across several sites, per-site status is correct, countdowns
advance against the recorded receipt time, and marking one site confirmed changes only that site.

**Depends on**: Phase 3. Uses T031's freshness function.

- [ ] T064 [US4] Implement `pullsheet/rollup/status.py` — each site derives exactly one of `clear` / `holding` / `unconfirmed`. **A site shows `clear` only when an export for it was successfully processed, it has zero lines, and the snapshot in use is inside the 24-hour window.** Site status is derived on read, never stored. **Verify**: `pytest tests/unit/test_rollup_status.py -v` → a site with lines is `holding`; a site with no processed export is `unconfirmed` with the reason named; a clean site inside the window is `clear`.
- [ ] T065 [US4] Implement `pullsheet/rollup/deadlines.py` — 24-hour distributor-notification and 48-hour inventory-assessment countdowns computed from `recall_records.received_at` against an injected `now`. An elapsed deadline shows the **overrun explicitly** rather than disappearing or resetting. **Verify**: `pytest tests/unit/test_deadlines.py -v` → at `now = received_at + 25h` the 24h clock reads `+1h overrun` and the 48h clock reads `23h remaining`.
- [ ] T066 [US4] Implement the roll-up on `GET /` with `templates/rollup.html` and `static/poll.js` — the site status board, both countdowns, the corpus provenance banner, and a 2-second poll against `/api/status`. **This is the only JavaScript in the project.** **Verify**: open `/` → every site shows exactly one status; drop a file into `data/watched/` without touching the browser → counts update within ~2 seconds.
- [ ] T067 [US4] Implement `POST /site/{site}/confirm` — records a `confirm_site_pulled` decision with actor and timestamp, changing only that site's status. **Verify**: `curl -X POST -d 'actor=AS' localhost:8000/site/lincoln/confirm` → 200; `/` shows lincoln confirmed and every other site unchanged; `select * from decisions where kind='confirm_site_pulled'` → one row with a non-empty actor.
- [ ] T068 [US4] Complete `tests/unit/test_freshness.py` (SC-013) — inject a `now` 30 hours after capture and assert **zero sites report clear**, sites read `unconfirmed (stale recall data)` with the capture date and age shown, and PULL/HELD lines are produced **unchanged**. A run that suppresses lines is a failure: staleness gates one word in the roll-up, not the matcher. **Verify**: `pytest tests/unit/test_freshness.py -v` → all pass, including the assertion that match counts are identical stale versus fresh.

**Checkpoint**: US1–US4 demoable independently.

---

## Phase 7: User Story 5 — Standing monitor (Priority: P5)

**Goal**: Nobody has to remember to check.

**Independent Test**: Store an inventory, introduce a new recall record into the corpus, run the
scheduled diff, and confirm an alert is raised naming exactly the affected sites.

**Depends on**: Phase 3.

- [ ] T069 [US5] Implement `pullsheet/monitor.py` — on a schedule, diff the corpus, evaluate **only** records not previously seen, run them through the existing matcher, and stamp new matches with `first_seen_run_id`. Write a `monitor_runs` row every time, including `zero_hit` when nothing new matched (FR-058 — a quiet run is still a run). **Verify**: `pytest tests/unit/test_monitor.py -v` → a run over an unchanged corpus evaluates 0 new records and writes a `zero_hit` row; injecting one new matching record produces exactly one new match with `first_seen_run_id` set.
- [ ] T070 [US5] Render alerts on `/` — an alert *is* a match carrying a `first_seen_run_id`; there is no alerts table. Each alert names the affected sites and the triggering recall record, and persists until acknowledged. **Verify**: inject a new matching recall, run the monitor → `/` shows an alert naming the correct sites; restart the app → the alert is still there.
- [ ] T071 [US5] Implement `POST /alerts/{match_id}/ack` — writes an `acknowledge_alert` decision with actor and timestamp. **Verify**: `curl -X POST -d 'actor=AS' localhost:8000/alerts/7/ack` → 200; the alert clears from `/` and `select * from decisions where kind='acknowledge_alert'` → one row; the underlying match row is untouched.
- [ ] T072 [US5] Write `tests/integration/test_monitor.py` covering US5 acceptance scenarios 1–4, including persistence across a restart. **Verify**: `pytest tests/integration/test_monitor.py -v` → 4 pass.

**Checkpoint**: all five stories demoable.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T073 [P] Implement `pullsheet/recalls/fetch.py` and `POST /recalls/refresh` — the openFDA poll with a bounded timeout, writing a new dated snapshot on success and falling back to the most recent cached snapshot on any failure, reporting which happened. An unreachable endpoint is **never** an error response. **Verify** (quickstart V9): with the network off, click **Refresh recalls** → the page renders, a banner names the cached snapshot with capture date and age, no error page, and the request returns within the timeout.
- [ ] T074 [P] Implement `GET /sources` — every source with its provenance label, capture date, and the adapter's honest `declares()` field-coverage map. **Verify**: open `/sources` → every source carries a `live` / `dated-snapshot` / `hand-authored` label and the coverage map matches what each adapter's `declares()` returns (SC-007, FR-003).
- [ ] T075 [P] Implement `pullsheet/adapters/email_drop.py` — parse an emailed export from a local mailbox file. If stubbed against a fixture mailbox for time, its provenance stays `hand-authored` in the UI; Principle V forbids presenting a stub as working. **Verify**: `pytest tests/adapters/test_email_drop.py -v` → the fixture mailbox yields records; `/sources` shows its true label. **This is the one task safe to cut entirely** — cut it rather than shipping it mislabeled.
- [ ] T076 Write `tests/integration/test_edge_cases.py` — one test per edge case in spec.md, all twelve (SC-010): malformed export, partially parseable rows, unreachable source, no GTIN, untracked lot code, same product different lots, two recalls one item, terminated/amended recall, zero matches, two exports one site, mismatched lot formats, stale snapshot. **Verify**: `pytest tests/integration/test_edge_cases.py -v` → 12 tests, all pass. ⚠️ **Over 45 min** — twelve scenarios.
  - *Split*: T076a the six ingestion and data-shape cases; T076b the six matching and staleness cases (parallelizable, different files).
- [ ] T077 Implement recall amendment and termination handling (FR-016) — record the change, mark affected lines amended or terminated showing prior and current state, and **never remove a line**. Clearing remains a human action. **Verify**: `pytest tests/integration/test_edge_cases.py -k terminated -v` → the line is still on the sheet, marked, with both states visible.
- [ ] T078 Run the full quickstart validation V1–V10 end to end. **Verify**: every scenario in [quickstart.md](./quickstart.md) passes as written, and `pytest -v` is green.
- [ ] T079 [P] Write `README.md` — one-command setup and run matching quickstart.md, plus an 8-minute demo script naming which screen answers which hostile question. **Verify**: a team member who has not touched the repo follows the README from a clean clone to a rendered pull sheet without asking anything.
- [ ] T080 Ownership pass (Principle VI, Ownership gate) — every team member opens every file they did not write and explains it aloud. Any file nobody present can explain is rewritten or deleted **before** the demo. **Verify**: every file in `pullsheet/` has a named owner who explained it, recorded in the README's ownership table. This is a merge gate, not a nicety.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)** → no dependencies.
- **Phase 2 (Foundational)** → blocks everything. Within it: T005 (snapshot) blocks T008 (you cannot seed correspondences against recalls you have not captured); T007 blocks T008 and T016; T013 blocks T014 blocks T015; T018 unblocks every adapter.
- **Phase 3 (US1)** → depends on Phase 2. **This is the MVP.**
- **Phases 4–7 (US2–US5)** → each depends on Phase 3 and on nothing else. They do not depend on each other and can be built in parallel by different people.
- **Phase 8 (Polish)** → depends on whichever stories were built.

### Story dependencies — stated honestly

The template's ideal is fully independent stories. That is not true here and pretending otherwise
would mislead whoever picks up the work. US2, US3, US4, and US5 all consume US1's match results;
none of them consumes any of the others. So: **US1 is a hard prerequisite, and US2–US5 are
mutually independent.** Each remains independently *demoable* — stopping after any phase leaves a
coherent product to present.

### Within User Story 1

T020 → T021 → T022 → T023 is a strict sequence, and the tests must be observed failing. Everything
else in the phase follows the section order: matcher → ingestion → sheet → manual paths → proof.

### Parallel opportunities

**Phase 2** — after T005 lands, T006, T009, T010, and T011 are fully parallel (four people, four
files). T016 runs parallel to the schema tasks.

**Phase 3** — T024, T025, and T026 are three independent modules with three independent test
files; hand them to three people. T033/T034 (watched folder) and T047/T048 (paste, upload) are all
`[P]` because the interface froze at T018 — the watched folder is scheduled first for demo
priority, not because the others are blocked.

**Phases 4–7** — four stories, four people, zero shared files after Phase 3 lands.

```bash
# Phase 2, after T005:
Task: "Hand-transcribe the FSIS snapshot in pullsheet/recalls/snapshots/fsis-2026-09-05.json"
Task: "Author the menu fixtures in data/fixtures/"
Task: "Author data/fixtures/unit_costs.csv"
Task: "Author the four header-layout fixtures in tests/adapters/fixtures/"

# Phase 3, after T023:
Task: "Implement pullsheet/matching/similarity.py"
Task: "Implement pullsheet/matching/lot.py"
Task: "Implement pullsheet/recalls/parse.py"
```

---

## Tasks flagged as over ~45 minutes

Five tasks will not fit in a 45-minute slot. Each carries a concrete split above.

| Task | Why it runs long | Split into |
|---|---|---|
| T006 FSIS snapshot | Hand transcription from published notices, detail-critical | T006a shape + 5 records; T006b the rest (parallel) |
| T007 Inventory fixture | ~50 authored rows carrying every edge case the demo needs | T007a–c, one site each (parallel after the header row) |
| T042 Sheet template | The demo's primary screen — markup, grouping, badges, HELD styling | T042a table and grouping; T042b header, badges, styling |
| T062 State report | Form-shaped work with many fields and a marker treatment | T062a data assembly; T062b template and markers |
| T076 Edge-case suite | Twelve independent scenarios | T076a six ingestion cases; T076b six matching cases (parallel) |

Everything else is estimated at 45 minutes or less. If a task overruns during the build, the honest
move is to split it in this file rather than let it silently expand.

---

## Implementation Strategy

### MVP first

Phases 1–3 (T001–T054). At T054 you have a rehearsed, network-off demo of a complete product:
an export lands unattended, the matcher runs, the sheet prints, and nothing in the codebase can
clear an item on its own. **Stop and rehearse here before starting Phase 4.** A rehearsed MVP
beats an unrehearsed superset every time, and the 8-minute clock is unforgiving.

### Incremental delivery

Each phase after 3 adds one story and a fresh rehearsal. Re-run T053 (`demo_reset.sh`) and T054
(network-off) after every phase — a regression in the offline path is the one failure the demo
cannot survive, and it is exactly the kind that creeps in when a later story adds a fetch.

### Demo order versus build order

They are not the same. Build order is US1 → US2 → US3 → US4 → US5. Demo order is roughly
US4 (the roll-up as the opening frame) → US1 (the drop and the sheet) → US2 → US3, with US5
mentioned rather than shown. Build the MVP first regardless; decide the narration order once you
know what actually exists at hour 20.

### Cut order, if time runs short

Cut from the bottom: T075 (email adapter) first, then Phase 7 (US5), then Phase 6 (US4). Never cut
T012 (provenance), T022 (the auto-clear test), T052 (the clearing audit), T053 (reset script), or
T054 (network-off rehearsal) — those five are what the constitution is for, and they are what three
minutes of hostile questioning will actually go after.
