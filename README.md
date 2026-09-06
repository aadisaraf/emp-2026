# PullSheet

A food recall lands. Somewhere in three school kitchens there are cases of the
recalled product, and the district has 24 hours to notify its distributor and 48
to finish the inventory assessment. Today that means a nutrition director
reading a PDF notice against a spreadsheet, by hand, per building.

PullSheet turns an inventory export into a printed pull sheet, unattended, with
no network.

**The design rule the whole thing is arranged around:** under-pulling risks a
child; over-pulling wastes a case of tomatoes. So every rule widens, and nothing
in the codebase can clear a line by itself. `matches.status` has exactly two
values, `PULL` and `HELD`, enforced by a `CHECK` constraint — an automatically
cleared item is not merely forbidden, it is *unrepresentable*.

---

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
./scripts/demo_reset.sh
```

## Run

```bash
.venv/bin/python -m pullsheet.main --port 8000
```

One command, one process: the web app **and** the folder poller. Starting
uvicorn against `pullsheet.app:app` directly serves the site but does not poll
`data/watched/`, so the unattended path would silently never fire.

Then, in another terminal:

```bash
cp data/fixtures/inventory_lincoln.csv data/watched/
```

Open `http://localhost:8000`. Within one poll interval the sheet exists.
**No network is required at any point**, and the file moves itself to
`data/archive/`.

## Tests

```bash
.venv/bin/python -m pytest -q
```

430 tests. The full validation walkthrough is
[specs/001-recall-pull-sheet/quickstart.md](specs/001-recall-pull-sheet/quickstart.md).

---

## What it does

| Screen | What it answers |
|---|---|
| `/` | Every building on the roster, one status word each, both USDA clocks, new alerts |
| `/sheet` | The pull sheet: what to pull, where it is, and why — PULL and HELD interleaved |
| `/match/{id}` | Both source records verbatim, with the triggering substring on each side |
| `/menu` | Which meals just became impossible, on which dates, for how many children |
| `/artifacts/hold/{site}` | Custody record, signature fields blank |
| `/artifacts/credit-claim` | Quantity × unit cost, itemized, nothing estimated |
| `/artifacts/state-report` | Derived fields filled; everything else marked, not blank |
| `/sources` | Every source, its provenance label, and what each adapter can honestly read |

Current numbers against the committed fixtures: **56 inventory rows across 3
sites, 889 lines, 42 PULL / 847 HELD**, matched against 1,000 openFDA records
and 12 hand-authored FSIS records.

---

## The 8-minute demo

Rehearse with the network physically off. The freshness banner will be showing;
that is intended behaviour worth narrating, not apologising for.

| Min | Screen | Beat |
|---|---|---|
| 0:00 | — | The problem: a Class I recall, three kitchens, a 24-hour clock, and a PDF |
| 0:45 | `/` | Two buildings read **unconfirmed** before anything happens. Silence is visible |
| 1:30 | terminal | `cp data/fixtures/inventory_lincoln.csv data/watched/` — then don't touch anything |
| 2:00 | `/sheet` | 42 lines to pull, grouped by site, Class I first. Nobody clicked anything |
| 3:00 | `/match/{id}` | Pick a line. Both records verbatim, the matching substring highlighted on each side |
| 4:00 | `/sheet` | Scroll to a HELD line. Explain why it is *held* and not cleared |
| 5:00 | `/menu` | 5,390 planned meals across 10 service days. One meal has a substitute; the rest name the component that makes it impossible |
| 6:00 | `/artifacts/credit-claim` | $8,862.50 over 24 of 27 lines. Three are quantity-only and named |
| 7:00 | `/artifacts/state-report` | 10 fields derived, 13 marked `REQUIRES HUMAN ENTRY` with the reason |
| 7:30 | `/` | Both clocks running from when *this district* saw the recall |

### The hostile questions, and the screen that answers each

