import { attempt, getMatch } from "@/lib/api";
import type { SheetResponse } from "@/lib/api";

/* Who cleared a line, and when. */

export interface ClearedFact {
  actor: string | null;
  /** The decision's own timestamp, unformatted. */
  at: string | null;
  /** cleared_count from the sheet line, which may be more than one. */
  count: number;
}

export type ClearedFacts = Map<number, ClearedFact>;

const MAX_LOOKUPS = 60;

/** Look up the clearing decisions behind every cleared line on this sheet. */
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
