"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import {
  ErrorState,
  EvidenceKind,
  NewMark,
  NotRecorded,
  ProvenanceLabel,
  StatusBadge,
  TierBadge,
} from "@/components";
import {
  getMatch,
  type ApiFailure,
  type MatchDetailResponse,
} from "@/lib/api";
import { formatDate, formatDateTime, formatMoney, formatQuantity } from "@/lib/format";
import { UNCLASSIFIED } from "@/lib/strings";
import { Highlighted, triggerParts } from "@/app/match/_components/highlight";
import {
  DECISION_WORD,
  INVENTORY_FIELDS,
  RECALL_FIELDS,
  decisionOnAnotherLine,
} from "@/app/match/_components/strings";
import styles from "./sheet.module.css";

/* One line, opened beside the sheet rather than on top of it. */

/** The agency writes classes in Roman numerals; class_rank is spelled back. */
const CLASS_NUMERAL: Record<number, string> = { 1: "I", 2: "II", 3: "III" };

function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className={styles.paneRow}>
      <span className={styles.paneTerm}>{term}</span>
      <span className={styles.paneValue}>{children}</span>
    </div>
  );
}

function Value({ children }: { children: string | null }) {
  return children ? <>{children}</> : <NotRecorded />;
}

type PaneState =
  | { phase: "loading" }
  | { phase: "ready"; detail: MatchDetailResponse }
  | { phase: "failed"; failure: ApiFailure };

