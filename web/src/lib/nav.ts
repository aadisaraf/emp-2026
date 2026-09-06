/*
  The nav, as data. One flat list of the routes that exist, plus the three
  printable artifacts under an "Artifacts" label.
*/

export interface NavItem {
  href: string;
  label: string;
  /** The state report exists only where the location runs a meal program. */
  mealProgramOnly?: boolean;
}

export const PRIMARY_NAV: NavItem[] = [
  { href: "/", label: "Today" },
  { href: "/sheet", label: "Pull sheet" },
  { href: "/runs", label: "Run history" },
  { href: "/impact", label: "Impact" },
  { href: "/sources", label: "Sources" },
  { href: "/ingest", label: "Add inventory" },
];

export const ARTIFACTS_LABEL = "Artifacts";

export const ARTIFACT_NAV: NavItem[] = [
  { href: "/artifacts/hold", label: "Hold record" },
  { href: "/artifacts/credit-claim", label: "Credit claim" },
  { href: "/artifacts/state-report", label: "State report", mealProgramOnly: true },
];

/* What the print control is called on each route. */
export const PRINT_LABEL: Record<string, string> = {
  "/sheet": "Print pull sheet",
  "/impact": "Print impact",
  "/sources": "Print sources",
  "/match": "Print this match",
  "/artifacts/hold": "Print hold record",
  "/artifacts/credit-claim": "Print credit claim",
  "/artifacts/state-report": "Print state report",
};

/** Exact match for the dashboard, prefix match for everything below it. */
export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
