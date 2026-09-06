"""The pull sheet: what an operator carries into the kitchen."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from pullsheet import location
from pullsheet.matching.run import ordered_matches
from pullsheet.recalls.corpus import corpus_summary


def by_storage(conn: sqlite3.Connection, run_id: int,
               decided_before: str | None = None) -> list[dict[str, Any]]:
    """Sheet sections, one per storage location, each already in the single
    deterministic order the whole application uses.
    """
    sections: dict[str, dict[str, Any]] = {}
    for row in ordered_matches(conn, run_id, decided_before):
        where = row["storage_location"] or "unspecified"
        section = sections.setdefault(where, {
            "storage_location": where, "lines": [], "pull": 0, "held": 0, "cleared": 0,
        })
        section["lines"].append(row)
        section["pull" if row["status"] == "PULL" else "held"] += 1
        if row["cleared_count"]:
            section["cleared"] += 1
    return sorted(sections.values(),
                  key=lambda s: (-s["pull"], s["storage_location"]))


def counts(conn: sqlite3.Connection, run_id: int) -> dict[str, int]:
    """This run's totals, from this run's rows."""
    row = conn.execute(
        """SELECT
             SUM(CASE WHEN status = 'PULL' THEN 1 ELSE 0 END) AS pull_count,
             SUM(CASE WHEN status = 'HELD' THEN 1 ELSE 0 END) AS held_count,
             SUM(is_new) AS new_count,
             COUNT(*) AS total
           FROM matches WHERE run_id = ?""", (run_id,)
    ).fetchone()
    return {"pull_count": row["pull_count"] or 0,
            "held_count": row["held_count"] or 0,
            "new_count": row["new_count"] or 0,
            "total": row["total"] or 0}


def rejections(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """Recent rejected deliveries, so a bad export is visible rather than silent."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM runs WHERE status = 'rejected' ORDER BY id DESC LIMIT ?",
        (limit,))]


def header(conn: sqlite3.Connection, run: sqlite3.Row, now: datetime) -> dict[str, Any]:
    """Everything the sheet header must state, per FR-035 and Principle V."""
    is_current = run["id"] == (latest := conn.execute(
        "SELECT MAX(id) AS id FROM runs WHERE status = 'ok'").fetchone())["id"]
    corpora = corpus_summary(conn, now) if is_current else []
    # How much of the recall corpus we could actually read.
    parsing = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN json_extract(parsed_codes,'$.unparsed') THEN 1 ELSE 0 END)
                    AS unparsed
             FROM recall_records"""
    ).fetchone()
    total = parsing["total"] or 0
    unparsed = parsing["unparsed"] or 0
    return {
        "location": location.summary(),
        "run": dict(run),
        "is_current": is_current,
        "generated_at": now.isoformat(timespec="seconds"),
        "corpora": corpora,
        # A past run states the corpus it was matched against, verbatim.
        "corpus_note": run["corpus_note"],
        "stale": any(c["stale"] for c in corpora),
        "counts": counts(conn, run["id"]),
        "coverage": {
            "total": total, "unparsed": unparsed, "parsed": total - unparsed,
            "percent": round(100.0 * (total - unparsed) / total, 1) if total else 0.0},
    }
