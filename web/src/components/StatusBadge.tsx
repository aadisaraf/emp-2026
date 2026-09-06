import type { LineStatus, RunStatus, StatusState } from "@/lib/types";
import { cx } from "@/lib/cx";
import styles from "./StatusBadge.module.css";

/**
  PULL and HELD are the only two line statuses, enforced by a SQLite CHECK.
  The run states and run statuses are also accepted here so one chip shape
*/
export type StatusValue = LineStatus | StatusState | RunStatus;

export interface StatusBadgeProps {
  value: StatusValue;
  /** The tooltip. Never the only place a fact appears. */
  title?: string;
}

const TONE: Record<string, string> = {
  // Act now.
  PULL: "pull",
  rejected: "alert",
  overdue: "alert",
  action: "alert",
  // Unresolved.
  HELD: "held",
  stale: "attend",
  // Recorded. `never` is neutral on purpose: it is not clear, and it is not
  // an alarm either. The sentence next to it does the work.
  clear: "neutral",
  never: "neutral",
  ok: "neutral",
  running: "neutral",
};

/**
  PULL is the only filled chip on the sheet. HELD is a hollow chip with the
  same footprint, because 814 filled ochre rows would be a wall of beige and
*/
export function StatusBadge({ value, title }: StatusBadgeProps) {
  const tone = TONE[value] ?? "neutral";
  return (
    <span
      className={cx(styles.badge, styles[tone])}
      data-status={value}
      title={title}
    >
      {value}
    </span>
  );
}
