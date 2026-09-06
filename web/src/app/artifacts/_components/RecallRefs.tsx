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
 * The recall notices behind one inventory line, grouped by the agency that
 * issued them.
 *
 * One line in the fixtures is named by 52 notices, so repeating the provenance
 * label after each of 52 ids would bury the label in its own repetition. The
 * label is therefore carried once per agency group and every id is printed
 * under it, which keeps the constitutional requirement (the label is visible,
 * on screen and on paper) while leaving the ids readable.
 *
 * Ids are set in mono and left aligned. They are names spelled with digits,
 * and the operator is comparing them against a notice in their other hand.
 *
 * A notice the agency has since terminated or amended keeps its place and
 * carries the word. A terminated recall did not un-recall the case that is
 * already in the freezer, and dropping it here would silently shorten a
 * custody record.
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
