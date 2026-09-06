import type { StatusResponse } from "./types";

/**
  A signature of the state a page was rendered with: which run, how many runs
  exist, and which of the six states is current.
*/
export function statusSignature(status: StatusResponse): string {
  return `${status.run?.id ?? 0}:${status.run_count}:${status.state}`;
}
