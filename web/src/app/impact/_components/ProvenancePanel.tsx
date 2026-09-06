import type { CorpusSnapshot, MenuSummary, Provenance, SourceRef } from "@/lib/api";
import { DataTable, Panel, ProvenanceLabel, type Column } from "@/components";
import { PROVENANCE_LEGEND } from "@/lib/strings";
import { formatCount, formatHours } from "@/lib/format";
import { PROVENANCE_PANEL } from "./copy";
import styles from "./impact.module.css";

export interface ProvenancePanelProps {
  /** claim.sources, already expanded from source_keys by the server. */
  sources: SourceRef[];
  /** header.corpora, populated because impact is always the current run. */
  corpora: CorpusSnapshot[];
  /** header.corpus_note, the frozen sentence, for the case where corpora is empty. */
  corpusNote: string | null;
  /** null on a restaurant deployment, where no menu fixture is in play. */
  menu: MenuSummary | null;
}

/** Every source behind the numbers above, with its label attached. */
export function ProvenancePanel({
  sources,
  corpora,
  corpusNote,
  menu,
}: ProvenancePanelProps) {
  const menuProvenance = menu ? menuProvenanceValues(menu) : [];

  return (
    <Panel id="sources" title={PROVENANCE_PANEL.title} note={PROVENANCE_LEGEND} printBlock>
      {menu && menuProvenance.length > 0 ? (
        <p className={styles.note}>
          {PROVENANCE_PANEL.menuLead}{" "}
          {menuProvenance.map((value, index) => (
            <span key={value}>
              {index > 0 ? " and " : null}
              <ProvenanceLabel provenance={value} />
            </span>
          ))}
          . {PROVENANCE_PANEL.menuLine}
        </p>
      ) : null}

      <p className={styles.note}>
        <span className={styles.inlineLabel}>{PROVENANCE_PANEL.corpusLabel}</span>{" "}
        {corpora.length === 0
          ? corpusNote
          : corpora.map((snapshot, index) => (
              <span key={snapshot.source}>
                {index > 0 ? <span aria-hidden="true"> · </span> : null}
                <span className={styles.identifier}>{snapshot.source}</span>{" "}
                <ProvenanceLabel
                  provenance={snapshot.provenance}
                  label={snapshot.provenance_label}
                  capturedAt={snapshot.captured_at}
                />{" "}
                {formatCount(snapshot.record_count)} records, {formatHours(snapshot.age_hours)} old
              </span>
            ))}
      </p>

      <div className={styles.tableBlock}>
        <DataTable<SourceRef>
          columns={COLUMNS}
          rows={sources}
          rowKey={(source) => source.key}
          caption={PROVENANCE_PANEL.caption}
          className={styles.wideSources}
          scroll
        />
      </div>
    </Panel>
  );
}

/** The distinct provenance values the menu fixtures actually carry. */
function menuProvenanceValues(menu: MenuSummary): Provenance[] {
  const seen = new Set<Provenance>();
  for (const entry of menu.entries) {
    for (const recipe of entry.recipes) seen.add(recipe.provenance);
  }
  return [...seen];
}

const COLUMNS: Column<SourceRef>[] = [
  {
    key: "source",
    header: PROVENANCE_PANEL.columns.source,
    variant: "identifier",
    width: "160px",
    render: (source) => source.key,
  },
  {
    key: "provenance",
    header: PROVENANCE_PANEL.columns.provenance,
    width: "140px",
    render: (source) => (
      <ProvenanceLabel provenance={source.provenance} label={source.provenance_label} />
    ),
  },
  {
    key: "path",
    header: PROVENANCE_PANEL.columns.path,
    variant: "identifier",
    width: "300px",
    groupEdge: true,
    render: (source) => source.path,
  },
  {
    key: "description",
    header: PROVENANCE_PANEL.columns.description,
    render: (source) => source.description,
  },
];
