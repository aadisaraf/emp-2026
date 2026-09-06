"""Name similarity. Our own scorer, no library."""

from __future__ import annotations


def dice(a: frozenset[str] | set[str], b: frozenset[str] | set[str]) -> float:
    """Dice coefficient of two token sets. 1.0 identical, 0.0 disjoint."""
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return (2.0 * overlap) / (len(a) + len(b))
