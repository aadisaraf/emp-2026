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

/**
 * One horizontal band of label and value pairs, separated by 1px rules.
 *
 * Not three cards in a row. PULL 42, HELD 814 and the clocks are not three
 * peers to be boxed and shadowed; they are the numbers an operator reads in one
 * saccade, so they sit on one line at one type size with the deadlines beside
 * them. Nothing counts up, and nothing here is a chart: 42 against 814 as a
 * donut is a sliver against a ring.
 */
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
