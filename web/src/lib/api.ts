/*
  The typed client for the PullSheet JSON API.

  One function per endpoint in brief/API.md, and every type from that document
  re-exported from here, so a page only ever imports "@/lib/api".

  Two rules this file exists to enforce:

  1. Server components fetch with { cache: "no-store" }. A cached status word is
     a lie: a file lands in data/watched/ and the sheet changes underneath you.
  2. A failure is a fact to render, never a crash and never a placeholder
     number. Every function throws ApiRequestError with a message that is safe
     to show; wrap the call in attempt() and hand the failure to <ErrorState />.

  The demo runs with the network physically off. This module contacts exactly
  one origin, the local FastAPI process, and nothing else.
*/

import type {
  CreditClaim,
  HoldRecordResponse,
  ImpactResponse,
  Location,
  MatchDetailResponse,
  RefreshResponse,
  RunDetailResponse,
  RunsResponse,
  SheetResponse,
  SourcesResponse,
  StateReportResponse,
  StatusResponse,
} from "./types";

export * from "./types";

/** Where the Python side is listening. Nothing else is ever contacted. */
export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

/** How often the shell asks /api/v1/status whether the run changed. */
export const POLL_INTERVAL_MS = 2000;

/** What went wrong, in a shape a component can render without interpreting it. */
export interface ApiFailure {
  /** unreachable: no answer at all. http: the API answered with a non-2xx.
   *  malformed: it answered, and the body was not the JSON we expect. */
  kind: "unreachable" | "http" | "malformed";
  /** HTTP status, or null when the request never completed. */
  status: number | null;
  /** The stable machine token from API.md section 2, when the API sent one. */
  code: string | null;
  /** A sentence that is safe to put on screen. */
  message: string;
  /** The URL that was asked. */
  url: string;
}

export class ApiRequestError extends Error {
  readonly failure: ApiFailure;

  constructor(failure: ApiFailure) {
    super(failure.message);
    this.name = "ApiRequestError";
    this.failure = failure;
  }
}

export type Attempt<T> = { ok: true; data: T } | { ok: false; error: ApiFailure };

/**
 * Run a request and return the failure instead of throwing it. This is the
 * shape every page uses:
 *
 *   const sheet = await attempt(getSheet());
 *   if (!sheet.ok) return <ErrorState failure={sheet.error} />;
 */
export async function attempt<T>(promise: Promise<T>): Promise<Attempt<T>> {
  try {
    return { ok: true, data: await promise };
  } catch (thrown) {
    return { ok: false, error: toFailure(thrown) };
  }
}

/** Turn anything thrown into an ApiFailure. Never throws itself. */
export function toFailure(thrown: unknown): ApiFailure {
  if (thrown instanceof ApiRequestError) return thrown.failure;
  const message = thrown instanceof Error ? thrown.message : String(thrown);
  return {
    kind: "unreachable",
    status: null,
    code: null,
    message,
    url: API_BASE,
  };
}

