"""FR-041. "No substitute exists" is a proof, not a failure to find one.

The difference matters. A system that searched, found nothing, and shrugged
would look identical to one that searched badly. So this module never reports an
absence: when it cannot propose a substitute it names the meal-pattern component
that no clean recipe in this kitchen can supply, and that named component IS the
proof.

The mechanism is set containment over ``recipe_components``, which holds the
five USDA meal-pattern components per recipe. A candidate substitutes for a
broken recipe only when

    components(broken) subset-of components(candidate)

-- the candidate must cover everything the broken recipe covered. Never an
approximation, never a closest match. A meal that is one component short is a
meal that fails a state review, and proposing it would be worse than proposing
nothing.

Candidates are what THIS kitchen can cook from what is on its own shelves right
now. A proposal that assumes stock from somewhere else is a proposal that fails
at 6:30 a.m.

Like the rest of the menu surface this is child-nutrition specific: the five
components are the USDA meal pattern.
"""

from __future__ import annotations

import sqlite3
from typing import Any

#: Rendered next to every proposal. The components are a hand-authored reading
#: of the USDA meal pattern, not a certification.
COMPONENTS_CAVEAT = ("meal-pattern components are hand-authored; a proposal is a "
                     "starting point for the director, not an approval")


def _components(conn: sqlite3.Connection) -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {}
    for row in conn.execute("SELECT recipe_id, component FROM recipe_components"):
        out.setdefault(row["recipe_id"], set()).add(row["component"])
    return {k: frozenset(v) for k, v in out.items()}


def _ingredients(conn: sqlite3.Connection) -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {}
    for row in conn.execute("SELECT recipe_id, normalized_name FROM recipe_ingredients"):
        out.setdefault(row["recipe_id"], set()).add(row["normalized_name"])
    return {k: frozenset(v) for k, v in out.items()}


def _on_hand(conn: sqlite3.Connection) -> frozenset[str]:
    """What is on the shelves now -- the active set, not one run's delivery.

    Substitution is a forward-planning tool: it answers "what can we cook
    tomorrow", which is a question about the food that is here, including items
    carried over from an export that did not list them again. Yesterday's menu
    is not re-planned, so there is no as-of version of this.
    """
    return frozenset(r["normalized_description"] for r in conn.execute(
        """SELECT DISTINCT normalized_description FROM inventory_records
            WHERE superseded_by IS NULL"""))


def _pulled(conn: sqlite3.Connection, run_id: int) -> frozenset[str]:
    """Products carrying a PULL line in this run. A recipe using one of these
    is not a candidate, whatever its components say."""
    return frozenset(r["normalized_description"] for r in conn.execute(
        """SELECT DISTINCT i.normalized_description
             FROM matches m JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE m.run_id = ? AND m.status = 'PULL'""", (run_id,)))


def _held(conn: sqlite3.Connection, run_id: int) -> frozenset[str]:
    """Products held on evidence stronger than a name coincidence.

    A held ingredient does NOT disqualify a candidate -- held means undecided,
    and refusing to propose anything touched by an undecided line would leave a
    director with no menu at all. It is named on the proposal instead, so the
    caveat travels with the recommendation rather than being discovered in the
    kitchen.

    Name-only holds are excluded from the caveat. Almost every product in a
    kitchen shares a word with some recall somewhere, so listing those would
    put every ingredient of every proposal under caution -- a warning that fires
    on everything warns about nothing. This narrows a CAVEAT, never a line: the
    pull sheet still carries every one of those holds, unchanged and visible.
    Holds resting on a lot code, a catalog number, or a supplier agreement are
    named here.
    """
    return frozenset(r["normalized_description"] for r in conn.execute(
        """SELECT DISTINCT i.normalized_description
             FROM matches m JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE m.run_id = ? AND m.status = 'HELD'
              AND m.evidence_kind != 'name'""", (run_id,)))


