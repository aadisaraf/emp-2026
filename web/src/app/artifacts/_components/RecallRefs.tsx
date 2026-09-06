import type { Provenance, RecallSource, RecallStatus } from "@/lib/api";
import { ProvenanceLabel } from "@/components";
import styles from "./RecallRefs.module.css";

export interface RecallRef {
  source: RecallSource;
  source_provenance: Provenance;
  source_provenance_label: string;
  source_record_id: string;
  recall_status?: RecallStatus;
}

export interface RecallRefsProps {
  refs: RecallRef[];
}

interface Group {
  source: RecallSource;
  provenance: Provenance;
  label: string;
  refs: RecallRef[];
}

/**
  The recall notices behind one inventory line, grouped by the agency that
  issued them.
*/
export function RecallRefs({ refs }: RecallRefsProps) {
  const groups: Group[] = [];

  for (const ref of refs) {
    const existing = groups.find((group) => group.source === ref.source);
    if (existing) {
      existing.refs.push(ref);
    } else {
      groups.push({
        source: ref.source,
        provenance: ref.source_provenance,
        label: ref.source_provenance_label,
        refs: [ref],
      });
    }
  }

  return (
    <span className={styles.refs}>
      {groups.map((group) => (
        <span className={styles.group} key={group.source}>
          <span className={styles.head}>
            <span className={styles.source}>{group.source}</span>{" "}
            <ProvenanceLabel provenance={group.provenance} label={group.label} />{" "}
            <span className={styles.count}>{group.refs.length}</span>
          </span>
          <span className={styles.ids}>
            {group.refs.map((ref, index) => (
              <span key={`${ref.source_record_id}-${index}`}>
                {index > 0 ? <span aria-hidden="true">, </span> : null}
                <span className={styles.id}>{ref.source_record_id}</span>
                {ref.recall_status && ref.recall_status !== "active" ? (
                  <span className={styles.recallStatus}> ({ref.recall_status})</span>
                ) : null}
              </span>
            ))}
          </span>
        </span>
      ))}
    </span>
  );
}
