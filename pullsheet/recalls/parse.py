"""Free-text ``code_info`` -> structured codes.

openFDA's ``code_info`` is prose written by whoever filed the recall. There is no
schema. This module is a documented regex table over the shapes that actually
occur in the committed snapshot -- every pattern below carries a real example
string from ``openfda-2026-09-05.json``.

The governing rule (FR-067): **failure to parse must widen, never narrow.** When
nothing is extractable the result is empty lists and ``unparsed: True``, which
sends the pair down the name-evidence path and onto the sheet as HELD. It never
raises, and it never returns something that looks like a confident non-match.
"""

from __future__ import annotations

import re
from typing import Any

# "GTIN 10073803048293"  /  "GTIN-14: 20073803110074"
_GTIN = re.compile(r"\bGTIN(?:-?14)?\s*[:#]?\s*(\d{14})\b", re.I)

# Any bare 14-digit run: "10073803110075"
_BARE_14 = re.compile(r"(?<!\d)(\d{14})(?!\d)")

# "UPC No. 632687615989"  /  "Retail UPC: 41220273355"  /  "UPC (Case): 210006046400"
# The 11-digit alternative is real: openFDA records routinely drop the leading zero.
_UPC_LABELLED = re.compile(r"\bUPC\b[^0-9]{0,30}?(\d{11,13})(?!\d)", re.I)

# Spaced/hyphenated retail UPC as printed on the package: "0 24284-96910 5"
# and "7 90629-08008 7".
_UPC_SPACED = re.compile(r"(?<![\d-])(\d[\s-]\d{5}[\s-]\d{5}[\s-]\d)(?![\d-])")

# "Lot Code SPM1.190.5"  /  "Lot No. 30661601"  /  "Lots: 25006, 25035, 25044"
# /  "Batch #4829B"  /  "Daycode: K10635"  /  "Product Code, Z160, Z162"
_LOT_LABEL = re.compile(
    r"\b(?:LOT|LOTS|LOTE|BATCH|DAYCODE|DAY\s*CODE|PRODUCT\s*CODE|CODE)\b"
    r"(?:\s*(?:CODES?|NUMBERS?|NOS?|#))?\s*[:#.]?\s*",
    re.I,
)
# What a lot token looks like once a label has introduced it. Allows the dots in
# "SPM1.190.5" and the hyphens in "8817-C", but not a bare 1-2 character scrap.
_LOT_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9.\-]{2,}", re.I)

# "Item Number: 10002800"  /  "Item #473015"  /  "SKU: 3107"  /  "Item # 74384"
# The manufacturer's own catalog number. Districts carry these because they order
# by them, and 239 of the 1000 committed openFDA records print one. A code is
# only ever product identity ALONGSIDE an agreeing manufacturer (FR-070): item
# number 02075 means a cod portion at High Liner and something else everywhere
# else.
_ITEM_CODE = re.compile(
    r"\b(?:ITEM|SKU|PRODUCT|CATALOG|CAT|MFR|MFG)\s*"
    r"(?:NUMBERS?|NOS?|CODES?|#)?\s*[:#.]?\s*([A-Z0-9][A-Z0-9\-]{3,19})\b", re.I)

# "Exp. Date 05/2018"  /  "Best By 07/09/27"  /  "Sell by 10/10/19 to 11/10/19"
# /  "Code Dates: 20 FEB 2015"  /  "001 JUN 05 24"
_DATE_NUMERIC = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
_DATE_WORDY = re.compile(
    r"\b\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4}\b", re.I)
