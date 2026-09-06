import Link from "next/link";
import type { RunHistoryEntry } from "@/lib/api";
import { DataTable, NotRecorded, StatusBadge, type Column } from "@/components";
import { formatCount, shortDeliveryRef } from "@/lib/format";
import { cx } from "@/lib/cx";
import { Tag } from "./Tag";
import {
  NO_FILE_ARRIVED,
  NO_FILE_READ,
  REMATCH_ROWS_TITLE,
  channelExplanation,
  channelLabel,
  corpusNoteFor,
  hasDelivery,
} from "./runsMeta";
import styles from "./RunsTable.module.css";

/* Every run, newest first, refused ones included and refused ones legible. */

export interface RunsTableProps {
  runs: readonly RunHistoryEntry[];
  currentRunId: number | null;
}

function columns(currentRunId: number | null): Column<RunHistoryEntry>[] {
  return [
    {
      key: "business_date",
      header: "Inventory date",
      width: "118px",
      headerTitle: "The local day the export describes, not the day it was read.",
      render: (run) => <span className={styles.date}>{run.business_date}</span>,
    },
    {
      key: "id",
      header: "Run",
      variant: "identifier",
      width: "66px",
      render: (run) => (
        <>
          <Link href={`/runs/${run.id}`} className={styles.runLink}>
            #{run.id}
          </Link>
          {run.id === currentRunId ? (
            <span className={styles.stack}>
              <Tag title="The most recent accepted run. This is the sheet in force.">
                current
              </Tag>
            </span>
          ) : null}
        </>
      ),
    },
    {
      key: "channel",
      header: "Channel",
      width: "132px",
      render: (run) => (
        <span title={channelExplanation(run.channel)}>{channelLabel(run.channel)}</span>
      ),
    },
    {
      key: "delivery_ref",
      header: "Delivery",
      variant: "identifier",
      width: "196px",
      render: (run) => {
        if (!hasDelivery(run)) {
          return (
            <span className={styles.noFile} title={channelExplanation(run.channel)}>
              {NO_FILE_ARRIVED}
            </span>
          );
        }
        if (!run.delivery_ref) return <NotRecorded />;
        // Name on one line, hash on the next. The hash is what an operator
        // compares against the file they re-sent, so it is not allowed to
        const hash = run.delivery_ref.indexOf("#");
        const name = hash === -1 ? run.delivery_ref : run.delivery_ref.slice(0, hash);
        return (
          <span title={shortDeliveryRef(run.delivery_ref) ?? undefined}>
            <span className={styles.refName}>{name}</span>
            {hash === -1 ? null : (
              <span className={styles.refHash}>
                #{run.delivery_ref.slice(hash + 1, hash + 9)}
              </span>
            )}
          </span>
        );
      },
    },
    {
      key: "rows_read",
      header: "Rows",
      variant: "measure",
      width: "78px",
      groupEdge: true,
      headerTitle: "Rows read out of the delivery, and how many were kept despite an unreadable field.",
      render: (run) => {
        if (!hasDelivery(run)) {
          return (
            <span className={styles.noFile} title={REMATCH_ROWS_TITLE}>
              {NO_FILE_READ}
            </span>
          );
        }
        return (
          <>
            {formatCount(run.rows_read)}
            {run.rows_partial > 0 ? (
              <span
                className={styles.sub}
                title="Rows with a field this build could not read. They were kept, not dropped."
              >
                {run.rows_partial} partial
              </span>
            ) : null}
          </>
        );
      },
    },
    {
      key: "pull_count",
      header: "Pull",
      variant: "measure",
      width: "58px",
      render: (run) => formatCount(run.pull_count),
    },
    {
      key: "held_count",
      header: "Held",
      variant: "measure",
      width: "58px",
      render: (run) => formatCount(run.held_count),
    },
    {
      key: "new_count",
      header: "New",
      variant: "measure",
      width: "52px",
      headerTitle: "Lines that were not on the previous accepted run.",
      render: (run) => formatCount(run.new_count),
    },
    {
      key: "status",
      header: "Result",
      width: "194px",
      groupEdge: true,
      render: (run) => (
        <>
          <StatusBadge value={run.status} />
          {run.rejection_reason ? (
            <span className={styles.reason}>{run.rejection_reason}</span>
          ) : null}
        </>
      ),
    },
    {
      key: "corpus_note",
      header: "Corpus in force",
      headerTitle:
        "The recall snapshots this run matched against, frozen when the run finalized.",
      render: (run) => {
        const note = corpusNoteFor(run);
        return (
          <span className={cx(styles.corpus, !note.frozen && styles.corpusMissing)}>
            {note.text}
          </span>
        );
      },
    },
  ];
}

export function RunsTable({ runs, currentRunId }: RunsTableProps) {
  return (
    <DataTable<RunHistoryEntry>
      columns={columns(currentRunId)}
      rows={runs}
      rowKey={(run) => run.id}
      caption="Every run this location has recorded, newest first, refused deliveries included."
      sticky
      className={styles.table}
      rowClassName={(run) => cx(run.status === "rejected" && styles.refused)}
    />
  );
}
