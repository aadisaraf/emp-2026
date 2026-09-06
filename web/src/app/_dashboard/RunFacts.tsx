import type { Counts, Run } from "@/lib/api";
import { DefinitionList, NotRecorded, Panel, StatusBadge, type DefinitionItem } from "@/components";
import { formatCount, formatDateTime, shortDeliveryRef } from "@/lib/format";
import { channelLabel } from "@/lib/strings";
import { cx } from "@/lib/cx";
import { COUNT_LABELS, FIRST_RUN_NOTE, NEW_COUNT_TITLE, RUN_TERMS, runTitle } from "./strings";
import styles from "./dashboard.module.css";

export interface RunFactsProps {
  run: Run;
  counts: Counts;
  /** The run new_count is measured against. null on the first run here. */
  previousRunId: number | null;
}

/**
 * The four counts, then where they came from.
 *
 * PULL 42 and HELD 814 are two exact integers and they are rendered as two
 * exact integers. There is no donut, because 42 against 814 is a sliver against
 * a ring, and there is no count-up, because 856 is not a scoreboard.
 *
 * The counts, the business date, the channel and the delivery reference sit in
 * one panel deliberately: a number and its provenance are read together, and
 * the corpus_note underneath is the frozen sentence that says which snapshots
 * this run was matched against.
 */
export function RunFacts({ run, counts, previousRunId }: RunFactsProps) {
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
      <div className={styles.counts}>
        <div className={cx(styles.count, styles.countPull)}>
          <span className={styles.countLabel}>{COUNT_LABELS.pull}</span>
          <span className={styles.countValue}>{formatCount(counts.pull_count)}</span>
        </div>
        <div className={styles.count}>
          <span className={styles.countLabel}>{COUNT_LABELS.held}</span>
          <span className={styles.countValue}>{formatCount(counts.held_count)}</span>
        </div>
        <div className={styles.count}>
          <span className={styles.countLabel}>{COUNT_LABELS.total}</span>
          <span className={styles.countValue}>{formatCount(counts.total)}</span>
        </div>
        <div
          className={styles.count}
          title={previousRunId === null ? FIRST_RUN_NOTE : NEW_COUNT_TITLE}
        >
          <span className={styles.countLabel}>{COUNT_LABELS.fresh}</span>
          <span className={styles.countValue}>{formatCount(counts.new_count)}</span>
        </div>
      </div>

      <DefinitionList items={facts} columns={2} />

      {run.corpus_note ? (
        <p className={styles.fine}>
          <span className={styles.fineLabel}>corpus</span> {run.corpus_note}
        </p>
      ) : null}
    </Panel>
  );
}
