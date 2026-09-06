import type { Provenance } from "@/lib/types";
import { PROVENANCE_EXPLANATION } from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./ProvenanceLabel.module.css";

export interface ProvenanceLabelProps {
  /** The raw value: live, dated-snapshot or hand-authored. */
  provenance: Provenance;
  /** The human label from the payload (provenance_label). Rendered verbatim. */
  label?: string;
  /** Appends "captured 2026-09-05" when the payload carries a capture time. */
  capturedAt?: string | null;
}

const FALLBACK: Record<Provenance, string> = {
  live: "live",
  "dated-snapshot": "dated snapshot",
  "hand-authored": "hand-authored",
};

/** Three provenance labels, rendered in exactly one place. */
export function ProvenanceLabel({ provenance, label, capturedAt }: ProvenanceLabelProps) {
  const text = label ?? FALLBACK[provenance];
  const captured = capturedAt ? capturedAt.slice(0, 10) : null;
  return (
    <span
      className={cx(styles.provenance, provenance === "hand-authored" && styles.authored)}
      data-provenance={provenance}
      title={PROVENANCE_EXPLANATION[provenance]}
    >
      {text}
      {captured ? <span className={styles.captured}> · captured {captured}</span> : null}
    </span>
  );
}
