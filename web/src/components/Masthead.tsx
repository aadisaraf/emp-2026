import type { StatusResponse } from "@/lib/types";
import { channelLabel } from "@/lib/strings";
import { PrintButton } from "./PrintButton";
import styles from "./Masthead.module.css";

export interface MastheadProps {
  /** null when the API did not answer. Nothing is invented in that case. */
  status: StatusResponse | null;
}

/** The fixed 48px bar: which location this is, which business date, which run. */
export function Masthead({ status }: MastheadProps) {
  const run = status?.run ?? null;
  return (
    <header className={styles.masthead} data-role="masthead">
      <span className={styles.brand}>PullSheet</span>
      {status ? (
        <>
          <span className={styles.rule} aria-hidden="true" />
          <span className={styles.where}>{status.location.name}</span>
          {run ? (
            <>
              <span className={styles.rule} aria-hidden="true" />
              <span className={styles.fact}>{run.business_date}</span>
              <span className={styles.rule} aria-hidden="true" />
              <span className={styles.fact}>
                run #{run.id} · {channelLabel(run.channel)}
              </span>
            </>
          ) : (
            <>
              <span className={styles.rule} aria-hidden="true" />
              <span className={styles.fact}>no run</span>
            </>
          )}
        </>
      ) : (
        <>
          <span className={styles.rule} aria-hidden="true" />
          <span className={styles.fact}>the API did not answer</span>
        </>
      )}
      <span className={styles.spacer} />
      <PrintButton />
    </header>
  );
}
