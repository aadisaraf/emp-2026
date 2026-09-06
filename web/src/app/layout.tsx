import type { Metadata } from "next";
import type { ReactNode } from "react";
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

/*
  The shell, on every route.

  Masthead, nav, one status line, one stat rail, then the page. It is fixed so
  that an operator who opens any route knows within one glance which location
  this is, which run they are looking at, how many lines are marked PULL, and
  how much of the 24 and 48 hour windows is left.

  The shell fetches the status itself rather than making every page do it, and
  it renders with no backend running: a failure becomes a stated fact in the
  status line, never a crash and never a placeholder number.
*/

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "PullSheet",
  description: "Recall response for one food-service location.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const result = await attempt(getStatus());
  const status = result.ok ? result.data : null;
  const failure = result.ok ? null : result.error;

  /*
    The counts exist only when a run does.

    `/api/v1/status` returns zeroes for a location that has never received an
    export, and rendering them here would put "PULL 0 · HELD 0" in the persistent
    chrome directly above the sentence whose entire job is to refuse that
    reading. Zero-to-pull and nothing-was-ever-checked are different facts, and
    only one of them is reassuring. The clocks still show, because a deadline
    runs whether or not anyone has reported inventory against it.
  */
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
    <html lang="en">
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
