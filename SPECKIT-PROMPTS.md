# PullSheet — Spec Kit Prompt Guide

Working name: **PullSheet**. Rename freely; it's used consistently below so find-and-replace works.

Run order (excluding `taskstoissues`):

```
/speckit.constitution → /speckit.specify → /speckit.clarify → /speckit.plan
→ /speckit.tasks → /speckit.analyze → /speckit.checklist → /speckit.implement
→ /speckit.converge (loop back to tasks/implement until "Converged")
```

---

## The product, in one paragraph

When the FDA or FSIS recalls a food product, a school district is legally required to find it, isolate it, count it, report it, and claim credit for it — USDA procedure gives roughly 24 hours to notify distributors and 48 hours to complete an inventory assessment. Today that hunt is manual: staff dig through agency emails and distributor notices, then hand-search inventory across every site. **PullSheet closes the loop automatically.** The district's existing nutrition software (PrimeroEdge, LINQ/Titan, Meals Plus, or a spreadsheet) drops a scheduled inventory export into a watched location. PullSheet normalizes it, matches it against live recall feeds on GTIN/UPC first and product name second, and produces a pull sheet — then keeps going: which menu items just broke, on which service days, how many meals, what to substitute, what paperwork to file, and what the distributor owes back.

**The core design principle: the system may add an item to the pull sheet on suspicion. It may never clear one.** That asymmetry is called **Fail-Safe Hold** and it is the product's identity.

---

## Verified facts to keep in the prompts

| Fact | Status |
|---|---|
| `https://api.fda.gov/food/enforcement.json` | ✅ Live, free, no API key. Fields: `product_description`, `code_info` (UPC + lot codes), `classification` (Class I/II/III), `recalling_firm`, `report_date`, `reason_for_recall`, `distribution_pattern`, `status` |
| FSIS recall API + RSS (meat/poultry) | ❌ Returns 403 to server-side requests. **Ship as a dated local snapshot.** Test from your own network first. |
| GTIN is the shared identifier | ✅ Vendors print GTIN at case level; USDA recall procedure names "product code, Lot/Batch number, or GTIN" |
| ~80–85% of school food is commercially procured | ⚠️ School Nutrition Association, Spring 2019. Say "roughly" and cite the year. |
| 24h distributor notice / 48h inventory assessment | ✅ USDA FNS recall procedures |
| Vendor inventory APIs | ❌ None public. PrimeroEdge's APIs are student-information sync only. Roadmap, not build. |

---

## ⚠️ One flag before you start

A prior research pass found an organizer rule that AI may be used for brainstorming and research but **not** for generating code, with judges scrutinizing authenticity. The DevPost page itself states no AI rules. **Verify which applies before running `/speckit.implement`.** If the restriction is real, use this guide through `/speckit.tasks` as a design and planning artifact, and hand-write the code from the task list.

---

# 1. `/speckit.constitution`

Establishes the principles every later step is checked against. Run once. The safety asymmetry belongs here, not in the spec — it's a rule about *how* everything is built.

```
Create the project constitution for PullSheet, a recall-response system for K-12
school nutrition departments.

Non-negotiable principles:

1. FAIL-SAFE HOLD. The matching engine may add an item to the pull sheet on
   suspicion, but may never remove one. Any match below the confidence threshold
   is HELD and routed to human review — never auto-cleared. Under-pulling risks a
   child; over-pulling wastes a case of tomatoes. Every code path that could clear
   an item must be explicitly justified.

2. DETERMINISTIC CORE. All quantities, dollar amounts, dates, deadlines, and
   pull/hold decisions are computed by plain, unit-tested code. No language model
   participates in any safety decision. If a model is used at all, it may only
   propose candidate name matches, which are then scored and gated by
   deterministic rules.

3. NO EXTERNAL DEPENDENCY AT DEMO TIME. The application must run end-to-end with
   the network unplugged, using cached recall snapshots. No OAuth, no vendor API,
   no third-party auth on the critical path. Pulling the plug must degrade the
   system, never break it.

4. ADAPTER-BASED INGESTION. The system never couples to a specific vendor. All
   inventory enters through a documented adapter interface that normalizes to one
   internal record shape. Adding a new source means adding an adapter, never
   touching the matcher.

5. DISCLOSED PROVENANCE. Every data source is labeled in the UI and in the repo as
   live / dated-snapshot / hand-authored. Nothing synthetic is ever presented as
   real. Every recall match displays the exact source record and the field value
   that triggered it.

6. TOTAL TEAM OWNERSHIP. Prefer boring, explainable implementations over clever
   ones. Any team member must be able to open any file, explain what it does, and
   modify it live under questioning. If a library hides the interesting logic,
   write the logic.

7. ARTIFACT OVER PROSE. Every user-facing flow ends in a concrete artifact — a
   pull sheet, a filed form, a dollar figure, a revised menu — never a paragraph of
   generated text.

Constraints: ~24 hour build, small team, in-person 8-minute live demo plus 3
minutes of hostile Q&A.
```

