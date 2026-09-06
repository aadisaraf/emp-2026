"""FR-051, FR-052, FR-053. The two USDA clocks.

    24 hours   notify the distributor
    48 hours   complete the inventory assessment

Both run from ``recall_records.received_at`` -- the moment the record first
became visible to THIS district -- not from the agency's own report date. A
recall published three weeks ago that a district learns about this morning
starts its clocks this morning, and computing from the report date would show a
district it was already three weeks late for a deadline it never had.

``now`` is injected. Nothing here reads the clock, which is why an overrun can
be demonstrated on demand instead of waited for.

FR-053 is the rule with teeth: **an elapsed deadline shows its overrun.** It does
not hide, it does not reset, and it does not turn green. A countdown that
disappears at zero is a countdown that lies at the exact moment it matters.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

DEADLINES: tuple[tuple[str, str, int], ...] = (
    ("distributor_notification", "Notify distributor", 24),
    ("inventory_assessment", "Complete inventory assessment", 48),
)


def _parse(value: str) -> datetime:
    from pullsheet.recalls.corpus import _parse_ts
    return _parse_ts(value)


def _phrase(delta: timedelta) -> tuple[str, bool]:
    """Human text for a remaining or elapsed interval, and whether it overran."""
    hours = delta.total_seconds() / 3600.0
    if hours >= 0:
        whole, minutes = int(hours), int(round((hours - int(hours)) * 60))
        return (f"{whole}h {minutes:02d}m remaining", False)
    over = -hours
    whole, minutes = int(over), int(round((over - int(over)) * 60))
    return (f"{whole}h {minutes:02d}m OVERRUN", True)


def clocks(conn: sqlite3.Connection, now: datetime) -> list[dict[str, Any]]:
    """One clock per deadline, measured from the earliest recall that produced a
    line on the sheet.

    Earliest, not latest: the tightest clock is the one a district is actually
    against, and showing the most forgiving one would be a comfortable lie.
    """
    row = conn.execute(
        """SELECT MIN(r.received_at) AS first_seen, COUNT(DISTINCT r.id) AS records
             FROM matches m
             JOIN recall_records r ON r.id = m.recall_record_id
             JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE i.superseded_by IS NULL"""
    ).fetchone()
    if not row or not row["first_seen"]:
        return []

    received = _parse(row["first_seen"])
    out = []
    for key, label, hours in DEADLINES:
        due = received + timedelta(hours=hours)
        text, overrun = _phrase(due - now)
        out.append({
            "key": key,
            "label": label,
            "hours": hours,
            "received_at": row["first_seen"],
            "due_at": due.isoformat(timespec="seconds"),
            "remaining_hours": round((due - now).total_seconds() / 3600.0, 2),
            "text": text,
            "overrun": overrun,
            "records": row["records"],
        })
    return out
