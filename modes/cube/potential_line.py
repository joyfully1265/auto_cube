"""PotentialLine model.

Represents a single possible cube line — the stat it provides, the numeric
value, and whether the value is a percentage or a flat number (e.g. cooldown
reduction).
"""

from __future__ import annotations

from dataclasses import dataclass

from .value_profile import ValueProfile


@dataclass(frozen=True)
class PotentialLine:
    """One possible stat line on a potential.

    Attributes:
        stat: Stat name, e.g. ``"Attack Power"``, ``"STR"``.
        value: Numeric value of the line.
        is_percent: ``False`` for flat stats like cooldown reduction;
            ``True`` (the default) for percentage-based stats.
    """

    stat: str
    value: int
    is_percent: bool = True

    def __post_init__(self) -> None:
        # Auto-detect flat stats so callers don't have to remember.
        if ValueProfile.is_flat_stat(self.stat):
            object.__setattr__(self, "is_percent", False)

    def __str__(self) -> str:
        suffix = "%" if self.is_percent else ""
        return f"{self.stat}: {self.value}{suffix}"
