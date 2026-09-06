/*
  The strings this page authors, and only those.

  Everything with a home in @/lib/strings is imported from there instead: the
  tier explanations, the evidence-kind labels, the clear form, the confirm
  form, and the two confirmations. Everything the server owns is rendered
  verbatim from the payload: the provenance label, the recall's own text, the
  agency identifiers.

  What is left is the connective tissue of one screen, and it follows the same
  house rules: no em dash, no exclamation mark, no emoji, digits for numbers,
  present tense for state, past tense with a named actor for anything a person
  did, and one word per concept.
*/

/** The page exists to answer one question, so the title is that question answered. */
export const MATCH_TITLE = "Why this line is on the sheet";

/** "Match #559 on run #1. Freezer 3." Storage is dropped when the export left it blank. */
export function matchContext(
  matchId: number,
  runId: number,
  storageLocation: string | null,
): string {
  const where = storageLocation ? ` ${storageLocation}.` : "";
  return `Match #${matchId} on run #${runId}.${where}`;
}

/** Back to the sheet this line is on, or to the history when it is a past run. */
export function backToSheet(runId: number): string {
  return `Pull sheet, run #${runId}`;
}

export const BACK_TO_RUNS = "Run history";

export const BOTH_RECORDS_NOTE =
  "Both records below are the stored text. Neither side is rewritten, shortened, or re-cased.";

/* ---------------------------------------------------------------------------
   The two sides.
--------------------------------------------------------------------------- */

export const INVENTORY_HEADING = "Inventory, as your system wrote it";
export const RECALL_HEADING = "Recall, as the agency wrote it";

export const INVENTORY_VERBATIM_LABEL = "Description, as exported";
export const RECALL_VERBATIM_LABEL = "Product description, as published";

export const HIGHLIGHT_LEGEND =
  "The highlighted text on each side is the trigger stored on this match, found in place. It is the stored value, not a fresh comparison run in the browser.";

export const TRIGGER_LABEL = "Trigger stored on this match";

/** Said only when a part of the trigger is not in any field on that side. */
export function triggerMissing(parts: string[]): string {
  const list = parts.map((part) => `"${part}"`).join(", ");
  return parts.length === 1
    ? `${list} is not present verbatim in the fields above, so it is not highlighted.`
    : `${list} are not present verbatim in the fields above, so they are not highlighted.`;
}

export function unpopulatedFields(fields: string[]): string {
  return `Fields this export did not carry: ${fields.join(", ")}`;
}

export function mergedFrom(rows: number[]): string {
  return `Merged from ${rows.length} export rows: ${rows.join(", ")}.`;
}

export const RECEIVED_AT_HINT =
  "The 24 hour and 48 hour clocks are measured from this time.";

export const UNCLASSIFIED = "unclassified (treated as Class I)";

export const NO_CODE_INFO = "The notice carried no code information.";

/* ---------------------------------------------------------------------------
   Field labels. Micro, uppercase, and the operators' words.
--------------------------------------------------------------------------- */

export const INVENTORY_FIELDS = {
  storage: "Storage location",
  quantity: "Quantity",
  packSize: "Pack size",
  gtin: "Barcode",
  lot: "Lot",
  brand: "Brand",
  manufacturer: "Manufacturer",
  mfrItem: "Manufacturer item",
  vendor: "Vendor",
  vendorItem: "Vendor item",
  unitCost: "Unit cost",
} as const;

export const RECALL_FIELDS = {
  record: "Record",
  firm: "Recalling firm",
  classification: "Class",
  status: "Recall status",
  reported: "Reported",
  received: "Received here",
  reason: "Reason",
  codeInfo: "Code information",
} as const;

export const VENDOR_ITEM_HINT =
  "Never a matching key. It is what the distributor needs to process the credit.";

/* ---------------------------------------------------------------------------
   The decision log.
--------------------------------------------------------------------------- */

export const DECISIONS_HEADING = "What has been decided about this";

export const DECISIONS_SCOPE =
  "Decisions are recorded against this item and this recall, not against one run's line, so a judgement taken on an earlier run is still here after every run since.";

export const DECISIONS_NONE = "Nothing yet. This line is on the sheet.";

export const DECISIONS_KEPT =
  "The line stays on the pull sheet, marked. Nothing is deleted.";

export const DECISION_WORD = {
  clear_match: "Cleared",
  confirm_pulled: "Confirmed pulled",
} as const;

/** Said when the decision was written against another run's line for this pair. */
export function decisionOnAnotherLine(matchId: number): string {
  return `Recorded on line #${matchId}, another run's line for the same item and recall.`;
}

/* ---------------------------------------------------------------------------
   The two actions.
--------------------------------------------------------------------------- */

/** The confirm-pulled action changes nothing, and the screen has to say so. */
export function confirmChangesNothing(status: string): string {
  return `Nothing about the line changes. Its status stays ${status} and it keeps its place on the sheet.`;
}

export const CLEAR_IS_A_HUMAN_ACT =
  "This records a judgement a person made. The system reaches CONFIRMED, PROBABLE or POSSIBLE and stops there; it cannot decide that this is not the recalled product, and clearing does not ask it to.";

/* ---------------------------------------------------------------------------
   The match row and the agency payload, for the reader who wants the floor
   under the floor.
--------------------------------------------------------------------------- */

export const MATCH_ROW_HEADING = "The match row itself";

export const MATCH_ROW_FIELDS = {
  id: "Match id",
  run: "Run",
  created: "Written at",
  isNew: "New on this run",
  evidence: "Evidence kind, raw",
  inventoryId: "Inventory record",
  recallId: "Recall record",
  score: "Order tie-break",
} as const;

export const SCORE_HINT =
  "Breaks ties in the sheet order. It decides nothing, and it is not a confidence value.";

export const NO_SCORE = "none on this row";

export const IS_NEW_HINT =
  "Written once by the matcher, by diffing this pair against the previous run. On the first run at a location there is no previous run, so every line reads no.";

export const AGENCY_RECORD_HEADING = "The agency record as it arrived";

export const AGENCY_RECORD_NOTE =
  "The payload this recall record was built from, stored as it arrived. Keys vary by agency.";

/* ---------------------------------------------------------------------------
   When a match id does not exist.
--------------------------------------------------------------------------- */

export const NO_SUCH_MATCH = "There is no match with this id.";
