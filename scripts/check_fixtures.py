#!/usr/bin/env python3
"""Fixture sanity checks. Run before trusting a demo.

`--menu` proves two things about the hand-authored menu fixtures:

  1. At least one recipe is reachable from `expected_matches.json` -- i.e. the
     menu cascade has something real to cascade from.
  2. At least one broken recipe has an *unsatisfiable* component set at its own
     site, so FR-041's "no substitute exists" is demonstrable rather than
     theoretical. Substitution is site-scoped on purpose: you cannot serve from
     another building's cooler.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "data" / "fixtures"


def _rows(name):
    with (FIX / name).open() as f:
        return list(csv.DictReader(f))


def check_menu() -> int:
    inventory = _rows("inventory_lincoln.csv")
    recipes = {r["recipe_id"]: r["name"] for r in _rows("recipes.csv")}
    ingredients = defaultdict(set)
    for r in _rows("recipe_ingredients.csv"):
        ingredients[r["recipe_id"]].add(r["ingredient_name"])
    components = defaultdict(set)
    for r in _rows("recipe_components.csv"):
        components[r["recipe_id"]].add(r["component"])

    seeds = json.loads((FIX / "expected_matches.json").read_text())["matches"]
    recalled = {(s["site"], s["item_description"]) for s in seeds}

    stock = defaultdict(set)
    for row in inventory:
        stock[row["Site"]].add(row["Item Description"])

    # 1. recipes reachable from a seeded recall
    reachable = []
    for rid, items in ingredients.items():
        hits = sorted({f"{site} / {item}" for (site, item) in recalled if item in items})
        if hits:
            reachable.append((rid, recipes[rid], hits))

    # 2. broken recipes with no site-local substitute
    unsatisfiable = []
    for site, on_hand in stock.items():
        clean_here = {
            rid for rid, items in ingredients.items()
            if items <= on_hand and not any((site, i) in recalled for i in items)
        }
        for rid, items in ingredients.items():
            if not (items <= on_hand):
                continue                      # not served at this site anyway
            if not any((site, i) in recalled for i in items):
                continue                      # not broken here
            covered = any(components[rid] <= components[c] for c in clean_here)
            if not covered:
                unsatisfiable.append((site, rid, recipes[rid], sorted(components[rid])))

    print(f"recipes reachable from expected_matches.json: {len(reachable)}")
    for rid, name, hits in sorted(reachable):
        print(f"  {rid} {name}  <- {', '.join(hits)}")
    print(f"\nbroken recipes with NO viable site-local substitute: {len(unsatisfiable)}")
    for site, rid, name, comps in sorted(unsatisfiable):
        print(f"  {site}: {rid} {name}  requires {{{', '.join(comps)}}}")

    ok = len(reachable) >= 1 and len(unsatisfiable) >= 1
    print("\nOK" if ok else "\nFAIL: need >=1 reachable recipe and >=1 unsatisfiable recipe")
    return 0 if ok else 1


def check_seeds() -> int:
    """Every seeded recall id must resolve against the committed corpus.

    The corpus spans two agencies, so the check is against the union of both
    snapshots. A seed pointing at a recall that is not in the corpus would make
    SC-005 unfalsifiable.
    """
    ids = set()
    for name in ("openfda-2026-09-05.json", "fsis-2026-09-05.json"):
        snap = ROOT / "pullsheet" / "recalls" / "snapshots" / name
        ids |= {r["recall_number"] for r in json.loads(snap.read_text())["results"]}

    seeds = json.loads((FIX / "expected_matches.json").read_text())["matches"]
    missing = [s["recall_source_record_id"] for s in seeds if s["recall_source_record_id"] not in ids]

    kinds = sorted({s["expected_evidence_kind"] for s in seeds})
    print(not missing, len(seeds))
    print(f"  evidence kinds covered: {', '.join(kinds)}")
    if missing:
        print(f"  MISSING from the corpus: {missing}")
    ok = not missing and len(seeds) >= 12 and len(kinds) == 5
    print("OK" if ok else "FAIL: need >=12 seeds, all 5 evidence kinds, none missing")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--menu", action="store_true", help="check the menu fixtures")
    ap.add_argument("--seeds", action="store_true", help="check the seeded correspondence map")
    args = ap.parse_args()
    if args.menu:
        return check_menu()
    if args.seeds:
        return check_seeds()
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
