"""CombinationGoal hierarchy.

A :class:`CombinationGoal` represents a stop condition for the cube
automation loop.  Each goal knows how to check itself against the
:class:`StatLine` objects extracted from a piece of equipment via OCR.

The hierarchy::

    CombinationGoal (ABC)
        SumGoal
        LineCountGoal
        AndGoal
        OrGoal
"""

from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Sequence

from ...models.stat_line import StatLine
from .value_profile import ValueProfile


class CombinationGoal(ABC):
    """Abstract base for all cubing goals.

    Every goal must implement :meth:`check` (boolean test against
    equipment lines) and :meth:`describe` (human-readable label).
    """

    @abstractmethod
    def check(self, lines: Sequence[StatLine]) -> bool:
        """Return ``True`` if *lines* satisfy this goal."""

    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description of this goal."""

    # -- Logical combinators ----------------------------------------------

    def __and__(self, other: CombinationGoal) -> AndGoal:
        return AndGoal([self, other])

    def __or__(self, other: CombinationGoal) -> OrGoal:
        return OrGoal([self, other])


# ---------------------------------------------------------------------------
# Atomic goals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SumGoal(CombinationGoal):
    """The total of one stat across all lines must meet a threshold.

    ``"All Stats"`` lines also count toward the four primary stats
    (STR, DEX, INT, LUK), matching MapleStory's in-game behaviour.
    """

    stat: str
    target_value: int
    _op: Callable[[int, int], bool] = field(default=operator.ge, repr=False, init=False)

    # Primary stats that receive the "All Stats" bonus.
    _PRIMARY_STATS: frozenset[str] = field(
        default=frozenset({"STR", "DEX", "INT", "LUK"}),
        repr=False,
        init=False,
    )

    def check(self, lines: Sequence[StatLine]) -> bool:
        includes_flat = ValueProfile.is_flat_stat(self.stat)
        total = sum(
            line.value
            for line in lines
            if line.stat == self.stat and (line.is_percent or includes_flat)
        )
        if self.stat in self._PRIMARY_STATS:
            total += sum(
                line.value
                for line in lines
                if line.stat == "All Stats" and line.is_percent
            )
        return self._op(total, self.target_value)

    def describe(self) -> str:
        suffix = "" if ValueProfile.is_flat_stat(self.stat) else "%"
        return f"{self.stat} >= {self.target_value}{suffix}"


@dataclass(frozen=True)
class LineCountGoal(CombinationGoal):
    """At least *min_lines* of the equipment's lines must belong to *stats*.

    This handles goals like "any 2 lines of Attack/Boss/IED" as well as
    "1 line of Attack Power" (min_lines=1, stats={"Attack Power"}).
    """

    stats: frozenset[str]
    min_lines: int

    def check(self, lines: Sequence[StatLine]) -> bool:
        count = sum(1 for line in lines if line.stat in self.stats and line.is_percent)
        return count >= self.min_lines

    def describe(self) -> str:
        stats_str = "/".join(sorted(self.stats))
        return f"Any {self.min_lines}+ line(s) of {stats_str}"


@dataclass(frozen=True)
class AndGoal(CombinationGoal):
    """All sub-goals must be satisfied."""

    goals: tuple

    def __init__(self, goals: Sequence[CombinationGoal]):
        object.__setattr__(self, "goals", tuple(goals))

    def check(self, lines: Sequence[StatLine]) -> bool:
        return all(goal.check(lines) for goal in self.goals)

    def describe(self) -> str:
        return " AND ".join(g.describe() for g in self.goals)


@dataclass(frozen=True)
class OrGoal(CombinationGoal):
    """At least one sub-goal must be satisfied."""

    goals: tuple

    def __init__(self, goals: Sequence[CombinationGoal]):
        object.__setattr__(self, "goals", tuple(goals))

    def check(self, lines: Sequence[StatLine]) -> bool:
        return any(goal.check(lines) for goal in self.goals)

    def describe(self) -> str:
        return " OR ".join(g.describe() for g in self.goals)


# ---------------------------------------------------------------------------
# Dump-all goal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DumpAllGoal(CombinationGoal):
    """Pseudo-goal that requests enumeration of ALL valid combinations.

    When used with :meth:`CombinationGenerator.generate_for_goal`, every
    combination of 2-3 lines from the allowed stat pool is produced.
    The :meth:`check` method always returns ``True`` so that every
    combination is considered a "match".
    """

    stats: frozenset[str] = frozenset()

    def check(self, lines: Sequence[StatLine]) -> bool:
        return True

    def describe(self) -> str:
        return "Dump All Possible Combinations"
