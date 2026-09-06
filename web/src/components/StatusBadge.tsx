import type { LineStatus, RunStatus, StatusState } from "@/lib/types";
import { cx } from "@/lib/cx";
import styles from "./StatusBadge.module.css";

/** PULL and HELD are the only two line statuses, enforced by a SQLite CHECK.
 *  Run states and run statuses go through the same chip. */
export type StatusValue = LineStatus | StatusState | RunStatus;

const TONE: Record<string, string> = {
  // Act now.
  PULL: "pull",
  rejected: "alert",
  overdue: "alert",
  action: "alert",
  // Unresolved.
  HELD: "held",
  stale: "attend",
  // Recorded. `never` is neutral: not clear, not an alarm.
  clear: "neutral",
  never: "neutral",
  ok: "neutral",
  running: "neutral",
};

/* PULL is the only filled chip. HELD is hollow with the same footprint. */
export function StatusBadge({ value, title }: {
  value: StatusValue;
  /** The tooltip. Never the only place a fact appears. */
  title?: string;
}) {
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
