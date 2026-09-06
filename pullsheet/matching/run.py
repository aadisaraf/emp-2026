"""Match orchestration: for every inventory row, generate candidates, build
evidence, and record a decision.

This module is an addition to the plan's source tree. It exists so ``gate.py``
stays a pure function of its arguments -- orchestration, database handles, and
loops all live here instead of being smuggled into the chokepoint.

The loop itself is deliberately dull. Every interesting rule is in one of the
four modules it calls, each of which is tested on its own.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from pullsheet.matching.gate import decide
from pullsheet.matching.screen import ScreenRecord, build_indexes, generate_candidates
from pullsheet.matching.tiers import build_evidence
from pullsheet.recalls.corpus import active_records

#: FR-032. The trailing `id` guarantees a total order, so two runs cannot
#: differ on ties (SC-011).
MATCH_ORDER = """
    ORDER BY r.class_rank,
             CASE m.tier WHEN 'CONFIRMED' THEN 1 WHEN 'PROBABLE' THEN 2 ELSE 3 END,
             m.score IS NULL,
             m.score DESC,
             m.id
"""


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

    This distinction is the whole safety argument for daily runs. An item that
    is absent from today's export is deliberately left active by
    ``db.persist_records``, because a missing line is not proof the food left
    the freezer. Matching the ACTIVE set into every run means that item keeps
    appearing on every sheet until an export actually replaces it. Matching only
    what today's file carried would make a partial export a silent clearing
    path, which is the exact failure Principle I exists to prevent.
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
    """Match every active inventory row against the loaded corpus, for one run.

    Rebuilds the indexes each run rather than caching them. At this corpus size
    that costs under a second, and a cache is a place for the corpus and the
    index to disagree about what exists.

    Every match is stamped with ``run_id``, and whether it is NEW is decided
    here, at the moment the row is written -- by asking whether the previous
    good run produced the same (item identity, recall) pair. Deciding it here
    rather than patching it afterwards is what keeps ``matches`` a table the
    matcher writes once and nothing ever edits (tests/unit/test_clearing_audit.py).
    """
    from pullsheet.db import previously_matched_pairs

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
                # remove, and generate_candidates is where that is justified.
                continue
            decision = decide(inv, rec, evidence)
            # The first run has no predecessor to be new against. Flagging its
            # whole sheet would bury the one line that matters on every run
            # after it.
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
    """One run's sheet, in the one deterministic order the whole application uses.

    PULL and HELD come back interleaved in this single order. HELD is never a
    separate section and never behind a toggle -- a held line that an operator
    has to go looking for is a held line they will not see.

    Scoped on ``m.run_id`` and on NOTHING ELSE. In particular it does not also
    filter ``i.superseded_by IS NULL``: the run already matched the active set
    as it stood, and re-applying today's supersession to a past run would empty
    its sheet retroactively -- which would read as "that day was clean" rather
    than as the bug it is.

    A clearing is matched on ``subject_key`` -- the item's identity and the
    recall, not the match row id -- so a false positive an operator cleared on
    Monday stays cleared on Tuesday's run, which writes new match rows for the
    same food. ``decided_before`` bounds that to the moment the sheet depicts,
    so a past run does not render lines as cleared before anyone cleared them.
    """
    from pullsheet.db import SUBJECT_KEY_SQL

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
                   AND (:before IS NULL OR d.created_at < :before)) AS cleared_count
          FROM matches m
          JOIN inventory_records i ON i.id = m.inventory_record_id
          JOIN recall_records   r ON r.id = m.recall_record_id
         WHERE m.run_id = :run
    """ + MATCH_ORDER, {"run": run_id, "before": decided_before}))