/** True when the API said this run, match or location has no record. */
export function isNotFound(failure: ApiFailure): boolean {
  return failure.status === 404;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

function cause(thrown: unknown): string {
  if (thrown instanceof Error) {
    const inner = (thrown as Error & { cause?: unknown }).cause;
    if (inner instanceof Error && inner.message) return inner.message;
    return thrown.message;
  }
  return String(thrown);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  let response: Response;

  try {
    response = await fetch(url, {
      cache: "no-store",
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (thrown) {
    throw new ApiRequestError({
      kind: "unreachable",
      status: null,
      code: null,
      message: `${url} did not answer. ${cause(thrown)}`,
      url,
    });
  }

  const text = await response.text();

  if (!response.ok) {
    let code: string | null = null;
    let message = `${url} answered ${response.status}.`;
    try {
      const body = JSON.parse(text) as { error?: { code?: string; message?: string } };
      if (body?.error?.code) code = body.error.code;
      if (body?.error?.message) message = body.error.message;
    } catch {
      // A non-JSON error body is itself the fact worth reporting.
    }
    throw new ApiRequestError({
      kind: "http",
      status: response.status,
      code,
      message,
      url,
    });
  }

  try {
    return JSON.parse(text) as T;
  } catch (thrown) {
    throw new ApiRequestError({
      kind: "malformed",
      status: response.status,
      code: null,
      message: `${url} answered ${response.status} with a body that is not JSON. ${cause(thrown)}`,
      url,
    });
  }
}

/* ---------------------------------------------------------------------------
   GET
--------------------------------------------------------------------------- */

/** The single location this deployment serves. There is no roster. */
export function getLocation(): Promise<Location> {
  return request<Location>("/api/v1/location");
}

/**
 * The status word, the counts, both clocks, corpus provenance and the refused
 * deliveries. This is the polled endpoint, and it never returns an error
 * status: "nothing has ever been ingested" is a 200 with never_received true.
 */
export function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/api/v1/status");
}

/** Run history, newest first, rejections included. */
export function getRuns(limit?: number): Promise<RunsResponse> {
  return request<RunsResponse>(`/api/v1/runs${query({ limit })}`);
}

/** One run's facts. Deliberately carries no lines; use getSheetForRun. */
export function getRun(runId: number): Promise<RunDetailResponse> {
  return request<RunDetailResponse>(`/api/v1/runs/${runId}`);
}

/**
 * The current pull sheet. PULL and HELD arrive interleaved in one order
 * (class rank, tier rank, score, id). Render them in the order received: do not
 * re-sort, do not group by status, do not filter cleared lines out.
 */
export function getSheet(): Promise<SheetResponse> {
  return request<SheetResponse>("/api/v1/sheet");
}

/** A past run's sheet, exactly as it was printed that morning. */
export function getSheetForRun(runId: number): Promise<SheetResponse> {
  return request<SheetResponse>(`/api/v1/sheet/${runId}`);
}

/** One match: both records verbatim, and every decision taken on this pair. */
export function getMatch(matchId: number): Promise<MatchDetailResponse> {
  return request<MatchDetailResponse>(`/api/v1/matches/${matchId}`);
}

/** Money always; the menu cascade only where the location runs a meal program. */
export function getImpact(): Promise<ImpactResponse> {
  return request<ImpactResponse>("/api/v1/impact");
}

/** The hold-and-destruction record. Signature fields render blank, always. */
export function getHoldRecord(runId?: number): Promise<HoldRecordResponse> {
  return request<HoldRecordResponse>(`/api/v1/artifacts/hold${query({ run: runId })}`);
}

/** Quantity times unit cost, summed. Nothing is estimated. */
export function getCreditClaim(runId?: number): Promise<CreditClaim> {
  return request<CreditClaim>(`/api/v1/artifacts/credit-claim${query({ run: runId })}`);
}

/** The child-nutrition report. 404 not_a_meal_program on a restaurant. */
export function getStateReport(runId?: number): Promise<StateReportResponse> {
  return request<StateReportResponse>(
    `/api/v1/artifacts/state-report${query({ run: runId })}`,
  );
}

/** Every channel and corpus with its provenance label. Works before any run. */
export function getSources(): Promise<SourcesResponse> {
  return request<SourcesResponse>("/api/v1/sources");
}

/* ---------------------------------------------------------------------------
   POST. Three mutations exist and these are all of them.
--------------------------------------------------------------------------- */

/**
 * Mark a line cleared. The only action in the system that can do that, and it
 * needs a named person. It writes one audit row: the match is not edited, the
 * line stays on every sheet, and its status stays PULL or HELD.
 */
export function clearMatch(
  matchId: number,
  body: { actor: string; note?: string | null },
): Promise<MatchDetailResponse> {
  return request<MatchDetailResponse>(`/api/v1/matches/${matchId}/clear`, {
    method: "POST",
    body: JSON.stringify({ actor: body.actor, note: body.note ?? null }),
  });
}

/**
 * Record that a named person walked to the cooler. Touches no match and no
 * inventory row, which is why it is safe as one click.
 */
export function confirmPulled(
  matchId: number,
  body: { actor: string },
): Promise<MatchDetailResponse> {
  return request<MatchDetailResponse>(`/api/v1/matches/${matchId}/confirm-pulled`, {
    method: "POST",
    body: JSON.stringify({ actor: body.actor }),
  });
}

/**
 * Try the agency, fall back to the committed snapshot. Always answers 200:
 * offline, the answer is cached_fallback with the reason attached.
 *
 * It does not re-match. Nothing on the pull sheet changes, and the UI must not
 * imply otherwise. Refetch the status after this call, not the sheet.
 */
export function refreshRecalls(): Promise<RefreshResponse> {
  return request<RefreshResponse>("/api/v1/recalls/refresh", {
    method: "POST",
    body: JSON.stringify({}),
  });
}
