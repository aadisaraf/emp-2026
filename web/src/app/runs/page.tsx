import { EmptyState, ErrorState, PageHeader, Panel } from "@/components";
import { attempt, getRuns } from "@/lib/api";
import { EMPTY_NO_DELIVERIES, EMPTY_NO_RUNS, PAGE_TITLES } from "@/lib/strings";
import { formatCount } from "@/lib/format";
import { RunDayStrip } from "./_components/RunDayStrip";
import { RunsTable } from "./_components/RunsTable";
import {
  RUNS_CONTEXT,
  RUNS_FOOTER,
  RUNS_REJECTION_NOTE,
  TABLE_TITLE,
  showingNote,
} from "./_components/runsMeta";
import styles from "./page.module.css";

/*
  Run history.

  The log of every delivery, refused ones included. A rejected run is not an
  error message that has been dealt with; it is the morning the kitchen worked
  from yesterday's sheet, and it stays in the list saying so.

  Above the table, one cell per calendar day. A run every day is the healthy
  pattern at a location like this, so the thing worth seeing at a glance is a
  date with nothing on it, and a strip that skipped those days would hide
  exactly the fact it exists to show.
*/

export const dynamic = "force-dynamic";

/** The API caps this at 200. Ask for all of them: a run history that pages is
 *  a run history with a week of failures on page two. */
const LIMIT = 200;

export default async function RunHistoryPage() {
  const result = await attempt(getRuns(LIMIT));

  if (!result.ok) {
    return (
      <>
        <PageHeader title={PAGE_TITLES.runHistory} context={RUNS_CONTEXT} />
        <ErrorState failure={result.error} />
      </>
    );
  }

  const { runs, run_count: runCount, current_run_id: currentRunId, generated_at } = result.data;

  if (runs.length === 0) {
    return (
      <>
        <PageHeader title={PAGE_TITLES.runHistory} context={RUNS_CONTEXT} />
        <div className={styles.stack}>
          <EmptyState
            heading={EMPTY_NO_DELIVERIES}
            body={EMPTY_NO_RUNS.body}
            action={EMPTY_NO_RUNS.action}
          />
        </div>
      </>
    );
  }

  const refused = runs.filter((run) => run.status === "rejected").length;
  const truncated = runs.length < runCount;

  return (
    <>
      <PageHeader
        title={PAGE_TITLES.runHistory}
        context={RUNS_CONTEXT}
        actions={
          <span className={styles.tally}>
            <span className={styles.tallyLabel}>runs</span>{" "}
            <span className={styles.tallyValue}>{formatCount(runCount)}</span>
            {refused > 0 ? (
              <>
                <span className={styles.tallyRule} aria-hidden="true" />
                <span className={styles.tallyLabel}>refused</span>{" "}
                <span className={styles.tallyValue}>{formatCount(refused)}</span>
              </>
            ) : null}
          </span>
        }
      />

      <div className={styles.stack}>
        <RunDayStrip runs={runs} generatedAt={generated_at} />

        <Panel title={TABLE_TITLE} note={RUNS_REJECTION_NOTE} flush printBlock>
          <RunsTable runs={runs} currentRunId={currentRunId} />
        </Panel>

        <footer className={styles.footer}>
          <p className={styles.note}>{RUNS_FOOTER}</p>
          {truncated ? (
            <p className={styles.note}>{showingNote(runs.length, runCount)}</p>
          ) : null}
        </footer>
      </div>
    </>
  );
}
