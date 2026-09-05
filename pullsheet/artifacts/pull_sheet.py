"""The pull sheet: what an operator carries into the kitchen.

Grouped by site, ordered class-first. PULL and HELD are INTERLEAVED in that one
order -- HELD is never a separate section and never behind a toggle. A held line
an operator has to go looking for is a held line they will not see, and the
whole point of holding rather than clearing is that a person looks at it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from pullsheet.matching.run import ordered_matches
from pullsheet.recalls.corpus import corpus_summary


def lines(conn: sqlite3.Connection, site: str | None = None) -> list[sqlite3.Row]:
    return ordered_matches(conn, site)


def by_site(conn: sqlite3.Connection, site: str | None = None) -> list[dict[str, Any]]:
    """Sheet sections, one per site, each already in the single deterministic
    order the whole application uses."""
    sections: dict[str, dict[str, Any]] = {}
    for row in lines(conn, site):
        section = sections.setdefault(row["site"], {
            "site": row["site"], "lines": [], "pull": 0, "held": 0, "cleared": 0,
        })
        section["lines"].append(row)
        section["pull" if row["status"] == "PULL" else "held"] += 1
        if row["cleared_count"]:
            section["cleared"] += 1
    # Sites are ordered by their most serious line, so the worst news is first.
    return sorted(sections.values(), key=lambda s: (-s["pull"], s["site"]))


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """SELECT
             SUM(CASE WHEN m.status = 'PULL' THEN 1 ELSE 0 END) AS pull_count,
             SUM(CASE WHEN m.status = 'HELD' THEN 1 ELSE 0 END) AS held_count,
             COUNT(*) AS total
           FROM matches m
           JOIN inventory_records i ON i.id = m.inventory_record_id
          WHERE i.superseded_by IS NULL"""
    ).fetchone()
    return {"pull_count": row["pull_count"] or 0,
            "held_count": row["held_count"] or 0,
            "total": row["total"] or 0}


def sites(conn: sqlite3.Connection) -> list[str]:
    return [r["site"] for r in conn.execute(
        "SELECT DISTINCT site FROM inventory_records WHERE superseded_by IS NULL ORDER BY site")]


def parser_coverage(conn: sqlite3.Connection) -> dict[str, int]:
    """How much of the recall corpus we could actually read.

    Shown on the sheet (T045) rather than rounded up. "We parse 45% of code_info
    fields and here is the number" is a defensible answer; silence is not.
    """
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN json_extract(parsed_codes,'$.unparsed') THEN 1 ELSE 0 END)
                    AS unparsed
             FROM recall_records"""
    ).fetchone()
    total = row["total"] or 0
    unparsed = row["unparsed"] or 0
    return {"total": total, "unparsed": unparsed, "parsed": total - unparsed,
            "percent": round(100.0 * (total - unparsed) / total, 1) if total else 0.0}


def last_ingest(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def rejections(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """Recent rejected runs, so a bad export is visible rather than silent."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM ingest_runs WHERE status = 'rejected' ORDER BY id DESC LIMIT ?",
        (limit,))]


def header(conn: sqlite3.Connection, now: datetime, site: str | None = None) -> dict[str, Any]:
    """Everything the sheet header must state, per FR-035 and Principle V."""
    corpora = corpus_summary(conn, now)
    return {
        "district": "Lincoln Unified School District",
        "site": site,
        "generated_at": now.isoformat(timespec="seconds"),
        "corpora": corpora,
        "stale": any(c["stale"] for c in corpora),
        "counts": counts(conn),
        "coverage": parser_coverage(conn),
        "last_ingest": last_ingest(conn),
    }
