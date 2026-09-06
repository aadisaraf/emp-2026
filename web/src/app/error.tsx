"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components";

/** The last-resort boundary. The API client resolves rather than throws, so
 *  only a render fault gets here. */
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
