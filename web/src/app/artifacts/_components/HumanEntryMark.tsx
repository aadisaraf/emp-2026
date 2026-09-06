import styles from "./HumanEntryMark.module.css";

interface HumanEntryMarkProps {
  /** state_report.HUMAN_MARKER, from the payload. Rendered verbatim. */
  marker: string;
}

/** What a field the system cannot fill says instead of nothing. */
export function HumanEntryMark({ marker }: HumanEntryMarkProps) {
  return (
    <span className={styles.wrap}>
      <span className={styles.mark}>{marker}</span>
      <span className={styles.rule} aria-hidden="true" />
    </span>
  );
}
