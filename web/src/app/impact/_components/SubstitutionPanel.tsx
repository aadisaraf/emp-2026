import type { MenuProposal } from "@/lib/api";
import { DataTable, NotRecorded, Panel, type Column } from "@/components";
import { formatCount } from "@/lib/format";
import { OutcomeMark } from "./OutcomeMark";
import { SUBSTITUTION, candidatesChecked } from "./copy";
import styles from "./impact.module.css";

export interface SubstitutionPanelProps {
  /** Both arms of the union, in the order the server sorted them. */
  proposals: MenuProposal[];
  /** substitute.COMPONENTS_CAVEAT, rendered verbatim. */
  caveat: string;
}

/**
 * What can replace a broken meal, and what provably cannot.
 *
 * Both outcomes sit in one table, interleaved in the order they arrived. A
 * proof is not a failed search and does not belong in a second section headed
 * like a list of errors: it is the result of testing every clean candidate
 * recipe in this kitchen against the meal-pattern components the broken meal
 * covered, and it names the component that went unmet. Five of the nine fixture
 * meals land there, and the unmet component is fruit every time.
 *
 * There is no closest match. A substitute is named only where it covers every
 * required component, so an approximate substitute has nowhere to appear.
 */
export function SubstitutionPanel({ proposals, caveat }: SubstitutionPanelProps) {
  return (
    <Panel id="substitution" title={SUBSTITUTION.title} note={caveat} printBlock>
      <p className={styles.note}>{SUBSTITUTION.standing}</p>
      <p className={styles.note}>{SUBSTITUTION.proofStanding}</p>

      <div className={styles.tableBlock}>
        <DataTable<MenuProposal>
          columns={COLUMNS}
          rows={proposals}
          rowKey={(proposal) => proposal.broken_recipe_id}
          caption={SUBSTITUTION.caption}
          className={styles.wideSubstitution}
          scroll
        />
      </div>
    </Panel>
  );
}

/*
  Unmet has its own column so that all five proofs stack in one vertical
  position and the reader sees at a glance that the same component is missing
  every time. On a substitute row the cell is not empty and not a dash: every
  required component is covered by definition, so it says so.
*/
const COLUMNS: Column<MenuProposal>[] = [
  {
    key: "meal",
    header: SUBSTITUTION.columns.meal,
    width: "220px",
    render: (proposal) => (
      <span className={styles.cellStack}>
        <span className={styles.strong}>{proposal.broken_recipe}</span>
        <span className={`${styles.support} ${styles.identifier}`}>
          {proposal.broken_recipe_id}
        </span>
      </span>
    ),
  },
  {
    key: "requires",
    header: SUBSTITUTION.columns.requires,
    width: "180px",
    render: (proposal) => (
      <span className={styles.tokens}>{proposal.required.join(", ")}</span>
    ),
  },
  {
    key: "outcome",
    header: SUBSTITUTION.columns.outcome,
    width: "124px",
    groupEdge: true,
    render: (proposal) => <OutcomeMark kind={proposal.kind} />,
  },
  {
    key: "unmet",
    header: SUBSTITUTION.columns.unmet,
    width: "110px",
    render: (proposal) =>
      proposal.kind === "none" ? (
        <span className={styles.unmet}>{proposal.unmet.join(", ")}</span>
      ) : (
        <span className={styles.nothingUnmet}>{SUBSTITUTION.nothingUnmet}</span>
      ),
  },
  {
    key: "detail",
    header: SUBSTITUTION.columns.detail,
    groupEdge: true,
    render: (proposal) =>
      proposal.kind === "substitute" ? (
        <span className={styles.cellStack}>
          <span className={styles.strong}>
            {proposal.name}{" "}
            <span className={styles.identifier}>{proposal.recipe_id}</span>
          </span>
          <span className={styles.support}>
            {SUBSTITUTION.coversLabel} {proposal.covers.join(", ")}
          </span>
          {proposal.extra.length > 0 ? (
            <span className={styles.support}>
              {SUBSTITUTION.extraLabel} {proposal.extra.join(", ")}
            </span>
          ) : null}
          {proposal.alternatives.length > 0 ? (
            <span className={styles.support}>
              {SUBSTITUTION.alternativesLabel}:{" "}
              {proposal.alternatives
                .map((other) => `${other.name} (${other.recipe_id})`)
                .join(", ")}
            </span>
          ) : null}
          {proposal.held_ingredients.length > 0 ? (
            <span className={styles.reason}>
              {SUBSTITUTION.heldIngredientsLabel}: {proposal.held_ingredients.join(", ")}
            </span>
          ) : null}
        </span>
      ) : (
        <span className={styles.cellStack}>
          <span className={styles.primary}>{proposal.reason}</span>
        </span>
      ),
  },
  {
    key: "checked",
    header: SUBSTITUTION.columns.checked,
    variant: "measure",
    width: "124px",
    render: (proposal) =>
      proposal.kind === "none" ? (
        <span title={candidatesChecked(proposal.candidates_checked)}>
          {formatCount(proposal.candidates_checked)}
        </span>
      ) : (
        <NotRecorded />
      ),
  },
];
