import type { Tier } from "@/lib/types";
import { TIER_EXPLANATION } from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./TierBadge.module.css";

export interface TierBadgeProps {
  tier: Tier;
  className?: string;
}

/** The tier word, uncoloured. */
export function TierBadge({ tier, className }: TierBadgeProps) {
  return (
    <span className={cx(styles.tier, className)} title={TIER_EXPLANATION[tier]}>
      {tier}
    </span>
  );
}