---

# 2. `/speckit.specify`

The big one. **What and why only — no tech.** Stories are priority-ordered so the cut line is explicit; P1 alone must be a complete, demoable product.

```
Build PullSheet: a food-recall response system for K-12 school district nutrition
departments.

## The problem

When the FDA or USDA-FSIS issues a food recall, a school district must determine
whether it holds the recalled product, isolate it, count it across every site,
report to its state child-nutrition agency, and claim credit from its distributor.
USDA procedure expects distributor notification within about 24 hours and a
completed inventory assessment within about 48 hours.

Today this is manual. Staff read agency emails and distributor notices, then
hand-search inventory site by site. Roughly 80-85% of school food is procured
commercially rather than through USDA Foods (School Nutrition Association, 2019),
and for that majority the recall information flow is weakest. Districts already
hold their inventory in nutrition software (PrimeroEdge, LINQ/Titan, Meals Plus)
or in spreadsheets — but none of those systems ingest recall feeds, so the last
mile is a person with a printout walking a freezer.

## The users

- District Nutrition Director — accountable for the response, files the state
  report, owns the deadline.
- Site Cafeteria Manager — physically pulls product from a specific kitchen,
  needs a printable sheet with locations and quantities.
- (Later) State child-nutrition agency staff — receive district reports.

## Core principle

The system may add an item to the pull sheet on suspicion. It may never clear one.
Uncertain matches are HELD for human review, never auto-dismissed.

## User stories, priority ordered

### P1 — Automatic recall detection from an existing inventory export (MVP)
As a Nutrition Director, I connect PullSheet to the inventory export my nutrition
software already produces on a schedule, so that recalled product is flagged
without anyone remembering to check.
- A scheduled inventory export arrives at a monitored location with no human
  action.
- The system normalizes it regardless of the source system's column layout.
- It matches every line against current recall records, preferring exact
  GTIN/UPC/lot matches and falling back to product-name similarity.
- Each match shows a confidence tier and the exact source text that triggered it.
- Matches below threshold are HELD, not cleared, and are visually distinct.
- The result is a printable pull sheet grouped by site, ordered with the most
  serious recall class first, showing item, quantity, location, and lot.
- A manual paste/upload path exists for kitchens with no software at all.

### P2 — Menu-break cascade and substitution
As a Nutrition Director, I see which planned meals just became impossible and what
to serve instead.
- Recalled items resolve to the recipes that use them.
- Recipes resolve to affected service dates and estimated meal counts.
- The system proposes a substitute that preserves the required meal-pattern
  components, or states plainly that it cannot find one.
- The revised menu is viewable and printable.

### P3 — Compliance artifacts
As a Nutrition Director, the paperwork is generated for me.
- A hold-and-destruction record per site, ready for signature.
- A pre-filled state child-nutrition recall report.
- A distributor credit claim with itemized quantities and a total dollar amount.

### P4 — District roll-up and deadline clock
As a Nutrition Director overseeing many schools, I see the whole district at once.
- Every site shown as clear / holding / unconfirmed.
- Countdowns to the 24-hour distributor-notification and 48-hour
  inventory-assessment deadlines, timed from recall receipt.
- Per-site confirmation that the physical pull is complete.

### P5 — Standing monitor
As a Nutrition Director, I never have to remember to check.
- Inventory persists between sessions.
- New recall records are diffed against stored inventory on a schedule.
- New hits raise an alert identifying affected sites.

## Success criteria (technology-agnostic)

- An inventory export placed in the monitored location produces a complete pull
  sheet with no human interaction.
- Every pull-sheet line traces to a specific recall record and a specific
  triggering field value.
- No item is ever auto-cleared below the confidence threshold; verified by test.
- The full flow runs with the network disconnected, using cached recall data.
- A realistic ~50-line inventory containing deliberately abbreviated item names
  (e.g. "chkn strips froz") still matches the correct recall records.
- Pull sheet renders within a few seconds of the export arriving.
- Every data source is labeled live / snapshot / hand-authored in the interface.

## Edge cases to handle explicitly

- Export arrives malformed, empty, or with unrecognized columns.
- Recall feed unreachable — must fall back to cached snapshot and say so.
- Item has no GTIN (common for produce and USDA commodity foods).
- Recall names a lot code the inventory does not track.
- Same product stocked at several sites with different lots.
- A recall is later terminated or amended.
- Two recalls affect the same item.

## Out of scope

Direct vendor API integration; user accounts and role permissions; mobile app;
barcode scanning hardware; payment; multi-district tenancy; anything requiring a
signed agreement with a software vendor, distributor, or agency.
```

