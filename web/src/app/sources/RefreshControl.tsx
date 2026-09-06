"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { refreshRecalls, toFailure, type RefreshResponse } from "@/lib/api";
import { ProvenanceLabel } from "@/components";
import { formatDateTime } from "@/lib/format";
import styles from "./sources.module.css";

/**
 * Ask the agency for a fresh corpus, and say what actually happened.
 *
 * Three things this control refuses to do.
 *
 * It does not claim the sheet changed, because it did not. A refresh writes a
 * dated snapshot and stops. Re-matching is a separate deliberate act that makes
 * a new run, and re-deciding lines underneath somebody who is holding a printout
 * is exactly the surprise this system exists to avoid.
 *
 * It does not treat an unreachable agency as an error. The demo runs with the
 * network off and the honest answer is the cached snapshot plus the reason the
 * fetch failed, printed in full rather than swallowed.
 *
 * It does not celebrate. The message comes from the server and is rendered
 * word for word.
 */
export function RefreshControl() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState<RefreshResponse | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  async function ask() {
    setAsking(true);
    setFailed(null);
    try {
      const response = await refreshRecalls();
      setResult(response);
      // The corpus ages move, so the shell's status line is now behind. The
      // sheet is not refetched: nothing on it changed.
      startTransition(() => router.refresh());
    } catch (thrown) {
      setResult(null);
      setFailed(toFailure(thrown).message);
    } finally {
      setAsking(false);
    }
  }

  const busy = asking || pending;

  return (
    <div className={styles.refresh}>
      <div className={styles.refreshRow}>
        <button
          type="button"
          className={styles.button}
          onClick={ask}
          disabled={busy}
          aria-busy={busy}
        >
          {busy ? "Asking the agency" : "Refresh the corpus"}
        </button>
        <p className={styles.refreshNote}>
          Writes a dated snapshot and stops there. No line on the pull sheet changes, and
          no line is re-decided. Re-matching is a separate act that produces a new run.
        </p>
      </div>

      {failed ? (
        <p className={styles.refreshResult}>
          The refresh route did not answer. {failed}
        </p>
      ) : null}

      {result ? (
        <div className={styles.refreshResult}>
          <p className={styles.refreshMessage}>{result.message}</p>
          {result.error ? <p className={styles.refreshError}>{result.error}</p> : null}
          <p className={styles.refreshCorpus}>
            {result.corpus.map((snapshot, index) => (
              <span key={snapshot.source}>
                {index > 0 ? <span aria-hidden="true"> · </span> : null}
                <span className={styles.refreshSource}>{snapshot.source}</span>{" "}
                <ProvenanceLabel
                  provenance={snapshot.provenance}
                  label={snapshot.provenance_label}
                />{" "}
                <span>
                  captured {formatDateTime(snapshot.captured_at) ?? snapshot.captured_at}
                </span>
              </span>
            ))}
          </p>
        </div>
      ) : null}
    </div>
  );
}