| Question | Screen | Answer |
|---|---|---|
| "How do I know it didn't miss something?" | `/sheet` | You don't, and neither do we — that is why 847 lines are HELD rather than discarded. Nothing is cleared without a name attached |
| "So it just flags everything?" | `/match/{id}` | Every line names the evidence that produced it. 42 pull; the rest are held for a human, ordered so the strongest evidence is first |
| "What if the description is worded differently?" | `/sources` | Both sides are the same distributor-catalog dialect. Supplier identity, not text, is the primary channel: `recalling_firm` is populated on 100% of the corpus, and 50 of 56 inventory rows carry no barcode |
| "Did you make the data up?" | `/sources` | Some of it, and it says so. Three labels, and the FSIS corpus is `hand-authored` because FSIS returns HTTP 403 to programmatic requests |
| "What if the recall feed is down?" | `/` → Refresh recalls | It falls back to the cached snapshot and tells you its age. There is no error page on that path |
| "What if your data is stale?" | `/` | No site may report **clear**, and the reason names the capture date and age. The lines themselves are unchanged — staleness gates one word, not the matcher |
| "What if the recall gets cancelled?" | `/sheet` | The line stays, marked *terminated (was active)*. Removing it would be clearing, and clearing is a human action |
| "Can it be wrong about a price?" | `/artifacts/credit-claim` | It can only be wrong about a price it was given. Lines without one appear quantity-only and are named as excluded |

---

## How it is put together

```
pullsheet/
  adapters/     the only boundary to the outside world. Never drops a row,
                never invents a value
  matching/     screen -> evidence -> gate. gate.decide() is a pure function
                and contains no threshold of any kind
  menu/         cascade to service days; substitution by set containment
  artifacts/    pull sheet, hold record, credit claim, district report
  rollup/       one status word per site, two USDA clocks
  recalls/      corpus loading, code parsing, refresh, amendment
```

Python 3.12, FastAPI, Jinja2, SQLite via `sqlite3` with hand-written SQL. No
ORM. ~5,100 lines of application code, ~3,900 lines of tests.

### Three claims worth checking rather than believing

1. **Nothing clears itself.** `tests/unit/test_clearing_audit.py` walks every
   function in the package and asserts there are exactly three justified
   narrowing paths, that each names a requirement and a covering test, and that
   no fourth exists. It prints them.
2. **There is no pull threshold.** The same file parses `gate.py` and asserts
   no comparison anywhere in it involves a score. Tiering is an evidence ladder,
   not a number.
3. **Nothing is ever deleted.** No table has a delete path. Supersession,
   amendment, and clearing are all new rows or status columns, so a pull sheet
   can be reconstructed as it stood at any moment.

---

## Ownership

Constitution Principle VI requires that every file has a named owner who has
read it and can explain it aloud, and that any file nobody present can explain
is rewritten or deleted **before** the demo.

**This gate has not been satisfied.** It cannot be satisfied by writing a table;
it is satisfied by people reading code out loud to each other. The table below
is the checklist for that session, not a record of it having happened.

| Area | Files | Lines | Owner | Explained |
|---|---|---|---|---|
| `matching/` — the gate, ladder, screening | 9 | 1,176 | _unassigned_ | ☐ |
| `adapters/` — ingestion boundary | 7 | 725 | _unassigned_ | ☐ |
| `app.py` — routes | 1 | 541 | _unassigned_ | ☐ |
| `db.py` + `schema.sql` — persistence | 2 | 631 | _unassigned_ | ☐ |
| `artifacts/` — the four printed artifacts | 5 | 482 | _unassigned_ | ☐ |
| `menu/` — cascade and substitution | 3 | 361 | _unassigned_ | ☐ |
| `recalls/` — corpus, parsing, refresh, amendment | 5 | 613 | _unassigned_ | ☐ |
| `rollup/` + `monitor.py` — status, clocks, standing diff | 4 | 356 | _unassigned_ | ☐ |
| `provenance.py` — the source labels | 1 | 116 | _unassigned_ | ☐ |

Start with `matching/gate.py` and `schema.sql`. Between them they hold every
claim the demo makes, and they are the two files three minutes of hostile
questioning will actually go after.

## Provenance

Every source carries one of three labels — `live`, `dated-snapshot`, or
`hand-authored` — on screen and on paper. The full table is
[data/PROVENANCE.md](data/PROVENANCE.md), and `/sources` renders the same data
from the same dictionary so the two cannot drift.

**The FSIS corpus is hand-authored.** FSIS returns HTTP 403 to programmatic
requests, so those records could not be fetched or verified against published
notices. They were written by the build team in FSIS notice format and are
labeled as such everywhere they appear. Presenting them as sourced data would be
the single most damaging thing this project could do.
