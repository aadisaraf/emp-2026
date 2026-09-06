"use client";

import { useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { Decision, DecisionKind, MatchDetailResponse } from "@/lib/api";
import { clearMatch, confirmPulled, toFailure } from "@/lib/api";
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

export interface LineDecisionsProps {
  detail: MatchDetailResponse;
  timeZone: string;
}

/**
  Every decision ever taken about this food and this recall, and the two
  actions a person can take now.
*/
export function LineDecisions({ detail, timeZone }: LineDecisionsProps) {
  const router = useRouter();

  // What the last write returned, shown until the server render catches up
  // with it. Derived, not synchronised: once the server's copy carries as many
  // decisions as the written one, the written one simply stops being used.
  const [written, setWritten] = useState<MatchDetailResponse | null>(null);
  const view =
    written && detail.decisions.length < written.decisions.length ? written : detail;

  const [pending, setPending] = useState<DecisionKind | null>(null);

  /* Neither action is offered until this component is running: both are
     written by fetch, so an button that appears before hydration is a button
     that does nothing. False on the server, true once mounted. */
  const ready = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  const [clearActor, setClearActor] = useState("");
  const [clearNote, setClearNote] = useState("");
  const [clearError, setClearError] = useState<string | null>(null);
  const [clearDone, setClearDone] = useState<string | null>(null);
  const clearActorRef = useRef<HTMLInputElement>(null);

  const [pulledActor, setPulledActor] = useState("");
  const [pulledError, setPulledError] = useState<string | null>(null);
  const [pulledDone, setPulledDone] = useState<string | null>(null);
  const pulledActorRef = useRef<HTMLInputElement>(null);

  function stamp(response: MatchDetailResponse, kind: DecisionKind): Decision | null {
    let latest: Decision | null = null;
    for (const decision of response.decisions) {
      if (decision.kind === kind) latest = decision;
    }
    return latest;
  }

  async function submitClear(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const actor = clearActor.trim();
    if (actor.length === 0) {
      setClearError(CLEAR_FORM.actorMissing);
      clearActorRef.current?.focus();
      return;
    }
    setPending("clear_match");
    setClearError(null);
    try {
      const note = clearNote.trim();
      const response = await clearMatch(detail.match.id, {
        actor,
        note: note.length > 0 ? note : null,
      });
      const decision = stamp(response, "clear_match");
      setWritten(response);
      setClearDone(
        clearConfirmation(
          decision?.actor ?? actor,
          decision
            ? (formatDateTime(decision.created_at, timeZone) ?? decision.created_at)
            : "",
        ),
      );
      setClearActor("");
      setClearNote("");
      router.refresh();
    } catch (thrown) {
      const failure = toFailure(thrown);
      setClearError(
        failure.code === "actor_required" ? CLEAR_FORM.actorMissing : failure.message,
      );
      if (failure.code === "actor_required") clearActorRef.current?.focus();
    } finally {
      setPending(null);
    }
  }

  async function submitPulled(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const actor = pulledActor.trim();
    if (actor.length === 0) {
      setPulledError(CONFIRM_PULLED_FORM.actorMissing);
      pulledActorRef.current?.focus();
      return;
    }
    setPending("confirm_pulled");
    setPulledError(null);
    try {
      const response = await confirmPulled(detail.match.id, { actor });
      const decision = stamp(response, "confirm_pulled");
      setWritten(response);
      setPulledDone(
        confirmPulledConfirmation(
          decision?.actor ?? actor,
          decision
            ? (formatDateTime(decision.created_at, timeZone) ?? decision.created_at)
            : "",
        ),
      );
      setPulledActor("");
      router.refresh();
    } catch (thrown) {
      const failure = toFailure(thrown);
      setPulledError(
        failure.code === "actor_required"
          ? CONFIRM_PULLED_FORM.actorMissing
          : failure.message,
      );
      if (failure.code === "actor_required") pulledActorRef.current?.focus();
    } finally {
      setPending(null);
    }
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
          <form className={styles.form} noValidate onSubmit={submitClear}>
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

          {/*
            One standing paragraph, not three. The panel note says who may
            clear and how long it lasts; this says what the system cannot do,
            which is the part no other sentence on the page carries.
          */}
          <p className={styles.standing}>{CLEAR_IS_A_HUMAN_ACT}</p>
        </Panel>

        <Panel title={CONFIRM_PULLED_FORM.heading} note={CONFIRM_PULLED_FORM.help} printBlock>
          <form className={styles.form} noValidate onSubmit={submitPulled}>
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
