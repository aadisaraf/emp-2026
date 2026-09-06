/* The joins this page needs, in one place and with no arithmetic of its own. */

import type { MenuEntry, MenuProposal, MenuSummary, Provenance } from "@/lib/api";

export interface BrokenMeal {
  /** The recipe id, e.g. "R01". An identifier, so it is set in mono. */
  recipeId: string;
  /** The recipe name from the proposal, which carries it on both arms. */
  name: string;
  /** hand-authored on every fixture recipe. Rendered, never styled down. */
  provenance: Provenance | null;
  /** The service dates this recipe is scheduled for. Empty is a real answer. */
  dates: string[];
  /** Planned meals for those dates. 0 when the recipe is not on this week's menu. */
  plannedMeals: number;
  /** The pulled inventory lines that broke it. */
  brokenBy: MenuEntry[];
  /** The substitute, or the proof that there is none. */
  proposal: MenuProposal;
}

/** One row per broken menu item, in the order the proposals arrived. */
export function brokenMeals(menu: MenuSummary, proposals: MenuProposal[]): BrokenMeal[] {
  const scheduled = new Map<string, { dates: string[]; planned: number }>();
  for (const [date, recipeId, planned] of menu.service_days) {
    const seen = scheduled.get(recipeId) ?? { dates: [], planned: 0 };
    seen.dates.push(date);
    seen.planned += planned;
    scheduled.set(recipeId, seen);
  }

  const provenanceOf = new Map<string, Provenance>();
  const brokenBy = new Map<string, MenuEntry[]>();
  for (const entry of menu.entries) {
    for (const recipe of entry.recipes) {
      provenanceOf.set(recipe.recipe_id, recipe.provenance);
      const lines = brokenBy.get(recipe.recipe_id) ?? [];
      lines.push(entry);
      brokenBy.set(recipe.recipe_id, lines);
    }
  }

  return proposals.map((proposal) => {
    const days = scheduled.get(proposal.broken_recipe_id);
    return {
      recipeId: proposal.broken_recipe_id,
      name: proposal.broken_recipe,
      provenance: provenanceOf.get(proposal.broken_recipe_id) ?? null,
      dates: days?.dates ?? [],
      plannedMeals: days?.planned ?? 0,
      brokenBy: brokenBy.get(proposal.broken_recipe_id) ?? [],
      proposal,
    };
  });
}
