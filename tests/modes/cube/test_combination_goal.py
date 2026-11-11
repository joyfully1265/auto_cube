"""Tests for the CombinationGoal hierarchy.

Each goal's own ``check``/``describe`` behaviour is covered here; the
integration with :class:`CubeGoalConfig` lives in ``test_goal_config.py`` and
combination generation in ``test_combination_generator.py``.
"""

import unittest

from cube.models.stat_line import StatLine
from cube.modes.cube.combination_goal import (
    AndGoal,
    DumpAllGoal,
    LineCountGoal,
    OrGoal,
    SumGoal,
)

# ===========================================================================
# SumGoal
# ===========================================================================


class TestSumGoal(unittest.TestCase):
    def test_sum_attack_power(self):
        goal = SumGoal("Attack Power", 21)
        lines = [
            StatLine("Attack Power", 12),
            StatLine("Attack Power", 12),
        ]
        self.assertTrue(goal.check(lines))

    def test_not_met(self):
        goal = SumGoal("Attack Power", 36)
        lines = [
            StatLine("Attack Power", 12),
            StatLine("Attack Power", 12),
        ]
        self.assertFalse(goal.check(lines))

    def test_sum_all_stats(self):
        for stat in ["STR", "DEX", "INT", "LUK"]:
            goal = SumGoal(stat, 21)
            lines = [
                StatLine(stat, 12),
                StatLine("All Stats", 9),
            ]
            self.assertTrue(goal.check(lines))

    def test_all_stats_vs_attack(self):
        goal = SumGoal("Attack Power", 10)
        lines = [StatLine("All Stats", 12)]
        self.assertFalse(goal.check(lines))

    def test_describe(self):
        goal = SumGoal("Attack Power", 21)
        self.assertEqual(goal.describe(), "Attack Power >= 21%")


# ===========================================================================
# LineCountGoal
# ===========================================================================


class TestLineCountGoal(unittest.TestCase):
    def test_2_of_3(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}),
            min_lines=2,
        )
        lines = [
            StatLine("Ignore Defense", 30),
            StatLine("Boss Damage", 40),
        ]
        self.assertTrue(goal.check(lines))

    def test_2_of_3_dupe(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}),
            min_lines=2,
        )
        lines = [
            StatLine("Boss Damage", 40),
            StatLine("Boss Damage", 40),
        ]
        self.assertTrue(goal.check(lines))

    def test_2_of_3_superset(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}),
            min_lines=2,
        )
        lines = [
            StatLine("Ignore Defense", 30),
            StatLine("Boss Damage", 40),
            StatLine("Boss Damage", 30),
        ]
        self.assertTrue(goal.check(lines))

    def test_any_3(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}),
            min_lines=3,
        )
        lines = [
            StatLine("Attack Power", 12),
            StatLine("Boss Damage", 40),
            StatLine("Ignore Defense", 30),
        ]
        self.assertTrue(goal.check(lines))

    def test_any_3_fails(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}),
            min_lines=3,
        )
        lines = [
            StatLine("Ignore Defense", 30),
            StatLine("Boss Damage", 40),
        ]
        self.assertFalse(goal.check(lines))

    def test_describe(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage"}),
            min_lines=2,
        )
        desc = goal.describe()
        self.assertIn("2", desc)
        self.assertIn("Attack Power", desc)
        self.assertIn("Boss Damage", desc)


# ===========================================================================
# AndGoal
# ===========================================================================


