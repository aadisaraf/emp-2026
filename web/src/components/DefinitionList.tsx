import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./DefinitionList.module.css";

export interface DefinitionItem {
  term: string;
  value: ReactNode;
  /** A second line under the value: a source, a provenance label, a caveat. */
  hint?: ReactNode;
}

export interface DefinitionListProps {
  items: DefinitionItem[];
  /** 1 by default. 2 for a wide panel; never more, the terms stop lining up. */
  columns?: 1 | 2;
  className?: string;
}

/** Label above value, label in the operational register, value in body type. */
export function DefinitionList({ items, columns = 1, className }: DefinitionListProps) {
  return (
    <dl className={cx(styles.list, columns === 2 && styles.two, className)}>
      {items.map((item) => (
        <div className={styles.pair} key={item.term}>
          <dt className={styles.term}>{item.term}</dt>
          <dd className={styles.value}>
            {item.value}
            {item.hint ? <span className={styles.hint}>{item.hint}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}
