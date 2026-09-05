"""The single normalization implementation.

Everything that compares two food descriptions goes through here: the matcher,
the screening index, and the menu cascade. One implementation means a recalled
item reaches recipes by the same code path it reaches inventory, and a change in
normalization cannot make those two disagree.

**Words are compared as written.** There is no spelling correction, no fuzzy
character distance, and no abbreviation dictionary. Neither side of the
comparison is freehand text: a district's item master carries the string its
distributor's catalog supplied, and agency notices quote the manufacturer's own
catalog string back. They are the same dialect, written by the same industry:

    inventory  BRD COD PORTIONS CRUNCHY ROW 3 OZ
    recall     HFS 10/6lb Crunchy Row Breaded Cod Rectangles 3 oz.

Both are database fields. Building machinery to recover ``chicken`` from
``chkn`` would be solving a problem neither side has, and every entry in such a
dictionary is a place where a wrong guess silently changes what matches.

What normalization does do is discard the parts that are noise for *identity*:
case, punctuation, pack sizes, units, and bare numbers. ``raw_description`` is
untouched and is what the operator sees on the pull sheet.
"""

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
    """Lowercase, strip pack sizes and units, sort the remaining words.

    Returns a stable string, so two descriptions that normalize the same way
    compare equal as strings as well as as sets.
    """
    return " ".join(sorted(tokens(text)))


def tokens(text: str | None) -> frozenset[str]:
    """The significant words of a food description, exactly as they were spelled.

    >>> sorted(tokens("HFS 10/6lb Crunchy Row Breaded Cod Rectangles 3 oz."))
    ['breaded', 'cod', 'crunchy', 'hfs', 'rectangles', 'row']
    """
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
