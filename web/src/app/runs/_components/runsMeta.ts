/* The words the two runs routes share. */

import type { RunChannel, RunStatus } from "@/lib/api";
/* Re-exported so the runs routes keep importing their vocabulary from one
   place, while the label itself has a single definition in lib/strings. */
export { channelLabel } from "@/lib/strings";

/* What each channel means, in a sentence. */

export const CHANNEL_EXPLANATION: Record<RunChannel, string> = {
  sftp_drop:
    "The inventory system wrote a scheduled export into data/watched/ and the poller read it. This is the ordinary morning.",
  spreadsheet_upload:
    "A person put the export in through the browser, for the morning the scheduled drop does not arrive.",
  email_drop:
    "Read from the committed fixture mailbox. Those records are hand-authored.",
  rematch:
    "The corpus changed and the inventory did not, so no file arrived that morning. This run matched the inventory already on hand against the recall records as they then stood.",
};

/** What the delivery cell says on a rematch run. Not "not recorded": nothing
 *  was missing from a file, because there was no file. */
export const NO_FILE_ARRIVED = "no file arrived";

/** The rows cell on the same run. 0 there would read as a file with no rows. */
export const NO_FILE_READ = "no file";

export const REMATCH_ROWS_TITLE =
  "A rematch run reads no file. The corpus changed and the inventory did not.";

/** A rematch run has no delivery behind it, whatever delivery_ref holds. */
export function hasDelivery(run: { channel: RunChannel }): boolean {
  return run.channel !== "rematch";
}

/* The corpus note, frozen at finalize. Where there is none, why there is
   none is itself the fact. */

export const CORPUS_NOT_FROZEN: Record<RunStatus, string> = {
  ok: "Not frozen.",
  rejected: "Not frozen. The delivery was refused before any matching ran.",
  running: "Not frozen. This run has not finalized.",
};

export function corpusNoteFor(run: { corpus_note: string | null; status: RunStatus }): {
  text: string;
  frozen: boolean;
} {
  if (run.corpus_note) return { text: run.corpus_note, frozen: true };
  return { text: CORPUS_NOT_FROZEN[run.status] ?? CORPUS_NOT_FROZEN.ok, frozen: false };
}

/* ---------------------------------------------------------------------------
   Page copy.
--------------------------------------------------------------------------- */

export const STRIP_TITLE = "Runs by day";

export const CURRENT_RUN_TAG_TITLE =
  "The most recent accepted run. Its sheet is the one /sheet shows.";

export const RUN_NOT_FOUND_HEADING = "That run is not in the run log.";

export const RUN_NOT_FOUND_DETAIL =
  "A run id is assigned when a delivery is processed. Every run this location has, refused ones included, is listed under Run history.";

export const REJECTED_HEADING = "This delivery was refused, so it has no lines.";

export const REJECTED_BODY =
  "It is listed here rather than discarded. The last accepted run before it stayed in force. A bad export never overwrites a good one.";

export const PRODUCED_NOTE =
  "Counts frozen when this run finalized. A past run prints its own numbers, not tonight's.";

export const CORPUS_PANEL_NOTE_PAST =
  "This is not the current run, so tonight's snapshot dates are not printed against its lines. The sentence below is the corpus note frozen when the run finalized.";

export const CORPUS_PANEL_NOTE_CURRENT =
  "The snapshots in force right now, which are the ones this run matched against.";

export const COVERAGE_NOTE =
  "Corpus-wide as it stands now, not frozen with this run.";

export const RUN_FOOTER =
  "A run is written once and never edited. The counts on this page are the ones this run froze when it finalized, not tonight's.";

export const CLOCKS_PANEL_NOTE =
  "This run's clocks, measured from the earliest recall notice behind its lines. They are not today's.";

export const NEW_PANEL_NOTE =
  "Written by the matcher when the line was created, by comparing this run against the one before it. It is not recomputed here.";

export const SHEET_LINK = "Pull sheet for this run";

export const BACK_LINK = "Run history";

/** "12 lines were not on run #11." / the first-run case, which is not a gap. */
export function newAgainst(newCount: number, previousRunId: number | null): string {
  if (previousRunId === null) {
    return "This is the first accepted run at this location, so no line could be new against a previous one. That is why the count is 0.";
  }
  return `${newCount} ${newCount === 1 ? "line was" : "lines were"} not on run #${previousRunId}.`;
}

/** Clearings on a past run are shown as they stood when it was replaced. */
export function decidedBeforeNote(whenText: string): string {
  return `Clearings on this run's sheet are shown as they stood at ${whenText}, the instant the next run replaced it. A line cleared after that is not back-dated onto it.`;
}

export function showingNote(shown: number, total: number): string {
  return `Showing the ${shown} most recent of ${total} runs.`;
}

/** "1 day" / "12 days". Digits always, including under ten. */
export function countWord(n: number, singular: string, plural: string): string {
  return `${n} ${n === 1 ? singular : plural}`;
}
