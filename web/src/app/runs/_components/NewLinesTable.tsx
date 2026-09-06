import type { NewLine } from "@/lib/api";
import {
  DataTable,
  EvidenceKind,
  NotRecorded,
  ProvenanceLabel,
  StatusBadge,
  TierBadge,
  type Column,
} from "@/components";
import { UNCLASSIFIED } from "@/lib/strings";
import styles from "./NewLinesTable.module.css";

/*
  The lines this run produced that the run before it did not.

  is_new is a column the matcher wrote when the line was created, by diffing
  the pair against the previous accepted run. Nothing here recomputes it and
  nothing here compares two runs client-side: this table renders the rows the
  API returned, in the order it returned them.
*/

export interface NewLinesTableProps {
  lines: readonly NewLine[];
}

const COLUMNS: Column<NewLine>[] = [
  {
    key: "status",
    header: "Status",
    width: "96px",
    render: (line) => (
      <>
        <StatusBadge value={line.status} />
        <span className={styles.tier}>
          <TierBadge tier={line.tier} />
        </span>
      </>
    ),
  },
  {
    key: "item",
    header: "Item",
    render: (line) => (
      <>
        <span className={styles.item}>{line.raw_description}</span>
        <span className={styles.against}>{line.product_description}</span>
      </>
    ),
  },
  {
    key: "storage_location",
    header: "Storage location",
    width: "146px",
    render: (line) =>
      line.storage_location ?? <NotRecorded word="storage not recorded" />,
  },
  {
    key: "lot_code",
    header: "Lot",
    variant: "identifier",
    width: "104px",
    render: (line) => line.lot_code ?? <NotRecorded />,
  },
  {
    key: "classification",
    header: "Class",
    width: "96px",
    groupEdge: true,
    render: (line) => line.classification ?? UNCLASSIFIED,
  },
  {
    key: "evidence_kind",
    header: "Evidence",
    width: "168px",
    render: (line) => <EvidenceKind kind={line.evidence_kind} />,
  },
  {
    key: "recall",
    header: "Recall record",
    width: "252px",
    groupEdge: true,
    render: (line) => (
      <>
        <span className={styles.recordId}>
          {line.source} {line.source_record_id}
        </span>
        <span className={styles.provenance}>
          <ProvenanceLabel
            provenance={line.source_provenance}
            label={line.source_provenance_label}
          />
        </span>
        <span className={styles.firm}>{line.recalling_firm ?? <NotRecorded />}</span>
      </>
    ),
  },
];

export function NewLinesTable({ lines }: NewLinesTableProps) {
  return (
    <DataTable<NewLine>
      columns={COLUMNS}
      rows={lines}
      rowKey={(line) => line.id}
      caption="Lines on this run that were not on the run before it."
      className={styles.table}
    />
  );
}
