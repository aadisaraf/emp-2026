import { attempt, getMatch } from "@/lib/api";
import type { SheetResponse } from "@/lib/api";

/*
  Who cleared a line, and when.

  A sheet line carries cleared_count and nothing else, because clearing is not
  a status: matches.status stays PULL or HELD and the row keeps its place in
  the single order. The name of the person and the time they did it live in the
  decisions table, which the match detail endpoint returns.

  So the page asks for the detail of the cleared lines only. That set is small
  by construction: every clearing costs a named human one deliberate action, and
  the fixture sheet has one across 856 lines. The cap below exists so that a
  pathological database cannot turn one page render into a thousand requests;
  a line past the cap still renders as cleared, without the name, and the
  ClearedMark component already says a person did it.
*/

export interface ClearedFact {
  actor: string | null;
  /** The decision's own timestamp, unformatted. */
  at: string | null;
  /** cleared_count from the sheet line, which may be more than one. */
  count: number;
}

export type ClearedFacts = Map<number, ClearedFact>;

const MAX_LOOKUPS = 60;

/**
 * Look up the clearing decisions behind every cleared line on this sheet.
 *
 * decided_before is honoured: on a past run the sheet shows clearings as they
 * stood the instant that sheet was replaced, so a decision taken afterwards is
 * counted by neither the server's cleared_count nor this name.
 */
export async function clearedFacts(sheet: SheetResponse): Promise<ClearedFacts> {
  const facts: ClearedFacts = new Map();

  const cleared = sheet.sections
    .flatMap((section) => section.lines)
    .filter((line) => line.cleared_count > 0);

  for (const line of cleared) {
    facts.set(line.id, { actor: null, at: null, count: line.cleared_count });
  }

  const bound = sheet.decided_before ? new Date(sheet.decided_before).getTime() : null;
  const wanted = cleared.slice(0, MAX_LOOKUPS);

  const details = await Promise.all(wanted.map((line) => attempt(getMatch(line.id))));

  details.forEach((result, index) => {
    if (!result.ok) return;
    const line = wanted[index];
    const clearings = result.data.decisions.filter((decision) => {
      if (decision.kind !== "clear_match") return false;
      if (bound === null) return true;
      const taken = new Date(decision.created_at).getTime();
      return Number.isNaN(taken) ? true : taken < bound;
    });
    const last = clearings[clearings.length - 1];
    if (!last) return;
    facts.set(line.id, { actor: last.actor, at: last.created_at, count: line.cleared_count });
  });

  return facts;
}
