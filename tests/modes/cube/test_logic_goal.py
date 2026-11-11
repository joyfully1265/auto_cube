"""Tests for compiling the GUI's row tree into a cube goal.

``GroupNode`` rows are compiled by ``to_goal()`` into a
:class:`CombinationGoal` tree, and the GUI feeds that goal to the
:class:`CombinationGenerator` to flag unreachable goals.  Goal *evaluation*
(``CubeGoalConfig.is_met``) is covered by ``test_goal_config`` and each goal
type's own behaviour by ``test_combination_goal``.

``TestGoalAgainstEquipment`` builds goals for the rows a cube GUI would show
and checks ``is_met`` against equipment whose stats are written out here; OCR
extraction from screenshots is covered by ``test_ocr_extraction``.
"""

import unittest

from cube.models.equipment import Equipment
from cube.models.stat_line import StatLine
from cube.modes.cube.combination_goal import AndGoal, OrGoal, SumGoal
from cube.modes.cube.combination_generator import CombinationGenerator
from cube.modes.cube.goal_config import CubeGoalConfig
from cube.modes.cube.logic_goal import AND, OR, DesiredLine, GroupNode
from cube.modes.cube.stat_combination import StatCombination

RANK = "Legendary"
LEVEL = "71-150"


def desired(*rows: tuple[str, int], operator: str = AND) -> GroupNode:
    """Build the row tree for *rows* of desired lines."""
    return GroupNode(operator, [DesiredLine(stat, value) for stat, value in rows])


def build_goal(root: GroupNode, rank: str = RANK) -> CubeGoalConfig:
    """Build the goal the GUI would run for *root*."""
    compiled = root.to_goal()
    goals = [compiled] if compiled is not None else []
    return CubeGoalConfig(
        category="Hat",
        target_rank=rank,
        goals=goals,
    )


def equipment(rank: str, *lines: tuple) -> Equipment:
    """Build equipment from *rank* and ``(stat, value[, is_percent])`` rows."""
    return Equipment(rank, [StatLine(*line) for line in lines])


def combinations_for(root: GroupNode, rank: str = RANK) -> list[StatCombination]:
    """Generate the combinations the GUI uses to flag unreachable goals."""
    compiled = root.to_goal()
    if compiled is None:
        return []
    return CombinationGenerator(LEVEL, rank).generate_for_goal(compiled)


class TestCompileAndGroup(unittest.TestCase):
    """AND rows are contributions: same-stat values are summed."""

    def test_same_stat_rows_are_summed(self):
        self.assertEqual(desired(("STR", 12), ("STR", 9)).to_goal(), SumGoal("STR", 21))

    def test_different_stats_become_an_and_goal(self):
        self.assertEqual(
            desired(("Attack Power", 12), ("Boss Damage", 30)).to_goal(),
            AndGoal([SumGoal("Attack Power", 12), SumGoal("Boss Damage", 30)]),
        )

    def test_single_row_collapses_to_a_sum_goal(self):
        self.assertEqual(desired(("STR", 12)).to_goal(), SumGoal("STR", 12))

    def test_all_stats_row_is_not_folded_into_a_primary_stat(self):
        self.assertEqual(
            desired(("STR", 9), ("All Stats", 9)).to_goal(),
            AndGoal([SumGoal("STR", 9), SumGoal("All Stats", 9)]),
        )

    def test_empty_group_compiles_to_none(self):
        self.assertIsNone(desired().to_goal())


class TestCompileOrGroup(unittest.TestCase):
    """OR rows are independent alternatives."""

    def test_each_row_is_an_alternative(self):
        self.assertEqual(
            desired(("STR", 12), ("Attack Power", 12), operator=OR).to_goal(),
            OrGoal([SumGoal("STR", 12), SumGoal("Attack Power", 12)]),
        )

    def test_single_alternative_collapses(self):
        self.assertEqual(
            desired(("STR", 12), operator=OR).to_goal(), SumGoal("STR", 12)
        )

    def test_empty_group_compiles_to_none(self):
        self.assertIsNone(desired(operator=OR).to_goal())


class TestCompileNestedGroup(unittest.TestCase):
    def test_nested_or_is_kept_inside_the_and(self):
        root = GroupNode(
            AND,
            [
                DesiredLine("STR", 12),
                DesiredLine("STR", 9),
                GroupNode(
                    OR,
                    [
                        DesiredLine("Boss Damage", 30),
                        DesiredLine("Ignore Defense", 30),
                    ],
                ),
            ],
        )
        self.assertEqual(
            root.to_goal(),
            AndGoal(
                [
                    SumGoal("STR", 21),
                    OrGoal([SumGoal("Boss Damage", 30), SumGoal("Ignore Defense", 30)]),
                ]
            ),
        )

    def test_empty_nested_group_is_skipped(self):
        root = GroupNode(AND, [DesiredLine("STR", 12), GroupNode(OR, [])])
        self.assertEqual(root.to_goal(), SumGoal("STR", 12))


