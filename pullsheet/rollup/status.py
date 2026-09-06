"""FR-049, FR-050, FR-068. One word per site, derived on read.

The word is derived, never stored. A stored status is a status that can disagree
with the rows beneath it, and the disagreement is always discovered at the worst
moment. Three words, and a site has exactly one:

    holding       lines are on the sheet for this site
    clear         an export was processed, produced zero lines, and the recall
                  snapshot behind that answer is inside the freshness window
    unconfirmed   anything else -- and the REASON is always named

`unconfirmed` is the default, and that is the whole design. A building that
never sent an export must not be able to look the same as a building that sent
one and came back empty. Without the site roster this module would not know the
second building existed, so the roster is what makes silence visible.

Staleness gates one word, never a line. When the corpus is old, no site may
report `clear` (SC-013) -- but the matcher still produces exactly the same PULL
and HELD lines it would have produced otherwise. Suppressing lines because the
data is old would trade a visible caveat for an invisible gap.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from typing import Any, Literal

from pullsheet.provenance import path_for
from pullsheet.recalls import corpus

SiteStatus = Literal["clear", "holding", "unconfirmed"]

STATUS_WORDS: tuple[SiteStatus, ...] = ("clear", "holding", "unconfirmed")


def roster() -> list[str]:
    """Every building the district operates, hand-authored.

    Read from the fixture rather than from inventory_records on purpose: a site
    is only absent from inventory because it never reported, which is precisely
    the condition that must be visible.
    """
    with path_for("sites").open() as f:
        return [row["site"] for row in csv.DictReader(f)]


def _known_sites(conn: sqlite3.Connection) -> list[str]:
    """The roster, plus any site an export mentioned that the roster does not.

    An export naming a building nobody listed is a real thing that happens, and
    dropping it would hide inventory. Union, never intersection.
    """
    seen = {r["site"] for r in conn.execute("SELECT DISTINCT site FROM inventory_records")}
    return sorted(set(roster()) | seen)


def _line_counts(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        """SELECT i.site,
                  SUM(CASE WHEN m.status='PULL' THEN 1 ELSE 0 END) AS pull,
                  SUM(CASE WHEN m.status='HELD' THEN 1 ELSE 0 END) AS held
             FROM matches m JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE i.superseded_by IS NULL GROUP BY i.site"""
    ):
        out[row["site"]] = {"pull": row["pull"] or 0, "held": row["held"] or 0}
    return out


def _processed_sites(conn: sqlite3.Connection) -> set[str]:
    """Sites reached by an ingest run that succeeded.

    A REJECTED run does not count. That is the point of FR-009: a bad export
    must not be able to make a building look answered.
    """
    return {r["site"] for r in conn.execute(
        """SELECT DISTINCT i.site FROM inventory_records i
             JOIN ingest_runs g ON g.id = i.source_export_id
            WHERE g.status = 'ok'""")}


def _confirmations(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        """SELECT target_id, actor, created_at FROM decisions
            WHERE kind = 'confirm_site_pulled' AND target_type = 'site'
            ORDER BY id"""
    ):
        out[row["target_id"]] = {"actor": row["actor"], "at": row["created_at"]}
    return out


def site_statuses(conn: sqlite3.Connection, now: datetime) -> list[dict[str, Any]]:
    """One row per site, each with exactly one status word and a stated reason."""
    stale = corpus.is_stale(conn, now)
    age = corpus.snapshot_age_hours(conn, now)
    captured = conn.execute(
        "SELECT MIN(captured_at) AS oldest FROM recall_snapshots").fetchone()["oldest"]

    counts = _line_counts(conn)
    processed = _processed_sites(conn)
    # The fixture loader writes inventory without an ingest run; treat any site
    # carrying current rows as reported, so a fixture-seeded rehearsal is honest.
    seeded = {r["site"] for r in conn.execute(
        "SELECT DISTINCT site FROM inventory_records WHERE superseded_by IS NULL")}
    confirmed = _confirmations(conn)

    rows = []
    for site in _known_sites(conn):
        lines = counts.get(site, {"pull": 0, "held": 0})
        total = lines["pull"] + lines["held"]
        reported = site in processed or site in seeded

        if total:
            status, reason = "holding", (
                f"{lines['pull']} to pull, {lines['held']} held for review")
        elif not reported:
            status, reason = "unconfirmed", "no export has been processed for this site"
        elif stale:
            # SC-013. The lines are unchanged; only this word is gated.
            status, reason = "unconfirmed", (
                f"stale recall data -- snapshot captured {(captured or '?')[:10]}, "
                f"{age:.0f}h old, older than the 24-hour window")
        else:
            status, reason = "clear", "an export was processed and produced no lines"

        rows.append({
            "site": site,
            "status": status,
            "reason": reason,
            "pull": lines["pull"],
            "held": lines["held"],
            "reported": reported,
            "on_roster": site in roster(),
            "confirmed": confirmed.get(site),
            "snapshot_captured_at": captured,
            "snapshot_age_hours": round(age, 1) if age is not None else None,
            "stale": stale,
        })
    # Worst news first: holding, then unconfirmed, then clear.
    order = {"holding": 0, "unconfirmed": 1, "clear": 2}
    return sorted(rows, key=lambda r: (order[r["status"]], -r["pull"], r["site"]))


def summary(conn: sqlite3.Connection, now: datetime) -> dict[str, Any]:
    rows = site_statuses(conn, now)
    return {
        "sites": rows,
        "counts": {word: sum(1 for r in rows if r["status"] == word) for word in STATUS_WORDS},
        "stale": corpus.is_stale(conn, now),
        "confirmed": sum(1 for r in rows if r["confirmed"]),
    }
