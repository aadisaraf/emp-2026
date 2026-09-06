import type { ReactNode } from "react";
import { DefinitionList, Panel, type DefinitionItem } from "@/components";
import { TRIGGER_LABEL, triggerMissing } from "./strings";
import { Highlighted } from "./highlight";
import styles from "./RecordSide.module.css";

export interface RecordSideProps {
  /** "Inventory, as your system wrote it" or "Recall, as the agency wrote it". */
  title: string;
  /** The provenance label on the recall side. Always visible, never a tooltip. */
  note?: ReactNode;
  /** What the long verbatim string is: a description, a product description. */
  verbatimLabel: string;
  verbatimText: string;
  /** The stored trigger, split into its verbatim parts. */
  parts: string[];
  items: DefinitionItem[];
  /** Row provenance the fields cannot carry: unpopulated columns, merged rows. */
  extras?: ReactNode;
  /** The stored trigger value, printed as stored. */
  trigger: string;
  /** Parts of the trigger that appear in no field on this side. */
  missing: string[];
}

/** One of the two source records, in full. */
export function RecordSide({
  title,
  note,
  verbatimLabel,
  verbatimText,
  parts,
  items,
  extras,
  trigger,
  missing,
}: RecordSideProps) {
  return (
    <Panel title={title} note={note} printBlock className={styles.side}>
      <p className={styles.verbatimLabel}>{verbatimLabel}</p>
      <p className={styles.verbatim}>
        <Highlighted text={verbatimText} parts={parts} />
      </p>

      <DefinitionList items={items} className={styles.fields} />

      {extras ? <div className={styles.extras}>{extras}</div> : null}

      <div className={styles.trigger}>
        <span className={styles.triggerLabel}>{TRIGGER_LABEL}</span>
        <code className={styles.triggerValue}>{trigger}</code>
        {missing.length > 0 ? (
          <span className={styles.triggerMissing}>{triggerMissing(missing)}</span>
        ) : null}
      </div>
    </Panel>
  );
}
