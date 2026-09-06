#!/usr/bin/env python3
"""Fixture sanity checks. Run before trusting a demo.
FR-041's "no substitute exists" is demonstrable rather than theoretical.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))   # run from anywhere, no install step
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
    recalled = {s["item_description"] for s in seeds}
    on_hand = {row["Item Description"] for row in inventory}

    # 1. recipes reachable from a seeded recall
    reachable = []
    for rid, items in ingredients.items():
        hits = sorted(recalled & items)
        if hits:
            reachable.append((rid, recipes[rid], hits))

    # 2. broken recipes with no substitute this kitchen can actually cook
    clean = {rid for rid, items in ingredients.items()
             if items <= on_hand and not (items & recalled)}
    unsatisfiable = []
    for rid, items in ingredients.items():
        if not (items <= on_hand):
            continue                          # not cookable here anyway
        if not (items & recalled):
            continue                          # not broken
        if not any(components[rid] <= components[c] for c in clean):
            unsatisfiable.append((rid, recipes[rid], sorted(components[rid])))

    print(f"recipes reachable from expected_matches.json: {len(reachable)}")
    for rid, name, hits in sorted(reachable):
        print(f"  {rid} {name}  <- {', '.join(hits)}")
    print(f"\nbroken recipes with NO viable substitute: {len(unsatisfiable)}")
    for rid, name, comps in sorted(unsatisfiable):
        print(f"  {rid} {name}  requires {{{', '.join(comps)}}}")

    ok = len(reachable) >= 1 and len(unsatisfiable) >= 1
    print("\nOK" if ok else "\nFAIL: need >=1 reachable recipe and >=1 unsatisfiable recipe")
    return 0 if ok else 1


def check_seeds() -> int:
    """Every seeded recall id must resolve against the committed corpus.
    SC-005 unfalsifiable.
    """
    ids = set()
    for name in ("openfda-2026-09-05.json", "fsis-2026-09-05.json"):
        snap = ROOT / "pullsheet" / "recalls" / "snapshots" / name
        ids |= {r["recall_number"] for r in json.loads(snap.read_text())["results"]}

    oracle = json.loads((FIX / "expected_matches.json").read_text())
    seeds, negatives = oracle["matches"], oracle["must_not_pull"]
    missing = [s["recall_source_record_id"] for s in seeds if s["recall_source_record_id"] not in ids]

    # Every rung of the ladder needs a fixture behind it. Reading the ladder
    # itself rather than a copied list means adding a rung and forgetting to
    from pullsheet.matching.gate import _LADDER
    kinds = {s["expected_evidence_kind"] for s in seeds}
    unseeded = sorted(set(_LADDER) - kinds)

    print(f"  {len(seeds)} seeds, {len(negatives)} must-not-pull rows")
    print(f"  evidence kinds covered: {', '.join(sorted(kinds))}")
    if missing:
        print(f"  MISSING from the corpus: {missing}")
    if unseeded:
        print(f"  LADDER RUNGS WITH NO FIXTURE: {unseeded}")
    ok = not missing and not unseeded and len(seeds) >= 12 and len(negatives) >= 2
    print("OK" if ok else
          "FAIL: need >=12 seeds, >=2 must-not-pull rows, every ladder rung seeded, none missing")
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
