"""The single normalization implementation.

Everything that compares two food descriptions goes through here: the matcher,
the screening index, and the menu cascade. One implementation means a recalled
item reaches recipes by the same code path it reaches inventory, and a change in
normalization cannot make those two disagree.

Normalization is lossy on purpose -- pack sizes, units, and bare numbers are
noise for matching. It never touches ``raw_description``, which is stored
verbatim and is what the operator sees on the pull sheet.
"""

from __future__ import annotations

import re

from pullsheet.matching.abbreviations import ABBREVIATIONS

# Units and measure words. Stripped from the token set: "2/5 lb" and "24/10 oz"
# say nothing about whether two products are the same product.
UNITS: frozenset[str] = frozenset({
    "oz", "ozs", "lb", "lbs", "pound", "pounds", "g", "kg", "ml", "l", "liter",
    "gal", "gallon", "qt", "quart", "pint", "ct", "count", "ea", "each",
    "cs", "case", "cases", "bg", "bag", "bags", "box", "boxes", "pk", "pack",
    "in", "inch", "inches", "dz", "dozen", "can", "cans", "pkg", "package",
})

# Pack-size shapes: "6/5 lb", "24/10 oz", "12/32 oz", "2/5 lb", "80/20".
_PACK = re.compile(r"\b\d+\s*/\s*\d+(?:\.\d+)?\s*(?:lb|lbs|oz|g|kg|ct|ea)?\b", re.I)
# Catalog sizes: "#10", "#10 can".
_HASHSIZE = re.compile(r"#\s*\d+\b")
# Number glued to a unit: "10oz", "50lb", "125ct", "8in", "4oz".
_GLUED = re.compile(r"\b\d+(?:\.\d+)?\s*(?:oz|lb|lbs|g|kg|ml|ct|in|qt|pt|gal)\b", re.I)
# Percentages: "1%", "80%".
_PCT = re.compile(r"\b\d+(?:\.\d+)?\s*%")

_PUNCT = re.compile(r"[^a-z0-9]+")


def normalize(text: str | None) -> str:
    """Lowercase, expand abbreviations, strip pack sizes and units, sort tokens.

    Returns a stable string, so two descriptions that normalize the same way
    compare equal as strings as well as as sets.
    """
    return " ".join(sorted(tokens(text)))


def tokens(text: str | None) -> frozenset[str]:
    """The significant tokens of a food description.

    >>> sorted(tokens("chkn strips froz"))
    ['chicken', 'frozen', 'strips']
    """
    if not text:
        return frozenset()

    s = text.lower()
    for pattern in (_PACK, _HASHSIZE, _GLUED, _PCT):
        s = pattern.sub(" ", s)
    s = _PUNCT.sub(" ", s)

    out: set[str] = set()
    for word in s.split():
        for piece in ABBREVIATIONS.get(word, word).split():
            if piece.isdigit():
                continue          # a bare number identifies nothing
            if piece in UNITS:
                continue
            if len(piece) == 1 and piece.isalpha():
                continue          # stray initials survive nothing useful
            out.add(piece)
    return frozenset(out)
