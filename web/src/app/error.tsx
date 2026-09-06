"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components";
import { toFailure } from "@/lib/api";

/**
  The boundary of last resort. A page that fetches through attempt() never
  reaches here; this catches the rest, and it still refuses to invent a number
*/
export default function RouteError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div>
      <ErrorState
        failure={toFailure(error)}
        heading="This page did not render."
        detail={error.digest ? `Digest ${error.digest}.` : undefined}
      />
      <p style={{ marginTop: "var(--space-3)" }}>
        <button type="button" onClick={() => retry()}>
          Load this page again
        </button>
      </p>
    </div>
  );
}
