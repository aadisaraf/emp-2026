import type { Run } from "@/lib/api";
import { DefinitionList, NotRecorded, Panel, StatusBadge, type DefinitionItem } from "@/components";
import { formatCount, formatDateTime, shortDeliveryRef } from "@/lib/format";
import { channelLabel } from "@/lib/strings";
import { RUN_TERMS, runTitle } from "./strings";
import styles from "./dashboard.module.css";

export interface RunFactsProps {
  run: Run;
}

/** Where this run came from, and when. The counts are the stat rail's job. */
export function RunFacts({ run }: RunFactsProps) {
  const facts: DefinitionItem[] = [
    { term: RUN_TERMS.status, value: <StatusBadge value={run.status} /> },
    { term: RUN_TERMS.date, value: run.business_date },
    { term: RUN_TERMS.channel, value: channelLabel(run.channel) },
    {
      term: RUN_TERMS.delivery,
      value: shortDeliveryRef(run.delivery_ref) ? (
        <span className="mono">{shortDeliveryRef(run.delivery_ref)}</span>
      ) : (
        <NotRecorded />
      ),
    },
    { term: RUN_TERMS.rowsRead, value: <span className="num">{formatCount(run.rows_read)}</span> },
    {
      term: RUN_TERMS.rowsPartial,
      value: <span className="num">{formatCount(run.rows_partial)}</span>,
    },
    { term: RUN_TERMS.started, value: formatDateTime(run.started_at) ?? run.started_at },
    {
      term: RUN_TERMS.finalized,
      value: formatDateTime(run.finalized_at) ?? <NotRecorded />,
    },
  ];

  return (
    <Panel title={runTitle(run.id)} printBlock>
      {/*
        The four counts are stated by the stat rail at the top of every route,
        at a size you can read across a kitchen. Repeating them here put the
        same four numbers twice on one screen, 300px apart, which is a large
        part of why the page read as cluttered. What this panel is for is the
        provenance of the run: where it came from and when.
      */}
      <DefinitionList items={facts} columns={2} />

      {run.corpus_note ? (
        <p className={styles.fine}>
          <span className={styles.fineLabel}>corpus</span> {run.corpus_note}
        </p>
      ) : null}
    </Panel>
  );
}
