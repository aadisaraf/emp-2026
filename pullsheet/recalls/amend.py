"""FR-016. A recall that is later terminated or amended."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from pullsheet.matching.normalize import normalize
from pullsheet.recalls.corpus import class_rank
from pullsheet.recalls.parse import parse_record


def _find(conn: sqlite3.Connection, source: str, source_record_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM recall_records
            WHERE source = ? AND source_record_id = ? AND status != 'amended'
            ORDER BY id DESC LIMIT 1""", (source, source_record_id)).fetchone()


def terminate(conn: sqlite3.Connection, source: str, source_record_id: str,
              now: datetime) -> dict[str, Any]:
    """The agency closed this notice. Record it; remove nothing."""
    row = _find(conn, source, source_record_id)
    if row is None:
        raise LookupError(f"no active record {source}/{source_record_id}")

    conn.execute(
        """UPDATE recall_records
              SET status = 'terminated', prior_status = ?, status_changed_at = ?
            WHERE id = ?""",
        (row["status"], now.isoformat(timespec="seconds"), row["id"]))
    conn.commit()

    affected = conn.execute(
        "SELECT COUNT(*) c FROM matches WHERE recall_record_id = ?", (row["id"],)
    ).fetchone()["c"]
    return {"record_id": row["id"], "prior_status": row["status"],
            "status": "terminated", "lines_marked": affected, "lines_removed": 0}


def amend(conn: sqlite3.Connection, source: str, source_record_id: str,
          revised: dict[str, Any], now: datetime) -> dict[str, Any]:
    """The agency reissued this notice. Both versions survive."""
    row = _find(conn, source, source_record_id)
    if row is None:
        raise LookupError(f"no active record {source}/{source_record_id}")

    description = revised.get("product_description") or row["product_description"]
    code_info = revised.get("code_info", row["code_info"])
    parsed = parse_record(description, code_info, revised.get("more_code_info"))
    classification = revised.get("classification", row["classification"])

    cur = conn.execute(
        """INSERT INTO recall_records
           (source, source_record_id, snapshot_id, recalling_firm, product_description,
            normalized_description, code_info, parsed_codes, classification, class_rank,
            report_date, received_at, reason_for_recall, status, prior_status,
            status_changed_at, amended_from, raw_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?,?,?)""",
        (source, revised.get("recall_number") or source_record_id, row["snapshot_id"],
         revised.get("recalling_firm", row["recalling_firm"]), description,
         normalize(description), code_info, json.dumps(parsed), classification,
         class_rank(classification), revised.get("report_date", row["report_date"]),
         now.isoformat(timespec="seconds"),
         revised.get("reason_for_recall", row["reason_for_recall"]),
         row["status"], now.isoformat(timespec="seconds"), row["id"],
         json.dumps(revised)))
    new_id = cur.lastrowid

    conn.execute(
        """UPDATE recall_records
              SET status = 'amended', prior_status = ?, status_changed_at = ?
            WHERE id = ?""",
        (row["status"], now.isoformat(timespec="seconds"), row["id"]))
    conn.commit()

    return {"record_id": row["id"], "superseded_by": new_id,
            "prior_status": row["status"], "status": "amended", "lines_removed": 0}


def history(conn: sqlite3.Connection, record_id: int) -> list[dict[str, Any]]:
    """The full chain for one recall, oldest first. Nothing in it is hidden."""
    chain: list[dict[str, Any]] = []
    row = conn.execute("SELECT * FROM recall_records WHERE id = ?", (record_id,)).fetchone()
    while row is not None:
        chain.insert(0, dict(row))
        row = (conn.execute("SELECT * FROM recall_records WHERE id = ?",
                            (row["amended_from"],)).fetchone()
               if row["amended_from"] else None)
    return chain
