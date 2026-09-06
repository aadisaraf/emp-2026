# PullSheet

A food recall lands. Somewhere in the walk-in there are cases of the recalled
product, and the kitchen has 24 hours to notify its distributor and 48 to finish
the inventory assessment. Today that means someone reading a PDF notice against
a spreadsheet, by hand.

PullSheet turns an inventory export into a printed pull sheet, unattended, with
no network. **One deployment is one location** — a school kitchen, or equally a
restaurant. The location's software already writes a scheduled export; PullSheet
reads it over SFTP or email every day and finalizes a dated run. Nobody logs
into anything on an ordinary morning; what a person opens is the result.

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

## Dashboard

`web/` is a Next.js front end over the same data, and it is what a manager
opens. It reads `/api/v1` and writes nothing of its own: a decision it records
goes through the same two named routes as the server-rendered pages, so there is
still exactly one place in the system that can clear a line.

```bash
cd web && npm install && npm run dev
```

Open `http://localhost:3000`, with the Python process still running on 8000.
Point it elsewhere with `NEXT_PUBLIC_API_BASE`.

The Jinja app on :8000 stays. It is the printable, addressable fallback, and it
is the one that runs when nothing else does.

## Tests

```bash
.venv/bin/python -m pytest -q
```

443 tests. The full validation walkthrough is
[specs/001-recall-pull-sheet/quickstart.md](specs/001-recall-pull-sheet/quickstart.md).

---

## What it does

**The recall picture** — the main section:

| Screen | What it answers |
|---|---|
| `/` | Today: one status word with the reason behind it, both USDA clocks, what is new since the last run |
| `/sheet` | The pull sheet: what to pull, where it is, and why — PULL and HELD interleaved |
| `/sheet/{run_id}` | Any past day, exactly as it was printed — its own counts, its own corpus |
| `/runs` | Every run: date, channel, delivery, counts, outcome |
| `/match/{id}` | Both source records verbatim, with the triggering substring on each side |

**What was affected** — the separate section:

| Screen | What it answers |
|---|---|
| `/impact` | The money always; which meals became impossible, on which dates, for how many children where the location runs a meal program |
| `/artifacts/hold` | Custody record, signature fields blank |
| `/artifacts/credit-claim` | Quantity × unit cost, itemized, nothing estimated |
| `/artifacts/state-report` | Derived fields filled; everything else marked, not blank |
| `/sources` | Every channel and corpus, its provenance label, and what each adapter can honestly read |

Current numbers against the committed fixtures: **56 export rows merging to 54
records, 856 lines, 42 PULL / 814 HELD**, matched against 1,000 openFDA records
and 12 hand-authored FSIS records.

---

## The 8-minute demo

Rehearse with the network physically off. The freshness banner will be showing;
that is intended behaviour worth narrating, not apologising for.

| Min | Screen | Beat |
|---|---|---|
| 0:00 | — | The problem: a Class I recall, one kitchen, a 24-hour clock, and a PDF |
| 0:45 | `/` | Before anything happens the page reads **no inventory has ever been received** — not "clear". Silence is visible |
| 1:30 | terminal | `cp data/fixtures/inventory_lincoln.csv data/watched/` — then don't touch anything |
| 2:00 | `/sheet` | The tab reloads itself. 42 lines to pull, grouped by storage location, Class I first. Nobody clicked anything |
| 3:00 | `/match/{id}` | Pick a line. Both records verbatim, the matching substring highlighted on each side |
| 4:00 | `/sheet` | Scroll to a HELD line. Explain why it is *held* and not cleared |
| 5:00 | `/impact` | 2,050 planned meals across 5 service days. Nine menu items break: four get a substitute, and the other five *prove* there is none by naming the component nothing clean in the kitchen supplies |
| 6:00 | `/artifacts/credit-claim` | $8,862.50 over 24 of 27 lines. Three are quantity-only and named |
| 6:45 | `/artifacts/state-report` | 11 fields derived, 13 marked `REQUIRES HUMAN ENTRY` with the reason |
| 7:15 | `/runs` | Drop a second export. A new run appears; yesterday's page is still yesterday's |
| 7:45 | `/` | Both clocks running from when *this kitchen* saw the recall |

### The hostile questions, and the screen that answers each

| Question | Screen | Answer |
|---|---|---|
| "How do I know it didn't miss something?" | `/sheet` | You don't, and neither do we — that is why 814 lines are HELD rather than discarded. Nothing is cleared without a name attached |
| "So it just flags everything?" | `/match/{id}` | Every line names the evidence that produced it. 42 pull; the rest are held for a human, ordered so the strongest evidence is first |
| "What if the description is worded differently?" | `/sources` | Both sides are the same distributor-catalog dialect. Supplier identity, not text, is the primary channel: `recalling_firm` is populated on 100% of the corpus, and 50 of 56 inventory rows carry no barcode |
| "Did you make the data up?" | `/sources` | Some of it, and it says so. Three labels, and the FSIS corpus is `hand-authored` because FSIS returns HTTP 403 to programmatic requests |
| "What if the recall feed is down?" | `/` → Refresh recalls | It falls back to the cached snapshot and tells you its age. There is no error page on that path |
| "What if your data is stale?" | `/` | The status word says the corpus is stale instead of saying nothing was found, and names the capture date and age. Every line is byte-identical either way — staleness gates one word, not the matcher |
| "What if today's export doesn't arrive?" | `/` | It says the last run is old and how old. It does not present yesterday's sheet as today's answer |
| "What if an item drops off one export?" | `/sheet` | It stays. The matcher reads the active inventory, not one run's rows, so inventory is superseded by a later export and never by silence |
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
  artifacts/    pull sheet, hold record, credit claim, state report
  runs.py       one status word for the location, run history, new-since diff
  deadlines.py  two USDA clocks, injected now -- never the wall clock
  location.py   the single location record: name, type, meal program or not
  recalls/      corpus loading, code parsing, refresh, amendment
```

Python 3.12, FastAPI, Jinja2, SQLite via `sqlite3` with hand-written SQL. No
ORM. ~4,700 lines of application code, ~4,450 lines of tests, plus a ~9,300-line
Next.js front end in `web/`.

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
| `matching/` — the gate, ladder, screening | 9 | 887 | _unassigned_ | ☐ |
| `api.py` — the JSON surface the dashboard reads | 1 | 691 | _unassigned_ | ☐ |
| `db.py` + `schema.sql` — persistence, runs, supersession | 2 | 634 | _unassigned_ | ☐ |
| `app.py` — routes | 1 | 578 | _unassigned_ | ☐ |
| `recalls/` — corpus, parsing, refresh, amendment | 5 | 544 | _unassigned_ | ☐ |
| `adapters/` — ingestion boundary | 6 | 522 | _unassigned_ | ☐ |
| `artifacts/` — the four printed artifacts | 5 | 420 | _unassigned_ | ☐ |
| `menu/` — cascade and substitution | 3 | 265 | _unassigned_ | ☐ |
| `runs.py` + `deadlines.py` + `location.py` — status word, clocks, the location record | 3 | 198 | _unassigned_ | ☐ |
| `provenance.py` — the source labels | 1 | 98 | _unassigned_ | ☐ |
| `main.py` + `match.py` — the watcher and the deliberate re-match | 2 | 81 | _unassigned_ | ☐ |

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
