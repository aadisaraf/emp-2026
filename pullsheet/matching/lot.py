"""Lot code normalization and comparison (R3).

The single hardest string problem in this system, and the one with the most
direct consequence: a kitchen writes ``4829-B``, the agency writes
``LOT 4829B``, and those are the same case of chicken.

Adapters pass lot codes through VERBATIM. All reconciliation happens here, so
the un-normalized string still exists to compare against and to show the
operator on the pull sheet.

Four outcomes, and only ``equal`` supports a PULL on lot evidence alone:

    equal        the same lot, written differently
    contained    one is a prefix or substring of the other -- related, not equal
    none         different lots
    unparseable  a date range, a "best by" window, or nothing we can compare
"""

from __future__ import annotations

import re
from typing import Literal, Optional

LotComparison = Literal["equal", "contained", "none", "unparseable"]

# Words agencies and operators put in front of the actual code.
_NOISE = re.compile(
    r"\b(LOT|LOTS|LOTE|BATCH|CODE|CODES|NO|NUMBER|NUM|PACK|PACKED|DAYCODE|"
    r"PRODUCTION|PROD|ITEM|SKU)\b\.?",
    re.I,
)
_NON_ALNUM = re.compile(r"[^A-Z0-9]")

# Shapes that are windows rather than identifiers: "03/12-04/02", "BEST BY ...",
# "SELL BY ...", "USE BY ...", "EXP ...". These cannot be compared as lots, and
# FR-067 requires that failure to parse WIDENS -- so they return `unparseable`
# and the gate holds the line rather than dropping it.
_WINDOW_WORDS = re.compile(r"\b(BEST\s*BY|SELL\s*BY|SELL\s*THRU|USE\s*BY|EXP|EXPIR\w*|THROUGH|THRU)\b", re.I)
_DATE_RANGE = re.compile(r"\d{1,2}\s*/\s*\d{1,2}(?:\s*/\s*\d{2,4})?\s*[-–—]\s*\d{1,2}\s*/\s*\d{1,2}")


def looks_like_a_window(raw: str | None) -> bool:
    """True when this string is a date window rather than a lot identifier."""
    if not raw:
        return False
    return bool(_WINDOW_WORDS.search(raw) or _DATE_RANGE.search(raw))


def normalize_lot(raw: str | None) -> Optional[str]:
    """Uppercase, drop label words, strip everything that is not alphanumeric.

    ``LOT 4829B`` and ``4829-B`` both become ``4829B``. Returns None when
    nothing identifier-shaped survives.
    """
    if not raw:
        return None
    s = _NOISE.sub(" ", raw.upper())
    s = _NON_ALNUM.sub("", s)
    return s or None


def compare(a: str | None, b: str | None) -> LotComparison:
    """Compare two raw lot strings. Never raises."""
    if looks_like_a_window(a) or looks_like_a_window(b):
        return "unparseable"

    na, nb = normalize_lot(a), normalize_lot(b)
    if na is None or nb is None:
        return "unparseable"
    if na == nb:
        return "equal"
    # Prefix or substring: 6112 and 6112A are related but not the same lot.
    # FR-066 makes this HELD with the lot marked unconfirmed, never a silent PULL
    # and never a silent drop.
    if na in nb or nb in na:
        return "contained"
    return "none"