---

# 3. `/speckit.clarify` *(optional — run it)*

This command interrogates *you* and writes the answers back into the spec. Its value is closing ambiguity before `/plan` bakes in a guess. Run it with no arguments, or steer it:

```
Clarify PullSheet, focusing on the areas most likely to cause rework:
the confidence-tier thresholds and what exactly happens at each tier; the
normalized inventory record shape; how lot codes are compared when formats differ
between recall notices and inventory records; what "affected meal count" is
computed from; and what the system does when the recall feed is unreachable.
Do not ask me about visual design or technology choices.
```

### Answer key — decide these now, answer in seconds during the build

| It will ask | Answer |
|---|---|
| Confidence tiers? | **Three.** `EXACT` = GTIN/UPC match, or brand + product + lot. `LIKELY` = normalized name similarity above threshold. `UNCERTAIN` = anything else with a shared distinctive token. EXACT and LIKELY → pull sheet. UNCERTAIN → **Hold queue** for human review. Nothing is ever auto-cleared. |
| Normalized record shape? | `site, item_name, gtin, lot_code, quantity, unit, received_date, source_adapter, source_row` — keep `source_row` so every match can show its origin. |
| Lot code comparison? | Normalize both sides: uppercase, strip spaces/punctuation, then substring match in both directions. Lot formats are inconsistent in the wild — a missing lot never clears an item, it downgrades it to `LIKELY`. |
| Meal count source? | Hand-authored planned-servings figure per recipe per service date, from a real published district menu. Label it hand-authored. |
| Feed unreachable? | Serve the cached snapshot, show a visible banner with the snapshot date, never fail silently, never show an empty pull sheet as if it meant "clear." |
| Units/conversions? | Out of scope. Report the unit as given. Do not invent conversions. |
| Auth? | None in MVP. Single-district, single-user. |
| Historical inventory? | Latest export per site replaces the previous. Keep prior exports on disk for the audit trail; do not merge them. |

---

# 4. `/speckit.plan`

Where technology enters. **Substitute your team's actual stack** — what you can explain under questioning matters more than what I'd pick.

```
Create the technical implementation plan for PullSheet.

## Stack

Python 3.11+ with FastAPI for the backend. SQLite via plain SQL (no ORM) for
storage — the schema must be readable in one screen. Server-rendered HTML with
Jinja2 templates plus a small amount of vanilla JavaScript for polling; no
frontend framework and no build step. Standard library plus httpx, and a
pure-Python string-similarity implementation we write ourselves rather than a
matching library. Everything runs from one `uvicorn` command with no external
services.

Rationale to honor: every team member must be able to open any file and modify it
live under questioning. Prefer readable over clever. Where a library would hide the
interesting logic — especially the matching — write the logic.

## Architecture

**Ingestion — adapter layer.** One `InventoryAdapter` interface with a single
method that yields normalized records:
`site, item_name, gtin, lot_code, quantity, unit, received_date, source_adapter,
source_row`

Ship four adapters:
- `WatchedFolderAdapter` — polls a directory on an interval, picks up new
  CSV/XLSX files, archives what it has processed. This is the primary integration
  and the demo centerpiece.
- `EmailDropAdapter` — parses an emailed export from a local mailbox file. May be
  stubbed against a fixture file if time is short; label it clearly.
- `SpreadsheetUploadAdapter` — browser upload with column detection and a mapping
  step for unrecognized headers.
- `PasteAdapter` — plain text, one item per line. The floor; must never fail.

Column mapping must be tolerant: detect likely name/GTIN/lot/quantity columns
across the differing export layouts of PrimeroEdge, LINQ/Titan, Meals Plus, and
ad-hoc spreadsheets. When detection is ambiguous, ask the user once and remember
the mapping per source.

**Recall ingestion.** Poll `https://api.fda.gov/food/enforcement.json` (free, no
key). Persist every fetch to a local snapshot with a timestamp. On any failure,
fall back to the most recent snapshot and surface its date in the UI. Ship a
committed FSIS meat/poultry snapshot as a JSON file — the FSIS API returns 403 to
server-side requests, so it cannot be fetched live; label it a dated snapshot
everywhere it appears. Parse UPCs and lot codes out of the free-text `code_info`
field with documented regex patterns.

