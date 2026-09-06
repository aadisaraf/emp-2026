import type { ApiFailure } from "@/lib/api";
import { EmptyState, ErrorState, PageHeader } from "@/components";
import { EMPTY_NO_RUNS } from "@/lib/strings";
import { RUN_NOT_FOUND_HEADING } from "@/app/runs/_components/runsMeta";

export interface ArtifactUnavailableProps {
  /** The page title, so the route still identifies itself when it has no data. */
  title: string;
  failure: ApiFailure;
}

/**
 * What an artifact route renders when the API refuses it.
 *
 * Three of the four cases are not errors at all, they are states, and each one
 * gets the sentence that belongs to it:
 *
 * - no_inventory   nothing has ever been ingested. This is the longest of the
 *                  three deliberately: a short line here would be read as
 *                  reassurance, and a document that does not exist because
 *                  nothing arrived is not the same as a document with nothing
 *                  in it.
 * - no_run         the run id in the address is not a run here.
 * - not_a_meal_program  the state report is a child nutrition artifact and
 *                  this deployment does not run a meal program. The route is
 *                  still reachable and still says why, because an invisible
 *                  route is not an explanation.
 *
 * Anything else is the backend not answering, which ErrorState states without
 * apologising and without inventing a number.
 */
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
