import type { Tier } from "@/lib/types";
import { TIER_EXPLANATION } from "@/lib/strings";
import styles from "./TierBadge.module.css";

export interface TierBadgeProps {
  tier: Tier;
}

/** The tier word, uncoloured. */
export function TierBadge({ tier }: TierBadgeProps) {
  return (
    <span className={styles.tier} title={TIER_EXPLANATION[tier]}>
      {tier}
    </span>
  );
}
