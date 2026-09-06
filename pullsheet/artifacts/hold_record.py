"""FR-043. The hold-and-destruction record for one run, ready to sign."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from pullsheet import location
from pullsheet.db import SUBJECT_KEY_SQL
from typing import Any

# Left blank, always, by design. Rendered as ruled lines on the printed record.
SIGNATURE_FIELDS: tuple[str, ...] = (
    "Removed from service by (print name)",
    "Title",
    "Date removed",
    "Storage location while held",
    "Witnessed by (print name)",
    "Disposition (destroyed / returned / other)",
    "Disposition date",
    "Authorizing signature",
)

# The sources every hold record draws on, labelled on the artifact (FR-048).
SOURCE_KEYS = ("openfda", "fsis", "inventory_lincoln")


def hold_record(conn: sqlite3.Connection, run_id: int, now: datetime) -> dict[str, Any]:
    # One row per inventory LINE in this run, with every recall that hit it.
    grouped: dict[int, dict[str, Any]] = {}
    for row in conn.execute(
        """SELECT i.id, i.storage_location, i.raw_description, i.quantity,
                  i.unit, i.pack_size, i.lot_code, i.gtin, i.brand, i.manufacturer,
                  i.manufacturer_item_code, i.vendor_name, i.vendor_item_code,
                  i.received_date,
                  m.id AS match_id, m.status, m.tier, m.evidence_kind,
                  r.source, r.source_record_id, r.recalling_firm, r.classification,
                  r.class_rank, r.status AS recall_status,
                  (SELECT COUNT(*) FROM decisions d
                    WHERE d.subject_key = """ + SUBJECT_KEY_SQL + """
                      AND d.kind = 'clear_match') AS cleared_count
             FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
             JOIN recall_records   r ON r.id = m.recall_record_id
            WHERE m.run_id = ?
            ORDER BY r.class_rank, i.storage_location, i.raw_description, m.id""",
        (run_id,),
    ):
        entry = grouped.get(row["id"])
        if entry is None:
            entry = grouped[row["id"]] = {
                k: row[k] for k in (
                    "id", "storage_location", "raw_description", "quantity",
                    "unit", "pack_size", "lot_code", "gtin", "brand", "manufacturer",
                    "manufacturer_item_code", "vendor_name", "vendor_item_code",
                    "received_date")}
            entry["recalls"] = []
            entry["status"] = "HELD"
        entry["recalls"].append({k: row[k] for k in (
            "match_id", "status", "tier", "evidence_kind", "source", "source_record_id",
            "recalling_firm", "classification", "recall_status", "cleared_count")})
        # A line is PULL if ANY recall against it pulls. Widening, per Principle I.
        if row["status"] == "PULL":
            entry["status"] = "PULL"
    rows = list(grouped.values())
    return {
        "location": location.summary(),
        "run_id": run_id,
        "generated_at": now.isoformat(timespec="seconds"),
        "lines": rows,
        "pull_count": sum(1 for r in rows if r["status"] == "PULL"),
        "held_count": sum(1 for r in rows if r["status"] == "HELD"),
        "signature_fields": SIGNATURE_FIELDS,
        "source_keys": SOURCE_KEYS,
        # Quantity is what the export said. Nothing here counted a freezer.
        "quantity_caveat": "quantities are as reported by the inventory export, not recounted",
    }
