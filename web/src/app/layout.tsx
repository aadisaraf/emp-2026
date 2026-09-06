import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { IconRail, StatusPoller, TopBar } from "@/components";
import { getStatus } from "@/lib/api";
import styles from "./layout.module.css";

/* The shell, on every route: a top bar and an icon rail. */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sift",
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
          {status ? <StatusPoller status={status} /> : null}
          <main className={styles.main}>{children}</main>
        </div>
      </body>
    </html>
  );
}
