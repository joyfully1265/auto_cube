"""StatGroup model.

A named, immutable set of stats used to express goals like
"any N lines of Attack/Boss/IED".
"""

from __future__ import annotations

from dataclasses import dataclass

from ...models.stat_line import COOLDOWN_STAT


@dataclass(frozen=True)
class StatGroup:
    """A named set of stat names.

    Attributes:
        name: Human-readable label, e.g. ``"Damage"``.
        stats: The stat names in this group.
    """

    name: str
    stats: frozenset[str]

    # -- Predefined groups ------------------------------------------------

    @classmethod
    def damage_group(cls) -> StatGroup:
        """Attack Power, Magic ATT, Boss Damage, Ignore Defense, Damage."""
        return cls(
            name="Damage",
            stats=frozenset(
                {"Attack Power", "Magic ATT", "Boss Damage", "Ignore Defense", "Damage"}
            ),
        )

    @classmethod
    def primary_stat_group(cls) -> StatGroup:
        """STR, DEX, INT, LUK."""
        return cls(
            name="Primary Stats",
            stats=frozenset({"STR", "DEX", "INT", "LUK"}),
        )

    @classmethod
    def utility_group(cls) -> StatGroup:
        """Item Drop Rate, Mesos Obtained."""
        return cls(
            name="Utility",
            stats=frozenset({"Item Drop Rate", "Mesos Obtained"}),
        )

    @classmethod
    def cooldown_group(cls) -> StatGroup:
        """Skill Cooldowns."""
        return cls(
            name="Cooldown",
            stats=frozenset({COOLDOWN_STAT}),
        )

    # -- Dunder helpers ---------------------------------------------------

    def __contains__(self, stat: str) -> bool:
        return stat in self.stats

    def __str__(self) -> str:
        return self.name
