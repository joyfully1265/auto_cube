"""Cube (potential) goal configuration.

The stop condition is the current rank plus every combination goal passing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ...models.equipment import Equipment
from ...models.goal import Goal
from ...models.ranks import rank_at_least
from .combination_goal import CombinationGoal


@dataclass
class CubeGoalConfig(Goal):
    """Configuration for a cube goal."""

    category: str
    target_rank: str
    goals: List[CombinationGoal]

    def __str__(self) -> str:
        if self.goals:
            goals_str = "\n  ".join(goal.describe() for goal in self.goals)
            goals_section = f"  Goals:\n  {goals_str}"
        else:
            goals_section = "  Goals: Rank only (any stats)"

        return (
            f"GoalConfig:\n"
            f"  Category: {self.category}\n"
            f"  Target Rank: {self.target_rank}\n"
            f"{goals_section}"
        )

    def describe(self) -> str:
        return str(self)

    def is_met(self, equipment: Equipment) -> bool:
        """Return True when the rank is at least the target and every goal passes."""
        if not rank_at_least(equipment.rank, self.target_rank):
            return False

        return all(goal.check(equipment.lines) for goal in self.goals)
