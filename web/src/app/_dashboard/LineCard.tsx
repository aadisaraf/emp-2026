"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { SheetLine } from "@/lib/types";
import { confirmPulled, toFailure } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { Icon } from "@/components/Icon";
import { cx } from "@/lib/cx";
import styles from "./dashboard.module.css";

/*
  One line, as a thing to do. The box on the left is the doing: ticking it
  writes a confirm_pulled decision under a person's name, the same record the
  full page writes. The name is asked for once and kept in this browser.
*/

const ROMAN: Record<SheetLine["class_rank"], string> = { 1: "I", 2: "II", 3: "III" };

const ACTOR_KEY = "pullsheet.actor";

function rememberedActor(): string {
  try {
    return window.localStorage.getItem(ACTOR_KEY) ?? "";
  } catch {
    return "";
  }
}

function rememberActor(name: string) {
  try {
    window.localStorage.setItem(ACTOR_KEY, name);
  } catch {
    // A browser that refuses storage just asks again next time.
  }
}

export function LineCard({ line }: { line: SheetLine }) {
  const router = useRouter();
  const [confirmed, setConfirmed] = useState(line.confirmed_pulled);
  const [asking, setAsking] = useState(false);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  const done = confirmed || line.cleared;
  const open = `/match/${line.id}`;

  /* Three facts, each with its own mark: how much, which lot, whose recall. */
  const facts: { icon: string; text: string }[] = [];
  if (line.quantity !== null) {
    facts.push({
      icon: "box",
      text: `${formatCount(line.quantity)} ${line.unit ?? ""}`.trim(),
    });
  }
  if (line.lot_code) facts.push({ icon: "tag", text: line.lot_code });
  if (line.recalling_firm) facts.push({ icon: "firm", text: line.recalling_firm });

  async function confirm(actor: string) {
    setPending(true);
    setFailed(null);
    try {
      await confirmPulled(line.id, { actor });
      rememberActor(actor);
      setConfirmed(true);
      setAsking(false);
      router.refresh();
    } catch (thrown) {
      setFailed(toFailure(thrown).message);
    } finally {
      setPending(false);
    }
  }

  function onTick() {
    if (done || pending) return;
    const actor = rememberedActor();
    if (actor) void confirm(actor);
    else setAsking(true);
  }

  function onName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const actor = nameRef.current?.value.trim() ?? "";
    if (!actor) {
      nameRef.current?.focus();
      return;
    }
    void confirm(actor);
  }

  return (
    <li className={styles.lineRow}>
      <div className={styles.gutter} aria-hidden="true">
        <span className={styles.gutterDot} data-rank={line.class_rank}>
          {ROMAN[line.class_rank]}
        </span>
        <span className={styles.gutterLabel}>{line.storage_location ?? ""}</span>
      </div>
      <article className={cx(styles.lineCard, done && styles.lineCardDone)}>
        <button
          type="button"
          className={cx(styles.checkbox, done && styles.checkboxDone)}
          onClick={onTick}
          disabled={pending}
          aria-pressed={done}
          aria-label={
            done
              ? line.cleared && !confirmed
                ? "Cleared by a person"
                : "Pulled. Recorded under a name"
              : "Record that this case has been pulled"
          }
        >
          {done ? <Icon name="check" size={14} /> : null}
        </button>
        <span className={styles.lineTitle}>{line.raw_description}</span>
        <span className={styles.lineChip} data-tier={line.tier}>
          {line.tier}
        </span>
        <Link href={open} className={styles.lineMore} aria-label="Open this line">
          <Icon name="open" size={16} />
        </Link>

        {asking && !done ? (
          <form className={styles.lineAsk} onSubmit={onName}>
            <input
              ref={nameRef}
              autoFocus
              type="text"
              placeholder="Your name"
              aria-label="Your name, recorded with the pull"
              className={styles.lineAskInput}
              disabled={pending}
            />
            <button type="submit" className={styles.lineAskButton} disabled={pending}>
              {pending ? "Recording" : "Record pull"}
            </button>
            <button
              type="button"
              className={styles.lineAskCancel}
              onClick={() => setAsking(false)}
              disabled={pending}
            >
              Not now
            </button>
          </form>
        ) : failed ? (
          <p className={cx(styles.lineMeta, styles.lineFailed)}>{failed}</p>
        ) : facts.length > 0 ? (
          <p className={styles.lineMeta}>
            {facts.map((f, i) => (
              <span key={f.icon} className={styles.lineFact}>
                {i > 0 ? <span className={styles.lineDot} aria-hidden="true" /> : null}
                <Icon name={f.icon} size={13} />
                {f.text}
              </span>
            ))}
          </p>
        ) : null}
      </article>
    </li>
  );
}
