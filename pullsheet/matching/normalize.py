"""The single normalization implementation."""

from __future__ import annotations

import re

# Units and measure words. Stripped from the token set: "2/5 lb" and "24/10 oz"
# say nothing about whether two products are the same product.
UNITS: frozenset[str] = frozenset({
    "oz", "ozs", "lb", "lbs", "pound", "pounds", "g", "kg", "ml", "l", "liter",
    "gal", "gallon", "qt", "quart", "pint", "pt", "ct", "count", "ea", "each",
    "cs", "case", "cases", "bg", "bag", "bags", "box", "boxes", "pk", "pack",
    "in", "inch", "inches", "dz", "dozen", "can", "cans", "pkg", "package",
    "net", "wt", "weight",
})

# Pack-size shapes: "6/5 lb", "24/10 oz", "12/32 oz", "2/5 lb", "80/20".
_PACK = re.compile(r"\b\d+\s*/\s*\d+(?:\.\d+)?\s*(?:lb|lbs|oz|g|kg|ct|ea)?\b", re.I)
# Catalog sizes: "#10", "#10 can", "10#".
_HASHSIZE = re.compile(r"(?:#\s*\d+|\b\d+\s*#)")
# Number glued to a unit: "10oz", "50lb", "125ct", "8in", "4oz".
_GLUED = re.compile(r"\b\d+(?:\.\d+)?\s*(?:oz|lb|lbs|g|kg|ml|ct|in|qt|pt|gal)\b", re.I)
# Percentages: "1%", "80%".
_PCT = re.compile(r"\b\d+(?:\.\d+)?\s*%")

_PUNCT = re.compile(r"[^a-z0-9]+")


def normalize(text: str | None) -> str:
    """Lowercase, strip pack sizes and units, sort the remaining words."""
    return " ".join(sorted(tokens(text)))


def tokens(text: str | None) -> frozenset[str]:
    """The significant words of a food description, exactly as they were spelled."""
    if not text:
        return frozenset()

    s = text.lower()
    for pattern in (_PACK, _HASHSIZE, _GLUED, _PCT):
        s = pattern.sub(" ", s)
    s = _PUNCT.sub(" ", s)

    out: set[str] = set()
    for word in s.split():
        if word.isdigit():
            continue              # a bare number identifies nothing
        if word in UNITS:
            continue
        if len(word) == 1:
            continue              # a stray initial survives nothing useful
        out.add(word)
    return frozenset(out)
