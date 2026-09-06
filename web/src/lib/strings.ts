/* Every user-facing string, so six pages cannot invent six synonyms. */

import type { EvidenceKind, Provenance, Tier } from "./types";

/** The empty-field word. Never "N/A", never a blank cell, which reads as zero. */
export const NOT_RECORDED = "not recorded";

/** Page titles, where a page needs one distinct from its nav label. */
export const PAGE_TITLES = {
  dashboard: "Today",
  pullSheet: "Pull sheet",
  runHistory: "Run history",
  impact: "What the pulls cost",
  sources: "Where every number comes from",
  holdRecord: "Hold record",
  creditClaim: "Credit claim",
  stateReport: "State report",
  addInventory: "Add inventory",
} as const;

/* ---------------------------------------------------------------------------
   Tier. Evidence, not severity, and never a percentage.
--------------------------------------------------------------------------- */

export const TIER_EXPLANATION: Record<Tier, string> = {
  CONFIRMED:
    "A barcode or the manufacturer's own item number matched. This is the same product the agency named.",
  PROBABLE:
    "The lot code matched, or the recalled firm made this item and both descriptions name the same product. Strong enough to pull.",
  POSSIBLE:
    "Only the product name lines up. Not enough to pull on, so it is held for a person to look at.",
};

export const TIER_LEGEND =
  "CONFIRMED and PROBABLE lines are PULL. POSSIBLE lines are HELD. There is no percentage and no threshold; the tier is the kind of evidence, nothing else.";

/* Evidence kind. Label all seven, or a raw key prints on a real line. */

export const EVIDENCE_LABEL: Record<EvidenceKind, string> = {
  gtin: "Barcode",
  upc: "Barcode (UPC)",
  lot: "Lot code",
  secondary_code: "Secondary code",
  firm_and_name: "Supplier and product name",
  mfr_item: "Manufacturer item number",
  name: "Product name",
};

export const EVIDENCE_EXPLANATION: Record<EvidenceKind, string> = {
  gtin: "The case barcode on your row is the barcode in the recall notice.",
  upc: "Same, on a 12-digit code.",
  lot: "Your lot code appears in the recall's code information.",
  secondary_code:
    "A pack date, best-by, or establishment number in the notice matched a code on your row.",
  firm_and_name:
    "The recalled firm made this item and both descriptions name the same product word.",
  mfr_item:
    "The manufacturer's own catalog number matched, and the manufacturer is the recalled firm.",
  name: "Only the wording of the product matched. Held, never pulled.",
};

export const EVIDENCE_UNKNOWN = "Unrecognised evidence kind. Treated as POSSIBLE and held.";

/* ---------------------------------------------------------------------------
   Provenance. Three labels and only three, always visible.
--------------------------------------------------------------------------- */

export const PROVENANCE_EXPLANATION: Record<Provenance, string> = {
  live: "Fetched from the agency while this run was happening.",
  "dated-snapshot":
    "Fetched once, committed to this build, and shown with the date it was captured.",
  "hand-authored": "Written by the build team. Not sourced from an agency.",
};

export const PROVENANCE_LEGEND =
  "Three labels and only three. Nothing in this application may present authored data as sourced data.";

export const FSIS_NOTE =
  "USDA FSIS records are hand-authored. FSIS returns HTTP 403 to programmatic requests, so these records could not be fetched or verified against published notices.";

/* ---------------------------------------------------------------------------
   The pull sheet table.
--------------------------------------------------------------------------- */

export const UNCLASSIFIED = "unclassified";

export const NEW_LINE_BADGE = "new";
export const NEW_LINE_TITLE = "not on the previous run";

/** "cleared by A. Reyes 2026-09-05 06:41". The line stays where it is. */
export function clearedBy(actor: string, whenText: string): string {
  return `cleared by ${actor} ${whenText}`;
}

/** A terminated or amended recall keeps its line. Clauses the agency did not
 *  state are left out, rather than printed empty. */
export function amendedRecallNote(
  status: string,
  prior?: string | null,
  date?: string | null,
): string {
  return `Recall ${status} by the agency${prior ? ` (was ${prior})` : ""}${
    date ? ` on ${date}` : ""
  }. This line stays on the sheet. Clearing it is a human action.`;
}

