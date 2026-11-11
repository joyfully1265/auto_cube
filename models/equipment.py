"""Equipment model.

Represents a parsed piece of equipment with its stat lines and, for potential
(cube) windows, the current rank. Flame windows have no rank, so it is optional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .stat_line import StatLine


@dataclass
class Equipment:
    """Parsed equipment with optional rank and stat lines."""

    rank: Optional[str] = None
    lines: List[StatLine] = field(default_factory=list)

    def __str__(self) -> str:
        lines_str = "\n  ".join(str(line) for line in self.lines)
        if self.rank is None:
            return f"Equipment\n  Lines:\n  {lines_str}"
        return f"Equipment(rank={self.rank})\n  Lines:\n  {lines_str}"
