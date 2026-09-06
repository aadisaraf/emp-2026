import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { IconRail } from "@/components/IconRail";
import { TopBar } from "@/components/TopBar";
import { StatusPoller } from "@/components";
import { getStatus } from "@/lib/api";
import { statusSignature } from "@/lib/status";
import styles from "./layout.module.css";

/* The shell, on every route: a top bar and an icon rail. */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "PullSheet",
  description: "Recall response for one food-service location.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const result = await getStatus();
  const status = result.ok ? result.data : null;

  return (
    <html lang="en">
      <body>
        <TopBar status={status} />
        <IconRail />
        <div className={styles.content} data-role="content">
          {status ? (
            <StatusPoller
              signature={statusSignature(status)}
              asOf={status.generated_at}
            />
          ) : null}
          <main className={styles.main}>{children}</main>
        </div>
      </body>
    </html>
  );
}
