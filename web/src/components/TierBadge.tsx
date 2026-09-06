import type { Tier } from "@/lib/types";
import { TIER_EXPLANATION } from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./TierBadge.module.css";

export interface TierBadgeProps {
  tier: Tier;
  className?: string;
}

/** The tier word, coloured by tier: confirmed reads as act now. */
export function TierBadge({ tier, className }: TierBadgeProps) {
  return (
    <span
      className={cx(styles.tier, className)}
      data-tier={tier}
      title={TIER_EXPLANATION[tier]}
    >
      {tier}
    </span>
  );
}
