"""Supplier identity: does this inventory line come from the firm being recalled?

The most reliably present join key in the whole system. ``recalling_firm`` is
populated on 100% of the openFDA corpus, and a district item master always knows
who supplies a line -- it has to, in order to reorder it. Barcodes and lot codes
are both absent from most district rows; the supplier never is.

Matching is containment over token sets, not string equality, because the two
sides write the same company differently and both are right:

    inventory manufacturer   High Liner Foods
    recall recalling_firm    High Liner Foods Inc.

    inventory brand          Simplot
    recall recalling_firm    JR Simplot Company

Corporate boilerplate is dropped first. ``Inc``, ``LLC``, ``Company``, ``Foods``
and their relatives appear in a third of the corpus and identify nobody, so
leaving them in would let any two firms agree on ``foods``.

**Firm agreement is never on its own enough to pull.** It says the maker is
being recalled, not that this product is. ``gate.decide()`` requires a
distinctive shared product word alongside it (FR-071), and a manufacturer item
code alongside it for CONFIRMED (FR-070).
"""

from __future__ import annotations

import re

#: Words that appear in company names and identify no company. Dropping them is
#: what lets "High Liner Foods" and "High Liner Foods Inc." agree; keeping them
#: would let "Reser's Fine Foods" and "Garden-Fresh Foods" agree too.
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
    """The identifying words of a company name.

    >>> sorted(firm_tokens("High Liner Foods Inc."))
    ['high', 'liner']
    >>> sorted(firm_tokens("JR Simplot Company"))
    ['jr', 'simplot']
    >>> sorted(firm_tokens("Reser's Fine Foods, Inc."))
    ['reser']

    When stripping boilerplate would leave nothing -- a company genuinely named
    "Whole Foods Market" -- the unstripped words are returned instead. Returning
    an empty set would make the firm match *everything*, and widening by accident
    is still widening in the wrong place.
    """
    if not name:
        return frozenset()
    words = [w for w in _PUNCT.sub(" ", name.lower()).split() if len(w) > 1 and not w.isdigit()]
    kept = frozenset(w for w in words if w not in BOILERPLATE)
    return kept or frozenset(words)


def agrees(inventory_name: str | None, recalling_firm: str | None) -> bool:
    """True when the inventory's brand or manufacturer names the recalling firm.

    Containment in ONE direction: every identifying word the district wrote must
    appear in the agency's firm name. The direction is not arbitrary. Districts
    record the short trade name (``Simplot``); agencies record the legal entity
    (``JR Simplot Company``), which is the longer of the two in essentially every
    record in the corpus.

    >>> agrees("High Liner Foods", "High Liner Foods Inc.")
    True
    >>> agrees("Simplot", "JR Simplot Company")
    True
    >>> agrees("Simplot", "McCain Foods USA")
    False

    Allowing the reverse direction as well looks harmless and is not. It lets a
    short generic company name swallow a longer specific one:

    >>> agrees("Sun World", "World Food LLC.")
    False

    -- which under the old two-way rule pulled a district's table grapes for a
    recall by an unrelated company that happened to share the word "world".
    """
    a, b = firm_tokens(inventory_name), firm_tokens(recalling_firm)
    if not a or not b:
        return False
    return a <= b
