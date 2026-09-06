import type { Tier } from "./types";

/*
  CONFIRMED, then PROBABLE, then POSSIBLE: the order a person works a list in,
  and the order the badge colours read in.
*/

export const TIER_RANK: Record<Tier, number> = {
  CONFIRMED: 0,
  PROBABLE: 1,
  POSSIBLE: 2,
};

/**
 * Sort by tier, keeping the API's own order inside each tier. Array sort is
 * stable, so class I still leads within a tier and nothing is re-ranked
 * beyond the one key the operator asked for.
 */
export function byTier<T extends { tier: Tier }>(lines: readonly T[]): T[] {
  return [...lines].sort((a, b) => TIER_RANK[a.tier] - TIER_RANK[b.tier]);
}
