"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { POLL_INTERVAL_MS, getStatus } from "@/lib/api";
import { statusSignature } from "@/lib/status";
import { pollUnreachable } from "@/lib/strings";
import { formatDateTime } from "@/lib/format";
import styles from "./StatusPoller.module.css";

export interface StatusPollerProps {
  /**
   * A signature of the state this page was rendered with. null means the API
   * did not answer, in which case the first successful poll refreshes.
   */
  signature: string | null;
  /** When the figures on screen were generated, quoted if the API goes quiet. */
  asOf: string;
}

/**
  The only thing in the browser that asks the API on a timer. A file lands in
  data/watched/, this notices that the run changed, and the open tab becomes
  today's sheet. When a poll stops answering it says so and leaves every figure
  where it is: a number that is merely old is still a number that was true.
*/
export function StatusPoller({ signature, asOf }: StatusPollerProps) {
  const router = useRouter();
  const inFlight = useRef(false);
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    let stopped = false;

    const tick = async () => {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const result = await getStatus();
        if (stopped) return;
        setReachable(result.ok);
        if (result.ok && statusSignature(result.data) !== signature) router.refresh();
      } finally {
        inFlight.current = false;
      }
    };

    const timer = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [signature, router]);

  if (reachable) return null;
  return (
    <p className={styles.unreachable}>
      {pollUnreachable(formatDateTime(asOf) ?? asOf)}
    </p>
  );
}
