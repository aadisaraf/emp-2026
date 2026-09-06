import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./Panel.module.css";

export interface PanelProps {
  /** Section identity is the heading. There is no section icon. */
  title?: ReactNode;
  /** One line under the title: a caveat, a source, a count. */
  note?: ReactNode;
  actions?: ReactNode;
  /** Drop the body padding when the panel contains a table. */
  flush?: boolean;
  /** Keep this panel on one page when printed. */
  printBlock?: boolean;
  id?: string;
  className?: string;
  children: ReactNode;
}

/** An opaque box with a 1px border. No shadow, no radius, no translucency. */
export function Panel({
  title,
  note,
  actions,
  flush,
  printBlock,
  id,
  className,
  children,
}: PanelProps) {
  return (
    <section
      id={id}
      className={cx(styles.panel, className)}
      data-print-block={printBlock ? "" : undefined}
    >
      {title || actions || note ? (
        <header className={styles.head}>
          <div className={styles.headText}>
            {title ? <h2 className={styles.title}>{title}</h2> : null}
            {note ? <p className={styles.note}>{note}</p> : null}
          </div>
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </header>
      ) : null}
      <div className={cx(styles.body, flush && styles.flush)}>{children}</div>
    </section>
  );
}
