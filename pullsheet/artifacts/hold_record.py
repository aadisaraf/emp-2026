"""FR-043. The hold-and-destruction record: one per site, ready to sign.

This is a physical-custody document. It says "these cases were taken out of
service, here is where they were, here is how much there was" -- and then it
stops, because everything after that is a human act. The signature, the title,
the date, and the destruction method are left BLANK. Pre-filling a signature
field would be forging a custody record, and a system that guesses at one is a
system nobody should sign anything from.

Both PULL and HELD lines appear. A held case is off the menu while a person
decides; leaving it off the custody record would mean a case in the freezer that
no paperwork accounts for.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

#: Left blank, always, by design. Rendered as ruled lines on the printed record.
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

#: The sources every hold record draws on, labelled on the artifact (FR-048).
SOURCE_KEYS = ("openfda", "fsis", "inventory_lincoln")


def lines(conn: sqlite3.Connection, site: str) -> list[dict[str, Any]]:
    """One row per inventory LINE at this site, with every recall that hit it.

    Per line, not per match: a case with three recalls against it is still one
    case in the freezer, and a custody record that lists it three times cannot
    be counted.
    """
    grouped: dict[int, dict[str, Any]] = {}
    for row in conn.execute(
        """SELECT i.id, i.site, i.storage_location, i.raw_description, i.quantity,
                  i.unit, i.pack_size, i.lot_code, i.gtin, i.brand, i.manufacturer,
                  i.manufacturer_item_code, i.vendor_name, i.vendor_item_code,
                  i.received_date, i.unpopulated_fields,
                  m.id AS match_id, m.status, m.tier, m.evidence_kind,
                  r.source, r.source_record_id, r.recalling_firm, r.classification,
                  r.class_rank, r.status AS recall_status,
                  (SELECT COUNT(*) FROM decisions d
                    WHERE d.target_type = 'match' AND d.target_id = CAST(m.id AS TEXT)
                      AND d.kind = 'clear_match') AS cleared_count
             FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
             JOIN recall_records   r ON r.id = m.recall_record_id
            WHERE i.site = ? AND i.superseded_by IS NULL
            ORDER BY r.class_rank, i.storage_location, i.raw_description, m.id""",
        (site,),
    ):
        entry = grouped.get(row["id"])
        if entry is None:
            entry = grouped[row["id"]] = {
                k: row[k] for k in (
                    "id", "site", "storage_location", "raw_description", "quantity",
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
    return list(grouped.values())


def hold_record(conn: sqlite3.Connection, site: str, now: datetime) -> dict[str, Any]:
    rows = lines(conn, site)
    return {
        "site": site,
        "district": "Lincoln Unified School District",
        "generated_at": now.isoformat(timespec="seconds"),
        "lines": rows,
        "pull_count": sum(1 for r in rows if r["status"] == "PULL"),
        "held_count": sum(1 for r in rows if r["status"] == "HELD"),
        "signature_fields": SIGNATURE_FIELDS,
        "source_keys": SOURCE_KEYS,
        # Quantity is what the export said. Nothing here counted a freezer.
        "quantity_caveat": "quantities are as reported by the inventory export, not recounted",
    }
