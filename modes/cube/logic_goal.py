"""Goal tree built from the GUI's rows of desired stat lines.

Each row describes one potential line the user would accept, e.g. ``12% STR``.
Rows of an AND group are contributions: their values are summed per stat, so
``12% STR`` plus ``9% STR`` means ``STR >= 21%``.  An ``All Stats`` row is
literal - its value only ever counts as All Stats, never as a primary stat.

The tree compiles onto :mod:`combination_goal`, so evaluation reuses
:class:`SumGoal` (which adds All Stats lines to primary stats),
:class:`AndGoal` and :class:`OrGoal`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Union

from .combination_goal import AndGoal, CombinationGoal, OrGoal, SumGoal
from .value_profile import ValueProfile

AND = "AND"
OR = "OR"


@dataclass(frozen=True)
class DesiredLine:
    """One desired stat line, e.g. ``STR 12``."""

    stat: str
    value: int


@dataclass(frozen=True)
class GroupNode:
    """An AND/OR group of desired lines and nested groups.

    AND: rows are contributions summed per stat.  OR: every row is an
    independent alternative.
    """

    operator: str
    items: List[Union["GroupNode", DesiredLine]] = field(default_factory=list)

    def to_goal(self) -> Optional[CombinationGoal]:
        """Compile this group into a ``CombinationGoal``, or ``None`` if empty."""
        if self.operator == OR:
            goals: List[CombinationGoal] = []
            for item in self.items:
                goal = (
                    item.to_goal()
                    if isinstance(item, GroupNode)
                    else SumGoal(item.stat, item.value)
                )
                if goal is not None:
                    goals.append(goal)
            return _combine(goals, OrGoal)

        totals: Dict[str, int] = {}
        groups: List[CombinationGoal] = []
        for item in self.items:
            if isinstance(item, GroupNode):
                goal = item.to_goal()
                if goal is not None:
                    groups.append(goal)
            else:
                totals[item.stat] = totals.get(item.stat, 0) + item.value
        goals = [SumGoal(stat, total) for stat, total in totals.items()]
        return _combine(goals + groups, AndGoal)

    def describe(self) -> str:
        """Return a human-readable summary, e.g. ``STR >= 21%``."""
        if not self.items:
            return "(any)"
        if self.operator == OR:
            parts = [_item_text(item) for item in self.items]
            return " OR ".join(parts)

        totals: Dict[str, int] = {}
        nested: List[str] = []
        for item in self.items:
            if isinstance(item, GroupNode):
                description = item.describe()
                if description != "(any)":
                    nested.append(f"({description})")
            else:
                totals[item.stat] = totals.get(item.stat, 0) + item.value
        parts = [_sum_text(stat, total) for stat, total in totals.items()]
        return " AND ".join(parts + nested)


def _combine(
    goals: Sequence[CombinationGoal],
    factory: Callable[[Sequence[CombinationGoal]], CombinationGoal],
) -> Optional[CombinationGoal]:
    """Wrap *goals* in *factory*, collapsing zero and one-element groups."""
    if not goals:
        return None
    if len(goals) == 1:
        return goals[0]
    return factory(goals)


def _item_text(item: Union[GroupNode, DesiredLine]) -> str:
    """Render one group item for :meth:`GroupNode.describe`."""
    if isinstance(item, GroupNode):
        description = item.describe()
        return "(any)" if description == "(any)" else f"({description})"
    return _sum_text(item.stat, item.value)


def _sum_text(stat: str, total: int) -> str:
    """Render a per-stat requirement, e.g. ``STR >= 21%``."""
    suffix = "" if ValueProfile.is_flat_stat(stat) else "%"
    return f"{stat} >= {total}{suffix}"
