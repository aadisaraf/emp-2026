/* Formatting, in one place, so a value looks the same on every page. */

/** Matches pullsheet/location.py TIMEZONE_NAME. */
export const DEFAULT_TIME_ZONE =
  process.env.NEXT_PUBLIC_TIME_ZONE ?? "America/Los_Angeles";

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** "2026-09-05". A date-only string is returned untouched: shifting it into a
 *  timezone would move the day. */
export function formatDate(
  value: string | null | undefined,
  timeZone: string = DEFAULT_TIME_ZONE,
): string | null {
  return formatDateTime(value, timeZone)?.slice(0, 10) ?? null;
}

/** "2026-09-05 09:34", 24-hour, in the location's zone. */
export function formatDateTime(
  value: string | null | undefined,
  timeZone: string = DEFAULT_TIME_ZONE,
): string | null {
  if (!value) return null;
  if (DATE_ONLY.test(value)) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const p: Record<string, string> = {};
  for (const part of formatter.formatToParts(date)) p[part.type] = part.value;
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;
}

/** "09:34". Empty for a date-only value, which carries no time to show. */
export function formatTime(
  value: string | null | undefined,
  timeZone: string = DEFAULT_TIME_ZONE,
): string | null {
  return formatDateTime(value, timeZone)?.slice(11) || null;
}

/** "1,012". Counts are measures: right-align them. */
export function formatCount(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

/** "$8,862.50". The server already rounded; this only adds separators. */
export function formatMoney(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/** "240" or "240 CS". null is not zero -- it comes back null to render as
 *  "not recorded". */
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

/** "1 line", "2 lines". Written out, because "line(s)" is a form, not a
 *  sentence, and this copy is read aloud to an inspector. */
export function plural(count: number, one: string, many?: string): string {
  return `${count} ${count === 1 ? one : (many ?? `${one}s`)}`;
}

/** "not fetched" from "not_fetched". For a token with no authored label. */
export function unslug(token: string): string {
  return token.replace(/_/g, " ");
}

/** "#8b65fe2c" from "inventory_lincoln.csv#8b65fe2cf7301b6a", for a narrow cell. */
export function shortDeliveryRef(ref: string | null): string | null {
  if (!ref) return null;
  const hash = ref.indexOf("#");
  if (hash === -1) return ref;
  return `${ref.slice(0, hash)} #${ref.slice(hash + 1, hash + 9)}`;
}
