---
description: "Branch and ownership plan — how a small team builds PullSheet's 80 tasks concurrently"
---

# Parallel Build Plan: PullSheet

**Companion to**: [tasks.md](./tasks.md) · [plan.md](./plan.md) · [constitution](../../.specify/memory/constitution.md)

`tasks.md` has eight phases, sequenced by **dependency and demo priority**. That is the right
order for one person and the wrong axis for four. Phases 3 through 8 each assume the previous
phase has landed; hand four people four phases and three of them are blocked immediately.

This document re-cuts the same 80 tasks along a second axis: **file ownership**. Two people are
parallel when no file appears in both their task lists. Everything below follows from that one
rule.

> **This team is three people.** The waves, lanes, and ownership map below are the general
> structure; **[The three-person build](#the-three-person-build) is the operative assignment** —
> named roles, hour by hour, with the one story to cut. Read that section, then keep the
> [file ownership map](#file-ownership-map) open while you work.

---

## The shape: three waves, not eight phases

```
WAVE 0 — Foundation            all hands, on main, no branches      ~90 min
  the shared surface everything imports: skeleton, schema, fixtures,
  normalize, adapter interface, base template
              │
              ▼   MERGE GATE 0 — main is importable and tests collect
WAVE 1 — MVP (US1)             3 lanes, 3 branches                  ~6-8 h
  MATCH ──────┐
  INGEST ─────┼── independent, no shared files
  WEB ────────┘
              │
              ▼   MERGE GATE 1 — demo_reset + network-off rehearsal
                  ★ STOP AND REHEARSE. This is a complete product.
WAVE 2 — Stories (US2-US5)     4 lanes, 4 branches                  ~4-6 h
  MENU ───────┐
  ARTIFACTS ──┼── independent, no shared files
  ROLLUP ─────┤
  MONITOR ────┘
              │
              ▼   MERGE GATE 2 — full suite + rehearsal again
WAVE 3 — Converge              all hands, on main                   ~3 h
  edge cases, quickstart, README, ownership pass, final rehearsals
```

Wave boundaries are **hard**. Nobody starts Wave 1 before Gate 0 is merged, because every Wave 1
lane imports something Wave 0 produces. Within a wave, lanes never block each other.

---

## Wave 0 — Foundation (everyone on `main`)

No branches. Four people, four disjoint file sets, pushing straight to `main`. This wave exists to
produce the shared surface *once*, so that nothing in Wave 1 has to touch it.

| Who | Tasks | Files produced |
|---|---|---|
| **A — data** | T005 → T006 → T008 | `recalls/snapshots/*.json`, `expected_matches.json` |
| **B — fixtures** | T007 (split by site) → T009 → T010 → T011 | `data/fixtures/*`, `tests/adapters/fixtures/*` |
| **C — storage** | T001 → T013 → T014 → T015 | `schema.sql`, `db.py`, package skeleton |
| **D — contracts** | T002, T003, T004 → T018 → T019 → T012 | `requirements.txt`, `adapters/base.py`, `provenance.py` |

Then, once B's fixture exists: **T016 → T017** (abbreviations, then normalize). Whoever is free.

**Do T005 first, before anything else.** It is the only task in the entire build that requires the
network. If the venue wifi is going to fail, it should fail while you still have hours to react.

Pull these forward into Wave 0 even though `tasks.md` lists them later — every Wave 1 lane needs
them and they are small:

- **T040** (`templates/base.html`, `static/app.css`, the provenance macro). Every template extends
  this. If it lands in Wave 1 the other two lanes rebase around it all day.
- **W1–W4** below.

### Gate 0 — merge criteria

```bash
python -c "import pullsheet, pullsheet.db, pullsheet.adapters.base, pullsheet.matching.normalize"
python -m pullsheet.db --reset --load-fixtures && pytest --collect-only
```

Imports clean, database builds, tests collect. Nobody branches until this passes on `main`.

---

## Four structural additions

These are not new product scope. They are the changes that make concurrent work possible, and
without them three lanes serialize on two files. They belong in Wave 0.

- [ ] **W1** Split routes into a router package: `pullsheet/routes/{__init__,sheet,ingest,artifacts,rollup,monitor}.py`, each an `APIRouter`. `app.py` shrinks to app construction plus one `include_router` line per module and never changes again.
  **Why**: `app.py` is otherwise touched by T039, T044, T046, T047, T048, T049, T058, T060, T061, T062, T066, T067, T070, T071, T073, T074 — sixteen tasks across every lane in both waves. It is the single largest merge hazard in the build. **Verify**: `grep -c include_router pullsheet/app.py` → 6, and `wc -l pullsheet/app.py` → under 40.
  **Cost, stated honestly**: one more directory for Principle VI's ownership pass. Worth it. The alternative is every lane rebasing on `app.py` all day, and a three-way conflict in the file that wires the whole demo together, at hour 20.

- [ ] **W2** Commit `data/fixtures/seed_matches.sql` — twenty hand-written `matches` rows against the T007 inventory and the T005 snapshot, spanning all three tiers, both statuses, and at least two sites. Add `--seed-matches` to `db.py`.
  **Why**: it is the seam stub that unblocks the WEB lane. Without it, WEB cannot render a sheet until MATCH finishes, and the two lanes serialize. **Verify**: `python -m pullsheet.db --reset --load-fixtures --seed-matches && sqlite3 data/pullsheet.db 'select tier,status,count(*) from matches group by 1,2'` → rows in all three tiers.

- [ ] **W3** Declare `pullsheet/matching/run.py::match_all(conn) -> int` in Wave 0 raising `NotImplementedError`, and have INGEST call it behind a try/except that logs and continues.
  **Why**: this is the one call INGEST makes into MATCH. Fixing the signature early means the two lanes never negotiate again. **Verify**: `grep -n "match_all" pullsheet/matching/run.py pullsheet/adapters/watched_folder.py` → declared in one, called in the other.

- [ ] **W4** Write `docs/OWNERSHIP.md` — the table below, committed, so the rule is in the repo rather than in someone's memory.
  **Verify**: every path in `pullsheet/` appears in exactly one row.

---

## Wave 1 — the MVP, three lanes

Branch from `main` at Gate 0. **This wave is the product.** If everything after it is cut you still
have a complete demo.

### Lane MATCH — `feat/matcher`

The safety-critical core. One person minimum, two after T023.

**Tasks**: T020 → T021 → T022 → T023 (strict, test-first, tests seen failing) → T024/T025/T026 in
parallel → T027 → T028 → T029 → T030 → T031 → T032 → T050, T051, T052.

**Owns**: `pullsheet/matching/*` (except `normalize.py`, `abbreviations.py` — frozen in Wave 0),
`pullsheet/recalls/parse.py`, `pullsheet/recalls/corpus.py`, `tests/unit/test_{gate,similarity,lot,parse,screen,determinism,clearing_audit}.py`, `tests/integration/test_abbreviations.py`.

**Touches no route, no template, no adapter.** T019 enforces the adapter half of that boundary as
a test — this lane cannot import `adapters` even by accident.

**Demoable alone**: `pytest tests/unit -v` plus `python -m pullsheet.matching.run --explain` printing
tier, status, and both triggering substrings for every match. That output *is* the Q&A answer.

### Lane INGEST — `feat/ingest`

**Tasks**: T033 → T034 → T035 → T036 → T037 → T038, then T047, T048, T049 in parallel.

**Owns**: `pullsheet/adapters/*` (except `base.py`), `pullsheet/main.py`, `pullsheet/routes/ingest.py`,
`templates/ingest.html`, `tests/adapters/*`.

**Depends on MATCH for exactly one symbol**: `run.match_all`, stubbed by W3. Nothing else.

**Demoable alone**: drop a CSV into `data/watched/`, then
`sqlite3 data/pullsheet.db 'select count(*) from inventory_records'` climbs and the file appears in
`data/archive/`. Drop `malformed.csv` and it stays put with a row in `ingest_runs`.

### Lane WEB — `feat/pull-sheet`

**Tasks**: T039 → T041 → T042 (split) → T043 → T044 → T045 → T046.

**Owns**: `pullsheet/app.py`, `pullsheet/routes/sheet.py`, `pullsheet/artifacts/pull_sheet.py`,
`templates/{sheet,match}.html`, `static/print.css`.

**Depends on MATCH for nothing** — it reads `matches` rows, which W2 seeds.

**Demoable alone**: `--seed-matches`, open `/sheet`, print to PDF. A correct, printable pull sheet
built entirely from committed rows, before the matcher exists.

### Gate 1 — merge criteria

Merge order: **MATCH → INGEST → WEB.** Matcher first because the other two only consume it.

Then, on `main`, together: **T053** (`demo_reset.sh` — it can only be written once all three lanes
have landed) and **T054** (network-off rehearsal, everyone watching).

```bash
pytest -v && ./scripts/demo_reset.sh && ./scripts/demo_reset.sh   # twice: idempotent
# unplug the network, then:
cp data/fixtures/inventory_lincoln.csv data/watched/ && open http://localhost:8000/sheet
```

**Stop here and rehearse the full eight minutes before anyone starts Wave 2.** An unrehearsed
superset loses to a rehearsed MVP on an eight-minute clock.

---

## Wave 2 — the stories, four lanes

Four branches off `main` at Gate 1. These are genuinely independent of one another — each reads
US1's match rows and writes only its own files.

| Lane | Branch | Tasks | Owns |
|---|---|---|---|
| **MENU** (US2) | `feat/menu` | T055–T059 | `pullsheet/menu/*`, `routes/menu.py`, `templates/menu.html` |
| **ARTIFACTS** (US3) | `feat/artifacts` | T060–T063 | `artifacts/{hold_record,credit_claim,state_report}.py`, `routes/artifacts.py`, `templates/artifacts/*` |
| **ROLLUP** (US4) | `feat/rollup` | T064–T068 | `pullsheet/rollup/*`, `routes/rollup.py`, `templates/rollup.html`, `static/poll.js` |
| **MONITOR** (US5) | `feat/monitor` | T069–T072 | `pullsheet/monitor.py`, `routes/monitor.py`, `templates/_alerts.html` |

Two coordinations, and only two:

1. **T055 edits `db.py --load-fixtures`.** MENU appends one function; nobody else touches that file
   in Wave 2. Append, never interleave.
2. **MONITOR renders alerts on `/`, which ROLLUP owns.** MONITOR writes `templates/_alerts.html`;
   ROLLUP adds the single `{% include '_alerts.html' %}` line. Agree the filename at wave start and
   never speak of it again.

`tasks.md` claims Phases 4–7 have "zero shared files." With W1's routers that is now true. Without
them it was not — all four wanted `app.py`.

---

## File ownership map

The merge-conflict table. A file belongs to exactly one lane per wave.

| Path | Wave 0 | Wave 1 | Wave 2 |
|---|---|---|---|
| `schema.sql`, `db.py` | C | *frozen* — INGEST appends persistence only | MENU appends loader only |
| `adapters/base.py`, `provenance.py` | D | *frozen* | *frozen* |
| `matching/normalize.py`, `abbreviations.py` | C/D | *frozen* | *frozen* |
| `templates/base.html`, `static/app.css` | D | *frozen* | *frozen* |
| `app.py` | W1 | WEB (untouched after) | *frozen* |
| `requirements.txt`, `pytest.ini`, `tests/conftest.py` | D | *frozen* | *frozen* |
| `matching/*`, `recalls/*` | — | MATCH | — |
| `adapters/*`, `main.py` | — | INGEST | — |
| `routes/sheet.py`, `artifacts/pull_sheet.py` | — | WEB | — |
| `routes/{menu,artifacts,rollup,monitor}.py` | — | — | one lane each |

**Frozen means frozen.** A change to a frozen file is a separate one-commit PR to `main`, announced
out loud, merged immediately, and everyone rebases. It never rides inside a lane branch — that is
how you get a three-way conflict in `schema.sql` at hour 19.

Lanes add pytest fixtures to `tests/<area>/conftest.py`, never to the root `tests/conftest.py`.

---

## Branch discipline

- **`main` is always demo-able.** That is the whole point of the wave gates. At any moment someone
  should be able to check out `main`, run `./scripts/demo_reset.sh`, and present.
- **Merge to `main` at least every two hours**, even mid-lane. Long-lived branches are how a
  24-hour build turns into a 20-hour build and a 4-hour merge.
- **One integrator owns `main`** for the whole build and runs every merge. Not a bottleneck at this
  size — it is the person who notices at hour 12 that two lanes both quietly added a `utils.py`.
- **Rebase onto `main` before opening a merge**, never merge `main` into a lane. Keeps history
  readable enough to explain under questioning (Principle VI).
- **Every merge runs `pytest -v` and `./scripts/demo_reset.sh`.** Red suite, no merge.

---

## The three-person build

Three is the natural size: Wave 1 has exactly three lanes. Take one each, keep it for the whole
build, and let each person's Wave 2 story follow the muscle memory they built in Wave 1.

| | Role | Owns for 24 hours | Fields these questions on stage |
|---|---|---|---|
| **M** | **Matcher** | `matching/`, `recalls/`, the gate tests | "How do you know it caught everything?" |
| **I** | **Pipes** | `adapters/`, `main.py`, ingestion | "Our export doesn't look like that." |
| **S** | **Surface** | `app.py`, `routes/`, templates, print CSS | "Show me the sheet." |

**S is also the integrator** — owns `main`, runs every merge, and is the one who notices when two
lanes both quietly add a `utils.py`. S is already reading everyone's output to render it.

---

### Wave 0 — foundation (~2 hours, all three, on `main`)

The first forty minutes are deliberately serial. Do not skip them: they are what makes the
following twenty hours parallel.

| Time | M | I | S |
|---|---|---|---|
| 0:00 | **T005**, all three watching | | |
| 0:05 | Read the snapshot together. Pick the ~12 recall records the inventory fixture will correspond to | | |
| 0:20 | **T007**, one site each (≈17 rows). S owns the file; M and I hand over rows | | |
| 0:45 | T006 (FSIS ⚠️) | T001 → T002, T003, T004 | T013 → T014 |
| 1:15 | T016 → T017 | T018 → T019 | T015 → T012 |
| 1:45 | T008 | T011, then T009/T010 | T040, **W1**, **W2**, **W3** |

Two things about that table are load-bearing.

**T005 goes first, at minute zero, with everyone watching.** It is the only task in the build that
needs the network. If the venue wifi is going to fail, it fails while you have twenty-two hours to
react instead of two.

**T007 is written by all three at once, before anyone splits up.** It is flagged over 45 minutes
and it blocks T008 and T016, which block the entire matcher. Three people writing seventeen rows
each takes twenty minutes. One person writing fifty takes an hour, and the other two wait. Author
it *from* the snapshot you just captured — pick inventory rows that deliberately correspond to
real recall records, and T008's correspondence map falls out of the work you already did.

**Gate 0**: `python -m pullsheet.db --reset --load-fixtures && pytest --collect-only` clean on `main`.
Now branch.

---

### Wave 1 — the MVP (~10 hours, three branches)

| | Branch | Tasks |
|---|---|---|
| **M** | `feat/matcher` | T020 → T021 → T022 → T023 (test-first, seen failing) → T024/T025/T026 → T027 → T028 → T029 → T030 → T031 → T032 |
| **I** | `feat/ingest` | T033 → T034 → T035 → T036 → T037 → T038, then T047, T048, T049 |
| **S** | `feat/pull-sheet` | T039 → T041 → T042 (⚠️, split) → T043 → T044 → T045 → T046 |

The lanes are not the same length. **M's lane is roughly a third longer than the other two** —
thirteen tasks against nine and seven, and the three strictly-ordered gate tasks at the front
cannot be parallelized away. Plan for that rather than discovering it at hour fourteen:

- **When I finishes ingestion, I takes T050, T051, T052** — the three proof tests. They live in
  their own files (`test_determinism.py`, `test_clearing_audit.py`, `test_abbreviations.py`), so I
  can write them against `matching/` while M is still implementing it. No conflict, and the person
  writing the audit is not the person who wrote the code being audited, which is worth something
  when a judge asks.
- **When S finishes the sheet, S takes T053** (`demo_reset.sh`) and starts T079 (README and the
  eight-minute demo script). Writing the demo script early is what turns "we built a thing" into a
  rehearsed eight minutes.

**Gate 1**: merge **M → I → S**. Then T053 and **T054 network-off, all three watching**.

**Stop and rehearse the full eight minutes here.** You now have a complete product. Everything
after this point is upside, and none of it is worth an unrehearsed demo.

---

### Wave 2 — three stories, drop one (~5 hours)

| | Branch | Story | Tasks | Why this person |
|---|---|---|---|---|
| **M** | `feat/menu` | US2 menu cascade | T055–T059 | Set containment and normalization — the same machinery, and the most differentiated feature you have |
| **S** | `feat/artifacts` | US3 compliance artifacts | T060–T063 (T062 ⚠️) | Already owns print CSS and the templates |
| **I** | `feat/rollup` | US4 roll-up and clocks | T064–T068 | Already owns the poll loop; consumes the `/api/status` S built at T039 |

**Cut US5 (standing monitor).** It is P5, it is the hardest of the five to show live because it is
a schedule rather than a screen, and at three people it is the honest thing to drop. Say in the
demo that it is designed and not built — Principle V applies to features as much as to data.

One thing to fix in Wave 1 so this cut stays cheap: **have S make `GET /` redirect to `/sheet`**
rather than render a placeholder. Then if US4 also slips, the landing page is still a real screen
instead of a stub with the room watching.

**Gate 2**: `pytest -v` green, `./scripts/demo_reset.sh` twice, network-off rehearsal again.

---

### Wave 3 — converge (~4 hours, all three)

- **T076** (⚠️, twelve edge cases) — four each. They are independent tests in one file; agree on
  test-function names up front and append, never interleave.
- **T077** amendment and termination handling → M.
- **T078** quickstart V1–V10 and **T079** README and demo script → S.
- **T080 ownership pass — all three, and it is a gate, not a nicety.** Every person opens every
  file they did not write and explains it aloud. Anything nobody present can explain gets rewritten
  or deleted. At three people this takes about an hour and it is the single highest-value hour in
  Wave 3, because it is a dress rehearsal for the questions.

---

### On stage

Eight minutes and three minutes of hostile Q&A, three people:

- **S drives and narrates.** They built every screen in the room.
- **M takes every question about the matcher, the hold gate, and "how do you know it didn't miss
  something."** T022 and T052 are the answers, and M wrote them.
- **I takes every question about "our data doesn't look like that."** T018's interface and the four
  header fixtures are the answer.

That mapping is not a presentation trick — it is Principle VI holding up under pressure. The
person who wrote the code answers the question about the code. Rehearse it at least four times,
two of them with the network physically off, and at least once with the other two playing hostile.

---

## Cut order, unchanged

Under time pressure: cut T075 (email adapter) → US5 → US4 → US3.

**Never cut T012, T022, T052, T053, T054, T080, or Gate 1's rehearsal.** Those are what the
constitution is for, and they are what three minutes of hostile questioning will actually go after.
