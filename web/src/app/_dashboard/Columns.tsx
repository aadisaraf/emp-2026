import Link from "next/link";
import type { ReactNode } from "react";
import type {
  CorpusSnapshot,
  Location,
  Run,
  SheetLine,
  SheetResponse,
} from "@/lib/types";
import { formatCount, formatDate, formatMoney, shortDeliveryRef } from "@/lib/format";
import { channelLabel } from "@/lib/strings";
import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import type { ArtifactFacts, Filters } from "./TodayBoard";
import styles from "./dashboard.module.css";

/* ------------------------------------------------------------------------ */
/* A card with a folder tab for a heading.                                   */

function TabCard({
  title,
  icon,
  tone = "plain",
  children,
}: {
  title: string;
  icon: string;
  tone?: "plain" | "accent";
  children: ReactNode;
}) {
  return (
    <section
      className={cx(styles.tabCard, tone === "accent" ? styles.toneAccent : styles.tonePlain)}
    >
      <div className={styles.tabHead}>
        <h2 className={styles.tab}>
          <Icon name={icon} size={16} />
          {title}
        </h2>
      </div>
      <div className={styles.tabBody}>{children}</div>
    </section>
  );
}

function Kv({ term, value }: { term: string; value: ReactNode }) {
  return (
    <div className={styles.kv}>
      <span className={styles.kvTerm}>{term}</span>
      <span className={styles.kvValue}>{value}</span>
    </div>
  );
}

export function LocationCard({ location }: { location: Location }) {
  return (
    <TabCard title="Location" icon="home" tone="accent">
      <Kv term="Name" value={location.name} />
      <Kv term="Operator" value={location.operator} />
      <Kv term="Address" value={location.address} />
      <Kv term="Contact" value={location.contact} />
    </TabCard>
  );
}

export function RunCard({ run, corpus }: { run: Run; corpus: CorpusSnapshot[] }) {
  const stale = corpus.some((c) => c.stale);
  const summary = corpus.map((c) => `${c.source} ${formatCount(c.record_count)}`).join(" · ");
  return (
    <TabCard title={`Run #${run.id}`} icon="history">
      <Kv term="Channel" value={channelLabel(run.channel)} />
      <Kv term="Delivery" value={shortDeliveryRef(run.delivery_ref) ?? "—"} />
      <Kv term="Rows read" value={formatCount(run.rows_read) ?? "0"} />
      <Kv term="Received" value={formatDate(run.business_date) ?? run.business_date} />
      <Kv
        term="Corpus"
        value={
          <span className={cx(stale && styles.staleText)}>
            {summary}
            {stale ? " · stale" : ""}
          </span>
        }
      />
    </TabCard>
  );
}

/* ------------------------------------------------------------------------ */
/* The lines, as a list of things to do.                                     */

const ROMAN: Record<SheetLine["class_rank"], string> = { 1: "I", 2: "II", 3: "III" };

const EVIDENCE: Record<string, string> = {
  gtin: "Barcode",
  upc: "Barcode",
  mfr_item: "Catalog no.",
  lot: "Lot code",
  secondary_code: "Code",
  firm_and_name: "Supplier and name",
  name: "Name",
};

function href(filters: Filters, patch: Partial<Filters>): string {
  const next = { ...filters, ...patch };
  const params = new URLSearchParams();
  if (next.q) params.set("q", next.q);
  if (next.loc) params.set("loc", next.loc);
  if (next.show) params.set("show", next.show);
  const qs = params.toString();
  return qs ? `/?${qs}` : "/";
}

function LineCard({ line, done }: { line: SheetLine; done: boolean }) {
  const qty =
    line.quantity !== null ? `${formatCount(line.quantity)} ${line.unit ?? ""}`.trim() : null;
  const meta = [qty, line.lot_code ? `lot ${line.lot_code}` : null, EVIDENCE[line.evidence_kind]]
    .filter(Boolean)
    .join(" · ");
  const open = `/match/${line.id}`;

  return (
    <li className={styles.lineRow}>
      <div className={styles.gutter} aria-hidden="true">
        <span className={styles.gutterDot} data-rank={line.class_rank}>
          {ROMAN[line.class_rank]}
        </span>
        <span className={styles.gutterLabel}>{line.storage_location ?? ""}</span>
      </div>
      <article className={styles.lineCard}>
        <Link
          href={open}
          className={cx(styles.checkbox, done && styles.checkboxDone)}
          aria-label={done ? "Recorded. Open this line" : "Open this line to record who pulled it"}
        >
          {done ? <Icon name="check" size={14} /> : null}
        </Link>
        <span className={styles.lineTitle}>{line.raw_description}</span>
        <span className={styles.lineChip} data-status={line.status}>
          {line.tier}
        </span>
        <Link href={open} className={styles.lineMore} aria-label="Open this line">
          <Icon name="more" size={16} />
        </Link>
        {meta ? <p className={styles.lineMeta}>{meta}</p> : null}
      </article>
    </li>
  );
}

