"""Evidence: what was found linking one inventory row to one recall record.

Evidence is a *description*, not a judgement. It says what matched and quotes
the exact substring from each side; ``gate.decide()`` is the only thing that
turns it into a status. Keeping those apart means the ladder can be read in one
place and the widening rules in another, and neither can quietly acquire a
threshold from the other.

The order the channels are tried in is the order of how much each one proves:
barcode, then manufacturer catalog number, then lot, then supplier-plus-product,
then name alone. The first one that fires wins, so a pair is always described by
its strongest link.
"""

from __future__ import annotations

from typing import Callable, Literal, NamedTuple, Optional

EvidenceKind = Literal["gtin", "upc", "mfr_item", "lot", "secondary_code",
                       "firm_and_name", "name"]
LotComparison = Literal["equal", "contained", "none", "unparseable"]

#: Kinds whose evidence is two things agreeing rather than one. Their trigger
#: text is the two components joined by ``JOINER``, and each component is a
#: verbatim substring of its own side -- FR-023 holds per component, which is
#: what an operator actually needs: every piece of quoted text findable on the
#: page in front of them.
#: Asserted by tests/unit/test_tiers.py::test_both_triggers_are_verbatim.
COMPOUND_KINDS: frozenset[str] = frozenset({"mfr_item", "firm_and_name"})
JOINER = " + "


class Evidence(NamedTuple):
    """What links this pair, and the exact text on each side that shows it."""

    kind: EvidenceKind
    trigger_inventory_text: str
    trigger_recall_text: str
    #: Name similarity, 0.0-1.0. Carried for ORDERING within POSSIBLE only.
    #: It never appears in a comparison that determines status or tier.
    score: Optional[float] = None
    #: Outcome of comparing the two lot strings, when both sides had one.
    lot_comparison: Optional[LotComparison] = None
    #: The recall names a lot or date code.
    recall_lot_present: bool = False
    #: The inventory row tracks a lot code at all.
    inventory_lot_present: bool = False
    #: The recall's code_info could not be parsed into codes (FR-067).
    recall_codes_unparsed: bool = False
    #: 'active' | 'terminated' | 'amended'. A terminated recall is marked, never dropped.
    recall_status: str = "active"
    #: The inventory row's brand or manufacturer names the recalling firm
    #: (FR-071). A boolean, deliberately: gate.decide() must stay free of the
    #: corpus statistics that produced it.
    firm_agreement: bool = False


# ---------------------------------------------------------------------------
# Evidence construction
# ---------------------------------------------------------------------------

import re  # noqa: E402

from pullsheet.matching.firm import agrees  # noqa: E402
from pullsheet.matching.lot import compare as compare_lots  # noqa: E402
from pullsheet.matching.normalize import tokens  # noqa: E402
from pullsheet.matching.screen import code_key, significant_tokens  # noqa: E402
from pullsheet.matching.similarity import dice  # noqa: E402

#: Labels that mean "this is a code, but not the lot code". A match on one of
#: these is real evidence and is worth a PULL, but calling it a lot match would
#: misdescribe it to the operator reading the sheet.
_SECONDARY_LABEL = re.compile(
    r"\b(DAYCODE|DAY\s*CODE|PRODUCT\s*CODE|ITEM\s*CODE|SKU|PLU)\b[^A-Z0-9]{0,12}$", re.I)

_CODE_RUN = re.compile(r"[0-9][0-9\s-]{6,}[0-9]")


def _digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def item_key(code: str | None) -> Optional[str]:
    """Index key for a manufacturer's catalog number.

    Uppercased, punctuation dropped, leading zeros removed: a kitchen that
    stores High Liner's cod portions as ``02075`` and an agency that prints
    ``Item Number: 2075`` are naming one product.
    """
    if not code:
        return None
    cleaned = re.sub(r"[^A-Z0-9]", "", str(code).upper()).lstrip("0")
    return cleaned or None


def find_code_substring(haystack: str | None, code: str) -> str | None:
    """The literal substring of ``haystack`` that prints ``code``.

    The recall writes ``0 24284-96910 5``; the inventory carries
    ``024284969105``. FR-023 requires the exact triggering text *as each side
    wrote it*, so the operator can find it on the page in front of them -- which
    means returning the spaced form, not our cleaned-up version of it.
    """
    if not haystack:
        return None
    if code in haystack:
        return code
    target = _digits(code)
    for m in _CODE_RUN.finditer(haystack):
        run = m.group(0)
        if _digits(run) == target or code_key(run) == code_key(target):
            return run.strip()
    return None


def find_source_word(token: str, text: str | None) -> str | None:
    """The word in ``text`` that produced ``token``.

    Words are compared as written, so this is usually the token back again --
    but the source spelled it with its own case and punctuation (``COD,``
    ``Row``), and FR-023 wants what the operator will see on their screen.
    """
    if not text:
        return None
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9/%.\-]*", text):
        if token in tokens(word):
            return word
    return None


def _label_before(haystack: str, needle: str) -> str:
    idx = haystack.find(needle)
    return haystack[max(0, idx - 40):idx] if idx >= 0 else ""


