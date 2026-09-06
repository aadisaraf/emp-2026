import styles from "./ClearedMark.module.css";

export interface ClearedMarkProps {
  /** The person who cleared it, when the payload carries the decision. */
  actor?: string | null;
  /** An absolute timestamp, already formatted. */
  when?: string | null;
  /** cleared_count, when more than one decision exists for this pair. */
  count?: number;
}

/** A cleared line, marked in place. */
export function ClearedMark({ actor, when, count }: ClearedMarkProps) {
  const who = actor ? `cleared by ${actor}` : "cleared by a named person";
  const extra = count && count > 1 ? ` (${count} decisions)` : "";
  return (
    <span className={styles.mark}>
      {who}
      {when ? ` ${when}` : ""}
      {extra}
    </span>
  );
}
