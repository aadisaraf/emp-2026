# Implementation Plan: PullSheet — Food-Recall Response for K-12 Nutrition Departments

**Branch**: `001-recall-pull-sheet` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-recall-pull-sheet/spec.md`

## Summary

PullSheet watches a folder for the inventory export a district's nutrition software already
produces, normalizes it through an adapter, matches every line against a cached recall corpus,
and emits a printable pull sheet. Uncertain matches are HELD on the same sheet, never cleared.
Downstream it cascades into broken menus, compliance paperwork, a district roll-up with USDA
deadline clocks, and a standing monitor.

The technical shape is deliberately plain: FastAPI serving server-rendered Jinja2 pages, SQLite
through hand-written SQL, and a matcher written from scratch — normalization, screening,
similarity scoring, and the pull/hold gate are all first-party code, because those are the parts
a judge will ask about and Principle VI requires the team be able to defend them line by line.

Three points in the input conflicted with the clarified spec. Each is resolved below under
**Reconciliations**, and each resolution follows the spec.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `fastapi`, `uvicorn`, `jinja2`, `python-multipart` (file upload),
`httpx` (openFDA fetch only), `openpyxl` (XLSX reading), `pytest`. Nothing else. No ORM, no
frontend framework, no build step, no PDF library, no matching or ML library.

**Storage**: SQLite via `sqlite3` from the standard library, plain SQL in `schema.sql`. One file
on disk at `data/pullsheet.db`, deleted and recreated by a reset command.

**Testing**: `pytest`. The pull/hold gate, the tier ladder, the screening rule, lot comparison,
quantity math, dollar math, and deadline math are all unit-tested against explicit expected
values. Fixture-driven adapter tests, one fixture per source layout.

**Target Platform**: Local machine, any OS with Python 3.11. Browser at `localhost:8000`.

**Project Type**: Single-process web service with server-rendered UI.

**Performance Goals**: Pull sheet available within 5 seconds of export arrival for 500 inventory
lines against 1,000 recall records (SC-006). Achieved by screening through an in-memory inverted
index rather than comparing all 500,000 pairs — see Phase 0 research.

**Constraints**: Runs end to end with the network unplugged (FR-060). One command to start. No
authentication anywhere (FR-061). Every network call bounded and optional (FR-062).

**Scale/Scope**: One district, ~10 sites, a few thousand inventory lines, a recall corpus in the
low thousands. Single operator, no concurrency beyond one browser and one folder poller.

## Reconciliations

Three conflicts between the plan input and the clarified spec. All three resolve toward the spec,
because the constitution makes the spec governing and because the clarify session (2026-09-05)
recorded deliberate answers on exactly these points.

### R1 — Tier names and, more importantly, tier meanings

The input proposes `EXACT` / `LIKELY` / `UNCERTAIN`, with `LIKELY` defined as *name similarity
above a threshold* routed **to the pull sheet**. The clarified spec (FR-019) says the tier is set
by the *kind of evidence*, that a score may never promote a candidate between tiers, and that
name-similarity-only evidence lands in a tier that **HOLDS**.

These are not the same ladder wearing different labels. Under the input, a strong name match is
actionable without review; under the spec, it is reviewable by construction.

**Resolution**: keep the spec's semantics *and* the spec's names — `CONFIRMED` / `PROBABLE` /
`POSSIBLE`. Reusing `EXACT`/`LIKELY`/`UNCERTAIN` with changed meanings would be the worst
outcome for Principle VI: a reader who remembers "LIKELY means a good name match" would be
confidently wrong about what the code does.

| Input tier | Input meaning | Spec tier used | Meaning implemented |
|---|---|---|---|
| `EXACT` | GTIN/UPC equality, or brand+product+lot | `CONFIRMED` | Normalized GTIN or UPC equality → PULL |
| `LIKELY` | Name similarity above threshold | `PROBABLE` | Lot/batch agreement, or a secondary code field match (this is where brand+product+lot lands) → PULL |
| `UNCERTAIN` | Shares a token, below threshold | `POSSIBLE` | Name similarity only, whatever the score → HELD |

The similarity score survives, but it is demoted: it orders lines *within* `POSSIBLE` and never
decides a status. There is consequently no "pull threshold" anywhere in the codebase, which is a
much easier thing to defend in Q&A than a number.

### R2 — The normalized record shape is a superset of the input's

The input lists nine fields. FR-002 requires fourteen. The four the input omits are not
cosmetic: without `storage_location` the pull sheet cannot tell a manager where to walk
(FR-033), without `unit_cost` the credit claim has no dollar total (FR-046), and without `upc`
the `CONFIRMED` tier loses half its definition (FR-017).

**Resolution**: implement FR-002's fourteen fields. The input's `item_name` maps to
`raw_description`, and `source_adapter` + `source_row` are preserved as ingest-run metadata
rather than dropped.

### R3 — Lot normalization belongs to the matcher, not the adapters

FR-066 requires lot codes normalized on both sides before comparison. Lot formatting is exactly
the thing that varies by vendor, so it is tempting to normalize in each adapter — which would put
vendor knowledge on the wrong side of the boundary Principle IV draws, and would mean a new
adapter could quietly change matching behavior.

**Resolution**: adapters pass `lot_code` through **verbatim**, exactly as the source wrote it.
All normalization lives in `matching/lot.py`. The verbatim value is what the pull sheet displays
as the triggering value; the normalized value is used only for comparison.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.0.0.

| Principle | Pre-design | How the design satisfies it | Post-design |
|---|---|---|---|
| **I. Fail-Safe Hold** | PASS | Every status flows through one function, `matching/gate.py::decide()`. It returns only `PULL` or `HELD` — the type has no third value, so "cleared" is unrepresentable in the matcher. Clearing lives in a separate `decisions` table written only by an HTTP route that requires an actor name. Screening (FR-020) is the one narrowing step and is isolated in `matching/screen.py` with its rule printed in the UI. | PASS |
| **II. Deterministic Core** | PASS | No model anywhere. Similarity is our own function over sorted token sets. All ordering is by explicit sort keys, never dict order. `decide()` takes an injected `now` and never reads the clock. Deadline and dollar math are plain arithmetic in dedicated modules. | PASS |
| **III. No External Dependency at Demo Time** | PASS | The only network call is the openFDA fetch, in `recalls/fetch.py`, wrapped in a bounded timeout with a snapshot fallback. FSIS ships as a committed snapshot because it 403s server-side. Nothing else touches the network; no auth of any kind. | PASS |
| **IV. Adapter-Based Ingestion** | PASS | One `InventoryAdapter` ABC. The matcher imports nothing from `adapters/`. Vendor-specific header knowledge is confined to `adapters/column_map.py`. R3 keeps lot formatting out of the adapters. | PASS |
| **V. Disclosed Provenance** | PASS | A `provenance.py` module holds one dict mapping every source to `live` / `dated-snapshot` / `hand-authored`, rendered by a single Jinja macro used on screen and in print CSS. `data/PROVENANCE.md` is the repo-side copy. Every match row carries `recall_record_id` and both triggering substrings. | PASS |
| **VI. Total Team Ownership** | PASS *(with 2 noted deps)* | Matching, scoring, screening, lot comparison, tiering, and the gate are all hand-written. Libraries appear only for HTTP serving, templating, XLSX parsing, and HTTP fetching. See Complexity Tracking for the two dependency judgements. | PASS |
| **VII. Artifact Over Prose** | PASS | Four generators produce print-styled HTML: pull sheet, hold record, state report, credit claim. Plus the revised menu. No flow terminates in generated prose; the substitution engine states a named unmet component rather than describing the problem. | PASS |

**Gate result: PASS.** No unjustified violations. Two dependency judgements and one schema-size
deviation are recorded in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-recall-pull-sheet/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── adapter-interface.md
│   ├── http-endpoints.md
│   └── hold-gate.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Created by /speckit-tasks, not here
```

