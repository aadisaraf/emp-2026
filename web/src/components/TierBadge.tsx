import type { Tier } from "@/lib/types";
import { TIER_EXPLANATION } from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./TierBadge.module.css";

export interface TierBadgeProps {
  tier: Tier;
  className?: string;
}

/**
 * The tier word, uncoloured.
 *
 * Tiering is an evidence ladder, not a severity scale and not a confidence
 * score: CONFIRMED and PROBABLE are PULL, POSSIBLE is HELD. There is no
 * threshold and no percentage anywhere in this system, so there is nothing
 * here to shade from green to red.
 */
export function TierBadge({ tier, className }: TierBadgeProps) {
  return (
    <span className={cx(styles.tier, className)} title={TIER_EXPLANATION[tier]}>
      {tier}
    </span>
  );
}
