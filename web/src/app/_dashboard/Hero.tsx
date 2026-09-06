import Link from "next/link";
import type { Deadline, Run, StatusResponse } from "@/lib/types";
import { formatCount, formatDate } from "@/lib/format";
import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import styles from "./dashboard.module.css";

/* The count, the word, and the four things you can do about it. */
export function Hero({ status }: { status: StatusResponse }) {
  const run = status.run;
  const count = run ? (formatCount(status.counts.pull_count) ?? "0") : "0";
  const nearest = status.deadlines.find((d) => !d.overrun) ?? status.deadlines[0] ?? null;

  return (
    <section className={styles.hero}>
      <div className={styles.figureBlock}>
        <span className={styles.figure} data-state={status.state}>
          {count}
        </span>
        <span className={cx(styles.word, status.stale_corpus && styles.stale)}>{status.word}</span>
      </div>

      <div className={cx(styles.actions, "no-print")}>
        {nearest ? (
          <span className={cx(styles.pill, nearest.overrun && styles.pillAlert)}>
            <Icon name="clock" size={16} />
            {nearest.text}
          </span>
        ) : null}
        {run ? (
          <>
            <Link href="/ingest" className={styles.roundAction} aria-label="Add inventory">
              <Icon name="plus" />
            </Link>
            <Link href="/sheet" className={cx(styles.pill, styles.pillPrimary)}>
              Open sheet
            </Link>
            <Link href="/impact" className={cx(styles.pill, styles.pillSecondary)}>
              Impact
            </Link>
          </>
        ) : (
          <Link href="/ingest" className={cx(styles.pill, styles.pillPrimary)}>
            Add inventory
          </Link>
        )}
      </div>
    </section>
  );
}

const FLEX: Record<Deadline["hours"], number> = { 24: 2, 48: 4 };

/* The run's life as segments: received, then each clock, in proportion. */
export function StageBar({ run, deadlines }: { run: Run; deadlines: Deadline[] }) {
  return (
    <section className={styles.stage}>
      <div className={styles.stageHead}>
        <span>Deadlines</span>
        <span className={styles.stageDate}>
          <Icon name="flag" size={14} />
          {formatDate(run.business_date) ?? run.business_date}
        </span>
      </div>
      <div className={styles.segments}>
        <span className={cx(styles.segment, styles.segmentDone)} style={{ flex: 1 }}>
          Received
          <Icon name="check" size={16} />
        </span>
        {deadlines.map((d, i) => {
          const tone = d.overrun
            ? styles.segmentAlert
            : i === 0
              ? styles.segmentCurrent
              : styles.segmentLater;
          return (
            <span key={d.key} className={cx(styles.segment, tone)} style={{ flex: FLEX[d.hours] }}>
              <span className={styles.segmentText}>
                {d.label} · {d.hours}h
              </span>
              <span className={styles.segmentLeft}>{d.text}</span>
              <Icon name={d.overrun ? "flag" : "clock"} size={16} />
            </span>
          );
        })}
      </div>
    </section>
  );
}
