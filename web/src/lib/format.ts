import { channelLabel } from "@/lib/strings";
/*
  Formatting, in one place, so a quantity looks the same on the sheet, in the
  claim and on the printed hold record.

  Three rules from the briefs are baked in here:

  - Timestamps arrive in two different shapes ("2026-09-06T03:34:14+00:00" from
    the run tables, "2026-09-05T09:12:00Z" from the committed snapshot files)
    and both can appear in one response. Everything goes through new Date();
    nothing is sliced at a fixed index or compared as a string.
  - Absolute first, always. ISO date, 24-hour clock. A relative age may follow
    an absolute value, never replace it.
  - An empty field is the word "not recorded", which is the caller's job: these
    functions return null for null so the caller renders <NotRecorded />
    instead of a blank cell that reads as zero.

  Times are rendered in the location's timezone, which is load-bearing: runs are
  grouped by business date and the boundary is a local-midnight question. The
  zone is fixed rather than read from the browser so the screen and the printout
  agree no matter who is looking.
*/

/** Matches pullsheet/location.py TIMEZONE_NAME. Override per call if needed. */
export const DEFAULT_TIME_ZONE =
  process.env.NEXT_PUBLIC_TIME_ZONE ?? "America/Los_Angeles";

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** Parse an API timestamp. Returns null for null, empty and unparseable input. */
export function parseTimestamp(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function parts(
  value: string,
  timeZone: string,
): Record<string, string> | null {
  const date = parseTimestamp(value);
  if (!date) return null;
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const out: Record<string, string> = {};
  for (const part of formatter.formatToParts(date)) out[part.type] = part.value;
  return out;
}

/**
 * "2026-09-05". A date-only string (business_date, service day, received_date)
 * is returned untouched: shifting it into a timezone would move the day.
 */
export function formatDate(
  value: string | null | undefined,
  timeZone: string = DEFAULT_TIME_ZONE,
): string | null {
  if (!value) return null;
  if (DATE_ONLY.test(value)) return value;
  const p = parts(value, timeZone);
  return p ? `${p.year}-${p.month}-${p.day}` : null;
}

/** "2026-09-05 09:34", 24-hour, in the location's zone. */
export function formatDateTime(
  value: string | null | undefined,
  timeZone: string = DEFAULT_TIME_ZONE,
): string | null {
  if (!value) return null;
  if (DATE_ONLY.test(value)) return value;
  const p = parts(value, timeZone);
  return p ? `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}` : null;
}

/** "09:34". For a second column where the date is already on the row. */
export function formatTime(
  value: string | null | undefined,
  timeZone: string = DEFAULT_TIME_ZONE,
): string | null {
  if (!value) return null;
  const p = parts(value, timeZone);
  return p ? `${p.hour}:${p.minute}` : null;
}

/** "1,012". Counts are measures: right-align them. */
export function formatCount(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

/**
 * "$8,862.50". The server has already rounded to 2 decimals; this only puts
 * the separators in. Never re-round, never estimate a missing cost.
 */
export function formatMoney(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * "240" or "240 CS". Quantity is a REAL and may be fractional; null is not
 * zero, so null comes back as null for the caller to render as not recorded.
 */
export function formatQuantity(
  value: number | null | undefined,
  unit?: string | null,
): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const amount = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
  }).format(value);
  return unit ? `${amount} ${unit}` : amount;
}

/** "61.7%". Parser coverage and nothing else. There is no match percentage. */
export function formatPercent(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value)}%`;
}

/** "8.4h". Corpus age and run age, one decimal, as the API reports them. */
export function formatHours(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value)}h`;
}

/** "31h". Whole hours, for an age that follows an absolute timestamp. */
export function formatWholeHours(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return `${Math.round(value)}h`;
}

/** "1 line", "2 lines". Written out, because "line(s)" is a form, not a
 *  sentence, and this copy is read aloud to an inspector. */
export function plural(count: number, one: string, many?: string): string {
  return `${count} ${count === 1 ? one : (many ?? `${one}s`)}`;
}

/** "not fetched" from "not_fetched". For a token with no authored label. */
export function unslug(token: string): string {
  return token.replace(/_/g, " ");
}

/** "run #1 · 2026-09-05 · sftp drop". Peer facts, middot, no em dash. */
export function formatRunStamp(run: {
  id: number;
  business_date: string;
  channel: string;
}): string {
  return `run #${run.id} · ${run.business_date} · ${channelLabel(run.channel)}`;
}

/** "#8b65fe2c" from "inventory_lincoln.csv#8b65fe2cf7301b6a", for a narrow cell. */
export function shortDeliveryRef(ref: string | null): string | null {
  if (!ref) return null;
  const hash = ref.indexOf("#");
  if (hash === -1) return ref;
  return `${ref.slice(0, hash)} #${ref.slice(hash + 1, hash + 9)}`;
}
