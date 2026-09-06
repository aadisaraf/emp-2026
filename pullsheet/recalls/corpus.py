"""Loading the committed recall corpus, and knowing how old it is.

Constitution Principle III: no external dependency at demo time. The corpus is
read from committed snapshot files on disk. ``fetch.py`` exists as a refresh
convenience and is never on the path between a dropped file and a printed sheet.

Freshness is measured against an INJECTED ``now``. Nothing here reads the clock.
That is what makes the 24-hour window testable without waiting a day, and it is
why the stale banner can be demonstrated on demand rather than hoped for.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from pullsheet.matching.normalize import normalize
from pullsheet.provenance import SOURCES
from pullsheet.recalls.parse import parse_record

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT_DIR = ROOT / "pullsheet" / "recalls" / "snapshots"

#: FR-068. Beyond this the corpus is presented as stale -- loudly, on every
#: surface. A stale banner during a demo is intended behaviour, not a defect.
FRESHNESS_WINDOW = timedelta(hours=24)

#: openFDA writes 'Ongoing' / 'Completed' / 'Terminated'. FR-016 keeps every one
#: of them; the status only changes how the line is marked.
_STATUS_MAP = {
    "ongoing": "active",
    "completed": "active",
    "active": "active",
    "terminated": "terminated",
    "amended": "amended",
}

#: A recall with no classification sorts as the MOST serious until an agency
#: says otherwise. Widening, not narrowing.
_CLASS_RANK = {"class i": 1, "class ii": 2, "class iii": 3}


def class_rank(classification: str | None) -> int:
    if not classification:
        return 1
    return _CLASS_RANK.get(classification.strip().lower(), 1)


def _iso(value: str | None) -> Optional[str]:
    """openFDA writes dates as YYYYMMDD."""
    if not value:
        return None
    v = value.strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
    return v


def snapshot_files() -> list[tuple[str, Path, Path]]:
    """(source key, snapshot path, meta path) for every committed snapshot."""
    out = []
    for key in ("openfda", "fsis"):
        path = ROOT / SOURCES[key][1]
        out.append((key, path, path.with_suffix(".meta.json")))
    return out


def load_snapshots(conn: sqlite3.Connection, received_at: str | None = None) -> dict[str, int]:
    """Load every committed snapshot into ``recall_snapshots`` and ``recall_records``.

    ``received_at`` is when THIS LOCATION first saw the recall, which is what the
    24-hour and 48-hour USDA FNS clocks run from (FR-051) -- not the agency's own
    report date. It is injected so a rehearsal can place the kitchen anywhere in
    that window on purpose.

    A daily cadence re-reads the same feeds every morning, so a record already
    held is UPDATED and its ``received_at`` is left exactly as it was. FR-053:
    a deadline never resets. Re-stamping it would quietly hand the kitchen a
    fresh 24 hours every time the corpus refreshed.
    """
    counts: dict[str, int] = {}
    now = received_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    for key, path, meta_path in snapshot_files():
        doc = json.loads(path.read_text())
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        results = doc.get("results", [])

        cur = conn.execute(
            """INSERT INTO recall_snapshots
               (source, captured_at, record_count, provenance, file_path, fetch_status)
               VALUES (?,?,?,?,?,?)""",
            (key, meta.get("captured_at") or now, len(results),
             meta.get("provenance") or SOURCES[key][0],
             str(path.relative_to(ROOT)), "committed"),
        )
        snapshot_id = cur.lastrowid

        for rec in results:
            description = rec.get("product_description") or ""
            parsed = parse_record(description, rec.get("code_info"), rec.get("more_code_info"))
            raw_status = (rec.get("status") or "active").strip().lower()
            conn.execute(
                """INSERT INTO recall_records
                   (source, source_record_id, snapshot_id, recalling_firm,
                    product_description, normalized_description, code_info,
                    parsed_codes, classification, class_rank, report_date,
                    received_at, reason_for_recall, status, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT (source, source_record_id) DO UPDATE SET
                       snapshot_id            = excluded.snapshot_id,
                       recalling_firm         = excluded.recalling_firm,
                       product_description    = excluded.product_description,
                       normalized_description = excluded.normalized_description,
                       code_info              = excluded.code_info,
                       parsed_codes           = excluded.parsed_codes,
                       classification         = excluded.classification,
                       class_rank             = excluded.class_rank,
                       report_date            = excluded.report_date,
                       reason_for_recall      = excluded.reason_for_recall,
                       raw_json               = excluded.raw_json""",
                (key, rec.get("recall_number") or "", snapshot_id,
                 rec.get("recalling_firm"), description, normalize(description),
                 rec.get("code_info"), json.dumps(parsed),
                 rec.get("classification"), class_rank(rec.get("classification")),
                 _iso(rec.get("report_date")), now, rec.get("reason_for_recall"),
                 _STATUS_MAP.get(raw_status, "active"), json.dumps(rec)),
            )
        counts[key] = len(results)

    conn.commit()
    return counts


def active_records(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The recall records the matcher runs against.

    ==========================================================================
    CONSTITUTION PRINCIPLE I -- JUSTIFIED NARROWING PATH 3 OF 3
    --------------------------------------------------------------------------
    Requirement:  FR-015. The corpus is what was actually loaded from the
                  committed snapshots.
    Rule:         restrict to records belonging to a snapshot row in
                  recall_snapshots. Nothing else is filtered here.
    Why safe:     this excludes only orphans -- records whose snapshot is gone.
                  It does NOT filter by recall status: terminated and amended
                  recalls are returned like any other and are MARKED downstream,
                  because the case was in the kitchen either way (FR-016).
    Covered by:   tests/unit/test_freshness.py::test_terminated_recalls_are_returned
                  tests/unit/test_clearing_audit.py
    ==========================================================================
    """
    return list(conn.execute(
        """SELECT r.* FROM recall_records r
           JOIN recall_snapshots s ON s.id = r.snapshot_id
           ORDER BY r.class_rank, r.id"""
    ))


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def snapshot_age_hours(conn: sqlite3.Connection, now: datetime) -> Optional[float]:
    """Age of the oldest loaded snapshot, in hours, measured from ``captured_at``.

    ``now`` is injected. Never read from the clock -- FR-068 is only testable
    because of that.
    """
    row = conn.execute("SELECT MIN(captured_at) AS oldest FROM recall_snapshots").fetchone()
    if not row or not row["oldest"]:
        return None
    return (now - _parse_ts(row["oldest"])).total_seconds() / 3600.0


def is_stale(conn: sqlite3.Connection, now: datetime) -> bool:
    """True when the corpus is older than the 24-hour window.

    A stale corpus never changes which lines are produced -- it changes what the
    header says about them. Suppressing lines because the data is old would trade
    a visible caveat for an invisible gap.
    """
    age = snapshot_age_hours(conn, now)
    return age is not None and age > FRESHNESS_WINDOW.total_seconds() / 3600.0


def corpus_summary(conn: sqlite3.Connection, now: datetime) -> list[dict]:
    """One row per snapshot, for the header and /api/status."""
    out = []
    for row in conn.execute(
        "SELECT * FROM recall_snapshots ORDER BY source"
    ):
        age = (now - _parse_ts(row["captured_at"])).total_seconds() / 3600.0
        out.append({
            "source": row["source"],
            "provenance": row["provenance"],
            "captured_at": row["captured_at"],
            "record_count": row["record_count"],
            "age_hours": round(age, 1),
            "stale": age > FRESHNESS_WINDOW.total_seconds() / 3600.0,
            "fetch_status": row["fetch_status"],
        })
    return out


def corpus_note(conn: sqlite3.Connection) -> str:
    """One line naming every snapshot this run was matched against.

    Frozen onto the run at finalize, and printed on that run's page thereafter.
    Reading it live instead would put tonight's corpus and capture date above
    yesterday's lines -- a document that looks sourced and is not.
    """
    parts = [
        f"{row['source']} {row['captured_at']} ({row['record_count']} records, "
        f"{row['provenance']})"
        for row in conn.execute(
            """SELECT source, captured_at, record_count, provenance
                 FROM recall_snapshots
                WHERE id IN (SELECT MAX(id) FROM recall_snapshots GROUP BY source)
                ORDER BY source"""
        )
    ]
    return "; ".join(parts) if parts else "no recall snapshot loaded"
