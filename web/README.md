# PullSheet dashboard

A Next.js front end over the PullSheet JSON API. It is an additional view of one
location's recall response, not a replacement: the server-rendered Jinja pages at
`:8000` stay, because they are the print path and the offline fallback.

One deployment serves one location. There is no site switcher, no district
roll-up and no tenant selector, and none should be added.

## Running it

Two processes. From the repository root:

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
backend is on another port. `npm run build && npm start` for a production check;
`npm run lint` and `npm run typecheck` for the rest.

The dashboard renders with the backend stopped: every fetch failure becomes a
stated fact on screen, and no page shows a number it did not receive.

Nothing is fetched from the network -- no web font, no CDN script, no analytics,
no external image host. The only origin this application contacts is the local
FastAPI process, and the demo runs with the network physically off.

The Python side owns the database. This application never writes to `data/`; its
only mutations are the three POSTs in the API contract.

## What is here

```
src/styles/tokens.css   every colour, size, space and radius, as custom properties
src/app/globals.css     the reset, the base type, the global classes, the print rules
src/app/layout.tsx      the shell: top bar, icon rail, status poller
src/components/         the shared library, plus ui.tsx (the page vocabulary)
src/lib/types.ts        every type from the API contract
src/lib/api.ts          one function per endpoint
src/lib/format.ts       dates, hours, money, quantities
src/lib/strings.ts      the UI copy the dashboard owns
```

Routes: `/`, `/sheet`, `/sheet/[runId]`, `/runs`, `/runs/[id]`, `/match/[id]`,
`/impact`, `/sources`, `/ingest`, and `/artifacts/hold`,
`/artifacts/credit-claim`, `/artifacts/state-report`.

## The pattern every page follows

Server component, one fetch, one honest failure branch:

```tsx
import { getSheet } from "@/lib/api";
import { ErrorState, PageHeader } from "@/components";

export const dynamic = "force-dynamic";

export default async function Page() {
  const result = await getSheet();
  if (!result.ok) return <ErrorState failure={result.error} />;
  const sheet = result.data;
  return <PageHeader title="Pull sheet" context={`Run #${sheet.run.id}`} />;
}
```

The client never throws: `request()` resolves to `{ ok: false, error }`, so a
stopped backend is a branch rather than a crash. Every call already fetches with
`{ cache: "no-store" }`; keep `export const dynamic = "force-dynamic"` on pages
so nothing is prerendered against a backend that was running at build time.

`app/error.tsx` catches whatever escapes. It is the boundary of last resort, not
the plan.

Exactly one thing polls: `StatusPoller`, mounted by the layout. It asks
`/api/v1/status` every two seconds, refreshes the tree when the run changes, and
says so when a poll stops answering. Do not add a second timer.

## The component library

Import from `@/components`.

| Component | For |
|---|---|
| `DataTable` | Homogeneous records. Dense, hairline row rules, fixed column order. |
| `StatusBadge` | `PULL`, `HELD`, the six status states, the three run statuses. |
| `TierBadge` | `CONFIRMED`, `PROBABLE`, `POSSIBLE`. Uncoloured: tier is evidence, not severity. |
| `EvidenceKind` | The evidence kind in words, with the unknown-key fallback. |
| `ProvenanceLabel` | The three provenance labels. The only place they are rendered. |
| `ClockStrip` | The two USDA clocks, as a rail item or as a table. |
| `PageHeader`, `Panel`, `DefinitionList` | Title blocks, sections, label/value pairs. |
| `EmptyState`, `ErrorState` | An empty region and an unanswered API, both stated. |
| `NotRecorded`, `NewMark`, `ClearedMark` | The inline marks, all in `Marks.tsx`. |
| `TopBar`, `IconRail`, `StatRail`, `StatusPoller` | The shell. The layout renders these. |
| `ui.tsx` | The page vocabulary: `PageHero`, `Facts`, `TabCard`, `Chip`, `Kv`. |

Naming collision worth knowing: the component `EvidenceKind` and the type
`EvidenceKind` share a name. Alias the type where you need both:
`import type { EvidenceKind as EvidenceKindValue } from "@/lib/api"`.

`DataTable` takes a column list; `variant` decides alignment and face:

```tsx
{ key: "qty", header: "Qty", variant: "measure",
  render: (line) => formatQuantity(line.quantity, line.unit) ?? <NotRecorded /> }

{ key: "lot", header: "Lot", variant: "identifier",
  render: (line) => line.lot_code ?? <NotRecorded /> }
```

Right-align anything you could sum. Left-align and set in mono anything that is a
name spelled with digits: lot codes, GTIN, run ids, item codes. Never centre a
numeric column, and never let a column be a measure in one table and an
identifier in another.

`DataTable` never sorts. The pull sheet arrives in one total order -- class rank,
tier rank, score, id -- and is rendered in the order received.

## Styling

CSS Modules next to the component, plus the tokens. No utility framework and no
Tailwind.

Use the tokens for every value. `globals.css` also carries `mono`, `sr-only`,
`no-print`, `money`, `num` and `deadline`; that is the whole set of global
classes, and anything else belongs in a module.

Borders instead of shadows. No gradient, no translucency, no entrance animation,
no emoji. Icons are hand-written SVG in `Icon.tsx` rather than a package.

Status is never carried by hue alone: PULL is a filled chip and HELD is hollow,
so both survive a grayscale printout and a colourblind reader.

Print is a first-class target. `@media print` in `globals.css` drops the nav and
keeps every chip, tier word and provenance label. Add `data-print-block` to a
section that must not break across pages, and `no-print` to a control.

## Rules that are not style preferences

These come from the constitution and the API contract. A page that breaks one is
wrong even if it looks right.

- `PULL` and `HELD` are the only two line statuses. Never render a third, never
  put HELD behind a toggle or in its own section, and never default a filter to
  hiding it.
- A cleared line stays on the sheet, in place, marked. Clearing writes an audit
  row; it never removes, moves or greys out a line, and only a named person can
  do it.
- There is no confidence percentage. `score` breaks ties in ordering and decides
  nothing, so it is never a bar, a badge or a percentage.
- Provenance is visible on screen and in print, on every source, always.
- `never` is not `clear`. A location that has received nothing reads "no
  inventory has ever been received", never an all-clear.
- Staleness gates one word. The lines themselves are byte-identical.
- `status.word`, `status.detail`, `deadline.label`, `deadline.text` and the
  provenance labels are server-owned. Render them verbatim.
- A missing field is the words `not recorded`. A blank cell reads as zero.
