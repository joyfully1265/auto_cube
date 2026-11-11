"""StatCombination model.

An ordered collection of :class:`PotentialLine` objects representing one
concrete way to satisfy a cubing goal (e.g. two prime Attack Power lines
and one non-prime All Stats line).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .potential_line import PotentialLine


@dataclass
class StatCombination:
    """A concrete combination of potential lines.

    Attributes:
        lines: The stat lines in this combination (order matches the
            in-game display order).
    """

    lines: List[PotentialLine] = field(default_factory=list)

    # -- Query methods ----------------------------------------------------

    def total_for(self, stat: str) -> int:
        """Sum of values for lines whose stat matches *stat* exactly."""
        return sum(line.value for line in self.lines if line.stat == stat)

    def contains_stat(self, stat: str) -> bool:
        """Return ``True`` if any line has the given *stat*."""
        return any(line.stat == stat for line in self.lines)

    def line_count_for_stats(self, stats: frozenset[str]) -> int:
        """Count lines whose stat is in the *stats* set."""
        return sum(1 for line in self.lines if line.stat in stats)

    # -- Dunder helpers ---------------------------------------------------

    def __len__(self) -> int:
        return len(self.lines)

    def __str__(self) -> str:
        if not self.lines:
            return "Empty Combination"
        return " | ".join(str(line) for line in self.lines)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StatCombination):
            return NotImplemented
        return self.lines == other.lines

    def __hash__(self) -> int:
        return hash(tuple(self.lines))