export function MatchPane({ matchId, onClose }: {
  matchId: number;
  onClose: () => void;
}) {
  /* Keyed by line id at the call site, so a different line mounts a fresh
     pane and one line's record can never appear under another's name. */
  const [state, setState] = useState<PaneState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    getMatch(matchId).then((result) => {
      if (cancelled) return;
      setState(
        result.ok
          ? { phase: "ready", detail: result.data }
          : { phase: "failed", failure: result.error },
      );
    });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const head = (
    <div className={styles.paneHead}>
      <p className={styles.paneTitle}>
        {state.phase === "ready" ? state.detail.inventory.raw_description : `Line #${matchId}`}
      </p>
      <button type="button" className={styles.paneClose} onClick={onClose}>
        Close
      </button>
    </div>
  );

  if (state.phase === "failed") {
    return (
      <aside className={`${styles.pane} no-print`} aria-label={`Line ${matchId}`}>
        {head}
        <div className={styles.paneSection}>
          <ErrorState failure={state.failure} heading="This line did not load." compact />
        </div>
      </aside>
    );
  }

  if (state.phase === "loading") {
    return (
      <aside className={`${styles.pane} no-print`} aria-label={`Line ${matchId}`}>
        {head}
        <div className={styles.paneSection}>
          <p className={styles.paneValue}>loading</p>
        </div>
      </aside>
    );
  }

  const { match, inventory, recall, decisions } = state.detail;
  const inventoryParts = triggerParts(match.trigger_inventory_text);
  const recallParts = triggerParts(match.trigger_recall_text);

  return (
    <aside className={`${styles.pane} no-print`} aria-label={`Line ${matchId}`}>
      {head}

      <div className={styles.paneChips}>
        <StatusBadge value={match.status} />
        <TierBadge tier={match.tier} />
        <EvidenceKind kind={match.evidence_kind} showRaw />
        {match.is_new ? <NewMark /> : null}
      </div>
      {match.lot_note ? <p className={styles.note}>{match.lot_note}</p> : null}

      <div className={styles.paneSection}>
        <p className={styles.paneLabel}>Triggered by</p>
        <Row term="Inventory">
          <code className={styles.code}>{match.trigger_inventory_text}</code>
        </Row>
        <Row term="Recall">
          <code className={styles.code}>{match.trigger_recall_text}</code>
        </Row>
      </div>

      <div className={styles.paneSection}>
        <p className={styles.paneLabel}>The inventory line</p>
        <p className={styles.paneVerbatim}>
          <Highlighted text={inventory.raw_description} parts={inventoryParts} />
        </p>
        <Row term={INVENTORY_FIELDS.storage}>
          <Value>{inventory.storage_location}</Value>
        </Row>
        <Row term={INVENTORY_FIELDS.quantity}>
          {formatQuantity(inventory.quantity, inventory.unit) ?? <NotRecorded />}
        </Row>
        <Row term={INVENTORY_FIELDS.packSize}>
          <Value>{inventory.pack_size}</Value>
        </Row>
        <Row term={INVENTORY_FIELDS.lot}>
          {inventory.lot_code ? (
            <code className={styles.code}>
              <Highlighted text={inventory.lot_code} parts={inventoryParts} />
            </code>
          ) : (
            <NotRecorded />
          )}
        </Row>
        <Row term={INVENTORY_FIELDS.gtin}>
          {inventory.gtin ? <code className={styles.code}>{inventory.gtin}</code> : <NotRecorded />}
        </Row>
        <Row term={INVENTORY_FIELDS.unitCost}>{formatMoney(inventory.unit_cost) ?? <NotRecorded />}</Row>
        <Row term={INVENTORY_FIELDS.brand}>
          <Value>{inventory.brand}</Value>
        </Row>
        <Row term={INVENTORY_FIELDS.manufacturer}>
          <Value>{inventory.manufacturer}</Value>
        </Row>
        <Row term={INVENTORY_FIELDS.mfrItem}>
          {inventory.manufacturer_item_code ? (
            <code className={styles.code}>{inventory.manufacturer_item_code}</code>
          ) : (
            <NotRecorded />
          )}
        </Row>
        <Row term={INVENTORY_FIELDS.vendor}>
          <Value>{inventory.vendor_name}</Value>
        </Row>
        <Row term={INVENTORY_FIELDS.vendorItem}>
          {inventory.vendor_item_code ? (
            <code className={styles.code}>{inventory.vendor_item_code}</code>
          ) : (
            <NotRecorded />
          )}
        </Row>
        {inventory.unpopulated_fields.length > 0 ? (
          <Row term="Not carried">
            <span className={styles.note}>
              this export carried no {inventory.unpopulated_fields.join(", ")}
            </span>
          </Row>
        ) : null}
        {inventory.merged_from ? (
          <Row term="Merged from">
            <span className={styles.note}>
              export rows {inventory.merged_from.join(", ")} merged into this record
            </span>
          </Row>
        ) : null}
      </div>

      <div className={styles.paneSection}>
        <p className={styles.paneLabel}>The recall record</p>
        <p className={styles.paneVerbatim}>
          <Highlighted text={recall.product_description} parts={recallParts} />
        </p>
        <Row term={RECALL_FIELDS.record}>
          <code className={styles.code}>{recall.source_record_id}</code>{" "}
          {recall.source}{" "}
          <ProvenanceLabel provenance={recall.provenance} label={recall.provenance_label} />
        </Row>
        <Row term={RECALL_FIELDS.classification}>
          {recall.classification ??
            `${UNCLASSIFIED} (ranked with Class ${
              CLASS_NUMERAL[recall.class_rank] ?? recall.class_rank
            })`}
        </Row>
        <Row term={RECALL_FIELDS.firm}>
          <Value>{recall.recalling_firm}</Value>
        </Row>
        <Row term={RECALL_FIELDS.reason}>
          <Value>{recall.reason_for_recall}</Value>
        </Row>
        <Row term={RECALL_FIELDS.codeInfo}>
          {recall.code_info ? (
            <code className={styles.code}>
              <Highlighted text={recall.code_info} parts={recallParts} />
            </code>
          ) : (
            <NotRecorded />
          )}
        </Row>
        <Row term={RECALL_FIELDS.status}>
          {recall.status}
          {recall.prior_status ? ` (was ${recall.prior_status})` : ""}
          {recall.status_changed_at
            ? ` on ${formatDate(recall.status_changed_at) ?? recall.status_changed_at}`
            : ""}
        </Row>
        <Row term={RECALL_FIELDS.reported}>
          <Value>{formatDate(recall.report_date)}</Value>
        </Row>
        <Row term={RECALL_FIELDS.received}>
          <Value>{formatDateTime(recall.received_at)}</Value>
        </Row>
      </div>

      <div className={styles.paneSection}>
        <p className={styles.paneLabel}>Decisions</p>
        {decisions.length === 0 ? (
          <p className={styles.paneValue}>
            No person has recorded a decision on this item and this recall.
          </p>
        ) : (
          decisions.map((decision) => (
            <div className={styles.decision} key={decision.id}>
              <p className={styles.decisionHead}>
                <span className={styles.decisionActor}>{decision.actor}</span>
                <span className={styles.note}>{DECISION_WORD[decision.kind]}</span>
                <span className={styles.note}>
                  {formatDateTime(decision.created_at) ?? decision.created_at}
                </span>
              </p>
              {decision.note ? <p className={styles.decisionNote}>{decision.note}</p> : null}
              {decision.match_id !== match.id ? (
                <p className={styles.note}>{decisionOnAnotherLine(decision.match_id)}</p>
              ) : null}
            </div>
          ))
        )}
      </div>

      <p className={styles.paneLink}>
        {/* The app's own record, which is where a line is cleared. The pane is
            a look; the page is where a decision gets written. */}
        <Link href={`/match/${match.id}`}>Open the full record for line #{match.id}</Link>
      </p>
    </aside>
  );
}
