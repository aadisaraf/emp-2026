"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { POLL_INTERVAL_MS, getStatus } from "@/lib/api";
import { statusSignature } from "@/lib/status";

export interface StatusPollerProps {
  /**
   * A signature of the state this page was rendered with. null means the API
   * did not answer, in which case the first successful poll refreshes.
   */
  signature: string | null;
  intervalMs?: number;
}

/**
  The reload. A file lands in data/watched/, the poller notices that the run
  changed, and the open tab becomes today's sheet.
*/
export function StatusPoller({ signature, intervalMs = POLL_INTERVAL_MS }: StatusPollerProps) {
  const router = useRouter();
  const inFlight = useRef(false);

  useEffect(() => {
    let stopped = false;

    const tick = async () => {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const status = await getStatus();
        if (!stopped && statusSignature(status) !== signature) router.refresh();
      } catch {
        // No answer is already stated on screen. Keep asking.
      } finally {
        inFlight.current = false;
      }
    };

    const timer = setInterval(tick, intervalMs);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [signature, intervalMs, router]);

  return null;
}
