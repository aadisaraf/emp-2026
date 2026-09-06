import type { ReactNode } from "react";
import type { ApiFailure } from "@/lib/api";
import {
  API_UNREACHABLE_HEADING,
  API_UNREACHABLE_HINT,
  apiUnreachableBody,
} from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./ErrorState.module.css";

export interface ErrorStateProps {
  /** The failure from attempt(). Its message is safe to display verbatim. */
  failure?: ApiFailure | null;
  /** Override the heading when the page knows something more specific. */
  heading?: string;
  /** Extra sentence under the API's own message. */
  detail?: ReactNode;
  /** Compact form for the status strip, where a panel would push data down. */
  compact?: boolean;
}

/**
 * What a screen says when the backend did not answer.
 *
 * It states the fact and nothing else: no apology, no "something went wrong",
 * no retry animation, and above all no placeholder numbers. A fabricated count
 * on a recall screen is worse than an empty one.
 */
export function ErrorState({ failure, heading, detail, compact }: ErrorStateProps) {
  const message = failure?.message ?? "";
  return (
    <div className={cx(styles.error, compact && styles.compact)} role="status">
      <p className={styles.heading}>{heading ?? API_UNREACHABLE_HEADING}</p>
      <p className={styles.body}>{apiUnreachableBody(message)}</p>
      {detail ? <p className={styles.body}>{detail}</p> : null}
      {failure?.code ? (
        <p className={styles.meta}>
          <span className={styles.metaLabel}>code</span>{" "}
          <code className={styles.code}>{failure.code}</code>
          {failure.status !== null ? (
            <>
              {" "}
              <span className={styles.metaLabel}>status</span>{" "}
              <code className={styles.code}>{failure.status}</code>
            </>
          ) : null}
        </p>
      ) : null}
      <p className={styles.hint}>{API_UNREACHABLE_HINT}</p>
    </div>
  );
}
