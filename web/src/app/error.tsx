"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components";

/**
  The boundary of last resort. A page that fetches through the API client never
  reaches here -- that client resolves to a failure rather than throwing -- so
  this catches a render fault, and it still refuses to invent a number.
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
        heading="This page did not render."
        detail={`${error.message}${error.digest ? ` Digest ${error.digest}.` : ""}`}
      />
      <p style={{ marginTop: "var(--space-3)" }}>
        <button type="button" onClick={() => retry()}>
          Load this page again
        </button>
      </p>
    </div>
  );
}
