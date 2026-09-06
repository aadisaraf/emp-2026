import { formatCount } from "@/lib/format";
import { MENU, plannedTitle } from "./copy";
import styles from "./impact.module.css";

interface PlannedMealsProps {
  /** The count from the payload. Never a served figure. */
  count: number;
  /** menu.caveat, rendered as the title verbatim: "planned, not served". */
  caveat: string;
  /** Drop the word when the column header already carries it. */
  tag?: boolean;
}

/** A meal count, with the word "planned" attached to it. */
export function PlannedMeals({ count, caveat, tag = true }: PlannedMealsProps) {
  return (
    <span className={styles.planned} title={plannedTitle(caveat)}>
      {formatCount(count)}
      {tag ? (
        <>
          {" "}
          <span className={styles.plannedTag}>{MENU.plannedWord}</span>
        </>
      ) : null}
    </span>
  );
}
