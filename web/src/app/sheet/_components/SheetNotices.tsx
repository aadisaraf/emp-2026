import Link from "next/link";
import type { Run, SheetHeader } from "@/lib/api";
import { EMPTY_ZERO_MATCHES_HEADING } from "@/lib/strings";
import { formatCount, formatDate, formatDateTime } from "@/lib/format";
import styles from "./sheet.module.css";

/*
  The three things a sheet has to be able to say about itself, none of which is
  an empty state and none of which reads as "clear":
*/

export interface PastRunBannerProps {
  header: SheetHeader;
  decidedBefore: string | null;
  /** The run that is current now, when the page was able to ask. */
  currentRunId: number | null;
}

export function PastRunBanner({ header, decidedBefore, currentRunId }: PastRunBannerProps) {
  const finalized = formatDateTime(header.run.finalized_at);
  const replaced = formatDateTime(decidedBefore);

  return (
    <div className={styles.notice} data-print-block>
      <p className={styles.noticeHeading}>This is a past run.</p>
      <p className={styles.noticeBody}>
        Run #{header.run.id} was finalized{finalized ? ` ${finalized}` : ""} and has since been
        replaced. The lines below are the lines that run produced, in the order it produced them,
        matched against the corpus named above. Nothing on this page is a statement about what is
        in the building now.
        {replaced
          ? ` Clearings are shown as they stood at ${replaced}, the moment this sheet was replaced.`
          : ""}
      </p>
      <p className={styles.noticeAction}>
        <Link href="/sheet">
          {currentRunId !== null
            ? `Go to the current sheet, run #${currentRunId}.`
            : "Go to the current sheet."}
        </Link>
      </p>
    </div>
  );
}

export interface RunWithoutLinesProps {
  run: Run;
  /** Offer the way back only when this is not the sheet the operator works. */
  showCurrentLink: boolean;
}

/**
  A rejected delivery, or one still being read. Either way there are no lines,
  and the plainest available sentence says so.
*/
export function RunWithoutLines({ run, showCurrentLink }: RunWithoutLinesProps) {
  const rejected = run.status === "rejected";
  const when = formatDateTime(rejected ? run.finalized_at : run.started_at);

  return (
    <div
      className={rejected ? `${styles.notice} ${styles.noticeRefused}` : styles.notice}
      data-print-block
    >
      <p className={styles.noticeHeading}>
        {rejected
          ? "This delivery was refused, so it has no lines."
          : "This run has not finished, so it has no lines yet."}
      </p>
      <p className={styles.noticeBody}>
        {rejected
          ? `Run #${run.id} was read${when ? ` at ${when}` : ""} and recorded as rejected. The sheet that was printed before it is unchanged.`
          : `Run #${run.id} started${when ? ` at ${when}` : ""} and has not been finalized, so it has no frozen counts.`}
      </p>
      {run.rejection_reason ? <p className={styles.reason}>{run.rejection_reason}</p> : null}
      {showCurrentLink ? (
        <p className={styles.noticeAction}>
          <Link href="/sheet">Go to the current sheet.</Link>
        </p>
      ) : null}
    </div>
  );
}

export interface ZeroMatchNoticeProps {
  header: SheetHeader;
}

/** Zero lines matched. The comparison ran; this page is the record that it ran. */
export function ZeroMatchNotice({ header }: ZeroMatchNoticeProps) {
  const against =
    header.corpora.length > 0
      ? header.corpora
          .map(
            (snapshot) =>
              `${formatCount(snapshot.record_count)} ${snapshot.source} records (${
                snapshot.provenance_label
              }) captured ${formatDate(snapshot.captured_at) ?? snapshot.captured_at}`,
          )
          .join(" and ")
      : (header.corpus_note ?? "the corpus named above");

  return (
    <div className={styles.notice} data-print-block>
      <p className={styles.noticeHeading}>{EMPTY_ZERO_MATCHES_HEADING}</p>
      <p className={styles.noticeBody}>
        Checked {formatCount(header.run.rows_read)} rows against {against}. A zero-line result is a
        result. This page is the record that the comparison ran.
      </p>
    </div>
  );
}
