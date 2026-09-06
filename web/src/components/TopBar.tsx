"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { StatusResponse } from "@/lib/types";
import { channelLabel } from "@/lib/strings";
import { Icon } from "./Icon";
import styles from "./TopBar.module.css";

export interface TopBarProps {
  status: StatusResponse | null;
  /** The current search, so the field keeps its text after a submit. */
  query?: string;
}

/* Who the operator is, from the contact line: "Nutrition Services, (555)" -> NS. */
function initials(contact: string): string {
  const name = contact.split(",")[0] ?? "";
  const letters = name.split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2);
  return letters.join("").toUpperCase() || "PS";
}

export function TopBar({ status, query = "" }: TopBarProps) {
  const router = useRouter();
  const run = status?.run ?? null;

  return (
    <header className={styles.bar} data-role="topbar">
      <Link href="/" className={styles.mark} aria-label="PullSheet, Today">
        P
      </Link>

      <button
        type="button"
        className={styles.ghost}
        aria-label="Back"
        onClick={() => router.back()}
      >
        <Icon name="back" />
      </button>

      <h1 className={styles.title}>{status?.location.name ?? "PullSheet"}</h1>
      {run ? (
        <span className={styles.chip}>
          run #{run.id} · {channelLabel(run.channel)}
        </span>
      ) : null}

      <form action="/" method="get" className={styles.search} role="search">
        <Icon name="search" size={16} />
        <input
          type="search"
          name="q"
          defaultValue={query}
          placeholder="Search lines"
          aria-label="Search lines on the pull sheet"
        />
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
