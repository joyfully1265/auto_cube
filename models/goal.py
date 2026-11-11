"""Goal abstraction shared by every game mode.

The controller only needs three things from a goal:

* ``is_met`` - decide whether the current equipment satisfies the goal.
* ``prepare`` - seed any state that must be computed from the first read
  (e.g. a flame baseline score).
* ``describe`` - a human-readable summary for CLI output.

``describe_state`` is an optional hook for per-evaluation detail such as a
flame score breakdown.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .equipment import Equipment


class Goal(ABC):
    """Stop condition evaluated against parsed equipment."""

    @abstractmethod
    def is_met(self, equipment: Equipment) -> bool:
        """Return True when the equipment satisfies this goal."""

    def prepare(self, equipment: Equipment) -> None:
        """Seed goal state from the first equipment read. Idempotent."""

    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description of the goal."""

    def describe_state(self, equipment: Equipment) -> Optional[str]:
        """Return optional detail about the current read for logging."""
        return None
