import type { CorpusSnapshot, SheetHeader } from "@/lib/api";
import { DataTable, Panel, ProvenanceLabel, type Column } from "@/components";
import { FSIS_NOTE, PROVENANCE_LEGEND } from "@/lib/strings";
import { formatCount, formatDateTime, formatHours, formatPercent } from "@/lib/format";
import { cx } from "@/lib/cx";
import {
  CORPUS_PANEL_NOTE_CURRENT,
  CORPUS_PANEL_NOTE_PAST,
  COVERAGE_NOTE,
  corpusNoteFor,
} from "./runsMeta";
import styles from "./CorpusInForce.module.css";

/* What this run was matched against. */

const SNAPSHOT_COLUMNS: Column<CorpusSnapshot>[] = [
  {
    key: "source",
    header: "Source",
    width: "110px",
    render: (snapshot) => <span className={styles.source}>{snapshot.source}</span>,
  },
  {
    key: "provenance",
    header: "Provenance",
    width: "210px",
    render: (snapshot) => (
      <ProvenanceLabel
        provenance={snapshot.provenance}
        label={snapshot.provenance_label}
      />
    ),
  },
  {
    key: "captured_at",
    header: "Captured",
    width: "170px",
    render: (snapshot) => formatDateTime(snapshot.captured_at) ?? snapshot.captured_at,
  },
  {
    key: "record_count",
    header: "Records",
    variant: "measure",
    width: "90px",
    render: (snapshot) => formatCount(snapshot.record_count),
  },
  {
    key: "age_hours",
    header: "Age",
    variant: "measure",
    width: "84px",
    render: (snapshot) => formatHours(snapshot.age_hours),
  },
  {
    key: "fetch_status",
    header: "Fetch",
    width: "150px",
    groupEdge: true,
    render: (snapshot) => (
      <>
        <span className={styles.fetch}>{snapshot.fetch_status}</span>
        {snapshot.stale ? <strong className={styles.stale}>stale</strong> : null}
      </>
    ),
  },
];

export function CorpusInForce({ header }: { header: SheetHeader }) {
  const current = header.corpora.length > 0;
  const note = corpusNoteFor({
    corpus_note: header.corpus_note,
    status: header.run.status,
  });
  const coverage = header.coverage;

  return (
    <Panel
      title="The corpus in force"
      note={current ? CORPUS_PANEL_NOTE_CURRENT : CORPUS_PANEL_NOTE_PAST}
      printBlock
    >
      {current ? (
        <DataTable<CorpusSnapshot>
          columns={SNAPSHOT_COLUMNS}
          rows={header.corpora}
          rowKey={(snapshot) => snapshot.source}
          caption="The recall snapshots loaded right now."
        />
      ) : (
        <p className={cx(styles.frozen, !note.frozen && styles.absent)}>{note.text}</p>
      )}

      {coverage.total > 0 ? (
        <p className={styles.coverage}>
          <span className={styles.coverageLabel}>code coverage</span>{" "}
          {formatCount(coverage.parsed)} of {formatCount(coverage.total)} recall
          records carry a code this build could parse ({formatPercent(coverage.percent)}).
          The other {formatCount(coverage.unparsed)} are matched on firm and product
          wording only. <span className={styles.caveat}>{COVERAGE_NOTE}</span>
        </p>
      ) : null}

      <p className={styles.legend}>{PROVENANCE_LEGEND}</p>
      <p className={styles.legend}>{FSIS_NOTE}</p>
    </Panel>
  );
}
