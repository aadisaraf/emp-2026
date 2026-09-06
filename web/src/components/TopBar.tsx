"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { StatusResponse } from "@/lib/types";
import { channelLabel } from "@/lib/strings";
import { Icon } from "./Icon";
import styles from "./TopBar.module.css";

export interface TopBarProps {
  status: StatusResponse | null;
}

/* Who the operator is, from the contact line: "Nutrition Services, (555)" -> NS. */
function initials(contact: string): string {
  const name = contact.split(",")[0] ?? "";
  const letters = name.split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2);
  return letters.join("").toUpperCase() || "PS";
}

/** The two routes that can filter lines. Anywhere else, a search means Today. */
const SEARCHABLE = new Set(["/", "/sheet"]);

export function TopBar({ status }: TopBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const run = status?.run ?? null;

  // Search the page you are on when it can be searched, so the field never
  // moves you somewhere else without saying so.
  const target = SEARCHABLE.has(pathname) ? pathname : "/";
  const query = params.get("q") ?? "";

  return (
    <header className={styles.bar} data-role="topbar">
      <Link href="/" className={styles.mark} aria-label="Sift, Today">
        S
      </Link>

      <button
        type="button"
        className={styles.ghost}
        aria-label="Back"
        onClick={() => router.back()}
      >
        <Icon name="back" />
      </button>

      <h1 className={styles.title}>{status?.location.name ?? "Sift"}</h1>
      {run ? (
        <span className={styles.chip}>
          run #{run.id} · {channelLabel(run.channel)}
        </span>
      ) : null}

      <form action={target} method="get" className={styles.search} role="search">
        <Icon name="search" size={16} />
        <input
          // Remount when the query changes, so the field always shows what is
          // actually filtering the page rather than a stale keystroke.
          key={query}
          type="search"
          name="q"
          defaultValue={query}
          placeholder="Search lines"
          aria-label="Search lines on the pull sheet"
        />
        {query ? (
          <Link href={target} className={styles.clear} aria-label="Clear the search">
            <Icon name="close" size={14} />
          </Link>
        ) : null}
      </form>

      <Link href="/ingest" className={styles.round} aria-label="Add inventory" title="Add inventory">
        <Icon name="plus" />
      </Link>

      <span className={styles.spacer} />

      <button
        type="button"
        className={styles.ghost}
        aria-label="Print"
        title="Print"
        onClick={() => window.print()}
      >
        <Icon name="print" />
      </button>
      <Link href="/sources" className={styles.ghost} aria-label="Sources" title="Sources">
        <Icon name="refresh" />
      </Link>
      <span className={styles.avatar} title={status?.location.contact ?? ""}>
        {initials(status?.location.contact ?? "")}
      </span>
    </header>
  );
}
