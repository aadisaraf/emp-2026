"""Candidate generation. **The one narrowing operation in the system.**"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, NamedTuple, Optional

from pullsheet.matching.firm import firm_tokens
from pullsheet.matching.lot import normalize_lot
from pullsheet.matching.normalize import tokens

# Hand-authored. These words appear in so many food descriptions that indexing
# them makes every product a candidate for every recall, which is the same as
STOPLIST: frozenset[str] = frozenset({
    # states and preparations that describe half the freezer
    "frozen", "fresh", "refrigerated", "chilled", "cooked", "raw", "prepared",
    "ready", "eat", "keep", "packed", "packaged", "individually", "wrapped",
    # packaging and commerce
    "case", "cases", "bag", "bags", "box", "boxes", "carton", "cartons", "pouch",
    "pack", "package", "packages", "container", "tray", "bulk", "net", "weight",
    "wt", "size", "sizes", "count", "single", "serving", "servings", "retail",
    "foodservice", "institutional", "distributed", "brand", "brands", "label",
    "labeled", "product", "products", "item", "items", "sold", "under",
    # filler
    "and", "with", "without", "the", "for", "all", "any", "other", "following",
    "includes", "including", "contains", "made", "approx", "approximately",
    "in", "on", "at", "to", "of", "by", "or", "is", "was", "were", "been", "has",
    "have", "had", "not", "no", "new", "use", "used", "also", "its", "this",
    "that", "these", "those", "each", "per", "one", "two", "three", "four",
    # code and date words that appear in descriptions rather than code fields
    "upc", "gtin", "sku", "plu", "code", "codes", "lot", "lots", "batch", "est",
    "date", "dates", "exp", "expiration", "best", "sell", "number", "numbers",
    "found", "located", "printed", "stamped", "bottom", "top", "back", "front",
    "side", "ingredients", "ingredient", "allergen", "warning",
    # corporate boilerplate
    "inc", "llc", "ltd", "company", "co", "corp", "corporation", "manufactured",
    "distributor", "distributors", "foods", "food", "brands",
    # packaging materials
    "plastic", "paper", "glass", "metal", "poly", "clear", "white", "black",
})


def code_key(code: str | None) -> Optional[str]:
    """Index key for a barcode."""
    if not code:
        return None
    digits = "".join(c for c in str(code) if c.isdigit())
    if len(digits) < 8:
        return None
    # openFDA routinely prints a UPC-12 with its leading zero dropped
    # ("41220273355"). Left-pad so it keys identically to the 12-digit form the
    if len(digits) < 12:
        digits = digits.rjust(12, "0")
    return digits[:-1][-11:]


class ScreenRecord(NamedTuple):
    """The minimum a recall record must expose to be screened."""

    id: Any
    normalized_description: str
    parsed_codes: dict
    recalling_firm: str = ""


# A token appearing in more than this share of the corpus narrows nothing on
# its own: "milk" reaches every milk recall there has ever been. Such a token
COMMON_TOKEN_SHARE = 0.02

# A pair sharing this many significant tokens is a candidate no matter how
# common each one is.
MIN_SHARED_TOKENS = 2


class Indexes(NamedTuple):
    by_code: dict[str, set]
    by_lot: dict[str, set]
    by_token: dict[str, set]
    record_count: int
    doc_freq: dict[str, int]
    by_firm: dict[str, set]

    def is_distinctive(self, token: str) -> bool:
        """True when this token is rare enough to justify a comparison alone."""
        if not self.record_count:
            return True
        return self.doc_freq.get(token, 0) <= COMMON_TOKEN_SHARE * self.record_count


def significant_tokens(text: str | None) -> frozenset[str]:
    """Tokens worth searching on: normalized, minus the stoplist."""
    return frozenset(tokens(text) - STOPLIST)


def build_indexes(records: Iterable[ScreenRecord]) -> Indexes:
    """Build the four inverted indexes over the recall corpus."""
    by_code: dict[str, set] = defaultdict(set)
    by_lot: dict[str, set] = defaultdict(set)
    by_token: dict[str, set] = defaultdict(set)
    by_firm: dict[str, set] = defaultdict(set)
    doc_freq: dict[str, int] = defaultdict(int)
    n = 0

    for rec in records:
        n += 1
        codes = rec.parsed_codes or {}
        for code in list(codes.get("gtins", ())) + list(codes.get("upcs", ())):
            key = code_key(code)
            if key:
                by_code[key].add(rec.id)
        for lot in codes.get("lots", ()):
            key = normalize_lot(lot)
            if key:
                by_lot[key].add(rec.id)
        for token in firm_tokens(rec.recalling_firm):
            by_firm[token].add(rec.id)
        for token in significant_tokens(rec.normalized_description):
            by_token[token].add(rec.id)
            doc_freq[token] += 1

    return Indexes(dict(by_code), dict(by_lot), dict(by_token), n, dict(doc_freq),
                   dict(by_firm))


def generate_candidates(inv, indexes: Indexes) -> set:
    """Which recall records this inventory row is compared against at all.

    ==========================================================================
    CONSTITUTION PRINCIPLE I -- JUSTIFIED NARROWING PATH 1 OF 3
    --------------------------------------------------------------------------
    Requirement:  FR-020. This is the screening floor, and the only operation in
                  PullSheet that can cause a pair never to be evaluated.
    Rule:         a recall record becomes a candidate if it shares, with this
                  inventory row, ANY of:
                    - a barcode fragment (right-most 11 digits, check digit off)
                    - a normalized lot code
                    - a word from the supplier's name
                    - two or more significant product words
                    - one product word appearing in <= 2% of the corpus
                  Union, never intersection. Any one of the five is enough.
    Why safe:     the channels are independent, and each covers the others'
                  blind spots. A row with no barcode is reachable by supplier or
                  by name (FR-026) -- which is the ordinary case, not the
                  exception: most kitchen rows carry neither a barcode nor a
                  lot. A row whose description normalizes to nothing is still
                  reachable by code or supplier. The token conditions only refuse
                  a pair whose ONLY link is a single word that reaches a large
                  fraction of the corpus -- "milk" alone is not evidence that
                  this milk is that milk, and a sheet that says it is cannot be
                  read, which is its own way of missing a recall.
    Cost:         measured, not assumed. All 25 hand-seeded correspondences
                  survive this rule; the test asserting so is build-stopping.
    Stoplist:     removed from SEARCH only. Stoplisted and common tokens are
                  still counted by similarity.dice() once a pair exists.
    Covered by:   tests/unit/test_screen.py::test_every_seeded_pair_survives_screening
                  tests/unit/test_clearing_audit.py
    ==========================================================================
    """
    hits: set = set()

    code = code_key(getattr(inv, "gtin", None))
    if code:
        hits |= indexes.by_code.get(code, set())

    lot_key = normalize_lot(getattr(inv, "lot_code", None))
    if lot_key:
        hits |= indexes.by_lot.get(lot_key, set())

    # Supplier channels. Any shared firm word admits the pair; whether the two
    # names actually agree is decided later, by firm.agrees(), on the full name.
    supplier_tokens: set[str] = set()
    for name in (getattr(inv, "manufacturer", None), getattr(inv, "brand", None)):
        supplier_tokens |= firm_tokens(name)
    for token in supplier_tokens:
        hits |= indexes.by_firm.get(token, set())

    # Name channel. Count how many of this row's significant tokens each recall
    # shares, so "two common tokens" and "one distinctive token" can both admit
    shared_counts: dict = defaultdict(int)
    for token in significant_tokens(getattr(inv, "normalized_description", None)):
        for recall_id in indexes.by_token.get(token, ()):
            shared_counts[recall_id] += 1
            if indexes.is_distinctive(token):
                hits.add(recall_id)

    hits |= {rid for rid, count in shared_counts.items() if count >= MIN_SHARED_TOKENS}

    return hits


# The screening rule in one sentence, rendered verbatim on the pull sheet so an
# operator can read what the system throws away without reading the code (T045).
SCREENING_RULE = (
    "A recall is compared against an inventory line only if the two share a barcode "
    "fragment, a lot code, a word from the supplier's name, two or more significant "
    "product words, or one product word that appears in fewer than 2% of recall "
    "records. A pair whose only link is a single common word - milk, chicken, cheese "
    "- is never evaluated."
)
