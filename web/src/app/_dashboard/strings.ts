/*
  The strings this page owns, in one file so a reviewer can grep them.

  Almost nothing is here on purpose. The six status words, their explanations,
  the deadline labels and phrases, the provenance labels and the six next
  actions are server-owned or already in @/lib/strings, and this page renders
  them verbatim. What is left is panel titles, column heads, and four sentences
  that state a fact the operator cannot derive from the numbers on screen.

  House rules that apply to every string below: no em dash, no exclamation
  mark, no emoji, digits for numbers including under ten, present tense for
  state, past tense with a named actor for anything a person did, and one word
  per concept (run, pull sheet, PULL, HELD, tier, evidence kind, storage
  location, corpus, delivery, cleared, line, item).
*/

/** Panel headings. "Deliveries that were refused" is spelled the way
 *  STATE_ACTIONS.rejected spells it, because that string tells the operator to
 *  go and read this section by name. */
export const PANEL = {
  corpus: "Recall corpus",
  refused: "Deliveries that were refused",
} as const;

/** "Run #1". The panel is about one run and names it, because a past run's
 *  page prints its own frozen counts and this one prints tonight's. */
export function runTitle(runId: number): string {
  return `Run #${runId}`;
}

/** The eyebrow above the status word. The machine token, next to the sentence,
 *  so the state is legible without reading colour. */
export const STATE_LABEL = "run state";

/** The label on the one string this page authors per state. */
export const NEXT_LABEL = "next";

/** The primary action, and the one that replaces it before any run exists. */
export const OPEN_SHEET = "Open the pull sheet";
export const ADD_INVENTORY = "Add inventory";

/** "as of 2026-09-06 04:16". Absolute first, always. */
export const AS_OF_LABEL = "as of";

/** Heading over the new lines. previous_run_id is the run they are measured
 *  against, so it is named rather than implied. */
export function newSinceTitle(previousRunId: number | null): string {
  return previousRunId === null ? "New on this run" : `New since run #${previousRunId}`;
}

/** The first run has no predecessor, so every is_new is 0. That is correct,
 *  and saying nothing here would let 0 read as "nothing changed". */
export const FIRST_RUN_NOTE =
  "This is the first run at this location. There is no previous run to compare against, so no line is marked new.";

/** 0 new against a real predecessor means something different, and also has to
 *  be said: the lines did not go away, they are just not new. */
export function nothingNewNote(previousRunId: number): string {
  return `No line on this run is new. Every line on the sheet was also on run #${previousRunId}, and none of them has gone away.`;
}

/** What the "never" state has instead of counts. run_count includes deliveries
 *  that were refused, so a location can have arrivals and still no run. */
export function deliveriesWithoutARun(count: number): string {
  return count === 1
    ? "1 delivery has arrived and it did not produce a run that could be read."
    : `${count} deliveries have arrived and none produced a run that could be read.`;
}

/** Why a refused delivery is on this page at all. */
export const REFUSED_NOTE =
  "A refused delivery is recorded here rather than swallowed. The run above is still what the sheet reflects: a bad export never overwrites a good one.";

/** The corpus table, when the corpus is empty. Not an error, a fact. */
export const NO_CORPUS = "No recall snapshot has been loaded.";

/** The word beside a snapshot older than its freshness window. Staleness gates
 *  the status word and nothing else; no line changes. */
export const STALE_WORD = "stale";
export const STALE_NOTE =
  "A snapshot older than 24 hours downgrades the status word above. Every line on the sheet is byte-identical either way.";

/** The poll stopped answering. State it, do not animate it, and do not replace
 *  a single figure with a placeholder. */
export function pollUnreachable(asOf: string): string {
  return `The API did not answer the last poll. Every figure on this page is from ${asOf}.`;
}

/** The footer. Both sentences are facts the operator cannot derive from the
 *  numbers above, which is the only reason a closing note is here. */
export const HOLD_POLICY =
  "Held lines are held. No automatic process in this system cleared a line, and none can: clearing is an action taken by a person who names themselves, and the line stays on the sheet afterwards.";

/* ---------------------------------------------------------------------------
   Column heads. Uppercase 11px is the operational register for a label, and
   these words match the pull sheet's own columns so the eye learns one
   horizontal position per field.
--------------------------------------------------------------------------- */

export const NEW_COLUMNS = {
  status: "Status",
  item: "Item",
  storage: "Storage location",
  lot: "Lot",
  klass: "Class",
  evidence: "Evidence",
  recall: "Recall",
  firm: "Recalling firm",
} as const;

export const CORPUS_COLUMNS = {
  source: "Source",
  provenance: "Provenance",
  captured: "Captured",
  records: "Records",
  age: "Age",
  fetch: "Fetch status",
} as const;

/** The run's own facts, as definition terms. */
export const RUN_TERMS = {
  status: "Run status",
  date: "Business date",
  channel: "Channel",
  delivery: "Delivery",
  rowsRead: "Rows read",
  rowsPartial: "Rows kept with an unreadable field",
  started: "Started",
  finalized: "Finalized",
} as const;

/** The four counts, in the stat-rail grammar. */
export const COUNT_LABELS = {
  pull: "PULL",
  held: "HELD",
  total: "Lines",
  fresh: "New",
} as const;

export const NEW_COUNT_TITLE = "Lines that were not on the previous run";

/* ---------------------------------------------------------------------------
   Tallies. Written out rather than templated with a bare "(s)", because a
   panel note is read at a glance and "1 sources" is the kind of small wrong
   thing that makes an operator distrust the large right things next to it.
--------------------------------------------------------------------------- */

export function corpusTally(records: string, sources: number): string {
  return sources === 1
    ? `${records} records from 1 source`
    : `${records} records across ${sources} sources`;
}

export function lineTally(lines: number): string {
  return lines === 1 ? "1 line" : `${lines} lines`;
}
