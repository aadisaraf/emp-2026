---
description: "Copy-paste /speckit-implement prompts for a three-person PullSheet build"
---


> **Amendment, 2026-09-05.** These prompts are the record of what was asked at the time, and are
> left as written. Two decisions inside them have since been superseded and the prompts for
> T016/T017 should NOT be followed as-is:
>
> * `matching/abbreviations.py` was written, then removed. Both sides of the comparison are
>   distributor-catalog strings, not freehand text, so words are compared as written.
> * The inventory record gained five supplier fields — `brand`, `manufacturer`,
>   `manufacturer_item_code`, `vendor_name`, `vendor_item_code` (FR-069) — and the ladder gained
>   two rungs that use them (FR-070, FR-071). Anything below that touches the record shape or the
>   evidence kinds should read `specs/001-recall-pull-sheet/data-model.md` first.
>
> `tests/integration/test_abbreviations.py` is now `tests/integration/test_seeded_correspondences.py`.

> **Amendment 3, 2026-09-05 — this file is a historical record.** It was written for the district
> model and executed against it. The system it describes building is not the system that exists:
> one deployment is now one location, deliveries arrive on a daily schedule over SFTP or email,
> and each one produces a dated run. `rollup/`, `monitor.py` and `adapters/paste.py` were all
> removed. See [spec.md](./spec.md), [plan.md](./plan.md) and
> [tasks.md](./tasks.md) for
> what the system is now. Nothing here should be followed as an instruction.

# Implement Prompts — Three-Person Team

**Companion to**: [parallel-plan.md](./parallel-plan.md) · [tasks.md](./tasks.md)

Nine prompts. Each is scoped to a task list and a file allowlist, because `/speckit-implement`
run bare executes **all 80 tasks** — three unscoped runs means three people building the same
product on top of each other.

## Roles for the whole build

| | **A — Core** | **B — Pipeline** | **C — Surface** |
|---|---|---|---|
| **Wave 0** | T005 → T006 → T013 → T014 → T015 → W3 | T007 → T016 → T017 → T011 → T009 → T010 | T001 → T002/3/4 → T018 → W1 → T012 → T040 → T019 |
| **Wave 1** | `feat/matcher` | `feat/ingest` | `feat/pull-sheet` |
| **Wave 2** | `feat/rollup` (US4) | `feat/menu` (US2) | `feat/artifacts` (US3) |
| **Wave 3** | all three on `main` | | |

**C is also the integrator** — owns `main`, runs every merge, resolves every conflict. Give this
role to whoever is most comfortable with git under pressure.

**A owns the safety-critical core.** At the demo, hostile questions land on the matcher. Give this
role to whoever will be most fluent explaining `gate.py` out loud.

