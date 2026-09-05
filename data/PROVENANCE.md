# Data provenance

Every data source PullSheet reads, what kind of thing it is, and how to regenerate it.

This table is checked against [`pullsheet/provenance.py`](../pullsheet/provenance.py) by
`tests/unit/test_provenance.py`. Adding a source to one without the other fails the build, and so
does naming a path here that does not exist on disk. That is deliberate: Constitution Principle V
makes provenance load-bearing, and a table nobody verifies is worse than no table.

Three labels, and only three:

| Label | Means |
|---|---|
| `live` | Fetched from the agency at run time |
| `dated-snapshot` | Fetched once, committed, and always displayed with its capture date |
| `hand-authored` | Written by the build team. Not sourced from anywhere |

## Sources

| Key | Label | Path | Captured | How to regenerate |
|---|---|---|---|---|
| `openfda` | `dated-snapshot` | `pullsheet/recalls/snapshots/openfda-2026-09-05.json` | 2026-09-05 | `curl -s 'https://api.fda.gov/food/enforcement.json?limit=1000' -o pullsheet/recalls/snapshots/openfda-2026-09-05.json` |
| `fsis` | `hand-authored` | `pullsheet/recalls/snapshots/fsis-2026-09-05.json` | 2026-09-05 | Hand-edit the file. There is no fetch path — see below |
| `inventory_lincoln` | `hand-authored` | `data/fixtures/inventory_lincoln.csv` | — | Hand-edit |
| `expected_matches` | `hand-authored` | `data/fixtures/expected_matches.json` | — | Hand-edit |
| `unit_costs` | `hand-authored` | `data/fixtures/unit_costs.csv` | — | Hand-edit |
| `recipes` | `hand-authored` | `data/fixtures/recipes.csv` | — | Hand-edit |
| `recipe_ingredients` | `hand-authored` | `data/fixtures/recipe_ingredients.csv` | — | Hand-edit |
| `recipe_components` | `hand-authored` | `data/fixtures/recipe_components.csv` | — | Hand-edit |
| `service_days` | `hand-authored` | `data/fixtures/service_days.csv` | — | Hand-edit |

## Why FSIS is `hand-authored` and not a snapshot

FSIS returns **HTTP 403 to programmatic requests**, verified on 2026-09-05 against both
`https://www.fsis.usda.gov/fsis/api/recall/v/1` and the public recalls page. The meat and poultry
corpus therefore could not be fetched, and could not be checked against published notices.

The twelve records in `fsis-2026-09-05.json` are written by the build team in FSIS notice format
so that the meat and poultry half of the corpus exists at all. They are **illustrative, not
transcriptions**. Calling them a "dated snapshot" would imply a capture that never happened, so
they carry the `hand-authored` label on every surface that shows them — screen, printed sheet, and
this table.

If you are asked in review "where did the FSIS data come from?", the answer is: we wrote it,
because the agency blocks automated access, and the label says so everywhere it appears.

## What the inventory fixture is, and what it is not

`inventory_lincoln.csv` is a **hand-authored** district export: 53 rows, three sites, written by
the build team. It is not an extract from any real district's system, and no real district's data
appears anywhere in this repository.

Two things about it are deliberate and worth stating, because both shape what the demo proves:

* **Its item descriptions are written in distributor-catalog dialect**, the way a real item master
  reads — `CHICKEN STRIPS BRD FC FROZEN 2/5 LB`, `POLLOCK WEDGE BRD WG OVEN READY 3.4 OZ` — rather
  than in an invented shorthand. The recall corpus writes the same dialect back
  (`HFS 10/6lb Crunchy Row Breaded Cod Rectangles 3 oz.`), which is why the matcher compares words
  as written.
* **46 of the 53 rows carry no barcode and most carry no lot code.** That is the realistic case,
  and it is what makes the supplier channels load-bearing rather than decorative. A fixture where
  every row had a GTIN would exercise the easy path and prove nothing.

The brands, manufacturers and item numbers on those rows are chosen so that some of them
correspond to **real firms and real recalls in the committed openFDA snapshot** — High Liner
Foods item 53374, JR Simplot item 473015, Mann Packing, Grimmway, Pictsweet, C. H. Guenther. The
inventory row is invented; the recall it reaches is not. The vendor names (Sysco, US Foods) and
the vendor item codes are invented and match nothing.

## Why the openFDA snapshot is committed rather than fetched

Constitution Principle III: no external dependency at demo time. The snapshot is captured once,
committed, and read from disk. The application will show its capture date and its age, and will
say so plainly when that age exceeds the 24-hour freshness window (FR-068). A stale-data banner
during the demo is intended behavior, not a defect.

The one live path, `pullsheet/recalls/fetch.py`, is a refresh convenience. It is never on the path
between a dropped file and a printed pull sheet.
