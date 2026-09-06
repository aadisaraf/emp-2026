import {
  EvidenceKind,
  NewMark,
  NotRecorded,
  StatusBadge,
  TierBadge,
  type Column,
} from "@/components";
import type { SheetLine } from "@/lib/api";
import { UNCLASSIFIED } from "@/lib/strings";
import { formatDate, formatDateTime, formatQuantity } from "@/lib/format";
import type { ClearedFacts } from "./clearedFacts";
import styles from "./sheet.module.css";

/*
  The nine columns of the pull sheet, in the order the Jinja macro uses, so
  that the screen and the printout are the same document and an operator's eye
  learns one horizontal position per field:
*/

/** A recall the agency has since terminated or amended keeps its line. */
function amendedNote(line: SheetLine): string {
  const prior = line.recall_prior_status ? ` (was ${line.recall_prior_status})` : "";
  const changed = formatDate(line.status_changed_at) ?? line.status_changed_at;
  const on = changed ? ` on ${changed}` : "";
  return `Recall ${line.recall_status} by the agency${prior}${on}. This line stays on the sheet. Clearing it is a human action.`;
}

export function sheetColumns(cleared: ClearedFacts): Column<SheetLine>[] {
  return [
    {
      key: "status",
      header: "Status",
      headerTitle:
        "PULL and HELD are interleaved in one order: class rank, then tier rank, then score, then id.",
      render: (line) => (
        <span className={styles.status}>
          <TierBadge tier={line.tier} />
          <span className={styles.statusRow}>
            <StatusBadge value={line.status} />
            {line.is_new ? <NewMark /> : null}
          </span>
        </span>
      ),
    },
    {
      key: "item",
      header: "Item",
      headerTitle: "The product as the inventory export wrote it.",
      render: (line) => {
        const supplier = line.brand ?? line.manufacturer;
        /*
          The description ellipsizes; the amendment flag never does. A recall
          the agency has since terminated keeps its line, and the word saying
          so is the reason the line looks unexplained without it.
        */
        return (
          <span className={styles.item}>
            <button
              type="button"
              className={styles.itemButton}
              data-match-id={line.id}
              title={[
                supplier,
                line.manufacturer_item_code ? `item ${line.manufacturer_item_code}` : null,
                line.vendor_name,
                line.pack_size,
                line.lot_note,
              ]
                .filter(Boolean)
                .join(" · ")}
            >
              {line.raw_description}
            </button>
            {line.recall_status !== "active" ? (
              <abbr className={styles.amendedFlag} title={amendedNote(line)}>
                amended
              </abbr>
            ) : null}
          </span>
        );
      },
    },
    {
      key: "where",
      header: "Where",
      headerTitle: "The walking order through the kitchen, as the export wrote it.",
      render: (line) =>
        line.storage_location ?? (
          <span className={styles.plain}>
            <NotRecorded />
          </span>
        ),
    },
    {
      key: "quantity",
      header: "Qty",
      variant: "measure",
      groupEdge: true,
      headerTitle: "An empty quantity is not zero. It is a field the export did not carry.",
      render: (line) =>
        formatQuantity(line.quantity, line.unit) ?? (
          <span className={styles.plain}>
            <NotRecorded />
          </span>
        ),
    },
    {
      key: "lot",
      header: "Lot",
      variant: "identifier",
      headerTitle: "The lot code as the export wrote it, never normalized.",
      render: (line) =>
        line.lot_code ?? (
          <span className={styles.plain}>
            <NotRecorded />
          </span>
        ),
    },
    {
      key: "class",
      header: "Class",
      groupEdge: true,
      headerTitle: "The agency's recall class. An unclassified record ranks with Class I.",
      render: (line) => (
        <span
          className={styles.classCell}
          title={
            line.classification
              ? undefined
              : "The agency published no classification. It is ranked with Class I."
          }
        >
          {line.classification ?? UNCLASSIFIED}
        </span>
      ),
    },
    {
      key: "evidence",
      header: "Evidence",
      headerTitle: "What agreed. Not a match type, and not a quality rating.",
      render: (line) => (
        <span className={styles.evidence}>
          <EvidenceKind kind={line.evidence_kind} />
        </span>
      ),
    },
    {
      key: "trigger",
      header: "Triggered by",
      headerTitle: "The two pieces of text that agreed, both verbatim.",
      render: (line) => (
        <span
          className={styles.triggerPair}
          title={`${line.recalling_firm ?? "firm not recorded"} · ${line.source} ${
            line.source_record_id
          } · ${line.source_provenance_label}`}
        >
          <code className={styles.code}>{line.trigger_inventory_text}</code>
          <span className={styles.arrow} aria-hidden="true">
            ↔
          </span>
          <code className={styles.code}>{line.trigger_recall_text}</code>
        </span>
      ),
    },
    {
      key: "pulled",
      header: "Pulled",
      groupEdge: true,
      headerTitle: "A box to tick in the cooler. A cleared line says so instead.",
      render: (line) => {
        const fact = cleared.get(line.id);
        if (line.cleared_count > 0) {
          return (
            <span
              className={styles.pulledCleared}
              title={
                fact
                  ? `Cleared by ${fact.actor}${
                      fact.at ? ` on ${formatDateTime(fact.at)}` : ""
                    }. The line stays on the sheet.`
                  : "Cleared by a person. The line stays on the sheet."
              }
            >
              cleared
            </span>
          );
        }
        return (
          <span className={styles.pulledBox} aria-hidden="true">
            ☐
          </span>
        );
      },
    },
  ];
}
