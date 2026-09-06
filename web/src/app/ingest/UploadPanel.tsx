"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useRouter } from "next/navigation";
import {
  answerMapping,
  uploadInventory,
  type IngestAmbiguous,
  type IngestResult,
} from "@/lib/api";
import { Chip, Note, TabCard } from "@/components";
import { formatCount } from "@/lib/format";
import { cx } from "@/lib/cx";
import styles from "./ingest.module.css";

/*
  One file, read once. The three things that can happen to it are all on this
  panel: it was read, one heading needs an answer, or the delivery was refused
  and is now a refused run. Nothing here fails silently.
*/

type Settled = Exclude<IngestResult, IngestAmbiguous>;

export function UploadPanel() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);

  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [question, setQuestion] = useState<IngestAmbiguous | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [settled, setSettled] = useState<Settled | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  function receive(result: IngestResult) {
    if (result.status === "ambiguous") {
      setQuestion(result);
      setAnswers(
        Object.fromEntries(Object.keys(result.ambiguous).map((h) => [h, "ignore"])),
      );
      setSettled(null);
      return;
    }
    setQuestion(null);
    setSettled(result);
    if (result.status === "ok") {
      // The sheet on every other route is now a run behind.
      router.refresh();
    }
  }

  async function send(file: File) {
    setBusy(true);
    setFailed(null);
    setSettled(null);
    const result = await uploadInventory(file);
    if (result.ok) receive(result.data);
    else setFailed(result.error.message);
    setBusy(false);
  }

  async function answer() {
    if (!question) return;
    setBusy(true);
    setFailed(null);
    const result = await answerMapping(question.filename, answers);
    if (result.ok) receive(result.data);
    else setFailed(result.error.message);
    setBusy(false);
  }

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void send(file);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void send(file);
  }

  return (
    <TabCard title="Upload one export">
      <div
        className={cx(styles.drop, over && styles.dropOver, busy && styles.dropBusy)}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <p className={styles.dropLead}>
          {busy ? "Reading the file" : "Drop one export here"}
        </p>
        <button
          type="button"
          className={styles.button}
          onClick={() => input.current?.click()}
          disabled={busy}
        >
          Choose a file
        </button>
        <input
          ref={input}
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className={styles.file}
          onChange={onPick}
          aria-label="Inventory export to upload"
        />
        <Note>CSV or XLSX. Read once, matched, and finalized as a run of its own.</Note>
      </div>

      {question ? (
        <div className={styles.question}>
          <p className={styles.questionLead}>
            {question.filename}: {formatCount(Object.keys(question.ambiguous).length)}{" "}
            {Object.keys(question.ambiguous).length === 1 ? "heading" : "headings"} could
            mean more than one thing. The answer is remembered for next time.
          </p>
          {Object.entries(question.ambiguous).map(([header, choices]) => (
            <label key={header} className={styles.field}>
              <span className={styles.fieldName}>{header}</span>
              <select
                className={styles.select}
                value={answers[header] ?? "ignore"}
                onChange={(e) =>
                  setAnswers((current) => ({ ...current, [header]: e.target.value }))
                }
              >
                <option value="ignore">Leave this column out</option>
                {choices.map((choice) => (
                  <option key={choice} value={choice}>
                    {choice}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <button type="button" className={styles.button} onClick={answer} disabled={busy}>
            {busy ? "Reading the file" : "Read the file with these answers"}
          </button>
        </div>
      ) : null}

      {settled ? <Outcome result={settled} /> : null}

      {failed ? (
        <p className={styles.failed}>The upload route did not answer. {failed}</p>
      ) : null}
    </TabCard>
  );
}

/** What happened to the file, in its own words. */
function Outcome({ result }: { result: Settled }) {
  if (result.status === "ok") {
    return (
      <p className={styles.outcome}>
        <Chip tone="done">read</Chip> {result.filename} is run #{result.run_id}. The pull
        sheet is now this run&apos;s.
      </p>
    );
  }
  if (result.status === "duplicate") {
    return (
      <p className={styles.outcome}>
        <Chip tone="held">already read</Chip> {result.reason} Nothing was changed, and no
        run was opened.
      </p>
    );
  }
  return (
    <p className={styles.outcome}>
      <Chip tone="pull">refused</Chip> {result.filename} could not be read, and is logged
      as refused run #{result.run_id}. {result.reason} The sheet in force is unchanged.
    </p>
  );
}
