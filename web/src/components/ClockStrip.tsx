import type { Deadline } from "@/lib/types";
import { CLOCKS, clockProvenance } from "@/lib/strings";
import { formatDateTime } from "@/lib/format";
import { cx } from "@/lib/cx";
import { DataTable, type Column } from "./DataTable";
import styles from "./ClockStrip.module.css";

export interface ClockStripProps {
  /** Either empty, or exactly two entries. */
  deadlines: Deadline[];
  /** rail sits in the stat band; table is the Reporting clocks section. */
  variant?: "rail" | "table";
  /** Show the standing note and the provenance line under the table. */
  notes?: boolean;
  className?: string;
}

/**
 * The two USDA clocks: 24 hours to notify the distributor, 48 hours to finish
 * the inventory assessment, both measured from when the recall notice arrived
 * here.
 *
 * An elapsed clock keeps its place, keeps its due time, and states the overrun
 * in the API's own words. It does not reset, disappear, turn green, or move to
 * a past section, and a client-side tick may never flip overrun back to false.
 *
 * An empty array means this run matched no recall at all. That renders as "no
 * notice has arrived", never as a satisfied clock.
 */
export function ClockStrip({
  deadlines,
  variant = "rail",
  notes,
  className,
}: ClockStripProps) {
  if (deadlines.length === 0) {
    return <p className={cx(styles.none, className)}>{CLOCKS.none}</p>;
  }

  if (variant === "table") {
    return (
      <div className={className}>
        <DataTable<Deadline>
          columns={CLOCK_COLUMNS}
          rows={deadlines}
          rowKey={(deadline) => deadline.key}
          caption={CLOCKS.heading}
        />
        {notes ? (
          <div className={styles.notes}>
            <p className={styles.note}>{CLOCKS.standingNote}</p>
            <p className={styles.note}>
              {clockProvenance(
                formatDateTime(deadlines[0].received_at) ?? deadlines[0].received_at,
                deadlines[0].records,
              )}
            </p>
            {deadlines.some((deadline) => deadline.overrun) ? (
              <p className={styles.overrunNote}>{CLOCKS.overrunNote}</p>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className={cx(styles.rail, className)}>
      {deadlines.map((deadline) => (
        <div className={styles.clock} key={deadline.key}>
          <span className={styles.label}>
            {deadline.label} {deadline.hours}h
          </span>
          <span className={cx(styles.text, deadline.overrun && styles.overrun)}>
            {deadline.text}
          </span>
        </div>
      ))}
    </div>
  );
}

const CLOCK_COLUMNS: Column<Deadline>[] = [
  {
    key: "obligation",
    header: CLOCKS.columns[0],
    render: (deadline) => deadline.label,
  },
  {
    key: "window",
    header: CLOCKS.columns[1],
    variant: "measure",
    width: "72px",
    render: (deadline) => `${deadline.hours}h`,
  },
  {
    key: "due",
    header: CLOCKS.columns[2],
    width: "170px",
    render: (deadline) => (
      <span className="deadline">{formatDateTime(deadline.due_at) ?? deadline.due_at}</span>
    ),
  },
  {
    key: "left",
    header: CLOCKS.columns[3],
    width: "180px",
    render: (deadline) => (
      <span className={cx(styles.text, deadline.overrun && styles.overrun)}>
        {deadline.text}
      </span>
    ),
  },
];
