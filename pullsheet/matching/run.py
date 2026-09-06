"""Match orchestration: for every inventory row, generate candidates, build
evidence, and record a decision.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from pullsheet.db import SUBJECT_KEY_SQL, previously_matched_pairs
from pullsheet.matching.gate import decide
from pullsheet.matching.screen import ScreenRecord, build_indexes, generate_candidates
from pullsheet.matching.tiers import build_evidence
from pullsheet.recalls.corpus import active_records


def _recall_objects(rows) -> list[SimpleNamespace]:
    out = []
    for row in rows:
        out.append(SimpleNamespace(
            id=row["id"],
            source=row["source"],
            source_record_id=row["source_record_id"],
            product_description=row["product_description"],
            normalized_description=row["normalized_description"],
            code_info=row["code_info"] or "",
            recalling_firm=row["recalling_firm"] or "",
            parsed_codes=json.loads(row["parsed_codes"] or "{}"),
            classification=row["classification"],
            class_rank=row["class_rank"],
            status=row["status"],
        ))
    return out


def _inventory_objects(conn) -> list[SimpleNamespace]:
    """Every inventory row that has not been replaced -- NOT every row this run
    delivered.
    """
    rows = conn.execute(
        "SELECT * FROM inventory_records WHERE superseded_by IS NULL ORDER BY id"
    ).fetchall()
    return [SimpleNamespace(
        id=r["id"], identity_key=r["identity_key"],
        storage_location=r["storage_location"],
        raw_description=r["raw_description"],
        normalized_description=r["normalized_description"],
        quantity=r["quantity"], gtin=r["gtin"],
        lot_code=r["lot_code"], unit_cost=r["unit_cost"],
        brand=r["brand"], manufacturer=r["manufacturer"],
        manufacturer_item_code=r["manufacturer_item_code"],
        vendor_name=r["vendor_name"], vendor_item_code=r["vendor_item_code"],
    ) for r in rows]


def run_matcher(conn: sqlite3.Connection, run_id: int,
                now: datetime | str | None = None) -> dict[str, int]:
    """Match every active inventory row against the loaded corpus, for one run."""
    if isinstance(now, str):
        created_at = now
    else:
        created_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    seen_before = previously_matched_pairs(conn, run_id)
    has_predecessor = bool(seen_before)

    recalls = _recall_objects(active_records(conn))
    by_id = {r.id: r for r in recalls}
    indexes = build_indexes([
        ScreenRecord(id=r.id, normalized_description=r.normalized_description,
                     parsed_codes=r.parsed_codes, recalling_firm=r.recalling_firm)
        for r in recalls
    ])

    stats = {"inventory_rows": 0, "candidate_pairs": 0, "matches": 0,
             "PULL": 0, "HELD": 0, "new": 0}

    for inv in _inventory_objects(conn):
        stats["inventory_rows"] += 1
        candidates = generate_candidates(inv, indexes)
        for recall_id in sorted(candidates):
            stats["candidate_pairs"] += 1
            rec = by_id[recall_id]
            evidence = build_evidence(inv, rec, indexes.is_distinctive)
            if evidence is None:
                # Screening let the pair through but nothing links it. Recording
                # no match here is not a clearing path: no line ever existed to
                continue
            decision = decide(evidence)
            # The first run has no predecessor to be new against. Flagging its
            # whole sheet would bury the one line that matters on every run
            is_new = int(has_predecessor
                         and (inv.identity_key, rec.id) not in seen_before)
            conn.execute(
                """INSERT INTO matches
                   (run_id, inventory_record_id, recall_record_id, tier, status,
                    evidence_kind, trigger_inventory_text, trigger_recall_text,
                    score, lot_note, is_new, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id, inv.id, rec.id, decision.tier, decision.status,
                 decision.evidence_kind,
                 decision.trigger_inventory_text, decision.trigger_recall_text,
                 decision.score, decision.lot_note, is_new, created_at),
            )
            stats["matches"] += 1
            stats[decision.status] += 1
            stats["new"] += is_new

    conn.commit()
    return stats


def ordered_matches(conn: sqlite3.Connection, run_id: int,
                    decided_before: str | None = None) -> list[sqlite3.Row]:
    """One run's sheet, in the one deterministic order the whole application uses."""
    return list(conn.execute("""
        SELECT m.*, i.storage_location, i.raw_description, i.quantity,
               i.unit, i.pack_size, i.lot_code, i.unit_cost, i.identity_key,
               i.merged_from,
               i.brand, i.manufacturer, i.manufacturer_item_code,
               i.vendor_name, i.vendor_item_code,
               r.source, r.source_record_id, r.product_description, r.code_info,
               r.classification, r.class_rank, r.recalling_firm, r.status AS recall_status,
               r.prior_status AS recall_prior_status, r.status_changed_at,
               r.amended_from,
               r.reason_for_recall,
               (SELECT COUNT(*) FROM decisions d
                 WHERE d.subject_key = """ + SUBJECT_KEY_SQL + """
                   AND d.kind = 'clear_match'
                   AND (:before IS NULL OR d.created_at < :before)) AS cleared_count,
               (SELECT COUNT(*) FROM decisions d
                 WHERE d.subject_key = """ + SUBJECT_KEY_SQL + """
                   AND d.kind = 'confirm_pulled'
                   AND (:before IS NULL OR d.created_at < :before)) AS confirmed_count
          FROM matches m
          JOIN inventory_records i ON i.id = m.inventory_record_id
          JOIN recall_records   r ON r.id = m.recall_record_id
         WHERE m.run_id = :run
         -- FR-032. The trailing `id` guarantees a total order, so two runs
         -- cannot differ on ties (SC-011).
         ORDER BY r.class_rank,
                  CASE m.tier WHEN 'CONFIRMED' THEN 1 WHEN 'PROBABLE' THEN 2 ELSE 3 END,
                  m.score IS NULL,
                  m.score DESC,
                  m.id
    """, {"run": run_id, "before": decided_before}))
