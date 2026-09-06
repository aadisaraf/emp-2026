import Link from "next/link";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./ui.module.css";

/*
  The shared page vocabulary: one figure, a row of facts, folder-tab cards and
  the quiet table. Today speaks this; so do the sheet, run history and impact.
*/

export type Tone = "plain" | "accent" | "sunken";

const TONE: Record<Tone, string> = {
  plain: styles.tonePlain,
  accent: styles.toneAccent,
  sunken: styles.toneSunken,
};

/* ---- the one figure ------------------------------------------------------ */

export function PageHero({
  figure,
  word,
  money = false,
  alert = false,
  actions,
}: {
  figure: string;
  word: string;
  money?: boolean;
  alert?: boolean;
  actions?: ReactNode;
}) {
  return (
    <section className={styles.hero}>
      <div className={styles.figureBlock}>
        <span
          className={cx(styles.figure, money && styles.figureMoney, alert && styles.figureAlert)}
        >
          {figure}
        </span>
        <span className={styles.word}>{word}</span>
      </div>
      {actions ? <div className={cx(styles.actions, "no-print")}>{actions}</div> : null}
    </section>
  );
}

export interface Fact {
  label: string;
  value: string;
  tone?: "plain" | "alert" | "attend";
}

/** The facts that qualify the figure, on one line, no boxes. */
export function Facts({ items }: { items: Fact[] }) {
  return (
    <div className={styles.facts}>
      {items.map((f) => (
        <span
          key={f.label}
          className={cx(
            styles.fact,
            f.tone === "alert" && styles.factAlert,
            f.tone === "attend" && styles.factAttend,
          )}
        >
          <span className={styles.factValue}>{f.value}</span>
          <span className={styles.factLabel}>{f.label}</span>
        </span>
      ))}
    </div>
  );
}

/* ---- pills --------------------------------------------------------------- */

export function Pill({
  href,
  children,
  tone = "plain",
}: {
  href: string;
  children: ReactNode;
  tone?: "plain" | "primary" | "alert" | "attend";
}) {
  const className = cx(
    styles.pill,
    tone === "primary" && styles.pillPrimary,
    tone === "alert" && styles.pillAlert,
    tone === "attend" && styles.pillAttend,
  );
  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

/** A pill that states a fact and goes nowhere. */
export function Tag({
  children,
  tone = "plain",
}: {
  children: ReactNode;
  tone?: "plain" | "alert" | "attend";
}) {
  return (
    <span
      className={cx(
        styles.pill,
        tone === "alert" && styles.pillAlert,
        tone === "attend" && styles.pillAttend,
      )}
    >
      {children}
    </span>
  );
}

/* ---- layout -------------------------------------------------------------- */

export function Body({ children }: { children: ReactNode }) {
  return <div className={styles.body}>{children}</div>;
}

export function Main({ children }: { children: ReactNode }) {
  return <div className={styles.main}>{children}</div>;
}

export function Rail({ children }: { children: ReactNode }) {
  return <div className={styles.rail}>{children}</div>;
}

/* ---- folder-tab card ----------------------------------------------------- */

export function TabCard({
  title,
  count,
  tone = "plain",
  flush = false,
  id,
  children,
}: {
  title: string;
  count?: string | null;
  tone?: Tone;
  /** The body holds a table, which draws its own padding. */
  flush?: boolean;
  id?: string;
  children: ReactNode;
}) {
  return (
    <section className={cx(styles.tabCard, TONE[tone])} id={id}>
      <div className={styles.tabHead}>
        <h2 className={styles.tab}>
          {title}
          {count ? <span className={styles.tabCount}>{count}</span> : null}
        </h2>
      </div>
      <div className={cx(styles.tabBody, flush && styles.tabBodyFlush)}>{children}</div>
    </section>
  );
}

export function Kv({ term, value }: { term: string; value: ReactNode }) {
  return (
    <div className={styles.kv}>
      <span className={styles.kvTerm}>{term}</span>
      <span className={styles.kvValue}>{value}</span>
    </div>
  );
}

/** A name on the left, a figure hard right. */
export function KvSplit({ term, value }: { term: string; value: ReactNode }) {
  return (
    <div className={cx(styles.kv, styles.kvSplit)}>
      <span className={styles.kvTerm}>{term}</span>
      <span className={styles.kvValue}>{value}</span>
    </div>
  );
}

/* ---- jump pills ---------------------------------------------------------- */

export interface Jump {
  href: string;
  label: string;
  count?: string | null;
  active?: boolean;
}

export function Jumps({ items }: { items: Jump[] }) {
  if (items.length === 0) return null;
  return (
    <nav className={cx(styles.tabs, "no-print")}>
      {items.map((j) => (
        <Link
          key={j.href}
          href={j.href}
          className={cx(styles.tabsPill, j.active && styles.tabsPillActive)}
        >
          {j.label}
          {j.count ? <span className={styles.tabsCount}>{j.count}</span> : null}
        </Link>
      ))}
    </nav>
  );
}

/* ---- chips --------------------------------------------------------------- */

export function Chip({
  children,
  tone = "plain",
}: {
  children: ReactNode;
  tone?: "plain" | "pull" | "held" | "done" | "quiet";
}) {
  return (
    <span
      className={cx(
        styles.chip,
        tone === "pull" && styles.chipPull,
        tone === "held" && styles.chipHeld,
        tone === "done" && styles.chipDone,
        tone === "quiet" && styles.chipQuiet,
      )}
    >
      {children}
    </span>
  );
}

export function ChipRow({ children }: { children: ReactNode }) {
  return <span className={styles.chipRow}>{children}</span>;
}

/* ---- odds and ends ------------------------------------------------------- */

export function Note({ children }: { children: ReactNode }) {
  return <p className={styles.note}>{children}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className={styles.empty}>{children}</p>;
}

export { styles as ui };
