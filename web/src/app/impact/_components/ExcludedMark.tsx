import { cx } from "@/lib/cx";
import { MONEY } from "./copy";
import styles from "./impact.module.css";

export interface ExcludedMarkProps {
  /** claim.excluded_because, verbatim. One of two sentences the server writes. */
  reason: string | null;
}

/**
 * A pulled line that is not in the total.
 *
 * Two of the fixture lines carry no unit cost and one carries no quantity, so
 * there is no arithmetic to do on them. Nothing is estimated in their place:
 * the line keeps its quantity, the chip says it is out of the total, and the
 * reason the export gave is printed beside the item.
 *
 * Hollow, not filled. Nothing on this page is an alert, and the word inside the
 * chip is what survives a grayscale printout.
 */
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