def held_ingredients(conn: sqlite3.Connection, run_id: int, recipe_id: str) -> list[str]:
    """The raw ingredient names in this recipe that carry a held line."""
    held = _held(conn, run_id)
    return sorted(r["ingredient_name"] for r in conn.execute(
        "SELECT ingredient_name, normalized_name FROM recipe_ingredients WHERE recipe_id = ?",
        (recipe_id,)) if r["normalized_name"] in held)


def clean_candidates(conn: sqlite3.Connection, run_id: int) -> list[str]:
    """Recipes this kitchen can actually cook right now: every ingredient on
    hand, and no ingredient under a pull."""
    on_hand, pulled = _on_hand(conn), _pulled(conn, run_id)
    return sorted(rid for rid, items in _ingredients(conn).items()
                  if items <= on_hand and not (items & pulled))


def propose(conn: sqlite3.Connection, run_id: int, recipe_id: str) -> dict[str, Any]:
    """Propose a substitute for ``recipe_id``, or prove there is none.

    Returns ``kind='substitute'`` with the covering recipe, or ``kind='none'``
    with the named component that makes it impossible. There is no third
    outcome and no partial proposal.
    """
    components = _components(conn)
    required = components.get(recipe_id, frozenset())
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM recipes")}
    candidates = [c for c in clean_candidates(conn, run_id) if c != recipe_id]

    covering = [c for c in candidates if required <= components.get(c, frozenset())]
    if covering:
        # Smallest covering set first: the least over-serving substitute that
        # still meets the pattern. Ties broken by recipe id, so two runs agree.
        best = min(covering, key=lambda c: (len(components[c]), c))
        return {
            "kind": "substitute",
            "broken_recipe_id": recipe_id,
            "broken_recipe": names.get(recipe_id, recipe_id),
            "recipe_id": best,
            "name": names.get(best, best),
            "required": sorted(required),
            "covers": sorted(required),
            "extra": sorted(components[best] - required),
            "alternatives": [{"recipe_id": c, "name": names.get(c, c)}
                             for c in covering if c != best],
            # Named, not hidden. See _held().
            "held_ingredients": held_ingredients(conn, run_id, best),
            "caveat": COMPONENTS_CAVEAT,
        }

    # No candidate covers. Name WHY, per component, so the answer is a proof.
    supplied = set().union(*(components.get(c, frozenset()) for c in candidates)) \
        if candidates else set()
    unmet = sorted(required - supplied)
    if unmet:
        reason = ("no clean recipe in this kitchen supplies "
                  + ", ".join(unmet)
                  + f" -- {len(candidates)} candidate"
                  + ("" if len(candidates) == 1 else "s")
                  + " were checked")
    else:
        # Every component exists somewhere, but no single recipe carries all of
        # them. Name the closest candidate and exactly what it lacks.
        closest = min(candidates, key=lambda c: (len(required - components.get(c, frozenset())), c))
        unmet = sorted(required - components.get(closest, frozenset()))
        reason = (f"every required component is on hand, but no single clean recipe "
                  f"carries all of them; the closest, {names.get(closest, closest)}, "
                  f"is short of " + ", ".join(unmet))
    return {
        "kind": "none",
        "broken_recipe_id": recipe_id,
        "broken_recipe": names.get(recipe_id, recipe_id),
        "required": sorted(required),
        "unmet": unmet,
        "candidates_checked": len(candidates),
        "reason": reason,
        "caveat": COMPONENTS_CAVEAT,
    }


def proposals_for(conn: sqlite3.Connection, run_id: int,
                  entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One proposal per distinct broken recipe across a cascade result."""
    seen: set[str] = set()
    out = []
    for entry in entries:
        for recipe in entry["recipes"]:
            if recipe["recipe_id"] in seen:
                continue
            seen.add(recipe["recipe_id"])
            out.append(propose(conn, run_id, recipe["recipe_id"]))
    return sorted(out, key=lambda p: p["broken_recipe_id"])
