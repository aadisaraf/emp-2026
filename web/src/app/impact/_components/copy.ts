/*
  The strings this page owns, and only those.

  Everything the API authors is rendered verbatim and is deliberately absent
  from this file: claim.arithmetic, claim.exclusion_statement, menu.caveat,
  proposal.caveat, proposal.reason, and every provenance label. Those are
  covered by Python tests, and a front end that paraphrases them can drift into
  a claim the backend never made.

  House rules for anything added here: no em dash, no exclamation mark, digits
  for every number including under ten, present tense for state, past tense with
  a named actor for anything a person did, and one word per concept (run, pull
  sheet, PULL, HELD, tier, evidence kind, storage location, corpus, delivery,
  cleared, line, item).
*/

import { plural } from "@/lib/format";

/* ---------------------------------------------------------------------------
   Money. Applies to every deployment, school or restaurant.
--------------------------------------------------------------------------- */

export const MONEY = {
  title: "Money",
  linesTitle: "Every pulled line",
  vendorTitle: "By vendor",
  standing:
    "A line the export priced carries an extended value. A line the export did not price is shown with its quantity, is marked excluded, and is left out of the total. No price is filled in for it.",
  heldNotClaimed:
    "Held lines are not claimed. Held means a person has not decided yet, and a distributor cannot be billed for a case nobody has decided to remove.",
  linesCaption: "Every pulled line, in the order the claim produced it.",
  vendorCaption: "Vendor totals, largest first.",
  rail: {
    claimable: "Claimable",
    pulledLines: "Pulled lines",
    priced: "Priced",
    excluded: "Excluded from total",
    vendors: "Vendors",
  },
  columns: {
    item: "Item",
    storage: "Storage location",
    qty: "Qty",
    unitCost: "Unit cost",
    extended: "Extended",
    lot: "Lot",
    vendor: "Vendor",
    recall: "Recall",
    lines: "Lines",
    excludedShort: "Excluded",
    total: "Total",
  },
  excludedWord: "excluded",
  creditClaimLink: "Full credit claim",
  holdRecordLink: "Hold record",
} as const;

/* ---------------------------------------------------------------------------
   The menu cascade. Child nutrition only.
--------------------------------------------------------------------------- */

export const MENU = {
  title: "Menu cascade",
  brokenTitle: "Menu items that broke",
  itemsTitle: "The pulled items behind them",
  stateReportLink: "State report",
  plannedWord: "planned",
  notScheduled: "not on this week's menu",
  zeroCascade: "No pulled item appears in any planned recipe.",
  zeroCascadeBody:
    "The pull stands and the money above still applies. Nothing on the planned menu changes.",
  brokenCaption: "One row per menu item that broke, ordered by recipe id.",
  itemsCaption: "One row per pulled inventory line that reaches a recipe.",
  rail: {
    plannedMeals: "Planned meals",
    serviceDays: "Service days",
    itemsBroken: "Menu items broken",
    substituted: "Substitute found",
    noSubstitute: "No substitute",
  },
  columns: {
    meal: "Meal",
    dates: "Service dates",
    meals: "Meals (planned)",
    brokenBy: "Broken by",
    item: "Item",
    storage: "Storage location",
    qty: "Qty",
    lot: "Lot",
    appearsIn: "Appears in",
    recall: "Recall",
  },
} as const;

/**
 * The two counts this page has to keep apart. 13 pulled inventory lines are not
 * 13 broken meals, and a page that ran them together would be wrong in both
 * directions.
 */
export function cascadeCounts(input: {
  brokenLines: number;
  brokenMeals: number;
  scheduledMeals: number;
  serviceDays: number;
  plannedMeals: string;
}): string {
  return `${plural(input.brokenLines, "pulled inventory line")} break ${plural(
    input.brokenMeals,
    "menu item",
  )}. ${input.scheduledMeals} of those meals are scheduled this week, across ${plural(
    input.serviceDays,
    "service day",
  )}, ${input.plannedMeals} planned meals.`;
}

/** Held lines are left out of the cascade on purpose, and the number is stated. */
export function heldNotCascaded(count: number): string {
  return `${plural(count, "held line")} ${
    count === 1 ? "is" : "are"
  } not cascaded into the menu. Held means undecided, and every one of them is on the pull sheet.`;
}

/** Every meal count on this page carries the caveat the backend wrote. */
export function plannedTitle(caveat: string): string {
  return `Meal counts are ${caveat}. Each service day is counted once, however many pulled items land on it.`;
}

/* ---------------------------------------------------------------------------
   Substitution. A proof is not a failed search.
--------------------------------------------------------------------------- */

export const SUBSTITUTION = {
  title: "Substitution",
  caption: "One row per broken menu item, ordered by recipe id.",
  standing:
    "A substitute is named only where it covers every meal-pattern component the broken meal covered. There is no closest match and no partial cover in this system.",
  proofStanding:
    "A row that names no substitute is a proof. It names the meal-pattern component no clean recipe in this kitchen supplies, and how many candidate recipes were tested to establish that.",
  substituteWord: "substitute",
  noneWord: "no substitute",
  noneUnmetLabel: "unmet",
  coversLabel: "covers",
  extraLabel: "adds",
  alternativesLabel: "other covering recipes",
  heldIngredientsLabel: "held in this recipe",
  nothingUnmet: "nothing unmet",
  columns: {
    meal: "Meal",
    requires: "Requires",
    outcome: "Outcome",
    unmet: "Unmet",
    detail: "Detail",
    checked: "Recipes checked",
  },
} as const;

export function candidatesChecked(count: number): string {
  return `${plural(count, "candidate recipe")} tested`;
}

/* ---------------------------------------------------------------------------
   Where these numbers come from.
--------------------------------------------------------------------------- */

export const PROVENANCE_PANEL = {
  title: "Where these numbers come from",
  menuLead: "Menu data is",
  menuLine:
    "Recipes, meal-pattern components and planned counts were written by the build team, not imported from a nutrition system. The label stays on them wherever they are shown.",
  corpusLabel: "Recall corpus",
  columns: {
    source: "Source",
    provenance: "Provenance",
    path: "Path in the repository",
    description: "What it is",
  },
  caption: "Every source behind the money on this page.",
} as const;
