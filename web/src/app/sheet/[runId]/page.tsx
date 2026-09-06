import Link from "next/link";
import { EmptyState, ErrorState, PageHeader } from "@/components";
import { attempt, getSheetForRun, getSources, getStatus } from "@/lib/api";
import { PAGE_TITLES } from "@/lib/strings";
import { SheetView } from "../_components/SheetView";
import { clearedFacts } from "../_components/clearedFacts";

/*
  A past run's sheet, shown exactly as it was printed that morning.

  The response shape is identical to the current sheet's and it renders through
  the same component, because a past run that went through different code could
  quietly become a different document. What differs comes from the payload
  itself: is_current is false, so the page carries the banner; corpora is empty
  and corpus_note carries the frozen provenance sentence; and decided_before
  bounds the clearings to the ones that existed the instant this sheet was
  replaced.

  A run the matcher never finished, or one that was refused, answers 200 with no
  sections. That is not "clear" and this page does not render it as such.
*/

export const dynamic = "force-dynamic";

export default async function PastRunSheetPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  const id = Number(runId);

  if (!Number.isInteger(id) || id < 1) {
    return (
      <>
        <PageHeader title={PAGE_TITLES.pullSheet} />
        <EmptyState
          heading={`There is no run "${runId}".`}
          body="A run is identified by a number. Nothing was read for this address, so nothing on this page describes what is in the building."
          action={<Link href="/runs">Every delivery is listed in the run history.</Link>}
        />
      </>
    );
  }

  const [sheet, sources, status] = await Promise.all([
    attempt(getSheetForRun(id)),
    attempt(getSources()),
    attempt(getStatus()),
  ]);

  if (!sheet.ok) {
    if (sheet.error.code === "no_run" || sheet.error.status === 404) {
      return (
        <>
          <PageHeader title={PAGE_TITLES.pullSheet} />
          <EmptyState
            heading={`There is no run #${id}.`}
            body="No delivery with this id has ever been recorded at this location."
            action={<Link href="/runs">Every delivery is listed in the run history.</Link>}
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
      currentRunId={status.ok ? (status.data.run?.id ?? null) : null}
    />
  );
}
