"""The run-level status word, and the two guarantees it carries.

Two things had to survive the removal of the site roster, and both live here.

**SC-013 -- a stale corpus gates a WORD, never a LINE.** When the recall corpus
is older than its freshness window, the status word says so. It does not
suppress a line, re-rank one, or change any status on the sheet. Trading a
visible caveat for an invisible gap is the failure the whole system is built
against, so the gate is deliberately confined to a string.

**FR-050 -- silence must not look like an answer.** The roster used to buy this:
a building that never reported read "unconfirmed" rather than simply not
appearing. Under one location the same question is about TIME rather than about
buildings -- "no export arrived today" and "an export arrived and matched
nothing" are completely different situations, and a dashboard that renders both
as a quiet green page is lying about one of them. ``run_status`` distinguishes
them by name.

Nothing here reads the clock; ``now`` is injected everywhere, so a stale corpus
and a missed delivery can both be demonstrated on demand.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from pullsheet import db
from pullsheet.recalls import corpus

#: How long after a daily export is due before its absence is called out. Wider
#: than 24 hours on purpose: a delivery that slips from 06:00 to 07:00 is late,
#: not missing, and a warning that fires on ordinary jitter gets ignored on the
#: morning it is real.
OVERDUE_AFTER = timedelta(hours=30)

#: The words. Each is a different situation, and no two of them mean the same
#: thing to the person reading the page.
NEVER_REPORTED = "no inventory has ever been received"
OVERDUE = "no inventory received recently"
REJECTED_LATEST = "the most recent delivery was rejected"
STALE_CORPUS = "recall data is stale"
CLEAR = "no recalled items found"
ACTION_REQUIRED = "items to pull"


def run_status(conn: sqlite3.Connection, now: datetime) -> dict[str, Any]:
    """One word for the whole deployment, and the reason behind it.

    Order matters and is not arbitrary. Absence outranks everything, because a
    system reporting "clear" on data it never received is worse than one
    reporting nothing at all. A stale corpus outranks "clear" for the same
    reason and cannot outrank "items to pull", which is a fact about food that
    is in the building regardless of how old the recall data is.
    """
    run = db.latest_ok_run(conn)
    if run is None:
        return {"word": NEVER_REPORTED, "state": "never", "run": None,
                "detail": "PullSheet has processed no inventory export for this "
                          "location. Nothing on this page is a statement about "
                          "the food in the building.",
                "stale_corpus": corpus.is_stale(conn, now)}

    age = (now - corpus._parse_ts(run["started_at"])).total_seconds() / 3600.0
    overdue = age > OVERDUE_AFTER.total_seconds() / 3600.0
    stale = corpus.is_stale(conn, now)
    counts = conn.execute(
        """SELECT SUM(status = 'PULL') AS pulls, COUNT(*) AS total
             FROM matches WHERE run_id = ?""", (run["id"],)).fetchone()
    pulls = counts["pulls"] or 0

    # Was the latest DELIVERY (of any outcome) a rejection? A rejected export
    # never replaces a good sheet, but the operator has to be told that what
    # they are looking at is not this morning's file.
    newest = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    rejected_since = newest is not None and newest["status"] == "rejected"

    if overdue:
        word, state = OVERDUE, "overdue"
        detail = (f"The last export was processed {round(age)} hours ago. This page "
                  f"shows that run. It is not a statement about what is in the "
                  f"building right now.")
    elif rejected_since:
        word, state = REJECTED_LATEST, "rejected"
        detail = ("The most recent delivery could not be read and was recorded as "
                  "rejected. The sheet below is the last export that was read "
                  "successfully, unchanged.")
    elif pulls:
        word, state = ACTION_REQUIRED, "action"
        detail = f"{pulls} line(s) are marked PULL on the most recent run."
    elif stale:
        # Deliberately NOT "clear". The lines are unchanged -- what is gated is
        # the confidence of the word, and only the word.
        word, state = STALE_CORPUS, "stale"
        detail = ("The most recent run found nothing to pull, but the recall corpus "
                  "is older than its freshness window. No line has been suppressed "
                  "or changed; only this summary is held back.")
    else:
        word, state = CLEAR, "clear"
        detail = ("The most recent run matched the full corpus against the full "
                  "inventory and produced no PULL line.")

    return {"word": word, "state": state, "run": dict(run), "detail": detail,
            "run_age_hours": round(age, 1), "stale_corpus": stale,
            "pull_count": pulls, "match_count": counts["total"] or 0,
            "rejected_since": rejected_since}


def history(conn: sqlite3.Connection, limit: int = 30) -> list[dict[str, Any]]:
    """Every run, newest first, rejections included.

    A rejected delivery is part of the history an operator needs to see. Listing
    only the good ones would make a week of failed drops look like a quiet week.
    """
    out = []
    for row in db.recent_runs(conn, limit):
        entry = dict(row)
        entry["new_count"] = conn.execute(
            "SELECT COALESCE(SUM(is_new), 0) FROM matches WHERE run_id = ?",
            (row["id"],)).fetchone()[0]
        out.append(entry)
    return out


def new_since_previous(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    """The lines this run found that the previous good run did not.

    This is what used to be a standing monitor with its own table and its own
    high-water mark. It is now a property of the run, computed once when the
    matcher wrote the rows -- one less place for state to disagree with itself.
    """
    return list(conn.execute("""
        SELECT m.id, m.status, m.tier, m.evidence_kind,
               i.raw_description, i.storage_location, i.lot_code,
               r.source, r.source_record_id, r.recalling_firm, r.classification,
               r.product_description
          FROM matches m
          JOIN inventory_records i ON i.id = m.inventory_record_id
          JOIN recall_records   r ON r.id = m.recall_record_id
         WHERE m.run_id = ? AND m.is_new = 1
         ORDER BY r.class_rank,
                  CASE m.status WHEN 'PULL' THEN 1 ELSE 2 END,
                  m.id""", (run_id,)))
