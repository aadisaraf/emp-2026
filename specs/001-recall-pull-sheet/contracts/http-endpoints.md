# Contract: HTTP endpoints

**Plan**: [../plan.md](../plan.md)

Server-rendered HTML throughout. JSON is returned only where `poll.js` needs it. No
authentication anywhere (FR-061). Routes are thin — each one parses input, calls a module, and
renders.

Eighteen routes. There were twenty-three before amendment 3; the site-scoped ones are gone, and
what replaced them is scoped on a run instead.

## Pages

### The recall picture — the main section

| Method | Path | Renders | Requirements |
|---|---|---|---|
| `GET` | `/` | Today: one status word with its reason, the two deadline clocks, what is new since the previous run, corpus provenance banner | FR-049 → FR-054, FR-068 |
| `GET` | `/sheet` | The latest run's pull sheet, PULL and HELD interleaved by class then tier, grouped by storage location | FR-031 → FR-036 |
| `GET` | `/sheet/{run_id}` | Any past run's sheet, exactly as it was printed — its own frozen counts and its own corpus note | FR-031, FR-033 |
| `GET` | `/runs` | Every run: date, channel, delivery, counts, outcome | FR-058 |
| `GET` | `/runs/{run_id}` | One run's facts — what arrived, what it produced, what was rejected | FR-006, FR-058 |
| `GET` | `/match/{id}` | One match: both source records verbatim, triggering substrings highlighted, every decision ever taken about this food and this recall | FR-015, FR-023 |

### What was affected — the separate section

| Method | Path | Renders | Requirements |
|---|---|---|---|
| `GET` | `/impact` | Money always; broken menu items, affected dates, planned meal counts and substitutions where the location runs a meal program | FR-037 → FR-042, FR-046 |
| `GET` | `/artifacts/hold` | Hold-and-destruction record, print-styled | FR-043 |
| `GET` | `/artifacts/state-report` | Pre-filled recall report. 404 with the reason stated where the location runs no meal program | FR-044, FR-045 |
| `GET` | `/artifacts/credit-claim` | Distributor credit claim with dollar total | FR-046, FR-047 |

### Operating surfaces

| Method | Path | Renders | Requirements |
|---|---|---|---|
| `GET` | `/ingest` | The three delivery channels, recent rejections, column-mapping UI | FR-005 |
| `GET` | `/sources` | Every channel and corpus with its provenance label and field-coverage map | FR-011, FR-012, FR-003 |

There is no `/menu` page: the cascade lives inside `/impact`, because a menu break is a
consequence of a recall rather than a subject of its own.

## Actions

| Method | Path | Body | Effect |
|---|---|---|---|
| `POST` | `/ingest/upload` | multipart file | Runs `SpreadsheetUploadAdapter` for the morning the scheduled drop fails; may redirect to column mapping |
| `POST` | `/ingest/mapping` | column map | Answers the ambiguous headers and re-runs the delivery |
| `POST` | `/match/{id}/clear` | `actor` (required), `note` | **The only clearing path.** Writes `decisions`. Rejects empty actor with 400 |
| `POST` | `/match/{id}/confirm-pulled` | `actor` (required) | Records `confirm_pulled`. Changes nothing about the line |
| `POST` | `/recalls/refresh` | — | Attempts openFDA fetch; on any failure falls back to snapshot and reports which. Deliberately does NOT re-match — see below |

`POST /match/{id}/clear` is the single most sensitive route in the application. It requires a
non-empty actor, writes an audit row, and never deletes or edits the match. After clearing, the
line remains queryable and renders as cleared-by-actor rather than disappearing. The decision is
keyed on the food and the recall, so it still applies to tomorrow's line for the same pair.

`POST /recalls/refresh` writes a new snapshot and stops there. Re-deciding lines underneath an
operator who is holding a printout is exactly the surprise this system must not spring, so
re-matching is a separate deliberate act — `python -m pullsheet.match` — and it produces a new
run rather than editing the old one.

**Withdrawn by amendment 3**: `POST /site/{site}/confirm` and `POST /alerts/{id}/ack` were
roll-up gestures with no meaning under one location. `POST /ingest/paste` is gone with the paste
adapter: an export is a file, and a textarea invited a shape nothing downstream could trust.

## Polling

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/status` | `{state, word, detail, run_id, business_date, pull_count, held_count, new_count, deadlines:[{key,label,hours,due_at,remaining_hours,text,overrun,records}], corpus:[{source, provenance, captured_at, age_hours, stale}], run_count}` |

`poll.js` hits this every 2 seconds and re-renders the status word, the counts, and the clocks.
It also compares `run_id` against the page's own and reloads when a new run has been finalized —
which is what makes the demo work: a file lands in the drop folder, and the open browser tab
becomes today's sheet with nobody touching it. That is the only JavaScript in the project.

## Error behavior

- A rejected export returns 200 with a visible rejection panel naming file, row or column, and
  reason — not a 4xx that a folder poller would swallow. (FR-006)
- A rejected export never replaces a good sheet. The rejected run is recorded; the sheet on screen
  stays the last one that was read successfully, and the status word says so. (FR-009)
- A repeated delivery is refused as a duplicate and returns the run it duplicates, rather than
  creating a second run. (FR-072)
- An unreachable openFDA endpoint is never an error response. It renders the page with the cached
  snapshot and a stale-data banner carrying the capture date and age. (FR-013)
- Zero matches renders the sheet, stating zero lines matched and naming the corpus and capture
  date. An empty sheet is an artifact. (FR-036)
- A run that never happened is not rendered as a clear result. `/` says "no inventory has ever
  been received" in those words. (FR-050)
