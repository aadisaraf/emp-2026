import { EmptyState, ErrorState, PageHero } from "@/components";
import { getSheet, getSources } from "@/lib/api";
import { EMPTY_NO_RUNS, PAGE_TITLES } from "@/lib/strings";
import { SheetView } from "./_components/SheetView";

/*
  The current pull sheet: the latest run that was read successfully, every line
  it produced, in the order it produced them.
*/

export const dynamic = "force-dynamic";

export default async function PullSheetPage() {
  const [sheet, sources] = await Promise.all([getSheet(), getSources()]);

  if (!sheet.ok) {
    if (sheet.error.code === "no_inventory" || sheet.error.status === 404) {
      return (
        <>
          <PageHero figure="0" word={PAGE_TITLES.pullSheet} />
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
        <PageHero figure="—" word={PAGE_TITLES.pullSheet} />
        <ErrorState failure={sheet.error} />
      </>
    );
  }

  return (
    <SheetView
      sheet={sheet.data}
      screeningRule={sources.ok ? sources.data.screening_rule : null}
      currentRunId={sheet.data.run.id}
    />
  );
}
