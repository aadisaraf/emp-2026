# Contract: HTTP endpoints

**Plan**: [../plan.md](../plan.md)

Server-rendered HTML throughout. JSON is returned only where `poll.js` needs it. No
authentication anywhere (FR-061). Routes are thin — each one parses input, calls a module, and
renders.

## Pages

| Method | Path | Renders | Requirements |
|---|---|---|---|
| `GET` | `/` | District roll-up: site status board, deadline countdowns, corpus provenance banner | FR-049 → FR-054, FR-068 |
| `GET` | `/sheet` | Full pull sheet, all sites, PULL and HELD interleaved by class then tier | FR-031 → FR-036 |
| `GET` | `/sheet/{site}` | Per-site printable pull sheet — the cafeteria manager's artifact | FR-031, FR-033 |
| `GET` | `/match/{id}` | One match: both source records verbatim, triggering substrings highlighted | FR-015, FR-023 |
| `GET` | `/menu` | Broken menu items, affected dates, planned meal counts, substitutions | FR-037 → FR-042 |
| `GET` | `/artifacts/hold/{site}` | Hold-and-destruction record, print-styled | FR-043 |
| `GET` | `/artifacts/state-report` | Pre-filled district recall report | FR-044, FR-045 |
| `GET` | `/artifacts/credit-claim` | Distributor credit claim with dollar total | FR-046, FR-047 |
| `GET` | `/ingest` | Upload / paste / column-mapping UI | FR-005 |
| `GET` | `/sources` | Every source with its provenance label and field-coverage map | FR-011, FR-012, FR-003 |

## Actions

| Method | Path | Body | Effect |
|---|---|---|---|
| `POST` | `/ingest/upload` | multipart file | Runs `SpreadsheetUploadAdapter`; may redirect to column mapping |
| `POST` | `/ingest/paste` | `text` | Runs `PasteAdapter`. Must never 500 |
| `POST` | `/ingest/mapping/{source_id}` | column map | Stores the remembered mapping |
| `POST` | `/match/{id}/clear` | `actor` (required), `note` | **The only clearing path.** Writes `decisions`. Rejects empty actor with 400 |
| `POST` | `/site/{site}/confirm` | `actor` (required) | Records `confirm_site_pulled` |
| `POST` | `/alerts/{match_id}/ack` | `actor` (required) | Records `acknowledge_alert` |
| `POST` | `/recalls/refresh` | — | Attempts openFDA fetch; on any failure falls back to snapshot and reports which |

`POST /match/{id}/clear` is the single most sensitive route in the application. It requires a
non-empty actor, writes an audit row, and never deletes the match. After clearing, the line
remains queryable and renders as cleared-by-actor rather than disappearing.

## Polling

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/status` | `{sheet_generated_at, pull_count, held_count, sites:{...}, corpus:{source, provenance, captured_at, age_hours, stale:bool}, last_ingest:{...}}` |

`poll.js` hits this every 2 seconds on `/` and `/sheet` and re-renders the header and counts. That
is the only JavaScript in the project. The watched-folder demo works through this endpoint: a file
lands, the poller ingests, the next status poll shows the new counts.

## Error behavior

- A rejected export returns 200 with a visible rejection panel naming file, row or column, and
  reason — not a 4xx that a folder poller would swallow. (FR-006)
- An unreachable openFDA endpoint is never an error response. It renders the page with the cached
  snapshot and a stale-data banner carrying the capture date and age. (FR-013)
- Zero matches renders the sheet, stating zero lines matched and naming the corpus and capture
  date. An empty sheet is an artifact. (FR-036)
