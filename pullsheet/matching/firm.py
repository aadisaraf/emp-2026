"""Supplier identity: does this inventory line come from the firm being recalled?
distinctive shared product word alongside it (FR-071), and a manufacturer item
"""

from __future__ import annotations

import re

# Words that appear in company names and identify no company. Dropping them is
# what lets "High Liner Foods" and "High Liner Foods Inc." agree; keeping them
BOILERPLATE: frozenset[str] = frozenset({
    # legal form
    "inc", "incorporated", "llc", "lc", "ltd", "limited", "lp", "llp", "plc",
    "corp", "corporation", "co", "cos", "company", "companies", "dba", "division",
    "div", "holdings", "holding", "group", "enterprises", "industries", "partners",
    "gmbh", "sa", "bv", "nv", "pty", "sons", "son", "brothers", "bros",
    # what nearly every food company calls itself
    "foods", "food", "brands", "brand", "products", "product", "provisions",
    "packing", "packaged", "packers", "processing", "manufacturing", "mfg",
    "distributing", "distributors", "distribution", "supply", "wholesale",
    "wholesalers", "sales", "trading", "imports", "exports", "market", "markets",
    "grocers", "grocery", "kitchen", "kitchens", "bakery", "bakeries", "creamery",
    "creameries", "dairy", "meats", "produce", "farms", "farm", "ingredients",
    # adjectives a company chooses about itself
    "fine", "quality", "premium", "best", "natural", "naturals", "fresh", "pure",
    "gourmet", "specialty", "homemade", "classic", "original", "select",
    # geography and scale
    "usa", "us", "america", "american", "national", "international", "intl",
    "global", "worldwide", "north", "south", "east", "west", "central", "pacific",
    "atlantic", "midwest", "the", "of", "and",
})

_PUNCT = re.compile(r"[^a-z0-9]+")


def firm_tokens(name: str | None) -> frozenset[str]:
    """The identifying words of a company name."""
    if not name:
        return frozenset()
    words = [w for w in _PUNCT.sub(" ", name.lower()).split() if len(w) > 1 and not w.isdigit()]
    kept = frozenset(w for w in words if w not in BOILERPLATE)
    return kept or frozenset(words)


def agrees(inventory_name: str | None, recalling_firm: str | None) -> bool:
    """True when the inventory's brand or manufacturer names the recalling firm."""
    a, b = firm_tokens(inventory_name), firm_tokens(recalling_firm)
    if not a or not b:
        return False
    return a <= b
