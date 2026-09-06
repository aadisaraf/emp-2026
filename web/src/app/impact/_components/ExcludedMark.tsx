import { cx } from "@/lib/cx";
import { MONEY } from "./copy";
import styles from "./impact.module.css";

export interface ExcludedMarkProps {
  /** claim.excluded_because, verbatim. One of two sentences the server writes. */
  reason: string | null;
}

/** A pulled line that is not in the total. */
export function ExcludedMark({ reason }: ExcludedMarkProps) {
  return (
    <span
      className={cx(styles.chip, styles.chipAttend)}
      title={reason ?? undefined}
      data-excluded=""
    >
      {MONEY.excludedWord}
    </span>
  );
}
