# PullSheet dashboard

A Next.js front end over the PullSheet JSON API. It is an additional view of
one location's recall response, not a replacement for anything: the
server-rendered Jinja pages at `:8000` stay, because they are the print path and
the offline fallback.

One deployment serves one location. There is no site switcher, no district
roll-up and no tenant selector anywhere in here, and none should be added.

## Running it alongside the Python backend

Two processes. From the repository root, start the backend first:

```
.venv/bin/python -m pullsheet.main --port 8000
```

Then, in a second shell:

```
cd web
npm install
npm run dev
```

The dashboard is at `http://localhost:3000` and reads
`http://127.0.0.1:8000/api/v1`. Copy `.env.local.example` to `.env.local` if the
backend is on another port.

For a production check, `npm run build && npm start`. `npm run lint` runs ESLint.

The dashboard renders with the backend stopped. Every fetch failure becomes a
stated fact on screen: the status line says the API did not answer, and no page
shows a number it did not receive.

Nothing is fetched from the network. There is no web font, no CDN script, no
analytics and no external image host, and the only origin this application
contacts is the local FastAPI process. Keep it that way: the demo runs with the
network physically off.

The Python side owns the database. This application never writes to `data/`, and
the only mutations it makes are the three POSTs in the API contract.

## What is here

```
src/styles/tokens.css     every colour, size, space and radius, as custom properties
src/app/globals.css       the reset, the base type, five type classes, the print rules
src/app/layout.tsx        the shell: masthead, nav, status line, stat rail, poller
src/components/           the shared library, one file and one CSS Module each
src/lib/types.ts          every type from the API contract
src/lib/api.ts            one function per endpoint, plus attempt()
src/lib/format.ts         dates, hours, money, quantities
src/lib/strings.ts        the UI copy the dashboard owns
src/lib/nav.ts            the nav, as data
src/app/_scaffold/        route placeholders; delete this once every page is built
```

Routes: `/`, `/sheet`, `/runs`, `/impact`, `/sources`, `/ingest`, and
`/artifacts/hold`, `/artifacts/credit-claim`, `/artifacts/state-report`. Every
one exists so the nav has nowhere dead to point; most are placeholders that say
so and render no numbers.

## The pattern every page follows

Server component, one fetch, one honest failure branch:

```tsx
import { attempt, getSheet } from "@/lib/api";
import { ErrorState, PageHeader } from "@/components";

export const dynamic = "force-dynamic";

export default async function Page() {
  const result = await attempt(getSheet());
  if (!result.ok) return <ErrorState failure={result.error} />;
  const sheet = result.data;
  return <PageHeader title="Pull sheet" context={`Run #${sheet.run.id}`} />;
}
```

`attempt()` turns a thrown `ApiRequestError` into `{ ok: false, error }`, so a
stopped backend is a branch rather than a crash. Every client function already
fetches with `{ cache: "no-store" }`; keep `export const dynamic =
"force-dynamic"` on pages so nothing is prerendered against a backend that was
running at build time.

`app/error.tsx` catches whatever escapes. It is the boundary of last resort, not
the plan.

## The component library

Import from `@/components`.

| Component | For |
|---|---|
| `DataTable` | Homogeneous records. Dense, bordered, hairline row rules, sticky header, fixed column order. |
| `StatusBadge` | `PULL`, `HELD`, the six status states, and the three run statuses. |
| `TierBadge` | `CONFIRMED`, `PROBABLE`, `POSSIBLE`. Uncoloured, because tier is evidence and not severity. |
| `EvidenceKind` | The evidence kind in words, with the unknown-key fallback. |
| `ProvenanceLabel` | The three provenance labels. The only place they are rendered. |
| `ClockStrip` | The two USDA clocks, as a rail item or as the Reporting clocks table. |
| `PageHeader` | Title, one line of context, optional actions. |
| `Panel` | A bordered section with a heading. |
| `DefinitionList` | Label and value pairs. |
| `EmptyState` | An empty region, stated. No illustration. |
| `ErrorState` | The API did not answer. No apology, no placeholder numbers. |
| `NotRecorded` | The word `not recorded`, for a field the export did not carry. |
| `NewMark` | The word `new`, for a line whose `is_new` column is 1. |
| `ClearedMark` | A cleared line, marked in place with who cleared it. |
| `PrintButton` | Print. |
| `Masthead`, `SideNav`, `StatRail`, `StatusLine`, `StatusPoller` | The shell. The layout already renders these. |

Naming collision worth knowing: the component `EvidenceKind` and the type
`EvidenceKind` share a name. In a file that needs both, alias the type:
`import type { EvidenceKind as EvidenceKindValue } from "@/lib/api"`.

`DataTable` takes a column list. `variant` decides alignment and face, and the
rule is measure against identifier:

```tsx
{ key: "qty", header: "Qty", variant: "measure", width: "64px",
  render: (line) => formatQuantity(line.quantity, line.unit) ?? <NotRecorded /> }

