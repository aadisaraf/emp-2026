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
    rows = conn.execute(
        "SELECT * FROM inventory_records WHERE superseded_by IS NULL ORDER BY id"
    ).fetchall()
    return [SimpleNamespace(
        id=r["id"], site=r["site"], storage_location=r["storage_location"],
        raw_description=r["raw_description"],
        normalized_description=r["normalized_description"],
        quantity=r["quantity"], gtin=r["gtin"], upc=r["upc"],
        lot_code=r["lot_code"], unit_cost=r["unit_cost"],
        brand=r["brand"], manufacturer=r["manufacturer"],
        manufacturer_item_code=r["manufacturer_item_code"],
        vendor_name=r["vendor_name"], vendor_item_code=r["vendor_item_code"],
    ) for r in rows]


def run_matcher(conn: sqlite3.Connection, now: datetime | None = None,
                first_seen_run_id: int | None = None,
                only_recall_ids: set[int] | None = None) -> dict[str, int]:
    """Match every current inventory row against the loaded corpus.

    Rebuilds the indexes each run rather than caching them. At this corpus size
    that costs under a second, and a cache is a place for the corpus and the
    index to disagree about what exists.

    ``only_recall_ids`` narrows which recalls may PRODUCE a line -- the standing
    monitor uses it to evaluate just the records it has not seen before, so a
    second pass does not duplicate every existing match. The indexes are still
    built over the WHOLE corpus, because word distinctiveness is a property of
    the corpus and would be meaningless measured against three new records. This
    is a re-run filter, not a narrowing of what the matcher can find: every id
    in the set is evaluated against every inventory row exactly as a full run
    would evaluate it.
    """
    created_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")

    recalls = _recall_objects(active_records(conn))
    by_id = {r.id: r for r in recalls}
    indexes = build_indexes([
        ScreenRecord(id=r.id, normalized_description=r.normalized_description,
                     parsed_codes=r.parsed_codes, recalling_firm=r.recalling_firm)
        for r in recalls
    ])

    stats = {"inventory_rows": 0, "candidate_pairs": 0, "matches": 0,
             "PULL": 0, "HELD": 0}

    for inv in _inventory_objects(conn):
        stats["inventory_rows"] += 1
        candidates = generate_candidates(inv, indexes)
        if only_recall_ids is not None:
            candidates = {r for r in candidates if r in only_recall_ids}
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
            conn.execute(
                """INSERT INTO matches
                   (inventory_record_id, recall_record_id, tier, status, evidence_kind,
                    trigger_inventory_text, trigger_recall_text, score, lot_note,
                    first_seen_run_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (inv.id, rec.id, decision.tier, decision.status, decision.evidence_kind,
                 decision.trigger_inventory_text, decision.trigger_recall_text,
                 decision.score, decision.lot_note, first_seen_run_id, created_at),
            )
            stats["matches"] += 1
            stats[decision.status] += 1

    conn.commit()
    return stats


def ordered_matches(conn: sqlite3.Connection, site: str | None = None) -> list[sqlite3.Row]:
    """Every match, in the one deterministic order the whole application uses.

    PULL and HELD come back interleaved in this single order. HELD is never a
    separate section and never behind a toggle -- a held line that an operator
    has to go looking for is a held line they will not see.
    """
    sql = """
        SELECT m.*, i.site, i.storage_location, i.raw_description, i.quantity,
               i.unit, i.pack_size, i.lot_code, i.unit_cost,
               i.brand, i.manufacturer, i.manufacturer_item_code,
               i.vendor_name, i.vendor_item_code,
               r.source, r.source_record_id, r.product_description, r.code_info,
               r.classification, r.class_rank, r.recalling_firm, r.status AS recall_status,
               r.prior_status AS recall_prior_status, r.status_changed_at,
               r.amended_from,
               r.reason_for_recall,
               (SELECT COUNT(*) FROM decisions d
                 WHERE d.target_type = 'match' AND d.target_id = CAST(m.id AS TEXT)
                   AND d.kind = 'clear_match') AS cleared_count
          FROM matches m
          JOIN inventory_records i ON i.id = m.inventory_record_id
          JOIN recall_records   r ON r.id = m.recall_record_id
         WHERE i.superseded_by IS NULL
    """
    params: tuple = ()
    if site:
        sql += " AND i.site = ?"
        params = (site,)
    return list(conn.execute(sql + MATCH_ORDER, params))
