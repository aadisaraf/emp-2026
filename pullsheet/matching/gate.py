"""THE chokepoint. Every pull/hold decision in PullSheet passes through here.

Constitution Principle I (Fail-Safe Hold, NON-NEGOTIABLE): the asymmetry is not
symmetric. Under-pulling risks a child; over-pulling wastes a case of tomatoes.
Every rule in this file therefore pushes toward the sheet, never away from it.

``Decision.status`` is ``Literal["PULL", "HELD"]``. There is no third value, so
an automatically cleared item is not merely forbidden -- it cannot be
represented. The database says the same thing independently:
``CHECK (status IN ('PULL','HELD'))`` in ``pullsheet/schema.sql``.

``decide()`` takes no clock, no config lookup, no database handle, and no I/O of
any kind. Same inputs, same output, always (FR-024, SC-011).
"""

from __future__ import annotations

from typing import Literal, NamedTuple, Optional

from pullsheet.matching.tiers import Evidence

Status = Literal["PULL", "HELD"]
Tier = Literal["CONFIRMED", "PROBABLE", "POSSIBLE"]

#: Tier and status are locked together, and nothing may vary one without the
#: other. A widening rule that "makes something HELD" demotes the tier to
#: POSSIBLE and says why in ``lot_note``. This is what makes the invariant
#: checkable from outside: any (tier, status) pair outside this map in the
#: matches table is a gate bypass.
TIER_STATUS: dict[str, Status] = {
    "CONFIRMED": "PULL",
    "PROBABLE": "PULL",
    "POSSIBLE": "HELD",
}


class Decision(NamedTuple):
    status: Status
    tier: Tier
    evidence_kind: str
    trigger_inventory_text: str
    trigger_recall_text: str
    score: Optional[float]
    lot_note: Optional[str]


#: The ladder. Evidence kind -> tier, and nothing else feeds this mapping.
#: Note what is absent: the score. It is carried on the Decision so POSSIBLE
#: lines can be ORDERED, and it never appears in a comparison that determines
#: tier or status. There is no pull threshold in this codebase, and
#: tests/unit/test_gate.py::test_no_input_can_auto_clear sweeps 101 score values
#: to keep it that way.
_LADDER: dict[str, Tier] = {
    "gtin": "CONFIRMED",
    "upc": "CONFIRMED",
    # A manufacturer's own catalog number, on an agreeing manufacturer. Product
    # identity, and the only kind of it most district rows can offer: barcodes
    # and lot codes are both absent from the majority of item masters, while the
    # supplier and the number used to order from them are always there (FR-070).
    "mfr_item": "CONFIRMED",
    "lot": "PROBABLE",
    "secondary_code": "PROBABLE",
    # The recalled firm made this line, and both descriptions name the same
    # distinctive product word. Two independent agreements, neither of which is
    # a guess about spelling (FR-071).
    "firm_and_name": "PROBABLE",
    "name": "POSSIBLE",
}

#: Kinds whose whole claim rests on the supplier being the recalled firm. If the
#: evidence does not actually carry that agreement, the claim is not the one the
#: kind names, and the pair falls to POSSIBLE rather than being trusted.
_NEEDS_FIRM: frozenset[str] = frozenset({"mfr_item", "firm_and_name"})

#: Kinds whose claim rests on two lot codes being the same code.
_NEEDS_LOT: frozenset[str] = frozenset({"lot", "secondary_code"})


def decide(inv, rec, evidence: Evidence) -> Decision:
    """Turn evidence into a pull-or-hold decision.

    Constitution Principle I: every branch below either produces a line or makes
    an existing line more cautious. None of them removes one. The only narrowing
    in the system happens earlier, in screen.generate_candidates(), which decides
    which pairs reach this function at all -- deliberately kept in a different
    file so a reviewer asking "where can something be lost?" has exactly one
    place to look.

    No clock, no config, no database handle, no I/O. FR-024, SC-011.
    """
    # An unrecognised evidence kind is treated as the weakest kind rather than
    # as an error: an exception here would drop a line, and dropping is the one
    # thing this function may never do.
    tier: Tier = _LADDER.get(evidence.kind, "POSSIBLE")

    notes: list[str] = []

    # --- Widening rule 1 (FR-027) -----------------------------------------
    # The recall names a lot; this district does not record lots for the item.
    # We cannot rule the case out, and not being able to rule it out is exactly
    # what keeps it on the sheet.
    if evidence.recall_lot_present and not evidence.inventory_lot_present:
        notes.append("recall lot not tracked in inventory")

    # --- Widening rule 2 (FR-067) -----------------------------------------
    # A date range or malformed code is not something we can compare. Failure to
    # parse widens; it must never narrow.
    if evidence.lot_comparison == "unparseable":
        notes.append("recall lot could not be parsed")

    # --- Widening rule 3 (FR-066) -----------------------------------------
    # Prefix or substring overlap: related, not equal.
    if evidence.lot_comparison == "contained":
        notes.append("lot unconfirmed - partial overlap between lot codes")

    # --- Widening rule 5 --------------------------------------------------
    if evidence.recall_codes_unparsed:
        notes.append("recall code_info carried no parseable codes")

    # --- Widening rule 7 (FR-016) -----------------------------------------
    # A terminated or amended recall is retained and MARKED, never removed. The
    # case was in this kitchen either way.
    if evidence.recall_status in ("terminated", "amended"):
        notes.append(f"recall status: {evidence.recall_status}")

    # --- Demotion ----------------------------------------------------------
    # A claim is demoted when the thing it is named after is not actually there.
    # Demotion moves a line from PULL to HELD; it never removes one, and the
    # notes above ride along either way, so the operator sees the same caveat.
    #
    # A barcode match (gtin/upc) is product identity outright and is never
    # demoted -- it names no second condition to be missing.
    if evidence.kind in _NEEDS_LOT and evidence.lot_comparison != "equal":
        # Prefix or partial overlap between two lot codes is not agreement.
        tier = "POSSIBLE"
    if evidence.kind in _NEEDS_FIRM and not evidence.firm_agreement:
        # An item number with no agreeing manufacturer behind it is just a
        # number, and a number is not an identity (FR-070).
        tier = "POSSIBLE"
        notes.append("supplier could not be confirmed against the recalling firm")

    # Widening rules 4 and 6 need no branch: a missing GTIN, an empty string, a
    # None, or a contradictory field simply never reaches a condition that could
    # suppress the line. Producing a Decision is the default and the floor.

    return Decision(
        status=TIER_STATUS[tier],
        tier=tier,
        evidence_kind=evidence.kind,
        trigger_inventory_text=evidence.trigger_inventory_text or "",
        trigger_recall_text=evidence.trigger_recall_text or "",
        score=evidence.score,
        lot_note="; ".join(notes) if notes else None,
    )
