import Link from "next/link";
import type { NewLine } from "@/lib/api";
import {
  DataTable,
  EvidenceKind,
  NotRecorded,
  Panel,
  ProvenanceLabel,
  StatusBadge,
  TierBadge,
  type Column,
} from "@/components";
import { UNCLASSIFIED } from "@/lib/strings";
import {
  FIRST_RUN_NOTE,
  NEW_COLUMNS,
  lineTally,
  newSinceTitle,
  nothingNewNote,
} from "./strings";
import styles from "./dashboard.module.css";

export interface NewSincePreviousProps {
  lines: NewLine[];
  previousRunId: number | null;
}

/**
 * What arrived that was not here yesterday.
 *
 * This is the reason a daily run is worth reading. An operator who pulled 42
 * cases yesterday needs the ones that are new today, and every one of them is
 * listed: the server does not truncate this and neither does this table.
 *
 * is_new is a column the matcher wrote once, by diffing this run's
 * (item, recall) pairs against the previous ok run. It is never recomputed and
 * it is never derived here by comparing two payloads.
 *
 * Both empty cases say something, because a bare "0" would be read as "nothing
 * changed" in one case and as "nothing to see" in the other, and only one of
 * those is true.
 */
export function NewSincePrevious({ lines, previousRunId }: NewSincePreviousProps) {
  const title = newSinceTitle(previousRunId);

  if (lines.length === 0) {
    return (
      <Panel title={title} printBlock>
        <p className={styles.note}>
          {previousRunId === null ? FIRST_RUN_NOTE : nothingNewNote(previousRunId)}
        </p>
      </Panel>
    );
  }

  return (
    <Panel
      title={title}
      note={lineTally(lines.length)}
      flush
      printBlock
    >
      <DataTable<NewLine>
        columns={COLUMNS}
        rows={lines}
        rowKey={(line) => line.id}
        caption={title}
        scroll
      />
    </Panel>
  );
}

const COLUMNS: Column<NewLine>[] = [
  {
    key: "status",
    header: NEW_COLUMNS.status,
    width: "112px",
    render: (line) => (
      <>
        <StatusBadge value={line.status} />
        <span className={styles.sub}>
          <TierBadge tier={line.tier} />
        </span>
      </>
    ),
  },
  {
    key: "item",
    header: NEW_COLUMNS.item,
    groupEdge: true,
    render: (line) => (
      // The pull sheet is where a line is read in full, so the link goes there
      // and lands on the line. A sheet that has not scrolled to the anchor yet
      // is still the right page to be on.
      <>
        <Link className={styles.itemLink} href={`/sheet#match-${line.id}`}>
          {line.raw_description}
        </Link>
        <span className={styles.sub}>{line.product_description}</span>
      </>
    ),
  },
  {
    key: "storage",
    header: NEW_COLUMNS.storage,
    width: "130px",
    render: (line) => line.storage_location ?? <NotRecorded />,
  },
  {
    key: "lot",
    header: NEW_COLUMNS.lot,
    variant: "identifier",
    width: "100px",
    render: (line) => line.lot_code ?? <NotRecorded />,
  },
  {
    key: "class",
    header: NEW_COLUMNS.klass,
    width: "92px",
    groupEdge: true,
    render: (line) => line.classification ?? UNCLASSIFIED,
  },
  {
    key: "evidence",
    header: NEW_COLUMNS.evidence,
    width: "150px",
    render: (line) => <EvidenceKind kind={line.evidence_kind} />,
  },
  {
    key: "recall",
    header: NEW_COLUMNS.recall,
    width: "190px",
    render: (line) => (
      <>
        <span className="mono">
          {line.source} {line.source_record_id}
        </span>
        <span className={styles.sub}>
          <ProvenanceLabel
            provenance={line.source_provenance}
            label={line.source_provenance_label}
          />
        </span>
      </>
    ),
  },
  {
    key: "firm",
    header: NEW_COLUMNS.firm,
    width: "180px",
    render: (line) => line.recalling_firm ?? <NotRecorded />,
  },
];
