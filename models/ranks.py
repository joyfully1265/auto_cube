"""Potential ranks, ordered from lowest to highest.

Rare only supplies the non-prime roll of an Epic line and cannot be targeted,
so it is excluded from ``SUPPORTED_TIERS``.
"""

from __future__ import annotations

from typing import Optional, Tuple

RANKS: Tuple[str, ...] = ("Rare", "Epic", "Unique", "Legendary")

# Ranks a cube goal may target.
SUPPORTED_TIERS: Tuple[str, ...] = RANKS[1:]


def rank_at_least(rank: Optional[str], target: str) -> bool:
    """Return True when *rank* is *target* or higher.

    Unknown ranks (including ``None`` from a failed OCR read) only satisfy an
    exact match, so a misread never counts as a hit.
    """
    if rank not in RANKS or target not in RANKS:
        return rank == target
    return RANKS.index(rank) >= RANKS.index(target)
