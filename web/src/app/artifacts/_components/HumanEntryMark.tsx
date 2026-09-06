import styles from "./HumanEntryMark.module.css";

export interface HumanEntryMarkProps {
  /** state_report.HUMAN_MARKER, from the payload. Rendered verbatim. */
  marker: string;
  /** Draw a ruled line under the mark, for a field somebody writes into. */
  ruled?: boolean;
}

/**
 * What a field the system cannot fill says instead of nothing.
 *
 * A blank box on a state form reads as "nothing to report". A box reading
 * REQUIRES HUMAN ENTRY reads as "you are not finished". The difference is the
 * whole point of this artifact, so the marker is a hollow chip in the ochre
 * that means unresolved everywhere else on this dashboard, and never an empty
 * cell, a dash, or the letters N/A.
 *
 * Hollow rather than filled: 13 of the 24 fields carry this, and 13 filled
 * chips would out-shout the 11 real values on the same page.
 */
export function HumanEntryMark({ marker, ruled }: HumanEntryMarkProps) {
  return (
    <span className={styles.wrap}>
      <span className={styles.mark}>{marker}</span>
      {ruled ? <span className={styles.rule} aria-hidden="true" /> : null}
    </span>
  );
}
