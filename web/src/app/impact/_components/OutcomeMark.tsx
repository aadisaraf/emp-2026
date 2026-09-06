import type { MenuProposal } from "@/lib/api";
import { cx } from "@/lib/cx";
import { SUBSTITUTION } from "./copy";
import styles from "./impact.module.css";

export interface OutcomeMarkProps {
  kind: MenuProposal["kind"];
}

/**
  What the substitution search settled on: a named covering recipe, or a proof
  that this kitchen has none.
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
