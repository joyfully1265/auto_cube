"""GoalConfigBuilder service.

Builds :class:`GoalConfig` objects from user input.  Each goal selection
string is parsed into a :class:`CombinationGoal`.
"""

from typing import Optional

from .goal_config import CubeGoalConfig
from .combination_goal import (
    CombinationGoal,
    SumGoal,
    LineCountGoal,
    AndGoal,
)
from ...core.config_loader import ConfigLoader


class GoalConfigBuilder:
    """Builds GoalConfig objects from user input and configuration data."""

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        self.config_loader = config_loader or ConfigLoader()

    def build_goal_config(
        self,
        category: str,
        target_stat: str,
        goal_selection: str,
        target_rank: str = "Legendary",
    ) -> CubeGoalConfig:
        """Build a CubeGoalConfig from user selections."""
        goal = self._parse_goal_selection(goal_selection, target_stat)
        return CubeGoalConfig(
            category=category,
            target_rank=target_rank,
            goals=[goal],
        )

    # -- Goal parsing ----------------------------------------------------

    # -- Stat-name abbreviation map --------------------------------------
    # Maps short names used in goal strings to full stat names.
    _STAT_ALIASES: dict[str, str] = {
        "Atk": "Attack Power",
        "Boss": "Boss Damage",
        "IED": "Ignore Defense",
        "Drop": "Item Drop Rate",
        "Meso": "Mesos Obtained",
    }

    def _resolve_stat(self, name: str) -> str:
        """Resolve a possibly-abbreviated stat name to its full form."""
        name = name.strip()
        if name in self._STAT_ALIASES:
            return self._STAT_ALIASES[name]
        return name

    # -- Standard goal string format ------------------------------------
    # All goal strings use a single consistent format:
    #
    #   SumGoal:          "X%+ Stat"
    #   Paired sums:      "X%+ Stat and Y%+ Stat"
    #   SumAndLine:       "X%+ Stat and Stat"
    #   LineCountGoal:    "N Line Stat or Stat or ..."
    #   LineCount AND:    "N Line Stat + N Line Stat"
    #   LineCount with set: "N Line Stat with N Line Stat or Stat or ..."
    #
    # Stats use short aliases (Atk, Boss, IED) resolved via _STAT_ALIASES.

    def _parse_goal_selection(
        self,
        goal_selection: str,
        target_stat: str,
    ) -> CombinationGoal:
        """Parse a goal-selection string into a ``CombinationGoal``."""

        # "X%+ A and Y%+ B" paired sums
        if " and " in goal_selection and goal_selection.count("%+") >= 2:
            return self._parse_paired_sum(goal_selection)

        # "X%+ A and Stat" hybrid (sum + single line requirement)
        if "%+" in goal_selection and " and " in goal_selection:
            return self._parse_sum_and_line(goal_selection)

        # "X%+ Stat" simple sum goals
        if "%+" in goal_selection:
            val = int(goal_selection.split("%")[0])
            return SumGoal(stat=target_stat, target_value=val)

        # "N Line Stat or Stat with M Line Stat" line-count-set + paired line
        if " with " in goal_selection and " or " in goal_selection.split(" with ")[0]:
            return self._parse_line_count_set_paired_line(goal_selection)

        # "N Line Stat with M Line Stat or Stat or ..." paired line + line-set
        if " with " in goal_selection:
            return self._parse_paired_line_set(goal_selection)

        # "N Line X + M Line Y" paired line counts
        if "+" in goal_selection:
            return self._parse_paired_lines(goal_selection)

        # "N Line Stat and N Line Stat or Stat" line-count AND line-count
        if " and " in goal_selection and "Line" in goal_selection:
            return self._parse_line_count_and_line_count(goal_selection)

        # "N Line Stat or Stat or ..." line-count from set
        if "Line" in goal_selection:
            return self._parse_line_count_set(goal_selection)

        # Fallback
        return SumGoal(stat=target_stat, target_value=0)

    def _parse_sum_and_line(self, text: str) -> AndGoal:
        """Parse 'X%+ Stat and Stat' into AndGoal(SumGoal, LineCountGoal)."""
        left, right = text.split(" and ", 1)
        val = int(left.split("%")[0].strip())
        stat_left = self._resolve_stat(left.split("+", 1)[1].strip())
        stat_right = self._resolve_stat(right.strip())
        return AndGoal(
            [
                SumGoal(stat=stat_left, target_value=val),
                LineCountGoal(stats=frozenset({stat_right}), min_lines=1),
            ]
        )

    def _parse_line_count_and_line_count(self, text: str) -> AndGoal:
        """Parse 'N Line Stat and N Line Stat or Stat or ...' into AndGoal."""
        left, right = text.split(" and ", 1)
        # Parse each side as a line-count goal string
        left_goal = self._parse_line_count_set(left.strip())
        right_goal = self._parse_line_count_set(right.strip())
        return AndGoal([left_goal, right_goal])

    # Primary stats that "Stat" expands to in accessory goals.
    _PRIMARY_STATS: frozenset[str] = frozenset({"STR", "DEX", "INT", "LUK"})

    def _parse_line_count_set(self, text: str) -> LineCountGoal:
        """Parse 'N Line Stat or Stat or ...' into a LineCountGoal."""
        # Split on " or " — first token is "N Line Stat", rest are "Stat"
        tokens = text.split(" or ")
        first_parts = tokens[0].strip().split("Line", 1)
        num = int(first_parts[0].strip())
        raw_stats = [first_parts[1].strip().rstrip("%")]
        for token in tokens[1:]:
            raw_stats.append(token.strip().rstrip("%"))
        # Expand "Stat" to all primary stats; resolve aliases for others.
        expanded: list[str] = []
        for s in raw_stats:
            resolved = self._resolve_stat(s)
            if resolved == "Stat":
                expanded.extend(sorted(self._PRIMARY_STATS))
            else:
                expanded.append(resolved)
        return LineCountGoal(
            stats=frozenset(expanded),
            min_lines=num,
        )

    def _parse_line_count_set_paired_line(self, text: str) -> CombinationGoal:
        """Parse 'N Line Stat or Stat with M Line Stat' into ANDed LineCountGoals."""
        left, right = text.split(" with ", 1)
        # Left side: "N Line Stat or Stat or ..."
        tokens = left.split(" or ")
        first_parts = tokens[0].strip().split("Line", 1)
        lines_a = int(first_parts[0].strip())
        raw_stats_a = [first_parts[1].strip().rstrip("%")]
        for token in tokens[1:]:
            raw_stats_a.append(token.strip().rstrip("%"))
        # Resolve aliases (but don't expand "Stat" — single-stat on right)
        stats_a = frozenset(self._resolve_stat(s) for s in raw_stats_a)
        # Right side: "M Line Stat"
        lines_b, stat_b = self._parse_line_part(right.strip())
        return AndGoal(
            [
                LineCountGoal(stats_a, lines_a),
                LineCountGoal(frozenset({stat_b}), lines_b),
            ]
        )

    def _parse_paired_line_set(self, text: str) -> CombinationGoal:
        """Parse 'N Line Stat with N Line Stat or Stat or ...' into ANDed LineCountGoals."""
        left, right = text.split(" with ", 1)
        lines_a, stat_a = self._parse_line_part(left.strip())
        right_parts = right.split("Line", 1)
        lines_b = int(right_parts[0].strip())
        stats = [s.strip().rstrip("%") for s in right_parts[1].strip().split(" or ")]
        stats_b = frozenset(self._resolve_stat(s) for s in stats)
        return AndGoal(
            [
                LineCountGoal(frozenset({stat_a}), lines_a),
                LineCountGoal(stats_b, lines_b),
            ]
        )

    def _parse_paired_lines(self, text: str) -> CombinationGoal:
        """Parse 'N Line Stat + N Line Stat' into two ANDed ``LineCountGoal``s."""
        left, right = text.split("+")
        lines_a, stat_a = self._parse_line_part(left.strip())
        lines_b, stat_b = self._parse_line_part(right.strip())
        return AndGoal(
            [
                LineCountGoal(frozenset({stat_a}), lines_a),
                LineCountGoal(frozenset({stat_b}), lines_b),
            ]
        )

    def _parse_line_part(self, text: str) -> tuple[int, str]:
        """Parse 'N Line Stat' -> (N, resolved_stat)."""
        parts = text.split("Line", 1)
        num = int(parts[0].strip())
        stat = parts[1].strip().rstrip("%")
        return num, self._resolve_stat(stat)

    def _parse_paired_sum(self, text: str) -> CombinationGoal:
        """Parse 'X%+ Stat and Y%+ Stat' into two ANDed ``SumGoal``s."""
        left, right = text.split(" and ")
        target_a, stat_a = self._parse_sum_part(left.strip())
        target_b, stat_b = self._parse_sum_part(right.strip())
        return AndGoal([SumGoal(stat_a, target_a), SumGoal(stat_b, target_b)])

    def _parse_sum_part(self, text: str) -> tuple[int, str]:
        """Parse 'X%+ Stat' -> (X, resolved_stat)."""
        pct_part, stat = text.split("+", 1)
        val = int(pct_part.replace("%", "").strip())
        return val, self._resolve_stat(stat.strip())

    def validate_category(self, category: str) -> bool:
        """Validate that the selected category exists."""
        categories = self.config_loader.load_categories()
        return category in categories

    def validate_level_range(self, level_range: str) -> bool:
        """Validate level range selection."""
        return level_range in ["71-150", "151+"]

    def validate_stat_for_category(self, category: str, stat: str) -> bool:
        """Validate that stat is allowed for the category."""
        categories = self.config_loader.load_categories()
        allowed_stats = categories.get(category, [])
        return stat in allowed_stats
