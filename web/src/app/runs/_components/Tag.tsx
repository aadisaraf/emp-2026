import styles from "./Tag.module.css";

interface TagProps {
  /** One or two words, lower case. The CSS does the uppercasing. */
  children: string;
  title?: string;
}

/** A hollow micro chip, the same footprint as the "new" mark on the sheet. */
export function Tag({ children, title }: TagProps) {
  return (
    <span className={styles.tag} title={title}>
      {children}
    </span>
  );
}
