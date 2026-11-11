"""CombinationGenerator service.

Generates :class:`StatCombination` objects for various goal types.
Uses :class:`ValueProfile` for level-dependent line values.
"""

import itertools
from typing import List, FrozenSet, Optional

from .value_profile import ValueProfile
from .potential_line import PotentialLine
from .stat_combination import StatCombination
from .combination_goal import (
    CombinationGoal,
    SumGoal,
    LineCountGoal,
    AndGoal,
    OrGoal,
    DumpAllGoal,
)


class CombinationGenerator:
    """Generates valid stat combinations based on cube rules."""

    def __init__(self, level_range: str, tier: str = "Legendary"):
        """
        Args:
            level_range: "71-150" or "151+".
            tier: Potential rank: Epic, Unique or Legendary.
        """
        self.profile = ValueProfile.for_level_range(level_range, tier)

    # -- Public API -------------------------------------------------------

    def generate_for_goal(
        self, goal: CombinationGoal, allowed_stats: Optional[FrozenSet[str]] = None
    ) -> List[StatCombination]:
        """Dispatch to the correct generator for *goal*'s type."""
        if isinstance(goal, SumGoal):
            return self._generate_for_sum(goal)
        if isinstance(goal, LineCountGoal):
            return self._generate_for_line_count(goal)
        if isinstance(goal, AndGoal):
            return self._generate_for_and(goal, allowed_stats)
        if isinstance(goal, OrGoal):
            return self._generate_for_or(goal, allowed_stats)
        if isinstance(goal, DumpAllGoal):
            stats = list(goal.stats) if goal.stats else []
            return self.generate_all_combinations(stats)
        raise TypeError(f"Unsupported goal type: {type(goal).__name__}")

    def generate_all_combinations(
        self, allowed_stats: List[str]
    ) -> List[StatCombination]:
        """Generate every valid 2-3 line combination from *allowed_stats*.

        For each allowed stat both a prime and a non-prime line is created,
        then all combinations-with-replacement of 2 and 3 lines are
        produced.  Single-line combinations are excluded since they are
        rarely useful for cubing goals.  Duplicate combinations are
        deduplicated via a set keyed on the tuple of lines.
        """
        # Build candidate pool using correct line values per stat.
        candidates: List[PotentialLine] = []
        for stat in allowed_stats:
            candidates.extend(self._candidate_lines_for(stat))

        results: List[StatCombination] = []
        seen: set[tuple[PotentialLine, ...]] = set()

        for r in range(2, 4):
            for combo in itertools.combinations_with_replacement(candidates, r):
                key = combo
                if key not in seen:
                    seen.add(key)
                    results.append(StatCombination(lines=list(combo)))

        return results

    def get_useful_stats_group(self, allowed_stats: List[str]) -> List[str]:
        """Identify damage-oriented stats for dynamic combo generation."""
        damage = {
            "Attack Power",
            "Magic ATT",
            "Boss Damage",
            "Ignore Defense",
            "Damage",
        }
        return [s for s in allowed_stats if s in damage]

    # -- Candidate-line helper -------------------------------------------

    def line_values_for(self, stat: str) -> List[int]:
        """Return the possible line values for *stat* at this level range and tier.

        Standard stats use the profile's prime and non-prime values;
        All Stats rolls one rank lower; Boss Damage and Ignore Defense use
        their own fixed values.
        """
        if ValueProfile.is_boss_damage(stat):
            return list(ValueProfile.boss_damage_values())
        if ValueProfile.is_ignore_defense(stat):
            return list(ValueProfile.ignore_defense_values())
        if ValueProfile.is_critical_damage(stat):
            return list(self.profile.critical_damage_line_values)
        if ValueProfile.is_all_stats(stat):
            return list(self.profile.all_stats_line_values)
        if ValueProfile.is_flat_stat(stat):
            return list(self.profile.flat_line_values)
        return list(self.profile.line_values)

    def _candidate_lines_for(self, stat: str) -> list[PotentialLine]:
        """Return the candidate lines for *stat* at this level range and tier."""
        return [PotentialLine(stat, value) for value in self.line_values_for(stat)]

    def get_max_possible_value(self) -> int:
        """Maximum total for a single stat across three prime lines."""
        return self.profile.max_single_stat

    # -- SumGoal ---------------------------------------------------------

    def _generate_for_sum(self, goal: SumGoal) -> List[StatCombination]:
        """Generate combinations where the sum of *goal.stat* >= *goal.target_value*."""
        target_stat = goal.stat

        # Build candidate lines for the target stat.
        candidates = self._candidate_lines_for(target_stat)
        if target_stat in {"STR", "DEX", "INT", "LUK"}:
            candidates = candidates + self._candidate_lines_for("All Stats")

        results: List[StatCombination] = []
        for r in range(1, 4):
            for combo in itertools.combinations_with_replacement(candidates, r):
                total = sum(line.value for line in combo if line.stat == target_stat)
                if target_stat in {"STR", "DEX", "INT", "LUK"}:
                    total += sum(
                        line.value for line in combo if line.stat == "All Stats"
                    )
                if total >= goal.target_value:
                    results.append(StatCombination(lines=list(combo)))
        return results

    # -- LineCountGoal ---------------------------------------------------

    def _generate_for_line_count(self, goal: LineCountGoal) -> List[StatCombination]:
        """Generate combinations with at least *goal.min_lines* from *goal.stats*."""
        # Candidate lines for each stat in the goal's stat set.
        candidates: list[PotentialLine] = []
        for stat in goal.stats:
            candidates.extend(self._candidate_lines_for(stat))

        results: List[StatCombination] = []
        for r in range(goal.min_lines, 4):
            for combo in itertools.combinations_with_replacement(candidates, r):
                count = sum(1 for line in combo if line.stat in goal.stats)
                if count >= goal.min_lines:
                    results.append(StatCombination(lines=list(combo)))
        return results

    # -- AndGoal ---------------------------------------------------------

    def _generate_for_and(
        self, goal: AndGoal, allowed_stats: Optional[FrozenSet[str]]
    ) -> List[StatCombination]:
        """Generate combinations satisfying all sub-goals.

        Strategy: generate for each sub-goal independently, then merge
        combinations that don't exceed 3 total lines.
        """
        sub_combos = [self.generate_for_goal(g, allowed_stats) for g in goal.goals]
        if not sub_combos:
            return []

        # Start with the first sub-goal's combos and iteratively merge.
        results: List[StatCombination] = sub_combos[0]
        for next_combos in sub_combos[1:]:
            merged: List[StatCombination] = []
            seen_merge: set[tuple[PotentialLine, ...]] = set()
            for a in results:
                for b in next_combos:
                    combined_lines = a.lines + b.lines
                    if len(combined_lines) <= 3:
                        key = tuple(combined_lines)
                        if key not in seen_merge:
                            seen_merge.add(key)
                            merged.append(StatCombination(lines=combined_lines))
            results = merged
        return results

    # -- OrGoal ----------------------------------------------------------

    def _generate_for_or(
        self, goal: OrGoal, allowed_stats: Optional[FrozenSet[str]]
    ) -> List[StatCombination]:
        """Generate combinations satisfying any sub-goal (union)."""
        results: List[StatCombination] = []
        seen: set[tuple[PotentialLine, ...]] = set()
        for g in goal.goals:
            for combo in self.generate_for_goal(g, allowed_stats):
                key = tuple(combo.lines)
                if key not in seen:
                    seen.add(key)
                    results.append(combo)
        return results
