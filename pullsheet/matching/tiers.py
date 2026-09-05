"""Evidence: what was found linking one inventory row to one recall record.

Evidence is a *description*, not a judgement. It says what matched and quotes
the exact substring from each side; ``gate.decide()` is the only thing that
turns it into a status. Keeping those apart means the ladder can be read in one
place and the widening rules in another, and neither can quietly acquire a
threshold from the other.
"""

from __future__ import annotations

from typing import Literal, NamedTuple, Optional

EvidenceKind = Literal["gtin", "upc", "lot", "secondary_code", "name"]
LotComparison = Literal["equal", "contained", "none", "unparseable"]


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


# ---------------------------------------------------------------------------
# Evidence construction
# ---------------------------------------------------------------------------

import re  # noqa: E402

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
    """The word in ``text`` that normalizes to ``token``.

    ``chicken`` came from ``chkn``. The operator sees ``chkn`` on their screen,
    so that is what the sheet must quote back at them.
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


def build_evidence(inv, rec) -> Optional[Evidence]:
    """Inspect a candidate pair and describe what links it.

    Returns None only when the pair shares nothing at all -- which screening
    should already have prevented. It never decides a status; that is
    ``gate.decide()``'s sole job.
    """
    codes = getattr(rec, "parsed_codes", None) or {}
    code_info = getattr(rec, "code_info", "") or ""
    rec_desc = getattr(rec, "product_description", "") or ""
    # Barcodes turn up in either field, and FR-023 wants the agency's own
    # printing -- "0 24284-96910 5", spaces and all -- not our cleaned version.
    rec_codes_text = f"{code_info} {rec_desc}"
    inv_desc = getattr(inv, "raw_description", "") or ""
    inv_lot = getattr(inv, "lot_code", None)

    recall_lots = list(codes.get("lots", ()))
    recall_lot_present = bool(recall_lots or codes.get("date_codes"))
    common = dict(
        recall_lot_present=recall_lot_present,
        inventory_lot_present=bool(inv_lot),
        recall_codes_unparsed=bool(codes.get("unparsed")),
        recall_status=getattr(rec, "status", "active") or "active",
    )

    # --- 1. GTIN ----------------------------------------------------------
    inv_code = getattr(inv, "gtin", None) or getattr(inv, "upc", None)
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

    # --- 3 / 4. lot or secondary code -------------------------------------
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
        # up. Fall through to name evidence -- a lot that does not match is not
        # a reason to stop looking at the name.

    # --- 5. name ----------------------------------------------------------
    inv_tokens = tokens(inv_desc)
    rec_tokens = tokens(rec_desc)
    shared = significant_tokens(inv_desc) & significant_tokens(rec_desc)
    if not shared and not (inv_tokens & rec_tokens):
        return None

    # Quote the most distinctive shared token: the longest one, which in food
    # descriptions is reliably the most specific.
    pick = max(shared or (inv_tokens & rec_tokens), key=lambda t: (len(t), t))
    lot_comparison = None
    if inv_lot and recall_lots:
        lot_comparison = compare_lots(inv_lot, recall_lots[0])
    elif recall_lots and not inv_lot:
        lot_comparison = None

    return Evidence(
        "name",
        find_source_word(pick, inv_desc) or inv_desc,
        find_source_word(pick, rec_desc) or rec_desc,
        score=dice(inv_tokens, rec_tokens),
        lot_comparison=lot_comparison,
        **common,
    )