**Matcher — three tiers, deterministic, no model.**
1. `EXACT` — normalized GTIN/UPC equality, or brand + product + lot agreement.
2. `LIKELY` — token-normalized name similarity above threshold. Normalization
   expands common kitchen abbreviations (chkn→chicken, froz→frozen, and so on)
   from a small hand-authored dictionary, strips pack sizes and units, then scores
   with a similarity function we implement and unit-test ourselves.
3. `UNCERTAIN` — shares a distinctive token but scores below threshold.

Every match records tier, score, the recall record id, and the exact triggering
substring from both sides.

**Fail-Safe Hold gate.** A single chokepoint function through which every
pull/hold decision passes. EXACT and LIKELY go to the pull sheet; UNCERTAIN goes
to the Hold queue. There is no code path that clears an item automatically. This
function is the most heavily unit-tested thing in the codebase.

**Menu graph.** Hand-authored tables from a real published district menu:
recipes → ingredients, and menu calendar → recipe → planned servings per date.
A recalled item traverses to affected recipes, dates, and meal counts.
Substitution uses a small hand-authored table of meal-pattern components; if no
substitute preserves the required components, say so explicitly rather than
guessing.

**Artifact generator.** Print-styled HTML (no PDF library) for the pull sheet,
hold-and-destruction record, state report, and distributor credit claim. All
dollar totals computed in plain code from quantity × unit cost.

**District roll-up.** Site status board plus countdowns computed from recall
receipt timestamp against the 24h and 48h deadlines.

## Data provenance — track in a table committed to the repo

| Source | Status |
|---|---|
| openFDA food enforcement | live API + local snapshot fallback |
| FSIS meat/poultry recalls | dated snapshot, cannot be fetched server-side |
| District inventory fixture | hand-authored, ~50 items, deliberately abbreviated names |
| Menu / recipe / servings tables | hand-authored from a real published district menu |
| Unit costs | hand-authored, plausible |

## Non-functional requirements

Runs fully offline from cached snapshots. Single command to start. No
authentication. No build step. Pull sheet renders within a few seconds of export
arrival. Every safety-relevant decision covered by a unit test.

## Explicitly not in this plan

Vendor APIs, OAuth, accounts and roles, cloud deployment, Docker, message queues,
ORMs, frontend frameworks, PDF generation libraries, ML frameworks.
```

---

# 5. `/speckit.tasks`

```
Generate the task list for PullSheet.

Sequence so that each priority level is independently demoable — if we stop after
P1 we still have a complete product to present.

Order requirements:
- Fixtures first: the hand-authored ~50-item inventory with abbreviated names, the
  committed openFDA snapshot, and the FSIS snapshot must exist before any matcher
  work, so nothing is ever blocked on the network.
- The Fail-Safe Hold gate gets its unit tests written before its implementation.
  Include an explicit test asserting that no input can cause an item to be
  auto-cleared.
- The WatchedFolderAdapter and the pull sheet are the demo centerpiece — they come
  before the email and upload adapters.
- Adapters are parallelizable once the interface is fixed; mark them so.
- Every task names its verification: the command to run and the observable result.

Also include:
- A task creating the committed data-provenance table.
- A task for a demo reset script that clears state and restores the watched folder
  to a known pre-drop condition, runnable between rehearsals.
- A task verifying the whole flow with the network disconnected.

Flag any task that cannot be completed in roughly 45 minutes so we can split it.
```

---

# 6. `/speckit.analyze` *(optional — run it after tasks, before implement)*

```
Analyze consistency and coverage across the PullSheet constitution, spec, plan,
and tasks.

Check specifically:
- Every P1 acceptance criterion maps to at least one task.
- No task violates the Fail-Safe Hold principle or introduces a path that could
  auto-clear an item.
