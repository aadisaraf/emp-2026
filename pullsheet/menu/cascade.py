"""US2. What was this case going to become?

A recalled item is not just a case in a freezer. It is a meal that was going to
be served on a specific day, to a specific number of children. This module walks
that chain:

    inventory line -> recipes using it -> service days -> planned meals

Four deliberate choices:

1. **The join is exact-normalized-name equality.** A recipe's ingredient row and
   an inventory row are the kitchen's own catalog strings for the same product,
   normalized by the SAME function the matcher uses. There is no fuzzy matching
   here on purpose: a near-miss on a menu is a wrong count on a screen, and a
   wrong count is worse than a missing one.

2. **Only PULL lines cascade.** A HELD line is undecided by definition, and
   cascading undecided lines would bury the decided ones. The count of held
   lines is reported alongside so the omission is stated, never silent.

3. **The count is planned, never measured.** ``service_days.planned_meals`` is
   what the kitchen planned to serve. Nothing here knows what was eaten, and
   every surface that shows the number says so.

4. **The total counts each service day once.** One inventory line can carry
   several recall matches, and two lots of the same product can sit in two
   coolers -- but Tuesday's taco bar is one Tuesday taco bar. Totals are summed
   over the distinct (recipe, date) set, not per match. Getting this wrong
   inflates the number an operator would repeat to a superintendent.

This is a child-nutrition surface. A restaurant deployment runs the same recall
pipeline and has no meal pattern; ``location.serves_meal_program()`` is what
decides whether this is shown.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from pullsheet.db import SUBJECT_KEY_SQL

#: Every count this module produces is planned, not served. Rendered verbatim
#: wherever the number appears, so the caveat cannot be styled off the page.
PLANNED_CAVEAT = "planned, not served"


def _broken_lines(conn: sqlite3.Connection, run_id: int,
                  statuses: tuple[str, ...]) -> list[sqlite3.Row]:
    """This run's inventory lines carrying a match in one of ``statuses``.

    Cleared lines are still returned. Clearing is a human decision recorded
    against a match; it is not this module's business to act on it, and a menu
    that quietly un-breaks itself is exactly the disappearance Principle I
    forbids. The cleared count travels with the row so the page can say so.
    """
    placeholders = ",".join("?" * len(statuses))
    return list(conn.execute(
        f"""SELECT i.id, i.raw_description, i.normalized_description,
                   i.quantity, i.unit, i.storage_location, i.lot_code,
                   i.brand, i.manufacturer,
                   m.id AS match_id, m.status, m.tier, m.evidence_kind,
                   r.source, r.source_record_id, r.recalling_firm, r.classification,
                   r.class_rank, r.status AS recall_status,
                   (SELECT COUNT(*) FROM decisions d
                     WHERE d.subject_key = {SUBJECT_KEY_SQL}
                       AND d.kind = 'clear_match') AS cleared_count
              FROM matches m
              JOIN inventory_records i ON i.id = m.inventory_record_id
              JOIN recall_records   r ON r.id = m.recall_record_id
             WHERE m.run_id = ?
               AND m.status IN ({placeholders})
             ORDER BY r.class_rank, i.storage_location, i.raw_description, m.id""",
        (run_id, *statuses)))


def _recipes_using(conn: sqlite3.Connection, normalized: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        """SELECT DISTINCT rc.id AS recipe_id, rc.name, rc.provenance
             FROM recipe_ingredients ri
             JOIN recipes rc ON rc.id = ri.recipe_id
            WHERE ri.normalized_name = ?
            ORDER BY rc.id""", (normalized,)))


def _service_days(conn: sqlite3.Connection, recipe_id: str) -> list[sqlite3.Row]:
    """Service days on which this recipe is planned.

    The whole calendar belongs to this location, so there is nothing to scope
    it to beyond the recipe itself.
    """
    return list(conn.execute(
        """SELECT date, planned_meals FROM service_days
            WHERE recipe_id = ? ORDER BY date""", (recipe_id,)))


def cascade(conn: sqlite3.Connection, run_id: int,
            statuses: tuple[str, ...] = ("PULL",)) -> list[dict[str, Any]]:
    """One entry per broken inventory LINE that reaches at least one recipe.

    Several recall records can hit one line; they are listed on that one entry
    rather than producing several. A line that reaches no recipe is omitted --
    it has no menu consequence, and the pull sheet already carries it. Nothing
    is omitted for being *unclear*; only for having no menu to break.
    """
    entries: dict[int, dict[str, Any]] = {}
    for row in _broken_lines(conn, run_id, statuses):
        entry = entries.get(row["id"])
        if entry is None:
            recipes = []
            for recipe in _recipes_using(conn, row["normalized_description"]):
                days = [dict(d) for d in _service_days(conn, recipe["recipe_id"])]
                recipes.append({
                    "recipe_id": recipe["recipe_id"],
                    "name": recipe["name"],
                    "provenance": recipe["provenance"],
                    "service_days": days,
                    "planned_meals": sum(d["planned_meals"] for d in days),
                })
            if not recipes:
                continue
            entry = entries[row["id"]] = {
                "line": {k: row[k] for k in (
                    "id", "storage_location", "raw_description",
                    "normalized_description", "quantity", "unit", "lot_code",
                    "brand", "manufacturer")},
                "recalls": [],
                "recipes": recipes,
                "planned_meals": sum(r["planned_meals"] for r in recipes),
                "caveat": PLANNED_CAVEAT,
            }
        entry["recalls"].append({k: row[k] for k in (
            "match_id", "status", "tier", "evidence_kind", "source",
            "source_record_id", "recalling_firm", "classification",
            "recall_status", "cleared_count")})
    return list(entries.values())


def held_not_cascaded(conn: sqlite3.Connection, run_id: int) -> int:
    """How many held lines were left out, so the omission is stated rather than
    inferred from an absence."""
    row = conn.execute(
        """SELECT COUNT(DISTINCT inventory_record_id) AS n
             FROM matches WHERE run_id = ? AND status = 'HELD'""", (run_id,)
    ).fetchone()
    return row["n"] or 0


def affected_service_days(entries: list[dict[str, Any]]) -> list[tuple[str, str, int]]:
    """The distinct (date, recipe_id, planned_meals) set behind the total.

    Exposed rather than kept private so a hostile question about the headline
    number has an answer that is a list, not an assurance.
    """
    seen: dict[tuple[str, str], int] = {}
    for entry in entries:
        for recipe in entry["recipes"]:
            for day in recipe["service_days"]:
                seen[(day["date"], recipe["recipe_id"])] = day["planned_meals"]
    return sorted((d, r, n) for (d, r), n in seen.items())


def summary(conn: sqlite3.Connection, run_id: int,
            statuses: tuple[str, ...] = ("PULL",)) -> dict[str, Any]:
    entries = cascade(conn, run_id, statuses)
    days = affected_service_days(entries)
    return {
        "entries": entries,
        "broken_items": len(entries),
        "recipes": len({d[1] for d in days}),
        "dates": sorted({d[0] for d in days}),
        "service_days": days,
        # Each service day counted once. See the module docstring, choice 4.
        "planned_meals": sum(d[2] for d in days),
        "caveat": PLANNED_CAVEAT,
        "held_not_cascaded": held_not_cascaded(conn, run_id),
    }
