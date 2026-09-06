import type { ReactNode } from "react";
import type { Deadline } from "@/lib/types";
import { ClockStrip } from "./ClockStrip";
import { cx } from "@/lib/cx";
import styles from "./StatRail.module.css";

export interface StatRailItem {
  label: string;
  value: ReactNode;
  title?: string;
}

export interface StatRailProps {
  items: StatRailItem[];
  /** The two USDA clocks sit at the right end of the same band. */
  deadlines?: Deadline[];
  className?: string;
}

/** One horizontal band of label and value pairs, separated by 1px rules. */
export function StatRail({ items, deadlines, className }: StatRailProps) {
  return (
    <div className={cx(styles.rail, className)} data-role="statrail">
      {items.map((item) => (
        <div className={styles.stat} key={item.label} title={item.title}>
          <span className={styles.label}>{item.label}</span>
          <span className={styles.value}>{item.value}</span>
        </div>
      ))}
      {deadlines ? <ClockStrip deadlines={deadlines} className={styles.clocks} /> : null}
    </div>
  );
}
