import { NEW_LINE_BADGE, NEW_LINE_TITLE } from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./NewMark.module.css";

export interface NewMarkProps {
  className?: string;
}

/**
 * The word "new" after the status, for a line whose is_new column is 1.
 *
 * is_new is written once by the matcher, by diffing against the previous ok
 * run. It is never recomputed and never derived here by comparing two runs.
 * On the first run at a location every line is is_new 0, which is correct.
 */
export function NewMark({ className }: NewMarkProps) {
  return (
    <span className={cx(styles.mark, className)} title={NEW_LINE_TITLE}>
      {NEW_LINE_BADGE}
    </span>
  );
}