### Source Code (repository root)

```text
pullsheet/
├── main.py                  # uvicorn entrypoint; one command starts everything
├── app.py                   # FastAPI routes only — thin, delegates immediately
├── db.py                    # sqlite3 connection, schema load, reset
├── schema.sql               # all DDL, one file
├── provenance.py            # source → live | dated-snapshot | hand-authored
│
├── adapters/
│   ├── base.py              # InventoryAdapter ABC + NormalizedRecord
│   ├── column_map.py        # tolerant header detection + remembered mappings
│   ├── watched_folder.py    # primary path; polls, ingests, archives
│   ├── spreadsheet_upload.py
│   ├── email_drop.py        # local mailbox file
│   └── paste.py             # the floor; must never raise
│
├── recalls/
│   ├── fetch.py             # openFDA poll, bounded timeout, snapshot write
│   ├── parse.py             # code_info → UPCs + lot codes, documented regexes
│   ├── corpus.py            # load active corpus, freshness window (FR-068)
│   └── snapshots/           # committed dated JSON, incl. FSIS
│
├── matching/
│   ├── normalize.py         # abbreviation expansion, unit/pack stripping, tokens
│   ├── abbreviations.py     # hand-authored dict: chkn→chicken, froz→frozen, …
│   ├── similarity.py        # our own scorer, no library
│   ├── lot.py               # lot normalization + comparison (R3)
│   ├── screen.py            # candidate generation + inverted index (FR-020)
│   ├── tiers.py             # evidence ladder → CONFIRMED | PROBABLE | POSSIBLE
│   └── gate.py              # THE chokepoint. Every decision passes here.
│
├── menu/
│   ├── cascade.py           # recalled item → recipes → dates → planned meals
│   └── substitute.py        # meal-pattern components; says no when it means no
│
├── artifacts/
│   ├── pull_sheet.py
│   ├── hold_record.py
│   ├── state_report.py
│   └── credit_claim.py      # quantity × unit_cost, plain arithmetic
│
├── rollup/
│   ├── status.py            # clear | holding | unconfirmed, incl. stale gate
│   └── deadlines.py         # 24h / 48h from receipt, injected now
│
├── monitor.py               # scheduled corpus diff → alerts
├── templates/               # Jinja2; print.css handles all four artifacts
├── static/                  # one poll.js, one stylesheet. No build step.
└── data/
    ├── fixtures/            # hand-authored inventory, menu, recipes, costs
    ├── watched/             # the folder the demo drops into
    ├── archive/             # processed exports
    └── PROVENANCE.md        # repo-side provenance table

tests/
├── unit/                    # gate, tiers, screen, similarity, lot, money, deadlines
├── adapters/                # one fixture per source layout
└── integration/             # end-to-end: file lands → sheet exists, network off
```

