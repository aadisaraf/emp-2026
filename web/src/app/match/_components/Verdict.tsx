import type { ReactNode } from "react";
import type { Decision, MatchCore, RecallSide } from "@/lib/api";
import {
  EVIDENCE_EXPLANATION,
  EVIDENCE_UNKNOWN,
  TIER_EXPLANATION,
  TIER_LEGEND,
  amendedRecallNote,
} from "@/lib/strings";
import { formatDate, formatDateTime } from "@/lib/format";
import {
  ClearedMark,
  EvidenceKind,
  NewMark,
  ProvenanceLabel,
  StatusBadge,
  TierBadge,
} from "@/components";
import { HIGHLIGHT_LEGEND, UNCLASSIFIED } from "./strings";
import styles from "./Verdict.module.css";

export interface VerdictProps {
  match: MatchCore;
  recall: RecallSide;
  /** The most recent clear_match decision, when a person has taken one. */
  clearedBy: Decision | null;
  clearedCount: number;
  timeZone: string;
}

function Cell({
  label,
  children,
  wide,
}: {
  label: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={wide ? `${styles.cell} ${styles.wide}` : styles.cell}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{children}</span>
    </div>
  );
}

/** What the system found: the status word and the evidence behind it. */
export function Verdict({
  match,
  recall,
  clearedBy,
  clearedCount,
  timeZone,
}: VerdictProps) {
  const evidenceSentence = EVIDENCE_EXPLANATION[match.evidence_kind] ?? EVIDENCE_UNKNOWN;

  const amended =
    recall.status !== "active" && recall.prior_status
      ? amendedRecallNote(
          recall.status,
          recall.prior_status,
          formatDate(recall.status_changed_at, timeZone) ?? "a date the agency did not state",
        )
      : null;

  return (
    <section className={styles.verdict} data-print-block="">
      <div className={styles.rail}>
        <Cell label="Status">
          <StatusBadge value={match.status} />
          {match.is_new ? <NewMark className={styles.new} /> : null}
        </Cell>
        <Cell label="Tier">
          <TierBadge tier={match.tier} />
        </Cell>
        <Cell label="Evidence">
          <EvidenceKind kind={match.evidence_kind} showRaw />
        </Cell>
        <Cell label="Class">{recall.classification ?? UNCLASSIFIED}</Cell>
        <Cell label="Recall">{recall.status}</Cell>
        <Cell label="Source" wide>
          <span className="mono">{recall.source}</span>{" "}
          <ProvenanceLabel
            provenance={recall.provenance}
            label={recall.provenance_label}
          />
        </Cell>
      </div>

      <div className={styles.body}>
        <p className={styles.sentence}>{TIER_EXPLANATION[match.tier]}</p>
        <p className={styles.sentence}>{evidenceSentence}</p>
        <p className={styles.sentence}>{HIGHLIGHT_LEGEND}</p>

        {match.lot_note ? (
          <p className={styles.note}>
            <span className={styles.noteLabel}>Lot note</span> {match.lot_note}
          </p>
        ) : null}

        {amended ? (
          <p className={styles.note}>
            <span className={styles.noteLabel}>Recall changed</span> {amended}
          </p>
        ) : null}

        {clearedBy ? (
          <p className={styles.note}>
            <ClearedMark
              actor={clearedBy.actor}
              when={formatDateTime(clearedBy.created_at, timeZone) ?? clearedBy.created_at}
              count={clearedCount}
            />{" "}
            <span className={styles.stays}>
              The line keeps its status of {match.status} and stays on the sheet.
            </span>
          </p>
        ) : null}
      </div>

      <p className={styles.legend}>{TIER_LEGEND}</p>
    </section>
  );
}