def build_evidence(inv, rec, is_distinctive: Optional[Callable[[str], bool]] = None
                   ) -> Optional[Evidence]:
    """Inspect a candidate pair and describe what links it.

    ``is_distinctive`` reports whether a product word is rare enough in the
    recall corpus to carry weight -- the same corpus statistic screening uses.
    It is passed in rather than looked up so that the only thing crossing into
    ``gate.decide()`` is a boolean, and ``decide()`` stays a pure function of its
    arguments (FR-024). Absent, every word counts as distinctive: that widens the
    sheet, which is the safe direction to fail in (Principle I).

    Returns None only when the pair shares nothing at all -- which screening
    should already have prevented. It never decides a status; that is
    ``gate.decide()``'s sole job.
    """
    if is_distinctive is None:
        def is_distinctive(_token: str) -> bool:      # noqa: ARG001
            return True

    codes = getattr(rec, "parsed_codes", None) or {}
    code_info = getattr(rec, "code_info", "") or ""
    rec_desc = getattr(rec, "product_description", "") or ""
    rec_firm = getattr(rec, "recalling_firm", "") or ""
    # Barcodes turn up in either field, and FR-023 wants the agency's own
    # printing -- "0 24284-96910 5", spaces and all -- not our cleaned version.
    rec_codes_text = f"{code_info} {rec_desc}"
    inv_desc = getattr(inv, "raw_description", "") or ""
    inv_lot = getattr(inv, "lot_code", None)
    inv_mfr = getattr(inv, "manufacturer", None)
    inv_brand = getattr(inv, "brand", None)

    # Does this line come from the firm being recalled? Checked once; used by two
    # rungs of the ladder and never on its own (FR-070, FR-071).
    firm_side = inv_mfr if agrees(inv_mfr, rec_firm) else (
        inv_brand if agrees(inv_brand, rec_firm) else None)
    firm_ok = firm_side is not None

    recall_lots = list(codes.get("lots", ()))
    recall_lot_present = bool(recall_lots or codes.get("date_codes"))
    common = dict(
        recall_lot_present=recall_lot_present,
        inventory_lot_present=bool(inv_lot),
        recall_codes_unparsed=bool(codes.get("unparsed")),
        recall_status=getattr(rec, "status", "active") or "active",
        firm_agreement=firm_ok,
    )

    # --- 1. GTIN ----------------------------------------------------------
    inv_code = getattr(inv, "gtin", None)
    if inv_code:
        key = code_key(inv_code)
        for gtin in codes.get("gtins", ()):
            if code_key(gtin) == key:
                return Evidence(
                    "gtin",
                    find_code_substring(inv_desc, inv_code) or inv_code,
                    find_code_substring(rec_codes_text, gtin) or gtin,
                    **common,
                )
        # --- 2. UPC -------------------------------------------------------
        for upc in codes.get("upcs", ()):
            if code_key(upc) == key:
                return Evidence(
                    "upc",
                    inv_code,
                    find_code_substring(rec_codes_text, upc) or upc,
                    **common,
                )

    # --- 3. Manufacturer catalog number (FR-070) --------------------------
    # Product identity, but ONLY next to an agreeing manufacturer. Item number
    # 02075 is a breaded cod portion at High Liner and something else entirely
    # at every other company; the number alone asserts an identity it does not
    # carry.
    inv_item = getattr(inv, "manufacturer_item_code", None)
    if firm_ok and inv_item:
        key = item_key(inv_item)
        for code in codes.get("item_codes", ()):
            if key and item_key(code) == key:
                return Evidence(
                    "mfr_item",
                    f"{firm_side}{JOINER}{inv_item}",
                    f"{rec_firm}{JOINER}{find_code_substring(rec_codes_text, code) or code}",
                    **common,
                )

    # --- 4 / 5. lot or secondary code -------------------------------------
    if inv_lot:
        for lot in recall_lots:
            outcome = compare_lots(inv_lot, lot)
            if outcome in ("equal", "contained"):
                printed = find_code_substring(code_info, lot) or lot
                label = _label_before(code_info, printed)
                kind = "secondary_code" if _SECONDARY_LABEL.search(label) else "lot"
                return Evidence(kind, inv_lot, printed,
                                lot_comparison=outcome, **common)
        # The recall names lots and this row tracks one, but none of them line
        # up. Fall through -- a lot that does not match is not a reason to stop
        # looking at the supplier and the name.

    # --- 6 / 7. supplier-and-product, then name ---------------------------
    inv_tokens = tokens(inv_desc)
    rec_tokens = tokens(rec_desc)
    shared = significant_tokens(inv_desc) & significant_tokens(rec_desc)
    if not shared and not (inv_tokens & rec_tokens):
        return None

    lot_comparison = None
    if inv_lot and recall_lots:
        lot_comparison = compare_lots(inv_lot, recall_lots[0])

    # Quote the most distinctive shared word: the longest one, which in food
    # descriptions is reliably the most specific.
    pool = shared or (inv_tokens & rec_tokens)
    pick = max(pool, key=lambda t: (len(t), t))
    score = dice(inv_tokens, rec_tokens)

    # --- 6. firm and product word (FR-071) --------------------------------
    # The maker is being recalled AND the two descriptions agree on a word that
    # is rare across the corpus. Either signal alone is weak -- a firm recalls
    # one line out of hundreds, and one shared word is the POSSIBLE tier -- but
    # a kitchen holding a High Liner product when High Liner recalls a cod
    # portion, where both descriptions say "cod", is not a coincidence.
    if firm_ok:
        distinctive = {t for t in shared if is_distinctive(t)}
        if distinctive:
            word = max(distinctive, key=lambda t: (len(t), t))
            return Evidence(
                "firm_and_name",
                f"{firm_side}{JOINER}{find_source_word(word, inv_desc) or word}",
                f"{rec_firm}{JOINER}{find_source_word(word, rec_desc) or word}",
                score=score,
                lot_comparison=lot_comparison,
                **common,
            )

    # --- 7. name ----------------------------------------------------------
    return Evidence(
        "name",
        find_source_word(pick, inv_desc) or inv_desc,
        find_source_word(pick, rec_desc) or rec_desc,
        score=score,
        lot_comparison=lot_comparison,
        **common,
    )
