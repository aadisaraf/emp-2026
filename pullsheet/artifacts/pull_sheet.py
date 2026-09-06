"""The pull sheet: what an operator carries into the kitchen.

One run, one sheet, grouped by storage location and ordered class-first within
each. Grouping by where the food physically is means the sheet is a walking
route -- freezer, cooler, dry store -- rather than a list to cross-reference.

PULL and HELD are INTERLEAVED in that one order -- HELD is never a separate
section and never behind a toggle. A held line an operator has to go looking for
is a held line they will not see, and the whole point of holding rather than
clearing is that a person looks at it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from pullsheet import location
from pullsheet.matching.run import ordered_matches
from pullsheet.recalls.corpus import corpus_summary


def lines(conn: sqlite3.Connection, run_id: int,
          decided_before: str | None = None) -> list[sqlite3.Row]:
    return ordered_matches(conn, run_id, decided_before)


def by_storage(conn: sqlite3.Connection, run_id: int,
               decided_before: str | None = None) -> list[dict[str, Any]]:
    """Sheet sections, one per storage location, each already in the single
    deterministic order the whole application uses.

    Sections are ordered by their most serious line, so the cooler with the
    recalled chicken in it comes before the dry store with a maybe.
    """
    sections: dict[str, dict[str, Any]] = {}
    for row in lines(conn, run_id, decided_before):
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
    """This run's totals, from this run's rows.

    A run's frozen columns say the same thing; this recomputes them for the
    live page so a clearing taken since finalize is reflected without rewriting
    a finalized run's record.
    """
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


def rejections(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """Recent rejected deliveries, so a bad export is visible rather than silent."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM runs WHERE status = 'rejected' ORDER BY id DESC LIMIT ?",
        (limit,))]


def header(conn: sqlite3.Connection, run: sqlite3.Row, now: datetime) -> dict[str, Any]:
    """Everything the sheet header must state, per FR-035 and Principle V.

    A finalized run carries its own corpus note, and that is what a past run's
    page prints. Reading the corpus live would put tonight's snapshot date above
    yesterday's lines -- a document that looks sourced and is not.
    """
    is_current = run["id"] == (latest := conn.execute(
        "SELECT MAX(id) AS id FROM runs WHERE status = 'ok'").fetchone())["id"]
    corpora = corpus_summary(conn, now) if is_current else []
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
        "coverage": parser_coverage(conn),
    }
