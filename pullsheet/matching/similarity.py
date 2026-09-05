"""Name similarity. Our own scorer, no library.

The Dice coefficient over normalized token sets:

    dice(A, B) = 2 * |A n B| / (|A| + |B|)

Chosen over edit distance because food descriptions differ by whole words, not
characters: "chkn strips froz" and "Frozen Chicken Strips, breaded" share three
tokens out of seven once abbreviations are expanded, which is a fact about the
products. Levenshtein on those two strings says almost nothing.

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
