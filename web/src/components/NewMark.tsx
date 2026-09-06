import { NEW_LINE_BADGE, NEW_LINE_TITLE } from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./NewMark.module.css";

export interface NewMarkProps {
  className?: string;
}

/** The word "new" after the status, for a line whose is_new column is 1. */
export function NewMark({ className }: NewMarkProps) {
  return (
    <span className={cx(styles.mark, className)} title={NEW_LINE_TITLE}>
      {NEW_LINE_BADGE}
    </span>
  );
}
