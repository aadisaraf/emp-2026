import Link from "next/link";
import { EmptyState, ErrorState, PageHeader } from "@/components";
import { getSheetForRun, getSources, getStatus } from "@/lib/api";
import { PAGE_TITLES } from "@/lib/strings";
import { SheetView } from "../_components/SheetView";

/* A past run's sheet, shown exactly as it was printed that morning. */

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
    getSheetForRun(id),
    getSources(),
    getStatus(),
  ]);

  if (!sheet.ok) {
    const missing = sheet.error.code === "no_run" || sheet.error.status === 404;
    return (
      <>
        <PageHeader title={PAGE_TITLES.pullSheet} />
        {missing ? (
          <EmptyState
            heading={`There is no run #${id}.`}
            body="No delivery with this id has ever been recorded at this location."
            action={<Link href="/runs">Every delivery is listed in the run history.</Link>}
          />
        ) : (
          <ErrorState failure={sheet.error} />
        )}
      </>
    );
  }

  return (
    <SheetView
      sheet={sheet.data}
      screeningRule={sources.ok ? sources.data.screening_rule : null}
      currentRunId={status.ok ? (status.data.run?.id ?? null) : null}
    />
  );
}
