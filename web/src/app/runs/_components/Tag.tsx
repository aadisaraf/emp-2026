import { cx } from "@/lib/cx";
import styles from "./Tag.module.css";

export interface TagProps {
  /** One or two words, lower case. The CSS does the uppercasing. */
  children: string;
  title?: string;
  className?: string;
}

/**
 * A hollow micro chip, the same footprint as the "new" mark on the sheet.
 *
 * Local to this route on purpose: the shared library has NewMark, which is
 * fixed to one word, and adding a general chip to it would be reaching into a
 * directory another agent owns.
 */
export function Tag({ children, title, className }: TagProps) {
  return (
    <span className={cx(styles.tag, className)} title={title}>
      {children}
    </span>
  );
}
