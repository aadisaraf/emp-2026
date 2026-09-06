"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { POLL_INTERVAL_MS, getStatus, type StatusResponse } from "@/lib/api";

/* The live half of the dashboard. */

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
