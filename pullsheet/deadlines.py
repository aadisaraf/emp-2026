"""FR-051, FR-052, FR-053. The two USDA clocks."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from pullsheet.recalls.corpus import _parse_ts

DEADLINES: tuple[tuple[str, str, int], ...] = (
    ("distributor_notification", "Notify distributor", 24),
    ("inventory_assessment", "Complete inventory assessment", 48),
)


def _phrase(delta: timedelta) -> tuple[str, bool]:
    """Human text for a remaining or elapsed interval, and whether it overran."""
    # Round to whole minutes FIRST, then split. Splitting first and rounding the
    # remainder produces "23h 60m", which reads like a broken clock.
    total_minutes = int(round(delta.total_seconds() / 60.0))
    hours, minutes = divmod(abs(total_minutes), 60)
    if total_minutes >= 0:
        return (f"{hours}h {minutes:02d}m remaining", False)
    return (f"{hours}h {minutes:02d}m OVERRUN", True)


def clocks(conn: sqlite3.Connection, run_id: int, now: datetime) -> list[dict[str, Any]]:
    """One clock per deadline, measured from the earliest recall that produced a
    line on the sheet.
    """
    row = conn.execute(
        """SELECT MIN(r.received_at) AS first_seen, COUNT(DISTINCT r.id) AS records
             FROM matches m
             JOIN recall_records r ON r.id = m.recall_record_id
            WHERE m.run_id = ?""", (run_id,)
    ).fetchone()
    if not row or not row["first_seen"]:
        return []

    received = _parse_ts(row["first_seen"])
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
