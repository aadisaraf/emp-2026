/*
  The impact page's own components. They live here rather than in the shared
  library because nothing else on the site renders a credit claim line, a
  cascade row or a substitution proof.
*/

export { ExcludedMark } from "./ExcludedMark";
export type { ExcludedMarkProps } from "./ExcludedMark";

export { MenuPanel } from "./MenuPanel";
export type { MenuPanelProps } from "./MenuPanel";

export { MoneyPanel } from "./MoneyPanel";
export type { MoneyPanelProps } from "./MoneyPanel";

export { OutcomeMark } from "./OutcomeMark";
export type { OutcomeMarkProps } from "./OutcomeMark";

export { PlannedMeals } from "./PlannedMeals";
export type { PlannedMealsProps } from "./PlannedMeals";

export { ProvenancePanel } from "./ProvenancePanel";
export type { ProvenancePanelProps } from "./ProvenancePanel";

export { SubstitutionPanel } from "./SubstitutionPanel";
export type { SubstitutionPanelProps } from "./SubstitutionPanel";

export { brokenMeals, proposalCounts, scheduledMealCount } from "./join";
export type { BrokenMeal } from "./join";
