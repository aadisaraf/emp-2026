import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import "./globals.css";
import {
  Masthead,
  SideNav,
  StatRail,
  StatusLine,
  StatusPoller,
  type StatRailItem,
} from "@/components";
import { attempt, getStatus } from "@/lib/api";
import { statusSignature } from "@/lib/status";
import { formatCount } from "@/lib/format";
import { COUNT_LABELS, NEW_COUNT_TITLE } from "./_dashboard/strings";
import styles from "./layout.module.css";

/* Self-hosted so the demo keeps working with the cable out. The latin subsets
   only, 142KB for all five faces. Fira Sans is a humanist sans with actual
   character; Fira Code carries the lot codes and GTINs, which are code. */
const firaSans = localFont({
  src: [
    { path: "../fonts/FiraSans-400.woff2", weight: "400", style: "normal" },
    { path: "../fonts/FiraSans-500.woff2", weight: "500", style: "normal" },
    { path: "../fonts/FiraSans-600.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-fira-sans",
  display: "swap",
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
});

const firaCode = localFont({
  src: [
    { path: "../fonts/FiraCode-400.woff2", weight: "400", style: "normal" },
    { path: "../fonts/FiraCode-500.woff2", weight: "500", style: "normal" },
  ],
  variable: "--font-fira-code",
  display: "swap",
  fallback: ["ui-monospace", "SFMono-Regular", "monospace"],
});

/* The shell, on every route. */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "PullSheet",
  description: "Recall response for one food-service location.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const result = await attempt(getStatus());
  const status = result.ok ? result.data : null;
  const failure = result.ok ? null : result.error;

  /* The counts exist only when a run does. */
  const hasRun = status !== null && status.run !== null;
  const items: StatRailItem[] =
    status && hasRun
      ? [
          { label: COUNT_LABELS.pull, value: formatCount(status.counts.pull_count) },
          { label: COUNT_LABELS.held, value: formatCount(status.counts.held_count) },
          {
            label: COUNT_LABELS.fresh,
            value: formatCount(status.counts.new_count),
            title: NEW_COUNT_TITLE,
          },
          { label: COUNT_LABELS.total, value: formatCount(status.counts.total) },
          { label: "Runs", value: formatCount(status.run_count) },
        ]
      : [];

  return (
    <html lang="en" className={`${firaSans.variable} ${firaCode.variable}`}>
      <body>
        <Masthead status={status} />
        <SideNav servesMealProgram={status?.location.serves_meal_program ?? true} />
        <div className={styles.content} data-role="content">
          <StatusLine status={status} failure={failure} />
          {status ? <StatRail items={items} deadlines={status.deadlines} /> : null}
          <main className={styles.main}>{children}</main>
        </div>
        <StatusPoller signature={status ? statusSignature(status) : null} />
      </body>
    </html>
  );
}
