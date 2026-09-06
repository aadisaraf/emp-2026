/* The typed client for the Sift JSON API. */

import type {
  CreditClaim,
  HoldRecordResponse,
  ImpactResponse,
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

export type Attempt<T> = { ok: true; data: T } | { ok: false; error: ApiFailure };

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

/** Every endpoint goes through here. Resolves to an error instead of throwing,
 *  so a page branches on `result.ok`. */
async function request<T>(path: string, init?: RequestInit): Promise<Attempt<T>> {
  const url = `${API_BASE}${path}`;
  let response: Response;

  try {
    response = await fetch(url, {
      cache: "no-store",
      ...init,
      headers: {
        Accept: "application/json",
        // FormData carries its own multipart boundary. Naming a content type
        // here would overwrite it and the file would arrive unreadable.
        ...(init?.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...init?.headers,
      },
    });
  } catch (thrown) {
    return {
      ok: false,
      error: {
        kind: "unreachable",
        status: null,
        code: null,
        message: `${url} did not answer. ${cause(thrown)}`,
        url,
      },
    };
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
    return {
      ok: false,
      error: {
        kind: "http",
        status: response.status,
        code,
        message,
        url,
      },
    };
  }

  try {
    return { ok: true, data: JSON.parse(text) as T };
  } catch (thrown) {
    return {
      ok: false,
      error: {
        kind: "malformed",
        status: response.status,
        code: null,
        message: `${url} answered ${response.status} with a body that is not JSON. ${cause(thrown)}`,
        url,
      },
    };
  }
}

/* ---------------------------------------------------------------------------
   GET
--------------------------------------------------------------------------- */

/** The polled endpoint. Answers 200 with state "never" when no run exists. */
export function getStatus(): Promise<Attempt<StatusResponse>> {
  return request<StatusResponse>("/api/v1/status");
}

/** Run history, newest first, rejections included. */
export function getRuns(limit?: number): Promise<Attempt<RunsResponse>> {
  return request<RunsResponse>(`/api/v1/runs${query({ limit })}`);
}

/** One run's facts. Deliberately carries no lines; use getSheetForRun. */
export function getRun(runId: number): Promise<Attempt<RunDetailResponse>> {
  return request<RunDetailResponse>(`/api/v1/runs/${runId}`);
}

/** The current pull sheet. PULL and HELD arrive interleaved in one order --
 *  render them as received; do not re-sort or split them. */
export function getSheet(): Promise<Attempt<SheetResponse>> {
  return request<SheetResponse>("/api/v1/sheet");
}

/** A past run's sheet, exactly as it was printed that morning. */
export function getSheetForRun(runId: number): Promise<Attempt<SheetResponse>> {
  return request<SheetResponse>(`/api/v1/sheet/${runId}`);
}

/** One match: both records verbatim, and every decision taken on this pair. */
export function getMatch(matchId: number): Promise<Attempt<MatchDetailResponse>> {
  return request<MatchDetailResponse>(`/api/v1/matches/${matchId}`);
}

/** Money always; the menu cascade only where the location runs a meal program. */
export function getImpact(): Promise<Attempt<ImpactResponse>> {
  return request<ImpactResponse>("/api/v1/impact");
}

/** The hold-and-destruction record. Signature fields render blank, always. */
export function getHoldRecord(runId?: number): Promise<Attempt<HoldRecordResponse>> {
  return request<HoldRecordResponse>(`/api/v1/artifacts/hold${query({ run: runId })}`);
}

/** Quantity times unit cost, summed. Nothing is estimated. */
export function getCreditClaim(runId?: number): Promise<Attempt<CreditClaim>> {
  return request<CreditClaim>(`/api/v1/artifacts/credit-claim${query({ run: runId })}`);
}

/** The child-nutrition report. 404 not_a_meal_program on a restaurant. */
export function getStateReport(runId?: number): Promise<Attempt<StateReportResponse>> {
  return request<StateReportResponse>(
    `/api/v1/artifacts/state-report${query({ run: runId })}`,
  );
}

/** Every channel and corpus with its provenance label. Works before any run. */
export function getSources(): Promise<Attempt<SourcesResponse>> {
  return request<SourcesResponse>("/api/v1/sources");
}

/* ---------------------------------------------------------------------------
   POST. Three mutations exist and these are all of them.
--------------------------------------------------------------------------- */

/** Mark a line cleared. Needs a named person, and writes one audit row: the
 *  matches row itself is never touched. */
export function clearMatch(
  matchId: number,
  body: { actor: string; note?: string | null },
): Promise<Attempt<MatchDetailResponse>> {
  return request<MatchDetailResponse>(`/api/v1/matches/${matchId}/clear`, {
    method: "POST",
    body: JSON.stringify({ actor: body.actor, note: body.note ?? null }),
  });
}

/** Record that a named person walked to the cooler. Writes only an audit row. */
export function confirmPulled(
  matchId: number,
  body: { actor: string },
): Promise<Attempt<MatchDetailResponse>> {
  return request<MatchDetailResponse>(`/api/v1/matches/${matchId}/confirm-pulled`, {
    method: "POST",
    body: JSON.stringify({ actor: body.actor }),
  });
}

/** Try the agency, fall back to the committed snapshot. Always answers 200. */
export function refreshRecalls(): Promise<Attempt<RefreshResponse>> {
  return request<RefreshResponse>("/api/v1/recalls/refresh", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

/* ---------------------------------------------------------------------------
   Inventory in, by hand. Three answers, and the caller must handle all three:
   the file was read, a heading needs one question answered, or the delivery
   was refused. A refusal is still a run; it is never silence.
--------------------------------------------------------------------------- */

export interface IngestOk {
  status: "ok";
  run_id: number;
  filename: string;
  matches?: number;
  [key: string]: unknown;
}

export interface IngestDuplicate {
  status: "duplicate";
  run_id: number;
  filename: string;
  reason: string;
}

export interface IngestRejected {
  status: "rejected";
  run_id: number;
  filename: string;
  reason: string;
}

export interface IngestAmbiguous {
  status: "ambiguous";
  filename: string;
  headers: string[];
  mapping: Record<string, string>;
  /** Heading -> the fields it could mean. Exactly one question per heading. */
  ambiguous: Record<string, string[]>;
  /** Every field a heading may be mapped to. */
  fields: string[];
}

export type IngestResult = IngestOk | IngestDuplicate | IngestRejected | IngestAmbiguous;

/** Send one export. The file is read once. */
export function uploadInventory(file: File): Promise<Attempt<IngestResult>> {
  const body = new FormData();
  body.append("file", file);
  return request<IngestResult>("/api/v1/ingest/upload", { method: "POST", body });
}

/** Answer the heading question, and read the file with the answer. */
export function answerMapping(
  filename: string,
  answers: Record<string, string>,
): Promise<Attempt<IngestResult>> {
  return request<IngestResult>("/api/v1/ingest/mapping", {
    method: "POST",
    body: JSON.stringify({ filename, answers }),
  });
}
