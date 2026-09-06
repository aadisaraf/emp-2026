"use client";

import type { StatusResponse } from "@/lib/api";
import { ClockStrip, EmptyState, Panel } from "@/components";
import { CLOCKS, EMPTY_NO_RUNS, TIER_LEGEND } from "@/lib/strings";
import { StateStatement } from "./StateStatement";
import { RunFacts } from "./RunFacts";
import { NewSincePrevious } from "./NewSincePrevious";
import { CorpusPanel } from "./CorpusPanel";
import { RefusedDeliveries } from "./RefusedDeliveries";
import { useStatusFeed } from "./useStatusFeed";
import { HOLD_POLICY } from "./strings";
import styles from "./dashboard.module.css";

export interface TodayBoardProps {
  /** The server's own fetch, so the first paint is real data, not a skeleton. */
  initial: StatusResponse;
}

/** The morning screen, and the live half of it. */
export function TodayBoard({ initial }: TodayBoardProps) {
  const { status, reachable } = useStatusFeed(initial);
  const run = status.run;

  return (
    <>
      <StateStatement status={status} reachable={reachable} />

      <div className={styles.stack}>
        {run ? (
          <>
            <div className={styles.pair}>
              <Panel title={CLOCKS.heading} printBlock>
                <ClockStrip deadlines={status.deadlines} variant="table" notes />
              </Panel>
              <RunFacts
                run={run}
                counts={status.counts}
                previousRunId={status.previous_run_id}
              />
            </div>

            <NewSincePrevious
              lines={status.new_lines}
              previousRunId={status.previous_run_id}
            />
          </>
        ) : (
          <>
            {/*
              Nothing has ever been read here, so the argument that silence is
              not an answer is the widest thing on the page, not a note in a
              side column. There are no counts to show and none are invented:
            */}
            <EmptyState
              heading={EMPTY_NO_RUNS.heading}
              body={EMPTY_NO_RUNS.body}
              action={EMPTY_NO_RUNS.action}
            />
            <Panel title={CLOCKS.heading} printBlock>
              <ClockStrip deadlines={status.deadlines} variant="table" notes />
            </Panel>
          </>
        )}

        <CorpusPanel snapshots={status.corpus} />

        {status.rejections.length > 0 ? (
          <RefusedDeliveries runs={status.rejections} />
        ) : null}
      </div>

      <footer className={styles.footer} data-print-block="">
        <p className={styles.footerNote}>{TIER_LEGEND}</p>
        <p className={styles.footerNote}>{HOLD_POLICY}</p>
      </footer>
    </>
  );
}