class TestDescribe(unittest.TestCase):
    """The row tree summarizes itself for the GUI."""

    def test_same_stat_rows_are_shown_as_a_total(self):
        self.assertEqual(desired(("STR", 12), ("STR", 9)).describe(), "STR >= 21%")

    def test_flat_stat_has_no_percent_sign(self):
        self.assertEqual(
            desired(("Skill Cooldowns", 2)).describe(), "Skill Cooldowns >= 2"
        )

    def test_empty_group_is_any(self):
        self.assertEqual(desired().describe(), "(any)")

    def test_or_group_joins_alternatives(self):
        self.assertEqual(
            desired(("STR", 12), ("Attack Power", 12), operator=OR).describe(),
            "STR >= 12% OR Attack Power >= 12%",
        )

    def test_nested_group_is_parenthesized(self):
        root = GroupNode(
            AND,
            [
                DesiredLine("STR", 12),
                DesiredLine("STR", 9),
                GroupNode(
                    OR,
                    [
                        DesiredLine("Boss Damage", 30),
                        DesiredLine("Ignore Defense", 30),
                    ],
                ),
            ],
        )
        self.assertEqual(
            root.describe(),
            "STR >= 21% AND (Boss Damage >= 30% OR Ignore Defense >= 30%)",
        )


class TestGoalFromTree(unittest.TestCase):
    """The GUI assembles the compiled condition for the row tree."""

    def test_empty_tree_has_no_goals(self):
        self.assertEqual(build_goal(desired()).goals, [])

    def test_goal_carries_the_compiled_condition(self):
        self.assertEqual(
            build_goal(desired(("STR", 12), ("STR", 9))).goals,
            [SumGoal("STR", 21)],
        )

    def test_target_rank_is_passed_through(self):
        goal = build_goal(desired(("STR", 12)), rank="Unique")
        self.assertEqual(goal.target_rank, "Unique")


class TestCombinationsFromTree(unittest.TestCase):
    """Reachable trees produce combinations; unreachable trees produce none."""

    def setUp(self):
        self.combos = combinations_for(desired(("STR", 12), ("STR", 9)))

    def test_reachable_goal_has_combinations(self):
        self.assertTrue(self.combos)

    def test_combinations_stay_within_three_lines(self):
        for combo in self.combos:
            self.assertLessEqual(len(combo), 3)

    def test_every_combination_meets_the_total(self):
        for combo in self.combos:
            total = combo.total_for("STR") + combo.total_for("All Stats")
            self.assertGreaterEqual(total, 21)

    def test_all_stats_lines_are_candidates(self):
        self.assertTrue(any(combo.contains_stat("All Stats") for combo in self.combos))

    def test_empty_tree_has_no_combinations(self):
        self.assertEqual(combinations_for(desired()), [])

    def test_unreachable_goal_has_no_combinations(self):
        self.assertEqual(combinations_for(desired(*[("STR", 12)] * 4)), [])

    def test_rank_selects_the_line_values(self):
        combos = combinations_for(desired(("STR", 12), ("STR", 9)), rank="Unique")
        values = {line.value for combo in combos for line in combo.lines}
        self.assertLessEqual(max(values, default=0), 9)

    def test_or_goal_combinations_cover_both_alternatives(self):
        combos = combinations_for(
            desired(("STR", 12), ("Attack Power", 12), operator=OR)
        )
        self.assertTrue(any(c.contains_stat("STR") for c in combos))
        self.assertTrue(any(c.contains_stat("Attack Power") for c in combos))


class TestGoalAgainstEquipment(unittest.TestCase):
    """A goal built from GUI rows is met by equipment with those stats."""

    def test_all_stats_lines_count_towards_the_summed_stat(self):
        gear = equipment(
            "Legendary",
            ("All Stats", 10),
            ("All Stats", 10),
            ("LUK", 10),
        )
        self.assertTrue(build_goal(desired(("LUK", 12), ("LUK", 9))).is_met(gear))

    def test_summed_rows_are_checked_against_the_equipment_rank(self):
        gear = equipment("Unique", ("All Stats", 7), ("All Stats", 4), ("STR", 7))
        self.assertTrue(
            build_goal(desired(("STR", 7), ("STR", 7)), rank="Unique").is_met(gear)
        )

    def test_flat_stat_rows_are_summed(self):
        gear = equipment(
            "Legendary",
            ("LUK", 13),
            ("Skill Cooldowns", 2, False),
            ("Skill Cooldowns", 2, False),
        )
        goal = build_goal(desired(("Skill Cooldowns", 2), ("Skill Cooldowns", 2)))
        self.assertTrue(goal.is_met(gear))

    def test_goal_above_the_written_stats_is_not_met(self):
        gear = equipment("Legendary", ("STR", 12), ("STR", 9))
        self.assertFalse(build_goal(desired(("STR", 12), ("STR", 12))).is_met(gear))

    def test_goal_above_the_equipment_rank_is_not_met(self):
        gear = equipment("Epic", ("STR", 12), ("STR", 9))
        self.assertFalse(build_goal(desired(("STR", 12), ("STR", 9))).is_met(gear))


if __name__ == "__main__":
    unittest.main()
