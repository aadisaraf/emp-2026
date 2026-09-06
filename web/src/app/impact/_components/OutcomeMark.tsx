import type { MenuProposal } from "@/lib/api";
import { cx } from "@/lib/cx";
import { SUBSTITUTION } from "./copy";
import styles from "./impact.module.css";

export interface OutcomeMarkProps {
  kind: MenuProposal["kind"];
}

/**
 * What the substitution search settled on: a named covering recipe, or a proof
 * that this kitchen has none.
 *
 * Both chips are hollow and both carry a word, because "no substitute" is a
 * finding and not an error. It is the result of testing every clean candidate
 * recipe against the meal-pattern components the broken meal covered, and it
 * names the component that went unmet. Rendering it as an alert, an empty
 * state, or a red row would misstate what happened.
 */
export function OutcomeMark({ kind }: OutcomeMarkProps) {
  const none = kind === "none";
  return (
    <span
      className={cx(styles.chip, none ? styles.chipAttend : styles.chipRecorded)}
      data-outcome={kind}
    >
      {none ? SUBSTITUTION.noneWord : SUBSTITUTION.substituteWord}
    </span>
  );
}