class TestAndGoal(unittest.TestCase):
    def test_21_atk_with_ied(self):
        """21%+ Attack AND 1 line IED."""
        goal = AndGoal(
            [
                SumGoal("Attack Power", 21),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        # Pass: 24% Atk + IED
        lines = [
            StatLine("Attack Power", 12),
            StatLine("Attack Power", 12),
            StatLine("Ignore Defense", 12),
        ]
        self.assertTrue(goal.check(lines))

    def test_21_atk_with_ied_fails_without_ied(self):
        goal = AndGoal(
            [
                SumGoal("Attack Power", 21),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        lines = [
            StatLine("Attack Power", 12),
            StatLine("Attack Power", 12),
            StatLine("Boss Damage", 12),
        ]
        self.assertFalse(goal.check(lines))

    def test_21_atk_with_boss_line(self):
        goal = AndGoal(
            [
                SumGoal("Attack Power", 21),
                LineCountGoal(frozenset({"Boss Damage"}), 1),
            ]
        )
        lines = [
            StatLine("Attack Power", 12),
            StatLine("Attack Power", 12),
            StatLine("Boss Damage", 12),
        ]
        self.assertTrue(goal.check(lines))

    def test_1l_atk_plus_1l_of_boss_ied(self):
        """1L Atk + 1L of (Boss/IED)."""
        goal = AndGoal(
            [
                LineCountGoal(frozenset({"Attack Power"}), 1),
                LineCountGoal(frozenset({"Boss Damage", "Ignore Defense"}), 1),
            ]
        )
        lines = [
            StatLine("Attack Power", 12),
            StatLine("Boss Damage", 12),
        ]
        self.assertTrue(goal.check(lines))

    def test_describe(self):
        goal = AndGoal(
            [
                SumGoal("Attack Power", 21),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        desc = goal.describe()
        self.assertIn("AND", desc)


# ===========================================================================
# OrGoal
# ===========================================================================


class TestOrGoal(unittest.TestCase):
    def test_boss_or_ied(self):
        """1 line of Boss OR IED."""
        goal = OrGoal(
            [
                LineCountGoal(frozenset({"Boss Damage"}), 1),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        # Pass with Boss
        lines = [StatLine("Boss Damage", 12)]
        self.assertTrue(goal.check(lines))

    def test_boss_or_ied_passes_with_ied(self):
        goal = OrGoal(
            [
                LineCountGoal(frozenset({"Boss Damage"}), 1),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        lines = [StatLine("Ignore Defense", 12)]
        self.assertTrue(goal.check(lines))

    def test_boss_or_ied_fails_with_neither(self):
        goal = OrGoal(
            [
                LineCountGoal(frozenset({"Boss Damage"}), 1),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        lines = [StatLine("Attack Power", 12)]
        self.assertFalse(goal.check(lines))

    def test_describe(self):
        goal = OrGoal(
            [
                LineCountGoal(frozenset({"Boss Damage"}), 1),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        desc = goal.describe()
        self.assertIn("OR", desc)


# ===========================================================================
# DumpAllGoal
# ===========================================================================


class TestDumpAllGoal(unittest.TestCase):
    def test_check_always_true(self):
        goal = DumpAllGoal(stats=frozenset({"Attack Power", "Boss Damage"}))
        self.assertTrue(goal.check([]))
        self.assertTrue(goal.check([StatLine("Attack Power", 12)]))
        self.assertTrue(
            goal.check(
                [
                    StatLine("Attack Power", 12),
                    StatLine("Boss Damage", 30),
                    StatLine("Ignore Defense", 12),
                ]
            )
        )

    def test_describe(self):
        goal = DumpAllGoal()
        self.assertEqual(goal.describe(), "Dump All Possible Combinations")

    def test_default_stats_empty(self):
        goal = DumpAllGoal()
        self.assertEqual(goal.stats, frozenset())


# ===========================================================================
# Operator overloading (& and |)
# ===========================================================================


class TestGoalOperators(unittest.TestCase):
    def test_and_operator(self):
        a = SumGoal("Attack Power", 21)
        b = LineCountGoal(frozenset({"Ignore Defense"}), 1)
        combined = a & b
        self.assertIsInstance(combined, AndGoal)
        self.assertEqual(len(combined.goals), 2)

    def test_or_operator(self):
        a = LineCountGoal(frozenset({"Boss Damage"}), 1)
        b = LineCountGoal(frozenset({"Ignore Defense"}), 1)
        combined = a | b
        self.assertIsInstance(combined, OrGoal)
        self.assertEqual(len(combined.goals), 2)


# ===========================================================================
# Flat stats (e.g. cooldowns)
# ===========================================================================


class TestCooldownStat(unittest.TestCase):
    def test_sum_goal_cooldown(self):
        goal = SumGoal("Skill Cooldowns", 2)
        lines = [StatLine("Skill Cooldowns", 2, is_percent=False)]
        self.assertTrue(goal.check(lines))

    def test_sum_goal_cooldown_one_second_fails_two_second_goal(self):
        goal = SumGoal("Skill Cooldowns", 2)
        lines = [StatLine("Skill Cooldowns", 1, is_percent=False)]
        self.assertFalse(goal.check(lines))

    def test_sum_goal_cooldown_multiple_lines(self):
        goal = SumGoal("Skill Cooldowns", 4)
        lines = [
            StatLine("Skill Cooldowns", 2, is_percent=False),
            StatLine("Skill Cooldowns", 2, is_percent=False),
        ]
        self.assertTrue(goal.check(lines))

    def test_sum_goal_cooldown_description_has_no_percent(self):
        self.assertEqual(
            SumGoal("Skill Cooldowns", 2).describe(), "Skill Cooldowns >= 2"
        )


# ===========================================================================
# Percentage-only filtering
# ===========================================================================


class TestGoalPercentFiltering(unittest.TestCase):
    """Validate that goals only count percentage-based stat lines."""

    def test_line_count_goal_excludes_flat_lines(self):
        """Attack Power flat line should not count toward a 2-line goal."""
        goal = LineCountGoal(frozenset({"Attack Power", "Boss Damage"}), 2)
        lines = [
            StatLine("Attack Power", 32, is_percent=False),  # flat – excluded
            StatLine("Attack Power", 9, is_percent=True),  # % – should count
        ]
        self.assertFalse(goal.check(lines))

    def test_line_count_goal_includes_percent_lines(self):
        """Two % lines of the target stats should still satisfy the goal."""
        goal = LineCountGoal(frozenset({"Attack Power", "Boss Damage"}), 2)
        lines = [
            StatLine("Attack Power", 9, is_percent=True),
            StatLine("Boss Damage", 30, is_percent=True),
        ]
        self.assertTrue(goal.check(lines))

    def test_line_count_goal_flat_and_percent_count_as_one(self):
        """One flat + one % Attack Power should count as 1, not 2."""
        goal = LineCountGoal(frozenset({"Attack Power"}), 2)
        lines = [
            StatLine("Attack Power", 32, is_percent=False),
            StatLine("Attack Power", 9, is_percent=True),
        ]
        self.assertFalse(goal.check(lines))

    def test_sum_goal_excludes_flat_lines(self):
        """Flat lines should not contribute to SumGoal totals."""
        goal = SumGoal("Attack Power", 9)
        lines = [
            StatLine("Attack Power", 32, is_percent=False),  # excluded
            StatLine("Attack Power", 9, is_percent=True),  # 9% – meets goal
        ]
        self.assertTrue(goal.check(lines))

    def test_sum_goal_flat_only_fails(self):
        """Only flat lines should not satisfy a % SumGoal."""
        goal = SumGoal("Attack Power", 10)
        lines = [
            StatLine("Attack Power", 32, is_percent=False),
            StatLine("Attack Power", 20, is_percent=False),
        ]
        self.assertFalse(goal.check(lines))


if __name__ == "__main__":
    unittest.main()
