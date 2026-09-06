"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { POLL_INTERVAL_MS, getStatus, type StatusResponse } from "@/lib/api";

/*
  The live half of the dashboard.

  Two jobs, and they are different jobs:

  1. Keep the numbers on this page current. Every two seconds the hook asks
     GET /api/v1/status and swaps the whole payload in, so the counts, both
     clocks, the new lines and the corpus ages update in place with no reload
     and no spinner. Nothing is ticked client side: the clocks are the API's own
     text, because a client-side tick is how an overrun gets quietly flipped
     back to "remaining" by a clock skew.

  2. Notice when the run itself changed and re-render the server route, which is
     what redraws the masthead, the shell's stat rail and the nav. A file lands
     in data/watched/, the poller sees a new run id, and the open tab becomes
     today's sheet with nobody touching it.

  run_count is compared as well as the run id, deliberately. A refused delivery
  does not change the current run id, and a rejection that never reached the
  screen is the failure this whole surface exists to prevent.

  The server's payload is used until the first poll answers and never copied
  into state, so there is no effect here that mirrors a prop and no render
  cascade behind it: a poll result is fresher than the render that preceded it,
  by construction.
*/

export interface StatusFeed {
  /** The freshest payload: the server's on first paint, the poller's after. */
  status: StatusResponse;
  /** false once a poll fails, true again on the next one that answers. */
  reachable: boolean;
}

export function useStatusFeed(
  initial: StatusResponse,
  intervalMs: number = POLL_INTERVAL_MS,
): StatusFeed {
  const router = useRouter();
  const [polled, setPolled] = useState<StatusResponse | null>(null);
  const [reachable, setReachable] = useState(true);

  const inFlight = useRef(false);
  const runId = useRef<number | null>(initial.run?.id ?? null);
  const runCount = useRef<number>(initial.run_count);

  useEffect(() => {
    let stopped = false;

    const tick = async () => {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const next = await getStatus();
        if (stopped) return;
        setPolled(next);
        setReachable(true);

        const id = next.run?.id ?? null;
        if (id !== runId.current || next.run_count !== runCount.current) {
          runId.current = id;
          runCount.current = next.run_count;
          router.refresh();
        }
      } catch {
        // No answer is a fact the page states in one muted line. It is not a
        // reason to blank the numbers, and it is not a reason to shout every
        // two seconds on a screen about contaminated food.
        if (!stopped) setReachable(false);
      } finally {
        inFlight.current = false;
      }
    };

    const timer = setInterval(tick, intervalMs);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [intervalMs, router]);

  return { status: polled ?? initial, reachable };
}
