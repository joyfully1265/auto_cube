"""Tests for CubeGoalConfig: construction, description, and ``is_met``."""

import unittest

from cube.models.equipment import Equipment
from cube.models.stat_line import StatLine
from cube.modes.cube.combination_goal import (
    AndGoal,
    LineCountGoal,
    OrGoal,
    SumGoal,
)
from cube.modes.cube.goal_config import CubeGoalConfig as GoalConfig

# ===========================================================================
# GoalConfig.is_met — Integration Tests
# ===========================================================================


class TestGoalConfigIsMet(unittest.TestCase):
    """Integration tests for GoalConfig.is_met against Equipment."""

    def setUp(self):
        self.stat_line1 = StatLine("Attack Power", 15)
        self.stat_line2 = StatLine("Boss Damage", 10)
        self.stat_line3 = StatLine("All Stats", 5)
        self.equipment = Equipment(
            "Legendary",
            [self.stat_line1, self.stat_line2, self.stat_line3],
        )

    def _make_config(self, goals):
        return GoalConfig(
            category="Weapon",
            target_rank="Legendary",
            goals=goals,
        )

    # -- Rank check -------------------------------------------------------

    def test_met_equal_rank(self):
        """A config with no stat goals is met when the rank matches."""
        config = self._make_config([])
        self.assertTrue(config.is_met(self.equipment))

    def test_met_greater_rank(self):
        """A config with no stat goals is met when the rank is above target."""
        config = GoalConfig(
            category="Weapon",
            target_rank="Epic",
            goals=[],
        )
        equipment = Equipment("Unique", [StatLine("STR", 3)])
        self.assertTrue(config.is_met(equipment))

    def test_not_met_lower_rank(self):
        """A config with no stat goals is not met when the rank is below target."""
        config = self._make_config([])
        equipment = Equipment("Unique", [StatLine("STR", 12)])
        self.assertFalse(config.is_met(equipment))

    def test_not_met_unknown_rank(self):
        """An unreadable rank never counts as a hit."""
        config = GoalConfig(
            category="Weapon",
            target_rank="Epic",
            goals=[],
        )
        equipment = Equipment(None, [StatLine("STR", 3)])
        self.assertFalse(config.is_met(equipment))

    def test_greater_rank_still_requires_the_goals(self):
        """A rank above target does not by itself satisfy the config."""
        config = GoalConfig(
            category="Weapon",
            target_rank="Epic",
            goals=[SumGoal("STR", 21)],
        )
        equipment = Equipment("Unique", [StatLine("STR", 12)])
        self.assertFalse(config.is_met(equipment))

    # -- SumGoal evaluation -----------------------------------------------

    def test_sum_goal_met(self):
        config = self._make_config([SumGoal("Attack Power", 15)])
        self.assertTrue(config.is_met(self.equipment))

    def test_sum_goal_not_met(self):
        config = self._make_config([SumGoal("Attack Power", 20)])
        self.assertFalse(config.is_met(self.equipment))

    def test_sum_goal_accumulates_lines_of_the_same_stat(self):
        """The total is summed across every line of the stat."""
        config = self._make_config([SumGoal("STR", 21)])
        equipment = Equipment(
            "Legendary",
            [StatLine("STR", 12), StatLine("STR", 9)],
        )
        self.assertTrue(config.is_met(equipment))

    def test_all_stats_contributes_to_str(self):
        config = self._make_config([SumGoal("STR", 21)])
        equipment = Equipment(
            "Legendary",
            [StatLine("STR", 12), StatLine("All Stats", 9)],
        )
        self.assertTrue(config.is_met(equipment))

    def test_all_stats_goal_only_counts_all_stats_lines(self):
        config = self._make_config([SumGoal("All Stats", 9)])
        equipment = Equipment(
            "Legendary",
            [StatLine("STR", 12), StatLine("STR", 9)],
        )
        self.assertFalse(config.is_met(equipment))

    def test_flat_stat_goal_counts_non_percent_lines(self):
        config = self._make_config([SumGoal("Skill Cooldowns", 2)])
        equipment = Equipment(
            "Legendary",
            [StatLine("Skill Cooldowns", 2, is_percent=False)],
        )
        self.assertTrue(config.is_met(equipment))

    def test_percent_stat_goal_ignores_flat_lines(self):
        """A flat Attack Power line never contributes to the % total."""
        config = self._make_config([SumGoal("Attack Power", 9)])
        equipment = Equipment(
            "Legendary",
            [StatLine("Attack Power", 32, is_percent=False)],
        )
        self.assertFalse(config.is_met(equipment))

    # -- LineCountGoal evaluation -----------------------------------------

    def test_line_count_met(self):
        config = self._make_config(
            [LineCountGoal(frozenset({"Attack Power", "Boss Damage"}), 2)]
        )
        self.assertTrue(config.is_met(self.equipment))

    def test_line_count_not_met(self):
        config = self._make_config(
            [LineCountGoal(frozenset({"Attack Power", "Boss Damage"}), 3)]
        )
        self.assertFalse(config.is_met(self.equipment))

    # -- AndGoal evaluation -----------------------------------------------

    def test_and_goal_both_met(self):
        config = self._make_config(
            [
                AndGoal(
                    [
                        SumGoal("Attack Power", 15),
                        SumGoal("Boss Damage", 10),
                    ]
                )
            ]
        )
        self.assertTrue(config.is_met(self.equipment))

    def test_and_goal_one_fails(self):
        config = self._make_config(
            [
                AndGoal(
                    [
                        SumGoal("Attack Power", 15),
                        SumGoal("Boss Damage", 20),
                    ]
                )
            ]
        )
        self.assertFalse(config.is_met(self.equipment))

    # -- OrGoal evaluation ------------------------------------------------

    def test_or_goal_first_met(self):
        config = self._make_config(
            [
                OrGoal(
                    [
                        SumGoal("Attack Power", 15),
                        SumGoal("Boss Damage", 20),
                    ]
                )
            ]
        )
        self.assertTrue(config.is_met(self.equipment))

    def test_or_goal_second_met(self):
        config = self._make_config(
            [
                OrGoal(
                    [
                        SumGoal("Attack Power", 20),
                        SumGoal("Boss Damage", 10),
                    ]
                )
            ]
        )
        self.assertTrue(config.is_met(self.equipment))

    def test_or_goal_none_met(self):
        config = self._make_config(
            [
                OrGoal(
                    [
                        SumGoal("Attack Power", 20),
                        SumGoal("Boss Damage", 20),
                    ]
                )
            ]
        )
        self.assertFalse(config.is_met(self.equipment))

    # -- Complex compound goal --------------------------------------------

    def test_21atk_with_ied_fails(self):
        config = self._make_config(
            [
                AndGoal(
                    [
                        SumGoal("Attack Power", 21),
                        LineCountGoal(frozenset({"Ignore Defense"}), 1),
                    ]
                )
            ]
        )
        self.assertFalse(config.is_met(self.equipment))

    def test_21atk_with_ied_met(self):
        eq = Equipment(
            "Legendary",
            [
                StatLine("Attack Power", 12),
                StatLine("Attack Power", 12),
                StatLine("Ignore Defense", 12),
            ],
        )
        config = self._make_config(
            [
                AndGoal(
                    [
                        SumGoal("Attack Power", 21),
                        LineCountGoal(frozenset({"Ignore Defense"}), 1),
                    ]
                )
            ]
        )
        self.assertTrue(config.is_met(eq))

    def test_and_goal_with_or_alternative_met(self):
        config = self._make_config(
            [
                AndGoal(
                    [
                        SumGoal("STR", 21),
                        OrGoal(
                            [
                                SumGoal("Boss Damage", 30),
                                SumGoal("Ignore Defense", 30),
                            ]
                        ),
                    ]
                )
            ]
        )
        equipment = Equipment(
            "Legendary",
            [
                StatLine("STR", 12),
                StatLine("STR", 9),
                StatLine("Ignore Defense", 30),
            ],
        )
        self.assertTrue(config.is_met(equipment))

    def test_and_goal_with_or_alternative_not_met(self):
        config = self._make_config(
            [
                AndGoal(
                    [
                        SumGoal("STR", 21),
                        OrGoal(
                            [
                                SumGoal("Boss Damage", 30),
                                SumGoal("Ignore Defense", 30),
                            ]
                        ),
                    ]
                )
            ]
        )
        equipment = Equipment(
            "Legendary",
            [StatLine("STR", 12), StatLine("STR", 9)],
        )
        self.assertFalse(config.is_met(equipment))

    # -- Multiple goals (all must pass) -----------------------------------

    def test_multiple_goals_all_pass(self):
        config = self._make_config(
            [
                SumGoal("Attack Power", 15),
                SumGoal("Boss Damage", 10),
            ]
        )
        self.assertTrue(config.is_met(self.equipment))

    def test_multiple_goals_one_fails(self):
        config = self._make_config(
            [
                SumGoal("Attack Power", 15),
                SumGoal("Boss Damage", 20),
            ]
        )
        self.assertFalse(config.is_met(self.equipment))

    # -- Flat lines never satisfy a percentage goal ------------------------

    def test_excludes_flat_attack_power(self):
        """End-to-end: goal config should not fire on flat + % Attack Power only."""
        goal = LineCountGoal(
            frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}), 2
        )
        config = self._make_config([goal])
        equipment = Equipment(
            "Legendary",
            [
                StatLine("Attack Power", 32, is_percent=False),  # flat
                StatLine("Attack Power", 9, is_percent=True),  # % – only 1
            ],
        )
        self.assertFalse(config.is_met(equipment))

    def test_accepts_percent_lines(self):
        """End-to-end: goal config fires when 2+ % lines of target stats exist."""
        goal = LineCountGoal(
            frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}), 2
        )
        config = self._make_config([goal])
        equipment = Equipment(
            "Legendary",
            [
                StatLine("Attack Power", 9, is_percent=True),
                StatLine("Boss Damage", 30, is_percent=True),
            ],
        )
        self.assertTrue(config.is_met(equipment))


class TestGoalConfigDescription(unittest.TestCase):
    """The config summarizes itself for logging and the GUI."""

    def test_rank_only(self):
        config = GoalConfig(category="Weapon", target_rank="Legendary", goals=[])
        text = str(config)
        self.assertIn("Rank only", text)
        self.assertIn("Legendary", text)

    def test_lists_each_goal(self):
        config = GoalConfig(
            category="Weapon",
            target_rank="Legendary",
            goals=[SumGoal("STR", 21), SumGoal("Boss Damage", 30)],
        )
        text = str(config)
        self.assertIn("STR >= 21%", text)
        self.assertIn("Boss Damage >= 30%", text)


if __name__ == "__main__":
    unittest.main()