**Structure Decision**: single Python package, flat by concern. Each directory maps to one
constitutional principle or one user story, so "who owns this file" has an obvious answer during
hostile Q&A. `matching/` is deliberately split into six small files rather than one large one:
every file in it is individually explainable in under a minute, which is the Principle VI test.

## Phase Outputs

- **Phase 0** → [research.md](./research.md) — the six decisions that needed resolving before
  code: screening index, similarity function, `code_info` parsing, XLSX dependency, freshness
  window mechanics, and how "no substitute exists" is proven rather than asserted.
- **Phase 1** → [data-model.md](./data-model.md), [contracts/](./contracts/),
  [quickstart.md](./quickstart.md).

## Complexity Tracking

Three judgements that need stating out loud rather than being discovered in review.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `openpyxl` dependency | The input specifies "standard library plus httpx", but the `WatchedFolderAdapter` must read XLSX and the standard library cannot. XLSX parsing is uninteresting work under Principle VI — it hides no logic a judge would ask about. | CSV-only support was rejected because real districts export XLSX, and the watched-folder path is the demo centerpiece. Writing an XLSX reader by hand would spend hours of a 24-hour build on ZIP and XML plumbing that proves nothing. |
| `jinja2` + `python-multipart` beyond the stated stack | Server-rendered HTML and browser file upload. Both are transport and templating, not logic. | Hand-rolling multipart parsing or string-concatenating HTML would be more code, less readable, and would still hide nothing interesting. |
| SQLite schema is twelve tables, not "one screen" | The spec's twelve entities do not compress below twelve tables without hiding relationships in JSON blobs, which would put safety-relevant data beyond SQL's reach. | Collapsing `matches` and `decisions` into one table was rejected specifically because Principle I depends on machine-produced candidates and human clearings being separately queryable. Mitigation: `schema.sql` is ordered so the four safety-critical tables — `inventory_records`, `recall_records`, `matches`, `decisions` — appear first and do fit one screen, with menu and monitor tables below. |

## Risks

| Risk | Mitigation |
|---|---|
| openFDA `code_info` is free text; regex extraction will miss some UPCs and lots | Every extraction failure widens rather than narrows: an unparsed `code_info` means the recall keeps only name evidence, so its candidates land in `POSSIBLE`/HELD instead of vanishing. Parser coverage is reported in the UI as a count, not hidden. |
| `EmailDropAdapter` may not be finished in 24h | It is fourth in build order and stubbed against a fixture mailbox if time runs short. Principle V requires the stub be labeled `hand-authored` in the UI, not quietly presented as working. |
| Screening index tuning could over-narrow and hide a real match | `screen.py` is unit-tested with a corpus of known-positive pairs, and the UI states the screening rule verbatim. SC-005 (every seeded correspondence appears) is the regression test. |
| Demo machine has no network and the FSIS snapshot is stale | That is the designed state, not a failure. FR-068's freshness window means sites show `unconfirmed (stale recall data)` rather than a false `clear`. Worth rehearsing so the team can narrate it as intended behavior. |
