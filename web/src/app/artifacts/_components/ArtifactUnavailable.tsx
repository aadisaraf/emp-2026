import type { ApiFailure } from "@/lib/api";
import { EmptyState, ErrorState, PageHeader } from "@/components";
import { EMPTY_NO_RUNS } from "@/lib/strings";
import { RUN_NOT_FOUND_HEADING } from "@/app/runs/_components/runsMeta";

export interface ArtifactUnavailableProps {
  /** The page title, so the route still identifies itself when it has no data. */
  title: string;
  failure: ApiFailure;
}

/** What an artifact route renders when the API refuses it. */
export function ArtifactUnavailable({ title, failure }: ArtifactUnavailableProps) {
  if (failure.code === "no_inventory") {
    return (
      <>
        <PageHeader title={title} />
        <EmptyState
          heading={EMPTY_NO_RUNS.heading}
          body={EMPTY_NO_RUNS.body}
          action={EMPTY_NO_RUNS.action}
        />
      </>
    );
  }

  if (failure.code === "no_run") {
    return (
      <>
        <PageHeader title={title} />
        <EmptyState
          heading={RUN_NOT_FOUND_HEADING}
          body={failure.message}
          action="Open the document without a run parameter to get the current run, or pick a run from Run history."
        />
      </>
    );
  }

  if (failure.code === "not_a_meal_program") {
    return (
      <>
        <PageHeader title={title} />
        <EmptyState
          heading="This deployment does not run a meal program."
          body={failure.message}
          action="The hold record and the credit claim apply to every deployment and are unaffected."
        />
      </>
    );
  }

  return (
    <>
      <PageHeader title={title} />
      <ErrorState failure={failure} />
    </>
  );
}
