import type { Tier } from "@/lib/types";
import {
  NEW_LINE_BADGE,
  NEW_LINE_TITLE,
  NOT_RECORDED,
  TIER_EXPLANATION,
} from "@/lib/strings";
import { cx } from "@/lib/cx";
import styles from "./Marks.module.css";

/* The four inline marks a value can carry. */

/** What an empty field says. A blank cell would read as zero. */
export function NotRecorded({ word = NOT_RECORDED }: { word?: string }) {
  return <span className={styles.missing}>{word}</span>;
}

/** The tier word, uncoloured. */
export function TierBadge({ tier }: { tier: Tier }) {
  return (
    <span className={styles.tier} title={TIER_EXPLANATION[tier]}>
      {tier}
    </span>
  );
}

/** The word "new" after the status, for a line whose is_new column is 1. */
export function NewMark({ className }: { className?: string }) {
  return (
    <span className={cx(styles.new, className)} title={NEW_LINE_TITLE}>
      {NEW_LINE_BADGE}
    </span>
  );
}

export interface ClearedMarkProps {
  actor?: string | null;
  /** An absolute timestamp, already formatted. */
  when?: string | null;
  /** cleared_count, when more than one decision exists for this pair. */
  count?: number;
}

/** A cleared line, marked in place. */
export function ClearedMark({ actor, when, count }: ClearedMarkProps) {
  return (
    <span className={styles.cleared}>
      {actor ? `cleared by ${actor}` : "cleared by a named person"}
      {when ? ` ${when}` : ""}
      {count && count > 1 ? ` (${count} decisions)` : ""}
    </span>
  );
}