After Wave 0, **A does T008** (needs both A's snapshot and B's fixture) and **C does W2**
(`seed_matches.sql`, needs B's fixture).

US5 (the standing monitor, T069–T072) is unassigned. It is second on the cut list. Pick it up in
Wave 3 only if you are ahead.

## Two things everyone hits immediately

1. **The checklist gate halts you.** `/speckit-implement` counts unchecked items in
   `checklists/requirements.md` and stops to ask. One item is unchecked: the FR-044
   `[NEEDS CLARIFICATION]` marker, which is about which state's recall report to pre-fill. It
   affects exactly one task — T062, in Wave 2. **Answer `yes` and continue.** Every prompt below
   says so.

2. **`tasks.md` is shared and the command writes to it.** Mark `[X]` only against your own task
   IDs, never reflow or reformat the file, never touch another lane's lines. Line ranges are
   disjoint per lane so git merges them cleanly — as long as nobody reformats. If you do hit a
   conflict there, take both sides.

---

# WAVE 0 — Foundation (all three on `main`, no branches)

Everyone pushes to `main` directly, every 15–20 minutes. **C runs T001 first and pushes it before
anything else** — the other two need the package skeleton. A starts on T005 in the meantime, which
needs only a directory.

## → Person A, Wave 0

```
/speckit-implement
SCOPE: Wave 0, data and storage. Implement ONLY these tasks, in this order:
T005, T006, T013, T014, T015, and W3 (below). Do not implement, scaffold, stub, or
create files for any other task in tasks.md.

W3 is an addition from parallel-plan.md: declare
pullsheet/matching/run.py::match_all(conn) -> int raising NotImplementedError, with a
docstring naming T032 as the task that implements it. Nothing else in that file.

Files you may create or modify:
  pullsheet/recalls/snapshots/*.json and *.meta.json
  pullsheet/schema.sql
  pullsheet/db.py
  pullsheet/matching/run.py
Every other path in the repo is READ-ONLY. If a task seems to require editing a file
outside this list, stop and report it rather than editing it.

Do T005 FIRST. It is the only task in the entire build that needs the network, and if
the wifi is going to fail we need to know now, not at hour 20.

Constraints that are not negotiable:
- T013 writes the four safety-critical tables at the TOP of schema.sql, exactly per
  data-model.md, with CHECK(status IN ('PULL','HELD')). There is no CLEARED value and
  no third status. The verification for T013 is that inserting 'CLEARED' FAILS with a
  CHECK constraint error. That failure is the schema enforcing Principle I — do not
  "fix" it.
- T015: db.py --load-fixtures loads inventory, unit costs, and menu fixtures only.
  Recall snapshot loading arrives in T030. Leave a literal TODO(T030) marker. Do NOT
  write a stub that silently loads nothing.
- Do not add anything to requirements.txt. The seven pinned dependencies are frozen.

When the checklist gate asks about unchecked items, answer yes and proceed. The one
unchecked item is FR-044, which only affects T062 in Wave 2.

In tasks.md mark [X] only for T005, T006, T013, T014, T015. Do not reformat the file
and do not touch any other task's line.

Stop when those six are done and verified. Do not continue into Phase 3 or any other
phase. Report which verification commands you ran and their actual output.
```

## → Person B, Wave 0

```
/speckit-implement
SCOPE: Wave 0, fixtures and normalization. Implement ONLY these tasks, in this order:
T007, T016, T017, T011, T009, T010. Do not implement, scaffold, stub, or create files
for any other task in tasks.md.

Files you may create or modify:
  data/fixtures/*
  tests/adapters/fixtures/*
  pullsheet/matching/abbreviations.py
  pullsheet/matching/normalize.py
  tests/unit/test_normalize.py
Every other path in the repo is READ-ONLY. If a task seems to require editing a file
outside this list, stop and report it rather than editing it.

T007 is the long pole and everything else in the build reads it. Do it first and do it
properly — it is flagged over 45 minutes for a reason. It must contain, verifiably:
at least 3 sites; the literal strings "chkn strips froz", "grnd bf 80/20", and
"mozz shred lm"; at least 5 rows with no GTIN; at least 2 rows with no unit cost; the
same product at two sites under different lots; the pair "4829-B" and "LOT 4829B";
one blank quantity; and PrimeroEdge-style headers.

T016's abbreviation dictionary must be DERIVED from the strings that actually appear
in the T007 file you just wrote — not invented from imagination. Every abbreviation in
the fixture needs an entry, or the SC-005 test in T050 fails later and nobody will know
why.

Constraint: normalize.py is imported by the matcher and by the menu cascade. After this
wave it is FROZEN — a change to it later is a separate one-commit PR to main, announced
out loud. Write it to be read.

Do not add anything to requirements.txt. The seven pinned dependencies are frozen.

When the checklist gate asks about unchecked items, answer yes and proceed. The one
unchecked item is FR-044, which only affects T062 in Wave 2.

In tasks.md mark [X] only for T007, T009, T010, T011, T016, T017. Do not reformat the
file and do not touch any other task's line.

Stop when those six are done and verified. Do not continue into Phase 3 or any other
phase. Report which verification commands you ran and their actual output.
```

## → Person C, Wave 0

```
/speckit-implement
SCOPE: Wave 0, skeleton and shared contracts. Implement ONLY these tasks, in this
order: T001, T002, T003, T004, T018, W1 (below), T012, T040, T019. Do not implement,
scaffold, stub, or create files for any other task in tasks.md.

Push T001 to main IMMEDIATELY when it is done and tell the other two. They are both
blocked on the package skeleton existing.

W1 is an addition from parallel-plan.md: create pullsheet/routes/ with __init__.py,
sheet.py, ingest.py, artifacts.py, rollup.py, monitor.py — each declaring an empty
APIRouter and nothing else. Rationale: app.py is otherwise touched by sixteen tasks
across every lane in both waves, and it is the file that wires the whole demo together.
Splitting it now is the difference between three lanes running and three lanes
rebasing.

Files you may create or modify:
  the package skeleton and every __init__.py
  requirements.txt, pytest.ini, tests/conftest.py
  pullsheet/adapters/base.py
  pullsheet/routes/*
  pullsheet/provenance.py, data/PROVENANCE.md
  pullsheet/templates/base.html, pullsheet/static/app.css
  tests/unit/test_provenance.py, tests/unit/test_boundaries.py
Every other path in the repo is READ-ONLY. If a task seems to require editing a file
outside this list, stop and report it rather than editing it.

Constraints that are not negotiable:
- T002: exactly seven dependencies, pinned. Adding an eighth requires a Complexity
  Tracking row in plan.md first. Do not add one.
- T018 freezes the adapter interface. Every adapter task in Wave 1 is parallel BECAUSE
  of this file, so get the thirteen NormalizedRecord fields exactly right against
  contracts/adapter-interface.md. After this wave it is FROZEN.
- T040's provenance macro is the single place a source label is rendered. Principle V
  requires every source to carry live / dated-snapshot / hand-authored everywhere it
  appears. One macro, used everywhere — not a string copied into six templates.
- T019 must genuinely walk the AST and genuinely fail when matching/ imports adapters.
  Prove it fails: temporarily add the import, watch the test go red, remove it.

Do not write any route logic. The routers are empty shells in this wave.

When the checklist gate asks about unchecked items, answer yes and proceed. The one
unchecked item is FR-044, which only affects T062 in Wave 2.

In tasks.md mark [X] only for T001, T002, T003, T004, T012, T018, T019, T040. Do not
reformat the file and do not touch any other task's line.

Stop when those are done and verified. Do not continue into Phase 3 or any other phase.
Report which verification commands you ran and their actual output.
```

## Gate 0 — before anyone branches

C runs this on `main` and announces the result:

```bash
python -c "import pullsheet, pullsheet.db, pullsheet.adapters.base, pullsheet.matching.normalize"
python -m pullsheet.db --reset --load-fixtures && pytest --collect-only
```

Then A does T008 and C does W2 (`seed_matches.sql`), both small, both on `main`. Then branch.

---

# WAVE 1 — the MVP

```bash
git checkout main && git pull && git checkout -b feat/matcher      # A
git checkout main && git pull && git checkout -b feat/ingest       # B
git checkout main && git pull && git checkout -b feat/pull-sheet   # C
```

## → Person A, Wave 1 — `feat/matcher`

```
/speckit-implement
SCOPE: Wave 1, Lane MATCH, on branch feat/matcher. Implement ONLY these tasks:
T020, T021, T022, T023, T024, T025, T026, T027, T028, T029, T030, T031, T032, T050,
T051, T052. Do not implement, scaffold, stub, or create files for any other task.

Files you may create or modify:
  pullsheet/matching/{gate,tiers,similarity,lot,screen,run}.py
  pullsheet/recalls/{parse,corpus}.py
  tests/unit/test_{gate,similarity,lot,parse,screen,determinism,clearing_audit}.py
  tests/integration/test_abbreviations.py
READ-ONLY, do not touch: matching/normalize.py, matching/abbreviations.py,
adapters/*, routes/*, app.py, templates/*, schema.sql, requirements.txt,
tests/conftest.py. Frozen in Wave 0. If you believe one must change, stop and tell
the integrator — it becomes a separate one-commit PR to main, not an edit on this
branch.

T020 → T021 → T022 → T023 IS A STRICT SEQUENCE AND THE TESTS COME FIRST.
Write T021 and T022. RUN THEM. Show me all 11 tests FAILING with NotImplementedError
before you write a single line of decide(). Do not write the implementation and the
tests in the same step. This is the constitution's test-first requirement for the
deterministic core and it is the thing the demo claims.

T022 is the assertion the whole product rests on. Both halves are required:
(a) a property sweep over generated (inv, rec, evidence) triples — including null,
    empty, malformed, and mutually contradictory fields — asserting status is always
    in {"PULL","HELD"} and that zero inputs raise.
(b) a score sweep from 0.0 to 1.0 in 0.01 steps (101 values) on name-only evidence,
    asserting HELD at every single value.
Part (b) is what turns "there is no pull threshold" from a slogan into a testable
claim. Do not reduce the step count.

Constraints that are not negotiable:
- decide() takes no clock, no config lookup, no database handle, and no I/O. Same
  inputs, same output, always.
- score orders lines WITHIN the POSSIBLE tier. It never appears in a comparison that
  determines status or tier. There is no threshold constant anywhere in this lane.
- Every widening rule pushes toward the sheet, never away. Unparseable, missing,
  ambiguous, contradictory — all of them produce or retain a line.
- Exactly three functions in the whole repo may narrow: screen.generate_candidates,
  app.clear_match, corpus.active_records. Two of them are yours (T028, T031). Each
  carries an inline comment naming the rule, the FR id, and the covering test. T052
  asserts there is no fourth. If you find yourself writing a fourth, you have a
  design problem, not a comment problem.
- T032 (run.py) implements the match_all() declared in Wave 0. Keep gate.py pure —
  orchestration lives in run.py, not smuggled into the gate.

You depend on nothing from the other two lanes. Do not stub, mock, or reference
adapters or routes; T019 fails the build if matching/ imports adapters.

When the checklist gate asks about unchecked items, answer yes and proceed.

In tasks.md mark [X] only for your sixteen task IDs. Do not reformat the file.

Rebase onto main and hand off to the integrator at least every two hours, even
mid-lane. Stop at T052. Do not start any Wave 2 story.
```

## → Person B, Wave 1 — `feat/ingest`

```
/speckit-implement
SCOPE: Wave 1, Lane INGEST, on branch feat/ingest. Implement ONLY these tasks, in this
order: T033, T034, T035, T036, T037, T038, then T047, T048, T049. Do not implement,
scaffold, stub, or create files for any other task.

Files you may create or modify:
  pullsheet/adapters/{column_map,watched_folder,paste,spreadsheet_upload}.py
  pullsheet/main.py
  pullsheet/routes/ingest.py
  pullsheet/templates/ingest.html
  tests/adapters/*
  the ingest-persistence functions in pullsheet/db.py (APPEND ONLY — add new
  functions at the end, never edit or reorder what is already there)
READ-ONLY, do not touch: adapters/base.py, matching/*, recalls/*, app.py,
routes/ other than ingest.py, templates/base.html, schema.sql, requirements.txt.
If you believe one must change, stop and tell the integrator.

The watched folder is the demo. T033–T038 come before the paste and upload adapters
for that reason alone — all four adapters are parallel, the ordering here is demo
priority, not dependency.

Constraints that are not negotiable, all from contracts/adapter-interface.md:
- NEVER DROP A ROW. A row you cannot parse is still yielded, unreadable fields None,
  those field names listed in `unpopulated`. There is no filter, no skip, no continue
  that discards a row.
- NEVER INVENT A VALUE. No defaulting a missing quantity to 1. No inferring a unit.
  No deriving a GTIN from a description. Absent means None plus an entry in
  `unpopulated`.
- lot_code passes through VERBATIM — case, punctuation, whitespace exactly as the
  source wrote it. Normalizing lots is the matcher's job and doing it here breaks
  T025.
- raw_description is never rewritten. It is what the cafeteria manager reads on the
  printed sheet, and it has to match what they see in their own system.
- Reject loudly, not partially. An unusable source raises AdapterRejection(filename,
  row_or_column, reason), is recorded in ingest_runs, and LEAVES ANY EXISTING PULL
  SHEET INTACT. A rejected file stays in the watched folder so it is visible; only a
  successful file is archived.
- declares() must be honest. It is rendered in the UI as the adapter's field-coverage
  map, and overstating it is a Principle V violation.
- PasteAdapter is the floor and MUST NEVER RAISE. Any line at all becomes a record.

Your only call into the matcher is pullsheet.matching.run.match_all(conn), declared in
Wave 0. It raises NotImplementedError until Person A lands T032. Call it behind a
try/except that logs and continues, so your lane is never blocked. Do not implement
any matching logic yourself. Do not import anything else from pullsheet.matching —
T019 fails the build if you do.

When the checklist gate asks about unchecked items, answer yes and proceed.

In tasks.md mark [X] only for T033–T038, T047, T048, T049. Do not reformat the file.

Rebase onto main and hand off to the integrator at least every two hours, even
mid-lane. Stop at T049. Do not start any Wave 2 story.
```

## → Person C, Wave 1 — `feat/pull-sheet`

```
/speckit-implement
SCOPE: Wave 1, Lane WEB, on branch feat/pull-sheet. Implement ONLY these tasks, in
this order: T039, T041, T042, T043, T044, T045, T046. T040 is already done — do not
redo it. Do not implement, scaffold, stub, or create files for any other task.

Files you may create or modify:
  pullsheet/app.py (app construction and include_router lines ONLY — no route
    bodies; every route you write goes in routes/sheet.py)
  pullsheet/routes/sheet.py
  pullsheet/artifacts/pull_sheet.py
  pullsheet/templates/{sheet,match}.html
  pullsheet/static/print.css
  tests/unit/test_pull_sheet.py
READ-ONLY, do not touch: matching/*, adapters/*, recalls/*, routes/ other than
sheet.py, templates/base.html, static/app.css, schema.sql, db.py, requirements.txt.
If you believe one must change, it is your call as integrator — but make it a
separate one-commit PR to main and tell the other two, do not bury it in this branch.

You do not wait for the matcher. Run:
  python -m pullsheet.db --reset --load-fixtures --seed-matches
and build the entire sheet against those committed rows. You should have a correct,
printable pull sheet before decide() exists.

Constraints that are not negotiable:
- Ordering is exactly: class_rank, tier_rank, score DESC NULLS LAST, id. The trailing
  id is what makes two runs identical on ties — SC-011 depends on it, do not drop it.
- PULL and HELD are INTERLEAVED in one list, ordered by seriousness. HELD is visually
  distinct but NOT a separate section and NOT collapsed, hidden, or below a fold. A
  held item the manager does not see is an item that does not get pulled.
- T044 renders BOTH source records verbatim with the triggering substring highlighted
  on each side. This is the screen that answers "how do you know?" in Q&A. Build it
  like the demo depends on it, because it does.
- T045 prints the screening rule verbatim in the /sheet footer — the actual rule for
  what makes a pair a candidate, stated in words a nutrition director could read.
  Disclosing the one narrowing operation in the system is the point.
- T046 POST /match/{id}/clear is the single most sensitive route in the application.
  It requires a non-empty actor (400 on empty), writes a decisions row, and NEVER
  DELETES THE MATCH. A cleared line stays on the sheet, rendered as cleared-by-actor.
  It does not disappear. There is no other clearing path in the web layer.
- Use the T040 provenance macro everywhere a source is displayed. Never hand-write a
  provenance label.
- T043: print.css is a deliverable, not polish. The artifact is a sheet someone
  carries into a walk-in freezer. Every column survives Letter portrait, provenance
  labels and the capture date print, site sections break cleanly.

When the checklist gate asks about unchecked items, answer yes and proceed.

In tasks.md mark [X] only for T039, T041, T042, T043, T044, T045, T046. Do not
reformat the file.

Stop at T046. Do not start any Wave 2 story.
```

## Gate 1 — merge, then STOP AND REHEARSE

Merge order: **`feat/matcher` → `feat/ingest` → `feat/pull-sheet`.** Matcher first; the other two
only consume it.

Then on `main`, all three together, T053 and T054 — `demo_reset.sh` can only be written once all
three lanes have landed:

```bash
pytest -v && ./scripts/demo_reset.sh && ./scripts/demo_reset.sh   # twice: must be idempotent
# then physically disconnect the network:
cp data/fixtures/inventory_lincoln.csv data/watched/ && open http://localhost:8000/sheet
sudo lsof -i -a -p $(pgrep -f uvicorn)   # must be empty
```

**Rehearse the full eight minutes before anyone opens a Wave 2 branch.** You now have a complete
product. An unrehearsed superset loses to a rehearsed MVP on that clock.

---

# WAVE 2 — the stories

```bash
git checkout main && git pull && git checkout -b feat/rollup      # A
git checkout main && git pull && git checkout -b feat/menu        # B
git checkout main && git pull && git checkout -b feat/artifacts   # C
```

Fully independent — three lanes, no shared files, one coordination (B appends one loader function
to `db.py --load-fixtures`; nobody else touches that file this wave).

## → Person A, Wave 2 — `feat/rollup` (US4)

```
/speckit-implement
SCOPE: Wave 2, Lane ROLLUP (User Story 4), on branch feat/rollup. Implement ONLY
T064, T065, T066, T067, T068. Nothing else.

Files: pullsheet/rollup/{status,deadlines}.py, pullsheet/routes/rollup.py,
pullsheet/templates/rollup.html, pullsheet/static/poll.js,
tests/unit/test_{status,deadlines,freshness}.py.
Everything else READ-ONLY. Do not touch app.py, db.py, schema.sql, or any other lane's
routes file.

Constraints:
- Site status is DERIVED at read time, never stored. Storing it lets it drift out of
  date with the matches underneath, and the staleness gate then silently stops
  applying.
- A site shows `clear` only when an export for it was successfully ingested AND the
  snapshot in use is under 24 hours old. No successful ingest means `unconfirmed`, not
  `clear`. This is the asymmetry the whole product exists for: a site nobody has heard
  from is not a safe site.
- Both countdowns run from recall_records.received_at against an INJECTED now, never
  datetime.now() read inside the function. T068 injects a now 30 hours after capture
  and asserts ZERO sites report clear.
- poll.js is the only JavaScript in the project. Keep it to polling /api/status and
  re-rendering counts. No framework, no build step.

When the checklist gate asks about unchecked items, answer yes and proceed.
Mark [X] only for T064–T068. Stop at T068.
```

## → Person B, Wave 2 — `feat/menu` (US2)

```
/speckit-implement
SCOPE: Wave 2, Lane MENU (User Story 2), on branch feat/menu. Implement ONLY T055,
T056, T057, T058, T059. Nothing else.

Files: pullsheet/menu/{cascade,substitute}.py, pullsheet/routes/menu.py,
pullsheet/templates/menu.html, tests/integration/test_menu_cascade.py, and ONE
appended loader function in pullsheet/db.py for T055 — append at the end of the file,
never edit or reorder what is already there. You are the only lane touching db.py this
wave.
Everything else READ-ONLY.

Constraints:
- Join recipe ingredients to inventory through matching/normalize.py — the SAME
  normalization the matcher uses. Do not write a second one. One code path, so a
  recalled item traverses to recipes the same way it matched in the first place.
- Affected meal count sums service_days.planned_meals and nothing else. It is PLANNED,
  never measured, and the UI says so. Do not estimate, extrapolate, or interpolate.
- Substitution is SET CONTAINMENT over recipe_components. Propose a substitute only
  when the candidate's component set contains the broken recipe's. When nothing
  qualifies, say so plainly and name the component that cannot be covered. "No
  substitute exists" is a proof, not a shrug — and the fixtures deliberately contain a
  recipe with no viable substitute so that this path is demonstrable. Never guess a
  substitute to avoid an empty state.

When the checklist gate asks about unchecked items, answer yes and proceed.
Mark [X] only for T055–T059. Stop at T059.
```

## → Person C, Wave 2 — `feat/artifacts` (US3)

```
/speckit-implement
SCOPE: Wave 2, Lane ARTIFACTS (User Story 3), on branch feat/artifacts. Implement ONLY
T060, T061, T062, T063. Nothing else.

Files: pullsheet/artifacts/{hold_record,credit_claim,state_report}.py,
pullsheet/routes/artifacts.py, pullsheet/templates/artifacts/*,
tests/integration/test_artifacts.py.
Everything else READ-ONLY.

Constraints:
- Every dollar figure is plain quantity × unit_cost in readable Python. No expression
  a team member cannot evaluate out loud under questioning.
- T061: rows with a NULL unit cost are EXCLUDED from the dollar total and LISTED
  SEPARATELY as quantity-only, with the claim stating on its face that it does so. The
  fixtures deliberately omit at least two unit costs. Silently treating a missing cost
  as zero would understate a real claim, and that is the failure mode this task exists
  to prevent.
- T062: FR-044 is the one open clarification in the spec — which state's report to
  pre-fill. Interim default: model it on USDA FNS guidance as a generic district
  report and label it hand-authored. Every derivable field pre-filled; every
  non-derivable field VISIBLY marked as requiring human entry. Do not invent a value
  to fill a blank.
- T063: apply the T040 provenance macro to all four artifacts. These are documents a
  district files with a state agency. Nothing hand-authored may appear without its
  label (Principle V).

When the checklist gate asks about unchecked items, answer yes and proceed — the
unchecked item is FR-044, which is exactly the T062 question above, and the interim
default resolves it for this build.
Mark [X] only for T060–T063. Stop at T063.
```

---

# WAVE 3 — Converge (all three on `main`)

No prompts, no branches. Split T076 (twelve edge cases) three ways — four each, one test file
section per person, coordinate the filename once. Then T073, T074, T077, T078, T079 to whoever is
free, and T080 together.

**T080 is a merge gate, not a nicety.** Every person opens every file they did not write and
explains it aloud. Anything nobody present can explain gets rewritten until someone can. That is
Principle VI, and it is also the last cheap chance to find out that one of you does not understand
the thing a judge is about to ask about.

Re-run `./scripts/demo_reset.sh` and the network-off rehearsal after every merge in this wave.

**Cut order under time pressure**: T075 (email adapter) → US5 monitor → US4 roll-up.
**Never cut**: T012, T022, T052, T053, T054, or the rehearsals.
