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
