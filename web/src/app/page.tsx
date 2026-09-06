import { ErrorState } from "@/components";
import {
  getCreditClaim,
  getSheet,
  getStateReport,
  getStatus,
} from "@/lib/api";
import { TodayBoard, type ArtifactFacts } from "./_dashboard/TodayBoard";

/* Today. */

export const dynamic = "force-dynamic";

type Params = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export default async function TodayPage({ searchParams }: { searchParams: Params }) {
  const params = await searchParams;
  const result = await getStatus();
  if (!result.ok) {
    return <ErrorState failure={result.error} />;
  }
  const status = result.data;

  /* The lines and the documents exist only when a run does. */
  const hasRun = status.run !== null;
  // A restaurant claims credit from its distributor; a school is funded, so
  // the claim is neither fetched nor offered there.
  const claims = status.location.deployment_type === "restaurant";
  const [sheet, credit, report] = hasRun
    ? await Promise.all([
        getSheet(),
        claims ? getCreditClaim() : Promise.resolve(null),
        status.location.serves_meal_program
          ? getStateReport()
          : Promise.resolve(null),
      ])
    : [null, null, null];

  const artifacts: ArtifactFacts = {
    credit: credit?.ok ? { total: credit.data.total, counted: credit.data.counted } : null,
    report: report?.ok
      ? { derived: report.data.derived_count, toEnter: report.data.unfilled.length }
      : null,
  };

  return (
    <TodayBoard
      status={status}
      sheet={sheet?.ok ? sheet.data : null}
      artifacts={artifacts}
      filters={{ q: first(params.q), loc: first(params.loc), show: first(params.show) }}
    />
  );
}
