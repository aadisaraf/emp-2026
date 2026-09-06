import styles from "./HumanEntryMark.module.css";

export interface HumanEntryMarkProps {
  /** state_report.HUMAN_MARKER, from the payload. Rendered verbatim. */
  marker: string;
  /** Draw a ruled line under the mark, for a field somebody writes into. */
  ruled?: boolean;
}

/** What a field the system cannot fill says instead of nothing. */
export function HumanEntryMark({ marker, ruled }: HumanEntryMarkProps) {
  return (
    <span className={styles.wrap}>
      <span className={styles.mark}>{marker}</span>
      {ruled ? <span className={styles.rule} aria-hidden="true" /> : null}
    </span>
  );
}
