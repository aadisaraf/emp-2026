"""Name similarity. Our own scorer, no library.

The Dice coefficient over normalized word sets:

    dice(A, B) = 2 * |A n B| / (|A| + |B|)

Word sets, not character distance, because food descriptions differ by whole
words. Both sides are catalog strings, so the words that agree are the words
both catalogs chose:

    inventory  CHICKEN STRIPS BRD FC FROZEN 2/5 LB   -> 5 words
    recall     Frozen Chicken Strips, breaded        -> 4 words
    shared     chicken, strips, frozen               -> 6/9 = 0.667

Levenshtein on those two strings says almost nothing, and it would say it with a
confidence nobody could audit.

The score ORDERS lines within POSSIBLE. It never promotes one out of POSSIBLE --
see gate.decide(), which never compares it to anything.
"""

from __future__ import annotations


def dice(a: frozenset[str] | set[str], b: frozenset[str] | set[str]) -> float:
    """Dice coefficient of two token sets. 1.0 identical, 0.0 disjoint.

    Two empty sets score 0.0 rather than 1.0: two descriptions we could not read
    are not evidence that they are the same product.
    """
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return (2.0 * overlap) / (len(a) + len(b))
