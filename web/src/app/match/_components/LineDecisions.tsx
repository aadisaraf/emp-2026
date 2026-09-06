"use client";

import { useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { DecisionKind, MatchDetailResponse } from "@/lib/api";
import { clearMatch, confirmPulled } from "@/lib/api";
import {
  CLEAR_FORM,
  CONFIRM_PULLED_FORM,
  clearConfirmation,
  confirmPulledConfirmation,
} from "@/lib/strings";
import { formatDateTime } from "@/lib/format";
import { Panel } from "@/components";
import {
  CLEAR_IS_A_HUMAN_ACT,
  DECISIONS_HEADING,
  DECISIONS_KEPT,
  DECISIONS_NONE,
  DECISIONS_SCOPE,
  DECISION_WORD,
  confirmChangesNothing,
  decisionOnAnotherLine,
} from "./strings";
import styles from "./LineDecisions.module.css";

const noSubscription = () => () => {};

/** Every decision on this pair, and the two actions a person can take now. */
export function LineDecisions({ detail, timeZone }: {
  detail: MatchDetailResponse;
  timeZone: string;
}) {
  const router = useRouter();

  // What the last write returned, until the server render catches up with it.
  const [written, setWritten] = useState<MatchDetailResponse | null>(null);
  const view = written && written.decisions.length > detail.decisions.length ? written : detail;

  const [pending, setPending] = useState<DecisionKind | null>(null);

  /* Server HTML carries no submit handler, so neither action is offered until
     this component is running in the browser. */
  const ready = useSyncExternalStore(noSubscription, () => true, () => false);

  const [clearActor, setClearActor] = useState("");
  const [clearNote, setClearNote] = useState("");
  const [clearError, setClearError] = useState<string | null>(null);
  const [clearDone, setClearDone] = useState<string | null>(null);
  const clearActorRef = useRef<HTMLInputElement>(null);

  const [pulledActor, setPulledActor] = useState("");
  const [pulledError, setPulledError] = useState<string | null>(null);
  const [pulledDone, setPulledDone] = useState<string | null>(null);
  const pulledActorRef = useRef<HTMLInputElement>(null);

  /* Both actions are the same shape -- name a person, POST, show what the
     server wrote -- so they share one path. */
  async function submit(kind: DecisionKind, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clearing = kind === "clear_match";
    const form = clearing ? CLEAR_FORM : CONFIRM_PULLED_FORM;
    const actorRef = clearing ? clearActorRef : pulledActorRef;
    const setError = clearing ? setClearError : setPulledError;
    const actor = (clearing ? clearActor : pulledActor).trim();

    if (actor.length === 0) {
      setError(form.actorMissing);
      actorRef.current?.focus();
      return;
    }

    setPending(kind);
    setError(null);
    const note = clearNote.trim();
    const response = clearing
      ? await clearMatch(detail.match.id, { actor, note: note.length > 0 ? note : null })
      : await confirmPulled(detail.match.id, { actor });
    setPending(null);

    if (!response.ok) {
      const missing = response.error.code === "actor_required";
      setError(missing ? form.actorMissing : response.error.message);
      if (missing) actorRef.current?.focus();
      return;
    }

    // The confirmation quotes the row that was written, not the form.
    const decisions = response.data.decisions;
    const decision = decisions[decisions.length - 1] ?? null;
    const at = decision
      ? (formatDateTime(decision.created_at, timeZone) ?? decision.created_at)
      : "";
    setWritten(response.data);
    if (clearing) {
      setClearDone(clearConfirmation(decision?.actor ?? actor, at));
      setClearActor("");
      setClearNote("");
    } else {
      setPulledDone(confirmPulledConfirmation(decision?.actor ?? actor, at));
      setPulledActor("");
    }
    router.refresh();
  }

  return (
    <>
      <Panel title={DECISIONS_HEADING} note={DECISIONS_SCOPE} printBlock>
        {view.decisions.length === 0 ? (
          <p className={styles.none}>{DECISIONS_NONE}</p>
        ) : (
          <>
            <ol className={styles.log}>
              {view.decisions.map((decision) => (
                <li className={styles.entry} key={decision.id}>
                  <span className={styles.what}>{DECISION_WORD[decision.kind]}</span>{" "}
                  <span className={styles.who}>by {decision.actor}</span>{" "}
                  <span className={styles.when}>
                    at {formatDateTime(decision.created_at, timeZone) ?? decision.created_at}
                  </span>
                  {decision.note ? (
                    <span className={styles.why}>{decision.note}</span>
                  ) : null}
                  {decision.match_id !== view.match.id ? (
                    <span className={styles.elsewhere}>
                      {decisionOnAnotherLine(decision.match_id)}
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
            <p className={styles.kept}>{DECISIONS_KEPT}</p>
          </>
        )}
      </Panel>

      <div className={styles.actions}>
        <Panel title={CLEAR_FORM.heading} note={CLEAR_FORM.help} printBlock>
          <form className={styles.form} noValidate onSubmit={(event) => submit("clear_match", event)}>
            <label className={styles.field} htmlFor="clear-actor">
              <span className={styles.label}>{CLEAR_FORM.actorLabel}</span>
              <input
                aria-describedby={clearError ? "clear-actor-error" : undefined}
                aria-invalid={clearError ? true : undefined}
                autoComplete="off"
                className={clearError ? `${styles.input} ${styles.invalid}` : styles.input}
                id="clear-actor"
                name="actor"
                onChange={(event) => setClearActor(event.target.value)}
                placeholder={CLEAR_FORM.actorPlaceholder}
                ref={clearActorRef}
                required
                value={clearActor}
              />
            </label>

            <label className={styles.field} htmlFor="clear-note">
              <span className={styles.label}>{CLEAR_FORM.noteLabel}</span>
              <input
                autoComplete="off"
                className={styles.input}
                id="clear-note"
                name="note"
                onChange={(event) => setClearNote(event.target.value)}
                placeholder={CLEAR_FORM.notePlaceholder}
                value={clearNote}
              />
            </label>

            {clearError ? (
              <p className={styles.error} id="clear-actor-error" role="alert">
                {clearError}
              </p>
            ) : null}

            <button
              className={`${styles.button} ${styles.primary}`}
              disabled={!ready || pending !== null}
              type="submit"
            >
              {CLEAR_FORM.submit}
            </button>
          </form>

          {clearDone ? (
            <p className={styles.done} role="status">
              {clearDone}
            </p>
          ) : null}

          {/* What the system cannot do. No other sentence here says it. */}
          <p className={styles.standing}>{CLEAR_IS_A_HUMAN_ACT}</p>
        </Panel>

        <Panel title={CONFIRM_PULLED_FORM.heading} note={CONFIRM_PULLED_FORM.help} printBlock>
          <form className={styles.form} noValidate onSubmit={(event) => submit("confirm_pulled", event)}>
            <label className={styles.field} htmlFor="pulled-actor">
              <span className={styles.label}>{CLEAR_FORM.actorLabel}</span>
              <input
                aria-describedby={pulledError ? "pulled-actor-error" : undefined}
                aria-invalid={pulledError ? true : undefined}
                autoComplete="off"
                className={pulledError ? `${styles.input} ${styles.invalid}` : styles.input}
                id="pulled-actor"
                name="actor"
                onChange={(event) => setPulledActor(event.target.value)}
                placeholder={CLEAR_FORM.actorPlaceholder}
                ref={pulledActorRef}
                required
                value={pulledActor}
              />
            </label>

            {pulledError ? (
              <p className={styles.error} id="pulled-actor-error" role="alert">
                {pulledError}
              </p>
            ) : null}

            <button className={styles.button} disabled={!ready || pending !== null} type="submit">
              {CONFIRM_PULLED_FORM.submit}
            </button>
          </form>

          {pulledDone ? (
            <p className={styles.done} role="status">
              {pulledDone}
            </p>
          ) : null}

          <p className={styles.standing}>{confirmChangesNothing(view.match.status)}</p>
        </Panel>
      </div>
    </>
  );
}
