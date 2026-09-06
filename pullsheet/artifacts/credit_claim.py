"""FR-046, FR-047. The distributor credit claim.

Plain arithmetic: quantity x unit cost, summed. No estimation anywhere, and that
is the whole design.

A line is excluded from the dollar total for exactly two reasons, and both are
stated on the claim by name:

  no unit cost   the export did not carry a price. Quantity is shown; no
                 dollar figure is invented for it.
  no quantity    the export left the count blank (FR-007 keeps the row). A price
                 without a count is not an amount.

A claim that quietly estimated either would be a claim a distributor could
reject wholesale, and the kitchen would have no way to tell which number was
guessed. Excluded lines are printed on the claim, not omitted from it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from pullsheet import location
from typing import Any

SOURCE_KEYS = ("openfda", "fsis", "inventory_lincoln", "unit_costs")

#: Only pulled lines. A held line is undecided, and billing a distributor for a
#: case you have not decided to remove is a claim you will have to withdraw.
CLAIM_STATUSES = ("PULL",)


def claim_lines(conn: sqlite3.Connection, run_id: int) -> list[dict[str, Any]]:
    """One row per pulled inventory line in this run, deduplicated across its
    recall matches."""
    grouped: dict[int, dict[str, Any]] = {}
    for row in conn.execute(
        """SELECT i.id, i.storage_location, i.raw_description, i.quantity,
                  i.unit, i.pack_size, i.lot_code, i.brand, i.manufacturer,
                  i.manufacturer_item_code, i.vendor_name, i.vendor_item_code,
                  i.unit_cost, i.received_date,
                  r.source, r.source_record_id, r.recalling_firm
             FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
             JOIN recall_records   r ON r.id = m.recall_record_id
            WHERE m.run_id = ? AND m.status = 'PULL'
            ORDER BY i.storage_location, i.raw_description, m.id""",
        (run_id,),
    ):
        entry = grouped.get(row["id"])
        if entry is None:
            entry = grouped[row["id"]] = {
                k: row[k] for k in (
                    "id", "storage_location", "raw_description", "quantity",
                    "unit", "pack_size", "lot_code", "brand", "manufacturer",
                    "manufacturer_item_code", "vendor_name", "vendor_item_code",
                    "unit_cost", "received_date")}
            entry["recalls"] = []
            # The distributor's own item number is what a credit desk keys on.
            # It never appears in an FDA notice, so it is carried, not matched.
            entry["extended"] = (
                round(row["quantity"] * row["unit_cost"], 2)
                if row["quantity"] is not None and row["unit_cost"] is not None else None)
            entry["excluded_because"] = (
                None if entry["extended"] is not None
                else "no unit cost in the export" if row["unit_cost"] is None
                else "no quantity in the export")
        if row["source_record_id"] not in [r["source_record_id"] for r in entry["recalls"]]:
            entry["recalls"].append({k: row[k] for k in
                                     ("source", "source_record_id", "recalling_firm")})
    return list(grouped.values())


def credit_claim(conn: sqlite3.Connection, run_id: int, now: datetime) -> dict[str, Any]:
    rows = claim_lines(conn, run_id)
    counted = [r for r in rows if r["extended"] is not None]
    excluded = [r for r in rows if r["extended"] is None]
    total = round(sum(r["extended"] for r in counted), 2)

    if excluded:
        statement = (
            f"This total covers {len(counted)} of {len(rows)} pulled lines. "
            f"{len(excluded)} {'line is' if len(excluded) == 1 else 'lines are'} "
            f"shown with quantity only and EXCLUDED from the ${total:,.2f}: "
            + "; ".join(f"{r['raw_description']} ({r['storage_location']}) -- {r['excluded_because']}"
                        for r in excluded)
            + ". No price has been estimated for them.")
    else:
        statement = (f"This total covers all {len(rows)} pulled lines. No line was "
                     f"excluded and no price was estimated.")

    by_vendor: dict[str, dict[str, Any]] = {}
    for row in rows:
        vendor = by_vendor.setdefault(row["vendor_name"] or "vendor not stated",
                                      {"vendor": row["vendor_name"] or "vendor not stated",
                                       "lines": 0, "total": 0.0, "excluded": 0})
        vendor["lines"] += 1
        if row["extended"] is None:
            vendor["excluded"] += 1
        else:
            vendor["total"] = round(vendor["total"] + row["extended"], 2)

    return {
        "location": location.summary(),
        "run_id": run_id,
        "generated_at": now.isoformat(timespec="seconds"),
        "lines": rows,
        "counted": len(counted),
        "excluded": excluded,
        "total": total,
        "exclusion_statement": statement,
        "by_vendor": sorted(by_vendor.values(), key=lambda v: -v["total"]),
        "source_keys": SOURCE_KEYS,
        "arithmetic": "extended value = quantity x unit cost. Nothing is estimated.",
    }
