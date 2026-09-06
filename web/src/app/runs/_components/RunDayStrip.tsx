import type { RunHistoryEntry } from "@/lib/api";
import { Note, TabCard } from "@/components";
import { formatDate } from "@/lib/format";
import { cx } from "@/lib/cx";
import { STRIP_TITLE, channelLabel, countWord } from "./runsMeta";
import styles from "./RunDayStrip.module.css";

/* The shape of the operation, one cell per calendar day. */

const DAY_MS = 86_400_000;

/** Past this, the strip stops being readable and the table is the record. */
const MAX_DAYS = 45;

export interface RunDayStripProps {
  /** Newest first, as the API returns them. */
  runs: readonly RunHistoryEntry[];
  /** The API's generated_at. "Today" comes from the server, never the browser. */
  generatedAt: string;
}

type DayKind = "ok" | "rejected" | "running" | "gap";

interface Day {
  date: string;
  kind: DayKind;
  /** The day's PULL count, from its most recent accepted run. */
  pull: number | null;
  runs: RunHistoryEntry[];
}

function dayIndex(value: string | null | undefined): number | null {
  if (!value) return null;
  const parts = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!parts) return null;
  const stamp = Date.UTC(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]));
  return Number.isNaN(stamp) ? null : Math.round(stamp / DAY_MS);
}

function isoDate(index: number): string {
  return new Date(index * DAY_MS).toISOString().slice(0, 10);
}

function kindOf(runs: RunHistoryEntry[]): DayKind {
  if (runs.length === 0) return "gap";
  if (runs.some((run) => run.status === "rejected")) return "rejected";
  if (runs.some((run) => run.status === "ok")) return "ok";
  return "running";
}

/** Build one entry per calendar day between the first run and today. */
export function buildDays(
  runs: readonly RunHistoryEntry[],
  today: string | null,
): { days: Day[]; truncated: boolean } {
  const byDate = new Map<string, RunHistoryEntry[]>();
  let first: number | null = null;
  let last: number | null = null;

  for (const run of runs) {
    const index = dayIndex(run.business_date);
    if (index === null) continue;
    const key = isoDate(index);
    const bucket = byDate.get(key);
    if (bucket) bucket.push(run);
    else byDate.set(key, [run]);
    if (first === null || index < first) first = index;
    if (last === null || index > last) last = index;
  }

  if (first === null || last === null) return { days: [], truncated: false };

  // A gap at the right-hand end is the most important gap on the strip: it is
  // the morning the export did not arrive. So the span runs to today, not to
  const todayIndex = dayIndex(today);
  const end = todayIndex !== null && todayIndex > last ? todayIndex : last;

  const full = end - first + 1;
  const truncated = full > MAX_DAYS;
  const start = truncated ? end - MAX_DAYS + 1 : first;

  const days: Day[] = [];
  for (let index = start; index <= end; index += 1) {
    const date = isoDate(index);
    const onThisDay = byDate.get(date) ?? [];
    const accepted = onThisDay.filter((run) => run.status === "ok");
    days.push({
      date,
      kind: kindOf(onThisDay),
      pull: accepted.length > 0 ? accepted[0].pull_count : null,
      runs: onThisDay,
    });
  }

  return { days, truncated };
}

function mark(day: Day): string {
  if (day.kind === "rejected") return "REJ";
  if (day.kind === "ok" && day.pull !== null) return String(day.pull);
  return "";
}

function describe(day: Day): string {
  if (day.kind === "gap") return `${day.date}: no run.`;
  const listed = day.runs
    .map((run) => {
      const channel = channelLabel(run.channel);
      if (run.status === "rejected") {
        return `run #${run.id}, ${channel}, refused. ${run.rejection_reason ?? ""}`.trim();
      }
      if (run.status === "running") return `run #${run.id}, ${channel}, still running.`;
      return `run #${run.id}, ${channel}, ${run.pull_count} PULL and ${run.held_count} HELD.`;
    })
    .join(" ");
  return `${day.date}: ${listed}`;
}

function summarise(days: Day[], truncated: boolean): string {
  const span = days.length;
  const gaps = days.filter((day) => day.kind === "gap").length;
  const refused = days.filter((day) => day.kind === "rejected").length;

  const head = truncated
    ? `The last ${span} days, ${days[0].date} to ${days[span - 1].date}.`
    : `${countWord(span, "day", "days")}, ${days[0].date} to ${days[span - 1].date}.`;

  const middle =
    gaps === 0
      ? " A run finished on every one."
      : ` ${gaps === 1 ? "1 of them has" : `${gaps} of them have`} no run.`;

  const tail =
    refused === 0
      ? ""
      : ` A delivery was refused on ${countWord(refused, "day", "days")}.`;

  return `${head}${middle}${tail}`;
}

export function RunDayStrip({ runs, generatedAt }: RunDayStripProps) {
  const { days, truncated } = buildDays(runs, formatDate(generatedAt));

  // One cell is not a strip. The table below is already the record for that.
  if (days.length < 2) return null;

  return (
    <TabCard title={STRIP_TITLE}>
      <div className={styles.strip}>
        <div className={styles.scroll}>
          <ol className={styles.days}>
            {days.map((day) => (
              <li
                key={day.date}
                className={cx(styles.day, styles[day.kind])}
                title={describe(day)}
              >
                <span className={styles.mark} aria-hidden="true">
                  {mark(day)}
                </span>
                <span className={styles.dayNumber} aria-hidden="true">
                  {day.date.slice(8)}
                </span>
                <span className="sr-only">{describe(day)}</span>
              </li>
            ))}
          </ol>
        </div>
        <Note>{summarise(days, truncated)}</Note>
      </div>
    </TabCard>
  );
}
