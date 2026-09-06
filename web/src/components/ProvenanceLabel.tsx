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
  className?: string;
}

const FALLBACK: Record<Provenance, string> = {
  live: "live",
  "dated-snapshot": "dated snapshot",
  "hand-authored": "hand-authored",
};

/**
 * Three labels and only three, and this component is the only place they are
 * rendered, so there is one place to check that they are still legible.
 *
 * The label is load-bearing UI: it must be visible on screen and in print. It
 * may not be styled into invisibility, hidden behind a tooltip, faded below
 * 4.5:1, or dropped because a row felt busy. Muted is 5.27:1 on white here,
 * which is quiet on purpose and readable on purpose.
 *
 * hand-authored also carries a dotted underline, so it is separable
 * from dated-snapshot at a glance and after a photocopy.
 */
export function ProvenanceLabel({
  provenance,
  label,
  capturedAt,
  className,
}: ProvenanceLabelProps) {
  const text = label ?? FALLBACK[provenance];
  const captured = capturedAt ? capturedAt.slice(0, 10) : null;
  return (
    <span
      className={cx(
        styles.provenance,
        provenance === "hand-authored" && styles.authored,
        className,
      )}
      data-provenance={provenance}
      title={PROVENANCE_EXPLANATION[provenance]}
    >
      {text}
      {captured ? <span className={styles.captured}> · captured {captured}</span> : null}
    </span>
  );
}
