import type { ReactNode } from "react";
import styles from "./PageHeader.module.css";

export interface PageHeaderProps {
  /** The page title. Once per page, and the only 20px text on it. */
  title: string;
  /** One line of context. A run stamp, a date, a count. Not a paragraph. */
  context?: ReactNode;
  /** Print, refresh, a link to the addressable fallback. Right-aligned. */
  actions?: ReactNode;
}

/**
 * The title block. There is no hero here and there is not going to be one:
 * an operator who opened this page already knows what the product is.
 */
export function PageHeader({ title, context, actions }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.text}>
        <h1 className={styles.title}>{title}</h1>
        {context ? <p className={styles.context}>{context}</p> : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}
