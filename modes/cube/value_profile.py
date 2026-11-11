"""ValueProfile model.

Encapsulates the prime and non-prime line values for a given level range
and potential rank.  In MapleStory the value of a single stat line depends
on both the item's level range and its rank: a line can roll at the item's
rank or one rank below, so each rank has a prime value (its own rank) and a
non-prime value (the rank below).  "All Stats" rolls one rank lower still.
This class captures that mapping so that combination generators and UI code
don't hard-code the numbers.

Rare is not a supported target rank; its values only supply the non-prime
roll of an Epic line.

Boss Damage and Ignore Defense use fixed line values (30/35/40) that do
not follow the rank system used by Attack Power and other percentage stats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...models.ranks import RANKS, SUPPORTED_TIERS
from ...models.stat_line import COOLDOWN_STAT

# Flat stats whose values are not expressed as percentages (e.g. cooldowns).
_FLAT_STATS: frozenset[str] = frozenset({COOLDOWN_STAT})

# Default rank used when a caller does not specify one.
_DEFAULT_TIER = SUPPORTED_TIERS[-1]

# Line values for standard %-based stats keyed by level range, then rank.
# These apply to Attack Power, Magic ATT, STR, DEX, INT, LUK, etc.  "All
# Stats" rolls one rank lower; see ``all_stats_line_values``.
_LEVEL_VALUES: dict[str, dict[str, int]] = {
    "71-150": {"Rare": 3, "Epic": 6, "Unique": 9, "Legendary": 12},
    "151+": {"Rare": 4, "Epic": 7, "Unique": 10, "Legendary": 13},
}

# Boss Damage and Ignore Defense line values (same for all level ranges).
# Each stat has three possible line values: 30%, 35%, 40%.
_BOSS_DAMAGE_VALUES: tuple[int, ...] = (30, 35, 40)
_IGNORE_DEFENSE_VALUES: tuple[int, ...] = (30, 35, 40)

# Critical Damage only rolls a single value; unlike the rank-based stats it
# does not depend on the item's level range or tier.
_CRITICAL_DAMAGE_VALUES: tuple[int, ...] = (8,)

# Flat stats do not follow the rank system; their values are the same at
# every tier.  Cooldown reduction values are seconds.
_COOLDOWN_VALUES: tuple[int, ...] = (2, 1)


@dataclass(frozen=True)
class ValueProfile:
    """Prime and non-prime line values for a level range and rank.

    Attributes:
        level_range: ``"71-150"`` or ``"151+"``.
        tier: Potential rank, e.g. ``"Legendary"``.
        prime: Value of a prime (best) line for standard %-based stats.
        non_prime: Value of a line rolled at the rank below *tier*.
    """

    level_range: str
    tier: str
    prime: int
    non_prime: Optional[int] = None

    @classmethod
    def for_level_range(
        cls, level_range: str, tier: str = _DEFAULT_TIER
    ) -> ValueProfile:
        """Factory that looks up the correct values for *level_range* and *tier*.

        Args:
            level_range: ``"71-150"`` or ``"151+"``.
            tier: One of ``"Epic"``, ``"Unique"``, ``"Legendary"``.

        Raises:
            ValueError: If *level_range* or *tier* is not supported.
        """
        if level_range not in _LEVEL_VALUES:
            raise ValueError(
                f"Unknown level range {level_range!r}; "
                f"expected one of {sorted(_LEVEL_VALUES)}"
            )
        if tier not in SUPPORTED_TIERS:
            raise ValueError(
                f"Unsupported tier {tier!r}; "
                f"expected one of {list(SUPPORTED_TIERS)}"
            )
        values = _LEVEL_VALUES[level_range]
        index = RANKS.index(tier)
        non_prime = values[RANKS[index - 1]]
        return cls(
            level_range=level_range,
            tier=tier,
            prime=values[tier],
            non_prime=non_prime,
        )

    @property
    def line_values(self) -> tuple[int, ...]:
        """Possible line values for standard %-based stats, best first."""
        if self.non_prime is None:
            return (self.prime,)
        return (self.prime, self.non_prime)

    @property
    def all_stats_line_values(self) -> tuple[int, ...]:
        """Possible ``All Stats`` line values, best first.

        All Stats rolls one rank lower than the item's rank, so a legendary
        151+ item rolls 10/7 while a unique one rolls 7/4.
        """
        values = _LEVEL_VALUES[self.level_range]
        index = RANKS.index(self.tier) - 1
        if index == 0:
            return (values[RANKS[0]],)
        return (values[RANKS[index]], values[RANKS[index - 1]])

    @property
    def max_single_stat(self) -> int:
        """Maximum total for a single stat across three lines (prime+prime+prime)."""
        return self.prime * 3

    @property
    def flat_line_values(self) -> tuple[int, ...]:
        """Possible line values for flat stats, best first.

        Flat stats do not use percentages and are not tied to a rank, so the
        same values are offered at every tier.
        """
        return _COOLDOWN_VALUES

    @property
    def critical_damage_line_values(self) -> tuple[int, ...]:
        """Possible Critical Damage line values; Legendary only."""
        return _CRITICAL_DAMAGE_VALUES if self.tier == "Legendary" else ()

    # -- Boss Damage / IED helpers ----------------------------------------

    @staticmethod
    def boss_damage_values() -> tuple[int, ...]:
        """Return the possible Boss Damage line values."""
        return _BOSS_DAMAGE_VALUES

    @staticmethod
    def ignore_defense_values() -> tuple[int, ...]:
        """Return the possible Ignore Defense line values."""
        return _IGNORE_DEFENSE_VALUES

    @staticmethod
    def is_critical_damage(stat: str) -> bool:
        """Return ``True`` for Critical Damage."""
        return stat == "Critical Damage"

    @staticmethod
    def is_legendary_only(stat: str) -> bool:
        """Return ``True`` for stats that only roll on Legendary items."""
        return stat == "Critical Damage" or stat == "Skill Cooldowns"

    @staticmethod
    def is_boss_damage(stat: str) -> bool:
        """Return ``True`` for Boss Damage."""
        return stat == "Boss Damage"

    @staticmethod
    def is_ignore_defense(stat: str) -> bool:
        """Return ``True`` for Ignore Defense."""
        return stat == "Ignore Defense"

    @staticmethod
    def is_all_stats(stat: str) -> bool:
        """Return ``True`` for All Stats."""
        return stat == "All Stats"

    @staticmethod
    def is_flat_stat(stat: str) -> bool:
        """Return ``True`` for stats that are not expressed as percentages."""
        return stat in _FLAT_STATS