{ key: "lot", header: "Lot", variant: "identifier", width: "110px",
  render: (line) => line.lot_code ?? <NotRecorded /> }
```

Right-align anything you could sum: quantities, unit costs, totals, line counts,
elapsed hours. Left-align and set in mono anything that is a name spelled with
digits: lot codes, GTIN, UPC, run ids, item codes. Never centre a numeric
column, and never let a column be a measure in one table and an identifier in
another.

`DataTable` never sorts. Its `sort` prop draws the marker on a header and
nothing else. The pull sheet arrives in one total order, class rank then tier
rank then score then id, and is rendered in the order received.

## Styling

CSS Modules next to the component, plus the tokens. There is no utility
framework and no Tailwind: a screen assembled from forty utility classes reads
as generated, and this one has to read as a logbook.

Use the tokens for every value. `globals.css` also carries five type classes
(`t-micro`, `t-body`, `t-body-strong`, `t-section`, `t-page`), `mono`, `muted`,
`secondary`, `sr-only`, `no-print` and `print-only`. That list is the whole set
of global classes; anything else belongs in a module.

The scale is five sizes and two weights: 11px uppercase labels, 13px body, 13px
strong, 15px section headings, 20px page title, at weights 400 and 600. No 14px,
no 16px body, no 500 weight.

Radius is by role: 0 for tables, cells, rows and the stat rail, 2px for chips
and buttons, 3px once on a dropzone. Nothing above 3px. Borders instead of
shadows; the only shadow permitted is the hairline under a stuck table header.
No gradient, no translucency, no entrance animation, no emoji, no decorative
icon. If a small icon is genuinely needed, hand-write the SVG rather than adding
a package.

Green is chrome: the masthead, the active nav item, the focus ring, the primary
button. It never means "no action required". Red means act now, ochre means
unresolved, neutral means recorded. Status is never carried by hue alone: PULL
is a filled chip and HELD is a hollow one, so both survive a grayscale printout
and a colourblind reader.

Print is a first-class target. `@media print` in `globals.css` drops the nav,
flattens the masthead to a rule, whitens the table header and keeps every chip,
tier word and provenance label. Add `data-print-block` to a section that must
not break across pages, and `no-print` to a control.

Density target: at 1440x900 the sheet shows 25 or more line rows. Row height is
28px and cell padding is 5px by 10px. If a change drops that count, the change
is wrong.

## Rules that are not style preferences

These come from the constitution and the API contract. A page that breaks one of
them is wrong even if it looks right.

- `PULL` and `HELD` are the only two line statuses. Never render a third, never
  put HELD behind a toggle or in its own section, and never default a filter to
  hiding it.
- A cleared line stays on the sheet, in place, marked with who cleared it and
  when. Clearing writes an audit row; it never removes, moves or greys out a
  line, and only a named person can do it.
- There is no confidence percentage. `score` breaks ties in ordering and decides
  nothing, so it is never a bar, a badge or a percentage.
- Provenance is visible on screen and in print, on every source, always. It is
  never a tooltip, never faded out, and never dropped because a row felt busy.
- `never` is not `clear`. A location that has received nothing reads "no
  inventory has ever been received", never an all-clear.
- Staleness gates one word. The lines themselves are byte-identical.
- `status.word`, `status.detail`, `deadline.label`, `deadline.text` and the
  provenance labels are server-owned. Render them verbatim.
- A missing field is the words `not recorded`. A blank cell reads as zero, and
  50 of the 56 fixture export rows carry no barcode.
