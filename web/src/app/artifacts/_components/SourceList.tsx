import type { SourceRef } from "@/lib/api";
import { ProvenanceLabel } from "@/components";
import { FSIS_NOTE, PROVENANCE_LEGEND } from "@/lib/strings";
import styles from "./document.module.css";

export interface SourceListProps {
  sources: SourceRef[];
  /** An extra sentence about this document's own layout, where it has one. */
  note?: string;
}

/** Every file behind the document, on the document. */
export function SourceList({ sources, note }: SourceListProps) {
  const namesFsis = sources.some((source) => source.key === "fsis");

  return (
    <footer className={styles.sources}>
      <p className={styles.sourcesHead}>Sources</p>
      <div className={styles.sourceList}>
        {sources.map((source) => (
          <div className={styles.source} key={source.key}>
            <span className={styles.sourceKey}>{source.key}</span>
            <span>
              <ProvenanceLabel
                provenance={source.provenance}
                label={source.provenance_label}
              />{" "}
              <span className={styles.sourcePath}>{source.path}</span>
            </span>
            <span className={styles.sourceWhat}>{source.description}</span>
          </div>
        ))}
      </div>
      <p className={styles.sourceLegend}>{PROVENANCE_LEGEND}</p>
      {namesFsis ? <p className={styles.sourceFsis}>{FSIS_NOTE}</p> : null}
      {note ? <p className={styles.sourceFsis}>{note}</p> : null}
    </footer>
  );
}