_DATE_WORDY_2 = re.compile(
    r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{1,2}\s+\d{2,4}\b", re.I)

# A lot list ends where a date window begins: "Lot Code SPM1.190.5 with a Best
# By 07/09/27" must yield SPM1.190.5 and not also 27.
_TAIL_END = re.compile(
    r"\b(?:WITH|BEST\s*BY|SELL\s*BY|SELL\s*THRU|USE\s*BY|EXP|EXPIR\w*|"
    r"THRU|THROUGH|IS|ARE|STAMPED|PRINTED|LOCATED|FOUND|ON\s+THE)\b", re.I)

_MONTHS = frozenset({"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
                     "SEP", "SEPT", "OCT", "NOV", "DEC"})

# Words that follow a lot label but are prose, not codes.
_STOP_TOKENS = frozenset({
    "AND", "THE", "ARE", "WITH", "WITHIN", "ALL", "EXPIRY", "EXPIRATION", "DATE",
    "DATES", "BEST", "SELL", "USE", "THRU", "THROUGH", "BY", "NUMBER", "NUMBERS",
    "CODE", "CODES", "INCLUDING", "STAMPED", "PRINTED", "LOCATED", "FOLLOWING",
    "PACKAGES", "PACKAGE", "PRODUCT", "PRODUCTS", "ITEM", "ITEMS", "NET", "WT",
    "WEIGHT", "WHERE", "ALSO", "EACH", "PER", "OZ", "LB", "LBS", "UPC", "GTIN",
    "RETAIL", "CASE", "EST", "CONTAINS", "STILL", "PALLET", "PALLETS",
    "LOT", "LOTS", "LOTE", "BATCH", "DAYCODE", "BACK", "FRONT", "NEAR", "BOTTOM",
    "TOP", "SIDE", "LABEL", "BAG", "BAGS", "BOX", "POUCH", "CARTON", "CONTAINER",
    "BOTTLE", "JAR", "INDIVIDUAL", "SINGLE", "MARK", "INSPECTION", "USDA", "FSIS",
    "PACK", "PACKED", "PRODUCTION", "PROD", "SKU", "NO", "NOS", "NUM",
}) | _MONTHS


def _dedupe(values):
    seen, out = set(), []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def parse_code_info(text: str | None) -> dict[str, Any]:
    """Extract codes from an agency's free-text code field.

    Returns ``{gtins, upcs, lots, date_codes, unparsed}``. Never raises: a
    ``code_info`` we cannot read must still produce a usable, honest result.
    """
    empty = {"gtins": [], "upcs": [], "lots": [], "date_codes": [],
             "item_codes": [], "unparsed": True}
    if not text or not text.strip():
        return empty

    gtins = _GTIN.findall(text) + _BARE_14.findall(text)

    upcs: list[str] = []
    for m in _UPC_LABELLED.findall(text):
        upcs.append(m)
    for m in _UPC_SPACED.findall(text):
        upcs.append(re.sub(r"[\s-]", "", m))

    # A 14-digit GTIN also matches the 11-13 digit UPC pattern in some strings;
    # keep them apart so the screening index does not key a GTIN as a UPC.
    upcs = [u for u in upcs if u not in gtins]

    lots: list[str] = []
    for label in _LOT_LABEL.finditer(text):
        # Read the run of text after the label, stopping at a sentence break.
        tail = text[label.end():label.end() + 220]
        tail = re.split(r"[;\n]|(?<=\.)\s+(?=[A-Z])", tail)[0]
        cut = _TAIL_END.search(tail)
        if cut:
            tail = tail[:cut.start()]
        for token in _LOT_TOKEN.findall(tail):
            upper = token.upper().strip(".-")
            if not upper or upper in _STOP_TOKENS:
                continue
            if upper in gtins or upper in upcs:
                continue
            if len(upper) >= 11 and upper.isdigit():
                continue                      # that is a barcode, not a lot
            if upper.isdigit() and len(upper) == 4 and 1900 <= int(upper) <= 2100:
                continue                      # a year, not a lot
            if upper.isalpha() and len(upper) <= 4:
                continue                      # a word fragment, not a lot
            lots.append(upper)

    item_codes: list[str] = []
    for raw in _ITEM_CODE.findall(text):
        code = raw.upper().strip(".-")
        if not any(c.isdigit() for c in code):
            continue                      # "Product codes beginning with B" is prose
        if code in gtins or code in upcs:
            continue
        if code.isdigit() and len(code) >= 11:
            continue                      # that is a barcode, not a catalog number
        item_codes.append(code)

    date_codes = (_DATE_NUMERIC.findall(text)
                  + _DATE_WORDY.findall(text)
                  + _DATE_WORDY_2.findall(text))

    gtins, upcs, lots, date_codes, item_codes = map(
        _dedupe, (gtins, upcs, lots, date_codes, item_codes))
    return {
        "gtins": gtins,
        "upcs": upcs,
        "lots": lots,
        "date_codes": date_codes,
        "item_codes": item_codes,
        # `unparsed` means "no identifier came out of this", which is what the
        # matcher needs to know. Date codes alone do not count: a date window is
        # not something a lot can be compared against.
        "unparsed": not (gtins or upcs or lots),
    }


def parse_record(product_description: str | None,
                 code_info: str | None,
                 more_code_info: str | None = None) -> dict[str, Any]:
    """Parse a whole recall record, not just its code field.

    Agencies put barcodes wherever they land: ``H-0109-2026`` prints its UPC in
    the product description and its lot codes in ``code_info``. Reading only
    ``code_info`` loses the UPC, and losing a barcode is losing the strongest
    evidence there is.

    Lots are taken from the code fields ONLY. A word like "lot" appearing in a
    product description is prose, and treating it as a label manufactures lot
    codes out of sentences.
    """
    codes = parse_code_info(" ".join(filter(None, (code_info, more_code_info))))
    from_description = parse_code_info(product_description)

    gtins = _dedupe(codes["gtins"] + from_description["gtins"])
    upcs = _dedupe([u for u in codes["upcs"] + from_description["upcs"] if u not in gtins])
    return {
        "gtins": gtins,
        "upcs": upcs,
        "lots": codes["lots"],
        "date_codes": _dedupe(codes["date_codes"] + from_description["date_codes"]),
        # Item numbers are printed in the product description far more often than
        # in code_info ("... Item Number: 10003220"), so both are read.
        "item_codes": _dedupe(codes["item_codes"] + from_description["item_codes"]),
        "unparsed": not (gtins or upcs or codes["lots"]),
    }