/* ---------------------------------------------------------------------------
   The two actions a person can take on a line.
--------------------------------------------------------------------------- */

export const CLEAR_FORM = {
  heading: "It is not this product",
  help: "Only a person can clear a line, and only under their own name. The clearing carries into every run after this one.",
  actorLabel: "Your name or initials",
  actorPlaceholder: "AS",
  noteLabel: "Why",
  notePlaceholder: "our lot is 4471, the recall is 4470",
  submit: "Clear this line",
  actorMissing: "Enter your name. A line cannot be cleared without one.",
} as const;

export function clearConfirmation(actor: string, timestamp: string): string {
  return `Cleared by ${actor} at ${timestamp}. The line stays on the sheet, marked cleared. Nothing was deleted.`;
}

export const CONFIRM_PULLED_FORM = {
  heading: "It has been pulled",
  help: "Records that somebody walked to the cooler. It does not remove the line from anything, which is why it is one click.",
  submit: "Confirm pulled",
  actorMissing: "Enter your name. Confirming a pull is recorded against it.",
} as const;

export function confirmPulledConfirmation(actor: string, timestamp: string): string {
  return `Confirmed pulled by ${actor} at ${timestamp}.`;
}

/* Empty states. None of them should read as reassurance. */

export const EMPTY_NO_RUNS = {
  heading: "Nothing has been ingested yet.",
  body: "This page is not blank by accident, and it does not say clear. No inventory has arrived, so there is nothing to compare against a recall, which is not the same as having compared and found nothing.",
  action: "Drop an export into data/watched/, or upload one.",
} as const;

export const EMPTY_ZERO_MATCHES_HEADING = "No inventory line matched a recall.";

export const EMPTY_NO_DELIVERIES = "No delivery has ever arrived at this location.";

/* The two clocks. OVERRUN, not "overdue" -- that word is a run state here. */

export const CLOCKS = {
  heading: "Reporting clocks",
  columns: ["Obligation", "Window", "Due", "Left"] as const,
  standingNote:
    "Counted from when each notice arrived here. A new inventory export tomorrow morning does not restart them.",
  overrunNote: "This deadline passed. The overrun is counted forward and does not reset.",
  none: "No notice has arrived, so no clock is running.",
} as const;

/** "Measured from 2026-09-05 09:34, the earliest of the 409 recall notices behind today's lines." */
export function clockProvenance(receivedAt: string, records: number): string {
  return `Measured from ${receivedAt}, the earliest of the ${records} recall notices behind today's lines.`;
}

/* ---------------------------------------------------------------------------
   When the API does not answer. Not cheerful, not apologetic, not reassuring.
--------------------------------------------------------------------------- */

export const API_UNREACHABLE_HEADING = "The API did not answer.";

export function apiUnreachableBody(detail: string): string {
  return `${detail ? `${detail} ` : ""}No inventory and no recall record was read, so nothing on this page describes what is in the building.`;
}

/** Said by the shell's poller, on any route, when the API goes quiet. */
export function pollUnreachable(asOf: string): string {
  return `The API did not answer the last poll. Every figure on this page is from ${asOf}.`;
}

export const API_UNREACHABLE_HINT =
  "The backend runs from the repository root: .venv/bin/python -m pullsheet.main --port 8000";

/* The four delivery channels. */

export const CHANNEL_LABEL: Record<string, string> = {
  sftp_drop: "SFTP drop",
  spreadsheet_upload: "Spreadsheet upload",
  email_drop: "Email drop",
  rematch: "Rematch",
};

export function channelLabel(channel: string): string {
  return CHANNEL_LABEL[channel] ?? channel.replace(/_/g, " ");
}

/** The print button's label, per route. */
export const PRINT_LABEL: Record<string, string> = {
  "/impact": "Print impact",
  "/sources": "Print sources",
  "/match": "Print this match",
  "/artifacts/hold": "Print hold record",
  "/artifacts/credit-claim": "Print credit claim",
  "/artifacts/state-report": "Print state report",
};
