import type { ApiFailure } from "@/lib/api";
import type { StatusResponse } from "@/lib/types";
import { STATE_ACTIONS, overdueAction } from "@/lib/strings";
import { formatHours } from "@/lib/format";
import { cx } from "@/lib/cx";
import { ErrorState } from "./ErrorState";
import { ProvenanceLabel } from "./ProvenanceLabel";
import styles from "./StatusLine.module.css";

export interface StatusLineProps {
  status: StatusResponse | null;
  failure?: ApiFailure | null;
}

/** The state of the location, in one line, above everything else. */
export function StatusLine({ status, failure }: StatusLineProps) {
  if (!status) {
    return (
      <div className={styles.line} data-role="statusline">
        <ErrorState failure={failure} compact />
      </div>
    );
  }

  const action =
    status.state === "overdue" && status.run_age_hours !== null
      ? overdueAction(status.run_age_hours)
      : STATE_ACTIONS[status.state];

  return (
    <div className={styles.line} data-role="statusline">
      <p className={styles.sentence}>
        <strong
          className={cx(styles.word, status.stale_corpus && styles.stale)}
          data-state={status.state}
        >
          {status.word}
        </strong>{" "}
        <span className={styles.detail}>{status.detail}</span>{" "}
        <span className={styles.action}>{action}</span>
      </p>
      <p className={styles.corpus}>
        <span className={styles.corpusLabel}>corpus</span>{" "}
        {status.corpus.length === 0 ? (
          <span>no recall snapshot has been loaded</span>
        ) : (
          status.corpus.map((snapshot, index) => (
            <span key={snapshot.source}>
              {index > 0 ? <span aria-hidden="true"> · </span> : null}
              <span className={styles.source}>{snapshot.source}</span>{" "}
              <ProvenanceLabel
                provenance={snapshot.provenance}
                label={snapshot.provenance_label}
                capturedAt={snapshot.captured_at}
              />{" "}
              <span className={styles.age}>
                {snapshot.record_count} records, {formatHours(snapshot.age_hours)} old
              </span>
              {snapshot.stale ? <strong className={styles.staleWord}> (stale)</strong> : null}
            </span>
          ))
        )}
      </p>
    </div>
  );
}
