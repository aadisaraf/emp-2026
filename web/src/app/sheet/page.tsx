import { EmptyState, ErrorState, PageHeader } from "@/components";
import { attempt, getSheet, getSources } from "@/lib/api";
import { EMPTY_NO_RUNS, PAGE_TITLES } from "@/lib/strings";
import { SheetView } from "./_components/SheetView";
import { clearedFacts } from "./_components/clearedFacts";

/*
  The current pull sheet: the latest run that was read successfully, every line
  it produced, in the order it produced them.

  This is the working screen and the printed artefact, so it is fetched fresh
  on every render. The shell polls /api/v1/status every two seconds and
  refreshes this page when the run id changes, which is what makes a file
  landing in data/watched/ turn an open tab into today's sheet.

  404 no_inventory is not an error here. It means no run has ever succeeded at
  this location, and the page has to say that in words rather than render an
  empty table that would be read as "clear".
*/

export const dynamic = "force-dynamic";

export default async function PullSheetPage() {
  const [sheet, sources] = await Promise.all([attempt(getSheet()), attempt(getSources())]);

  if (!sheet.ok) {
    if (sheet.error.code === "no_inventory" || sheet.error.status === 404) {
      return (
        <>
          <PageHeader title={PAGE_TITLES.pullSheet} />
          <EmptyState
            heading={EMPTY_NO_RUNS.heading}
            body={EMPTY_NO_RUNS.body}
            action={EMPTY_NO_RUNS.action}
          />
        </>
      );
    }
    return (
      <>
        <PageHeader title={PAGE_TITLES.pullSheet} />
        <ErrorState failure={sheet.error} />
      </>
    );
  }

  const cleared = await clearedFacts(sheet.data);

  return (
    <SheetView
      sheet={sheet.data}
      screeningRule={sources.ok ? sources.data.screening_rule : null}
      cleared={cleared}
      currentRunId={sheet.data.run.id}
    />
  );
}
