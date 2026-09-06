import type { ApiFailure } from "@/lib/api";
import { EmptyState, ErrorState, PageHeader } from "@/components";
import { EMPTY_NO_RUNS } from "@/lib/strings";
import { RUN_NOT_FOUND_HEADING } from "@/app/runs/_components/runsMeta";

interface ArtifactUnavailableProps {
  /** The page title, so the route still identifies itself when it has no data. */
  title: string;
  failure: ApiFailure;
}

/** What an artifact route renders when the API refuses it. */
export function ArtifactUnavailable({ title, failure }: ArtifactUnavailableProps) {
  const empty =
    failure.code === "no_inventory"
      ? EMPTY_NO_RUNS
      : failure.code === "no_run"
        ? {
            heading: RUN_NOT_FOUND_HEADING,
            body: failure.message,
            action:
              "Open the document without a run parameter to get the current run, or pick a run from Run history.",
          }
        : failure.code === "not_a_meal_program"
          ? {
              heading: "This deployment does not run a meal program.",
              body: failure.message,
              action:
                "The hold record and the credit claim apply to every deployment and are unaffected.",
            }
          : null;

  return (
    <>
      <PageHeader title={title} />
      {empty ? <EmptyState {...empty} /> : <ErrorState failure={failure} />}
    </>
  );
}
