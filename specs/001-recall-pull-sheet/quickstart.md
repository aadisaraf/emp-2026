# Quickstart & Validation: PullSheet

**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

How to run PullSheet and how to prove it does what the spec claims. This is a run-and-verify
guide; implementation belongs in `tasks.md`.

## Prerequisites

Python 3.11+. Nothing else — no Docker, no database server, no API key, no account.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

```bash
python -m pullsheet.db --reset && python -m pullsheet.db --load-fixtures
```

The second command creates `data/pullsheet.db`, applies `schema.sql`, and loads the hand-authored
fixtures: ~50 inventory lines with deliberately abbreviated names, the menu and recipe tables, and
the committed FSIS snapshot.

## Run

```bash
python -m pullsheet.main --port 8000
```

One command, one process: this starts the web app **and** the folder poller
together. Starting uvicorn against `pullsheet.app:app` directly serves the site
but does not poll `data/watched/`, so V1 would silently never fire.

Open `http://localhost:8000`.

---

## Validation scenarios

Each maps to a success criterion in the spec. Run them in order — scenario 1 is the demo.

### V1 — The watched folder produces a sheet with no human action (SC-001, SC-004)

**Disconnect the network first.** This is the point.

```bash
cp data/fixtures/inventory_lincoln.csv data/watched/
```

Watch `http://localhost:8000/sheet`. Within one poll interval the sheet appears, grouped by storage location,
Class I first. The header states the corpus in use, its provenance label, and its capture date.
The file moves to `data/archive/`.

**Passes when**: a complete pull sheet exists, nobody touched the browser, and the network was off
the whole time.

### V2 — Every seeded correspondence reaches the sheet (SC-005)

`data/fixtures/expected_matches.json` names 30 inventory-row-to-recall pairs that must appear,
covering every rung of the ladder, plus two rows bought from a recalled firm whose product is not
recalled — those must appear and must be HELD.

```bash
pytest tests/integration/test_seeded_correspondences.py -v
```

**Passes when**: every seeded correspondence is present, and no `must_not_pull` row pulled. A
seeded pair that is *absent* is a failure; a seeded pair that appears as HELD rather than PULL is
not.

### V3 — Nothing clears itself (SC-003)

```bash
pytest tests/unit/test_gate.py -v
```

This includes the score sweep (name-only evidence stays HELD from 0.0 to 1.0), every widening
rule, and the clearing audit that walks `matching/` asserting no function there can remove a row.

**Passes when**: all pass, and the audit reports exactly the three justified clearing paths listed
in [contracts/hold-gate.md](./contracts/hold-gate.md). A fourth path is a failure.

### V4 — Every line traces to a record and a field (SC-002)

Open any line on `/sheet` and follow it to `/match/{id}`. Both source records render verbatim with
the triggering substrings highlighted on each side.

**Passes when**: no line on the sheet lacks a working trace.

### V5 — Determinism (SC-011)

```bash
pytest tests/unit/test_determinism.py -v
```

Ingests the same fixture twice into fresh databases and diffs the resulting match rows on tier,
status, score, and order.

**Passes when**: the diff is empty.

### V6 — Stale data cannot produce a green page (SC-013)

```bash
pytest tests/unit/test_freshness.py -v
```

Injects a `now` past the snapshot's capture time, on a run with nothing to pull — the only state
in which "clear" and "stale" are distinguishable at all.

**Passes when**: the status word states the corpus is stale rather than that nothing was found,
and every PULL/HELD line is byte-identical to the same run read inside the window. A run that
suppresses lines is a failure — staleness gates one word, not the matcher. The same file also
asserts that a location which never reported is not rendered as a quiet green page (FR-050).

### V7 — Adapters cannot reach the matcher (SC-012)

```bash
pytest tests/unit/test_boundaries.py -v
```

Asserts `matching/` imports nothing from `adapters/`, and that lot codes arrive at the matcher
byte-identical to the source.

### V8 — A bad delivery never empties a good sheet

```bash
pytest tests/integration/test_ingest.py tests/adapters/test_sftp_drop.py -v
```

Feeds a malformed export, an empty file, a file of null bytes, a headers-only file, a PDF, and the
same good file twice.

**Passes when**: each is either read or rejected — never raising past the caller, because a drop
poller that dies on a bad file stops watching the folder. A rejected run is recorded with the
failing row or column named, leaves the existing sheet intact, and the file stays where it landed.
The repeated delivery is refused as a duplicate rather than becoming the baseline the next
new-since diff is measured against.

### V9 — Degradation is visible, not silent (SC-007, FR-013)

With the network off, click **Refresh recalls** on `/`.

**Passes when**: the page still renders, a banner names the cached snapshot with capture date and
age, and no error page appears. Every source on `/sources` carries a `live` / `dated-snapshot` /
`hand-authored` label.

### V10 — Artifacts print (SC-008, FR-035)

Print-preview `/sheet/lincoln`, `/artifacts/hold/lincoln`, `/artifacts/state-report`, and
`/artifacts/credit-claim`.

**Passes when**: no column is cut off at standard paper width, and the credit claim's dollar total
matches `quantity × unit_cost` computed by hand for the itemized lines — with any lines lacking
`unit_cost` shown as quantity-only and named as excluded from the total.

---

## Full suite

```bash
pytest -v
```

## Demo rehearsal

Run V1 end to end with the network physically disconnected at least once before the demo. The
freshness banner will be showing, and that is intended behavior worth narrating rather than
apologizing for: the system knows how old its data is and refuses to call the kitchen clear on
it.
