"""Exhaustive subset-sum search over small value lists."""

from itertools import combinations


def find_combination(values, target, tolerance=0):
    """Return a tuple of values whose sum equals target (within tolerance),
    or None. Brute-forces combinations of increasing size with an early break;
    fast and reliable for roughly 20 or fewer candidate values."""
    for size in range(1, len(values) + 1):
        for combo in combinations(values, size):
            if abs(sum(combo) - target) <= tolerance:
                return combo
    return None