const TODO_LIMIT = 6;
const DONE_LIMIT = 3;

export function LinesColumn({
  sheet,
  filters,
}: {
  sheet: SheetResponse | null;
  filters: Filters;
}) {
  if (!sheet) {
    return (
      <section className={styles.lines}>
        <p className={styles.empty}>The sheet could not be read.</p>
      </section>
    );
  }

  const held = filters.show === "held";
  const q = filters.q.trim().toLowerCase();
  const pool = sheet.sections
    .flatMap((s) => s.lines)
    .filter((l) => (held ? l.status === "HELD" : l.status === "PULL"))
    .filter((l) => !filters.loc || l.storage_location === filters.loc)
    .filter(
      (l) =>
        !q ||
        l.raw_description.toLowerCase().includes(q) ||
        l.product_description.toLowerCase().includes(q),
    );
  const todo = pool.filter((l) => !l.cleared);
  const done = pool.filter((l) => l.cleared);
  const heldCount = sheet.header.counts.held_count;
  const pullCount = sheet.header.counts.pull_count;

  return (
    <section className={styles.lines}>
      <div className={styles.tabs}>
        <span className={styles.tabsFolder}>
          <Icon name="sheet" size={16} />
          Lines
        </span>
        {sheet.sections.map((s) => {
          const active = filters.loc === s.storage_location;
          return (
            <Link
              key={s.storage_location}
              href={href(filters, { loc: active ? "" : s.storage_location })}
              className={cx(styles.tabsPill, active && styles.tabsPillActive)}
            >
              {s.storage_location}
            </Link>
          );
        })}
        <Link
          href={href(filters, { show: held ? "" : "held" })}
          className={cx(styles.tabsPill, held && styles.tabsPillActive)}
        >
          {held ? `To pull ${formatCount(pullCount)}` : `Held ${formatCount(heldCount)}`}
        </Link>
      </div>

      <div className={styles.group}>
        <h3 className={styles.groupTitle}>{held ? "Held" : "To pull"}</h3>
        {todo.length === 0 ? (
          <p className={styles.empty}>Nothing matches.</p>
        ) : (
          <ul className={styles.list}>
            {todo.slice(0, TODO_LIMIT).map((l) => (
              <LineCard key={l.id} line={l} done={false} />
            ))}
          </ul>
        )}
        {todo.length > TODO_LIMIT ? (
          <Link href="/sheet" className={styles.more}>
            {formatCount(todo.length - TODO_LIMIT)} more on the sheet
            <Icon name="open" size={14} />
          </Link>
        ) : null}
      </div>

      <div className={styles.group}>
        <h3 className={styles.groupTitle}>Recorded</h3>
        {done.length === 0 ? (
          <p className={styles.empty}>No one has recorded a pull yet.</p>
        ) : (
          <ul className={styles.list}>
            {done.slice(0, DONE_LIMIT).map((l) => (
              <LineCard key={l.id} line={l} done />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------------ */
/* The three printed documents, as files.                                    */

function DocCard({
  href: to,
  title,
  date,
  lines,
}: {
  href: string;
  title: string;
  date: string;
  lines: string[];
}) {
  return (
    <Link href={to} className={styles.docCard}>
      <div className={styles.docHead}>
        <span>
          <span className={styles.docDate}>{date}</span>
          <span className={styles.docName}>{title}</span>
        </span>
        <span className={styles.docOpen}>
          <Icon name="open" size={16} />
        </span>
      </div>
      <div className={styles.thumb} aria-hidden="true">
        <span className={styles.thumbBar}>{title}</span>
        {lines.map((l) => (
          <span key={l} className={styles.thumbLine}>
            {l}
          </span>
        ))}
      </div>
    </Link>
  );
}

export function DocumentsColumn({
  run,
  sheet,
  artifacts,
  servesMealProgram,
}: {
  run: Run;
  sheet: SheetResponse | null;
  artifacts: ArtifactFacts;
  servesMealProgram: boolean;
}) {
  const date = formatDate(run.business_date) ?? run.business_date;
  const holdLines = sheet
    ? [`${formatCount(sheet.line_count)} lines`, `${sheet.sections.length} storage locations`]
    : ["—"];
  const creditLines = artifacts.credit
    ? [formatMoney(artifacts.credit.total) ?? "—", `${artifacts.credit.counted} lines priced`]
    : ["—"];
  const reportLines = artifacts.report
    ? [`${artifacts.report.derived} fields derived`, `${artifacts.report.toEnter} to enter`]
    : ["—"];

  return (
    <section className={styles.docs}>
      <h3 className={styles.docTitle}>Documents</h3>
      <DocCard href="/artifacts/hold" title="Hold record" date={date} lines={holdLines} />
      <DocCard href="/artifacts/credit-claim" title="Credit claim" date={date} lines={creditLines} />
      {servesMealProgram ? (
        <DocCard href="/artifacts/state-report" title="State report" date={date} lines={reportLines} />
      ) : null}
    </section>
  );
}
