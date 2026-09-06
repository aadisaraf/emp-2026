import type { EvidenceKind as EvidenceKindValue } from "@/lib/types";
import { EVIDENCE_EXPLANATION, EVIDENCE_LABEL, EVIDENCE_UNKNOWN } from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./EvidenceKind.module.css";

export interface EvidenceKindProps {
  /** The raw matches.evidence_kind value. Unknown keys are handled. */
  kind: EvidenceKindValue | string;
  /** Show the raw key after the label, for a detail pane. */
  showRaw?: boolean;
  className?: string;
}

function isKnown(kind: string): kind is EvidenceKindValue {
  return Object.prototype.hasOwnProperty.call(EVIDENCE_LABEL, kind);
}

/**
 * What agreed, in words. The column is called Evidence, not "Match type", and
 * the value is the kind of evidence, not a quality rating.
 *
 * An unrecognised key prints raw rather than being swallowed: the matcher
 * emitting a kind this build does not know about is a fact worth seeing on the
 * line, not a gap to paper over.
 */
export function EvidenceKind({ kind, showRaw, className }: EvidenceKindProps) {
  if (!isKnown(kind)) {
    return (
      <span className={cx(styles.kind, styles.unknown, className)} title={EVIDENCE_UNKNOWN}>
        <code className={styles.raw}>{kind}</code>
      </span>
    );
  }
  return (
    <span className={cx(styles.kind, className)} title={EVIDENCE_EXPLANATION[kind]}>
      {EVIDENCE_LABEL[kind]}
      {showRaw ? <code className={styles.raw}> {kind}</code> : null}
    </span>
  );
}
