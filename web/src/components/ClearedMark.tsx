import { cx } from "@/lib/cx";
import styles from "./ClearedMark.module.css";

export interface ClearedMarkProps {
  /** The person who cleared it, when the payload carries the decision. */
  actor?: string | null;
  /** An absolute timestamp, already formatted. */
  when?: string | null;
  /** cleared_count, when more than one decision exists for this pair. */
  count?: number;
  className?: string;
}

/**
 * A cleared line, marked in place.
 *
 * Clearing is not a status: matches.status stays PULL or HELD and the row stays
 * on the sheet, in its position, for every future run. What exists is an audit
 * row, and this is that row rendered on the line. Nothing is deleted, nothing
 * moves to a "resolved" section, and there is no filter that hides this.
 *
 * A clearing is always the act of a named person. When the payload only carries
 * the count, the text still says a person did it, because no automatic process
 * in this system can.
 */
export function ClearedMark({ actor, when, count, className }: ClearedMarkProps) {
  const who = actor ? `cleared by ${actor}` : "cleared by a named person";
  const extra = count && count > 1 ? ` (${count} decisions)` : "";
  return (
    <span className={cx(styles.mark, className)}>
      {who}
      {when ? ` ${when}` : ""}
      {extra}
    </span>
  );
}