- No task introduces a network dependency on the demo critical path.
- Nothing in the plan requires a vendor API, OAuth, or a signed agreement.
- Every data source named in the plan appears in the provenance table.
- Every edge case in the spec has either a task or an explicit deferral.
- The task ordering never blocks P1 on a P2+ dependency.

Report contradictions and gaps with the specific artifact and line. Do not
propose new scope.
```

---

# 7. `/speckit.checklist` *(optional — generate three)*

Run once per checklist; they serve different purposes.

**Demo readiness**
```
Generate a demo-readiness checklist for PullSheet: an 8-minute live in-person
presentation followed by 3 minutes of hostile technical Q&A, presented from one
laptop. Cover: the reset-between-rehearsals path, behavior with the network
disconnected, what is visible on screen at the moment the pull sheet appears,
print output actually printing, and the failure modes most likely to embarrass us
on stage. Include a checklist item for every point at which the demo depends on
something outside the laptop.
```

**Safety asymmetry**
```
Generate a checklist verifying the Fail-Safe Hold principle across the PullSheet
codebase. Every path that could result in an item NOT appearing on the pull sheet
must be enumerated and justified. Include: threshold boundary conditions, empty
and malformed inventory input, unreachable recall feed, missing GTIN, missing lot
code, terminated and amended recalls, and duplicate matches. For each, state the
expected behavior and the test that proves it.
```

**Data provenance**
```
Generate a checklist confirming every piece of data in PullSheet is correctly
labeled live, dated-snapshot, or hand-authored — in the interface, in the README,
and in the provenance table. Include a check that no hand-authored or synthetic
data is presented anywhere as real, and that every snapshot displays its date to
the user.
```

---

# 8. `/speckit.implement`

⚠️ Confirm the organizer's AI-code rule first (see flag at top).

```
Implement PullSheet following the task list in order.

Rules:
- Write the Fail-Safe Hold gate's tests before its implementation, and show them
  failing before they pass.
- Do not add dependencies beyond those named in the plan. If something seems to
  need a new library, stop and ask.
- Do not introduce authentication, vendor APIs, or a build step.
- Keep every file small enough to explain out loud. If a file exceeds roughly 200
  lines, split it along a boundary a person would describe naturally.
- Comment the non-obvious matching logic — abbreviation expansion, lot-code
  normalization, and threshold choices — with the reasoning, not the mechanics.
- After each task, state the verification command and its actual output.

Stop and ask rather than guessing whenever a decision would change observable
behavior.
```

**Run it in slices** rather than one shot: implement P1, verify it end to end, rehearse the demo on it, then continue. A working P1 at hour 10 is worth far more than a half-finished P3 at hour 23.

---

# 9. `/speckit.converge`

Run after `implement`. It audits the codebase against spec/plan/tasks and appends what's left as new tasks. Loop `converge → implement` until it reports **Converged**.

```
Assess the PullSheet codebase against the constitution, spec, plan, and tasks.

Prioritize by demo risk, not by completeness: anything that could fail live during
the 8-minute presentation ranks above missing P3 and P4 features. Explicitly
verify that the constitution still holds — particularly Fail-Safe Hold, offline
operation, and disclosed provenance — and flag any drift as the highest-priority
remaining work.

Append remaining work as new tasks. Do not add scope beyond the spec.
```

### The convergence cut line

With roughly 24 hours, decide honestly at each loop:

| Hours remaining | Do this |
|---|---|
| > 12 | Keep converging on P1 + P2 |
| 6–12 | Freeze features. Converge on demo risk only. |
| 3–6 | Stop converging. Rehearse. Write the Q&A answers. |
| < 3 | Fix only the single thing most likely to embarrass you. Nothing else. |

---

## Quick reference

| # | Command | Optional | Purpose |
|---|---|---|---|
| 1 | `/speckit.constitution` | No | Fail-Safe Hold, determinism, offline, provenance |
| 2 | `/speckit.specify` | No | What & why, P1–P5 stories, success criteria |
| 3 | `/speckit.clarify` | Yes | Close ambiguity — use the answer key above |
| 4 | `/speckit.plan` | No | Stack, adapters, three-tier matcher, menu graph |
| 5 | `/speckit.tasks` | No | Ordered, demoable per priority, fixtures first |
| 6 | `/speckit.analyze` | Yes | Cross-artifact consistency |
| 7 | `/speckit.checklist` | Yes | Demo readiness · safety asymmetry · provenance |
| 8 | `/speckit.implement` | No | Build in slices, P1 first |
| 9 | `/speckit.converge` | No | Loop until "Converged" |
