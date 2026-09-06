"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { POLL_INTERVAL_MS, getStatus, type StatusResponse } from "@/lib/api";
import { pollUnreachable } from "@/lib/strings";
import { formatDateTime } from "@/lib/format";
import styles from "./StatusPoller.module.css";

/** Which run, how many runs, and which state. The poller refreshes when this
 *  changes; nothing else on the page is compared. */
function signatureOf(status: StatusResponse): string {
  return `${status.run?.id ?? 0}:${status.run_count}:${status.state}`;
}

/**
  The only timer in the browser. A file lands in data/watched/, this notices the
  run changed, and the open tab becomes today's sheet. A failed poll says so and
  leaves the figures alone.
*/
export function StatusPoller({ status }: { status: StatusResponse }) {
  const signature = signatureOf(status);
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
        if (result.ok && signatureOf(result.data) !== signature) router.refresh();
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
      {pollUnreachable(formatDateTime(status.generated_at) ?? status.generated_at)}
    </p>
  );
}
