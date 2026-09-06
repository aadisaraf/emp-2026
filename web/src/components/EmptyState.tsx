import type { ReactNode } from "react";
import styles from "./EmptyState.module.css";

export interface EmptyStateProps {
  /** A declarative sentence, ending in a full stop. Not a rhetorical question. */
  heading: string;
  /** Why the page is empty, when a blank page would be read as reassurance. */
  body?: ReactNode;
  /** What to do next, when there is something to do. */
  action?: ReactNode;
}

/**
 * An empty region, stated. No illustration, no checkmark, no green.
 *
 * The lengths of these are deliberately uneven: "nothing has been ingested yet"
 * is three sentences because a short one would be read as "clear", and "this
 * deployment runs no meal program" is one because it is uninteresting.
 */
export function EmptyState({ heading, body, action }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <p className={styles.heading}>{heading}</p>
      {body ? <p className={styles.body}>{body}</p> : null}
      {action ? <p className={styles.action}>{action}</p> : null}
    </div>
  );
}
