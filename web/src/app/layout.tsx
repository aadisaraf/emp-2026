import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { IconRail } from "@/components/IconRail";
import { TopBar } from "@/components/TopBar";
import { StatusPoller } from "@/components";
import { attempt, getStatus } from "@/lib/api";
import { statusSignature } from "@/lib/status";
import styles from "./layout.module.css";

/* The shell, on every route: a top bar and an icon rail. */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sift",
  description: "Recall response for one food-service location.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const result = await attempt(getStatus());
  const status = result.ok ? result.data : null;

  return (
    <html lang="en">
      <body>
        <TopBar status={status} />
        <IconRail />
        <div className={styles.content} data-role="content">
          <main className={styles.main}>{children}</main>
        </div>
        <StatusPoller signature={status ? statusSignature(status) : null} />
      </body>
    </html>
  );
}
