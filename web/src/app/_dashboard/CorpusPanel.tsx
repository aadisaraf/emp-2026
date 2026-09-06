import Link from "next/link";
import type { CorpusSnapshot } from "@/lib/api";
import { DataTable, Panel, ProvenanceLabel, type Column } from "@/components";
import { FSIS_NOTE, PROVENANCE_LEGEND } from "@/lib/strings";
import { formatCount, formatDateTime, formatHours } from "@/lib/format";
import {
  CORPUS_COLUMNS,
  NO_CORPUS,
  PANEL,
  STALE_NOTE,
  STALE_WORD,
  corpusTally,
} from "./strings";
import styles from "./dashboard.module.css";

/** Where every recall record on this screen came from. */
export function CorpusPanel({ snapshots }: { snapshots: CorpusSnapshot[] }) {
  if (snapshots.length === 0) {
    return (
      <Panel title={PANEL.corpus} printBlock>
        <p className={styles.note}>{NO_CORPUS}</p>
        <p className={styles.note}>{PROVENANCE_LEGEND}</p>
      </Panel>
    );
  }

  const records = snapshots.reduce((total, snapshot) => total + snapshot.record_count, 0);
  const authored = snapshots.some((snapshot) => snapshot.provenance === "hand-authored");
  const stale = snapshots.some((snapshot) => snapshot.stale);

  return (
    <Panel
      title={PANEL.corpus}
      note={corpusTally(formatCount(records) ?? String(records), snapshots.length)}
      printBlock
    >
      <DataTable<CorpusSnapshot>
        columns={COLUMNS}
        rows={snapshots}
        rowKey={(snapshot) => snapshot.source}
        caption={PANEL.corpus}
        scroll
      />
      <p className={styles.fine}>{PROVENANCE_LEGEND}</p>
      {authored ? <p className={styles.fine}>{FSIS_NOTE}</p> : null}
      {stale ? <p className={styles.fine}>{STALE_NOTE}</p> : null}
      <p className={styles.fine}>
        <Link href="/sources">Where every number comes from</Link>
      </p>
    </Panel>
  );
}

const COLUMNS: Column<CorpusSnapshot>[] = [
  {
    key: "source",
    header: CORPUS_COLUMNS.source,
    width: "120px",
    render: (snapshot) => (
      <>
        <span className={styles.source}>{snapshot.source}</span>
        {snapshot.stale ? (
          <span className={styles.sub}>
            <span className={styles.staleFlag}>{STALE_WORD}</span>
          </span>
        ) : null}
      </>
    ),
  },
  {
    key: "provenance",
    header: CORPUS_COLUMNS.provenance,
    width: "170px",
    render: (snapshot) => (
      <ProvenanceLabel
        provenance={snapshot.provenance}
        label={snapshot.provenance_label}
      />
    ),
  },
  {
    key: "captured",
    header: CORPUS_COLUMNS.captured,
    width: "170px",
    groupEdge: true,
    render: (snapshot) => formatDateTime(snapshot.captured_at) ?? snapshot.captured_at,
  },
  {
    key: "records",
    header: CORPUS_COLUMNS.records,
    variant: "measure",
    width: "90px",
    render: (snapshot) => formatCount(snapshot.record_count),
  },
  {
    key: "age",
    header: CORPUS_COLUMNS.age,
    variant: "measure",
    width: "90px",
    render: (snapshot) => formatHours(snapshot.age_hours),
  },
  {
    key: "fetch",
    header: CORPUS_COLUMNS.fetch,
    width: "150px",
    render: (snapshot) => <span className={styles.source}>{snapshot.fetch_status}</span>,
  },
];
