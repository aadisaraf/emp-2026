"""US5. Nobody has to remember to check.

The standing monitor diffs the corpus, evaluates only what it has not seen
before, and records a run every single time -- including the runs that find
nothing.

That last part is the whole point. **A quiet run is still a run** (FR-058).
"Nothing new was found at 06:00" and "nobody looked at 06:00" must not produce
the same picture, because only one of them is safe. So every pass writes a
``monitor_runs`` row, and a pass that matched nothing writes it with
``zero_hit`` set rather than writing nothing at all.

There is no alerts table. An alert IS a match carrying a ``first_seen_run_id``,
and it is acknowledged by a ``decisions`` row. One less table is one less place
for state to disagree with itself, and it means an alert cannot exist for a line
that does not.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from pullsheet.matching.run import run_matcher


def _high_water(conn: sqlite3.Connection) -> int:
    """The largest recall record id already evaluated.

    Taken from prior monitor runs when there are any. When there are none, the
    baseline is the corpus as it currently stands: whatever is loaded was
    already evaluated by the initial matcher pass, and re-evaluating it would
    duplicate every existing match and alert on a recall the district has been
    looking at all day.
    """
    row = conn.execute("SELECT MAX(max_record_id) AS m FROM monitor_runs").fetchone()
    if row and row["m"]:
        return row["m"]
    row = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM recall_records").fetchone()
    return row["m"] or 0


def unseen_record_ids(conn: sqlite3.Connection) -> set[int]:
    """Recall records loaded since the last run. Ids are monotonic in SQLite."""
    mark = _high_water(conn)
    return {r["id"] for r in conn.execute(
        "SELECT id FROM recall_records WHERE id > ?", (mark,))}


def run(conn: sqlite3.Connection, now: datetime | None = None) -> dict[str, Any]:
    """One monitor pass. Always writes a row; never removes one."""
    at = now or datetime.now(timezone.utc)
    mark = _high_water(conn)
    new_ids = unseen_record_ids(conn)
    ceiling = conn.execute(
        "SELECT COALESCE(MAX(id), 0) AS m FROM recall_records").fetchone()["m"] or 0
    snapshot = conn.execute(
        "SELECT MAX(id) AS m FROM recall_snapshots").fetchone()["m"]

    cur = conn.execute(
        """INSERT INTO monitor_runs
           (ran_at, snapshot_id, records_evaluated, new_records, new_matches,
            max_record_id, zero_hit)
           VALUES (?,?,?,?,0,?,1)""",
        (at.isoformat(timespec="seconds"), snapshot, len(new_ids), len(new_ids),
         max(mark, ceiling)))
    run_id = cur.lastrowid

    stats = {"matches": 0, "PULL": 0, "HELD": 0}
    if new_ids:
        stats = run_matcher(conn, now=at, first_seen_run_id=run_id,
                            only_recall_ids=new_ids)

    conn.execute(
        "UPDATE monitor_runs SET new_matches = ?, zero_hit = ? WHERE id = ?",
        (stats["matches"], 0 if stats["matches"] else 1, run_id))
    conn.commit()
    return {
        "run_id": run_id,
        "ran_at": at.isoformat(timespec="seconds"),
        "records_evaluated": len(new_ids),
        "new_records": len(new_ids),
        "new_matches": stats["matches"],
        "pull": stats.get("PULL", 0),
        "held": stats.get("HELD", 0),
        "zero_hit": stats["matches"] == 0,
    }


def open_alerts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Matches first seen by a monitor run and not yet acknowledged.

    Unacknowledged, not unresolved: acknowledging an alert says a person saw it,
    and says nothing about the line. The line stays on the pull sheet either
    way, which is why acknowledging is safe to make a one-click action.
    """
    return [dict(r) for r in conn.execute(
        """SELECT m.id, m.status, m.tier, m.evidence_kind, m.created_at,
                  m.first_seen_run_id, g.ran_at,
                  i.site, i.raw_description, i.quantity, i.unit, i.lot_code,
                  r.source, r.source_record_id, r.recalling_firm, r.classification
             FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
             JOIN recall_records   r ON r.id = m.recall_record_id
             LEFT JOIN monitor_runs g ON g.id = m.first_seen_run_id
            WHERE m.first_seen_run_id IS NOT NULL
              AND i.superseded_by IS NULL
              AND NOT EXISTS (SELECT 1 FROM decisions d
                               WHERE d.target_type = 'match'
                                 AND d.target_id = CAST(m.id AS TEXT)
                                 AND d.kind = 'acknowledge_alert')
            ORDER BY r.class_rank,
                     CASE m.status WHEN 'PULL' THEN 1 ELSE 2 END,
                     m.id""")]


def runs(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    """Recent runs, quiet ones included. The record of having looked."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM monitor_runs ORDER BY id DESC LIMIT ?", (limit,))]
