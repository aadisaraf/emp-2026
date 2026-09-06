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
import { getStatus } from "@/lib/api";
import { statusSignature } from "@/lib/status";
import { formatCount } from "@/lib/format";
import { COUNT_LABELS, NEW_COUNT_TITLE } from "./_dashboard/strings";
import styles from "./layout.module.css";

/* The shell, on every route. */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "PullSheet",
  description: "Recall response for one food-service location.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const result = await getStatus();
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
    <html lang="en">
      <body>
        <Masthead status={status} />
        <SideNav servesMealProgram={status?.location.serves_meal_program ?? true} />
        <div className={styles.content} data-role="content">
          <StatusLine status={status} failure={failure} />
          {status ? (
            <StatusPoller
              signature={statusSignature(status)}
              asOf={status.generated_at}
            />
          ) : null}
          {status ? <StatRail items={items} deadlines={status.deadlines} /> : null}
          <main className={styles.main}>{children}</main>
        </div>
      </body>
    </html>
  );
}
