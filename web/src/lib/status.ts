import type { StatusResponse } from "./types";

/**
 * A signature of the state a page was rendered with: which run, how many runs
 * exist, and which of the six states is current.
 *
 * The poller compares this against a fresh /api/v1/status every two seconds and
 * refreshes when it differs. run_count is in it deliberately: a refused
 * delivery does not change the current run id, and a rejection that never
 * reached the screen is the failure the whole surface exists to prevent.
 *
 * This lives outside the poller because the shell computes it on the server.
 */
export function statusSignature(status: StatusResponse): string {
  return `${status.run?.id ?? 0}:${status.run_count}:${status.state}`;
}
