import Link from "next/link";
import type { StatusResponse } from "@/lib/api";
import { STATE_ACTIONS, NEVER_NOTE, overdueAction } from "@/lib/strings";
import { formatDateTime } from "@/lib/format";
import { StatusBadge } from "@/components";
import { cx } from "@/lib/cx";
import {
  ADD_INVENTORY,
  AS_OF_LABEL,
  NEXT_LABEL,
  OPEN_SHEET,
  STATE_LABEL,
  deliveriesWithoutARun,
  pollUnreachable,
} from "./strings";
import styles from "./dashboard.module.css";

export interface StateStatementProps {
  status: StatusResponse;
  /** false once a poll stops answering. The figures stay; a line says so. */
  reachable: boolean;
}

/** The state of this location, in the largest text on the page. */
export function StateStatement({ status, reachable }: StateStatementProps) {
  const action =
    status.state === "overdue" && status.run_age_hours !== null
      ? overdueAction(status.run_age_hours)
      : STATE_ACTIONS[status.state];

  const asOf = formatDateTime(status.generated_at) ?? status.generated_at;
  const hasRun = status.run !== null;

  return (
    <section className={styles.statement} data-print-block="">
      <div className={styles.eyebrow}>
        <span className={styles.eyebrowLabel}>{STATE_LABEL}</span>
        <StatusBadge value={status.state} />
        <span className={styles.spacer} />
        <div className={cx(styles.actions, "no-print")}>
          {/*
            The primary weight belongs to the sheet, which is the work. A
            location that has never received an export has nothing to do yet,
            so the way in is offered, not urged.
          */}
          {hasRun ? (
            <Link className={styles.primary} href="/sheet">
              {OPEN_SHEET}
            </Link>
          ) : (
            <Link className={styles.secondary} href="/ingest">
              {ADD_INVENTORY}
            </Link>
          )}
        </div>
      </div>

      <h1
        className={cx(styles.word, status.stale_corpus && styles.stale)}
        data-state={status.state}
      >
        <span className={styles.mark}>{status.word}</span>
      </h1>

      <p className={styles.detail}>{status.detail}</p>

      {status.never_received ? (
        <>
          <p className={styles.neverNote}>{NEVER_NOTE}</p>
          {status.run_count > 0 ? (
            <p className={styles.neverNote}>
              {deliveriesWithoutARun(status.run_count)}
            </p>
          ) : null}
        </>
      ) : null}

      {reachable ? null : (
        <p className={styles.unreachable}>{pollUnreachable(asOf)}</p>
      )}

      <div className={styles.nextRow}>
        <span className={styles.nextLabel}>{NEXT_LABEL}</span>
        <span className={styles.next}>{action}</span>
        <span className={styles.asOf}>
          <span className={styles.asOfLabel}>{AS_OF_LABEL}</span> {asOf}
        </span>
      </div>
    </section>
  );
}
