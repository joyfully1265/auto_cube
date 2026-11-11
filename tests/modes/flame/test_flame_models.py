"""Flame scorer and flame goal tests."""

import unittest

from cube.models.equipment import Equipment
from cube.models.stat_line import StatLine
from cube.modes.flame.flame_scorer import FlameScorer
from cube.modes.flame.goal_config import FlameGoalConfig


class TestFlameScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = FlameScorer()

    def test_main_stat_flat(self):
        self.assertEqual(self.scorer.calculate([StatLine("STR", 84)], "STR", "DEX"), 84.0)

    def test_secondary_stat_flat(self):
        self.assertEqual(self.scorer.calculate([StatLine("DEX", 60)], "STR", "DEX"), 5.0)

    def test_all_stats_percent(self):
        lines = [StatLine("All Stats", 5, is_percent=True)]
        self.assertEqual(self.scorer.calculate(lines, "STR", "DEX"), 50.0)

    def test_all_stats_flat(self):
        lines = [StatLine("All Stats", 30, is_percent=False)]
        self.assertEqual(self.scorer.calculate(lines, "STR", "DEX"), 30.0)

    def test_attack_power(self):
        lines = [StatLine("Attack Power", 9, is_percent=True)]
        self.assertEqual(self.scorer.calculate(lines, "STR", "DEX"), 27.0)

    def test_magic_att(self):
        lines = [StatLine("Magic ATT", 12, is_percent=True)]
        self.assertEqual(self.scorer.calculate(lines, "STR", "DEX"), 36.0)

    def test_boss_damage(self):
        lines = [StatLine("Boss Damage", 35, is_percent=True)]
        self.assertEqual(self.scorer.calculate(lines, "STR", "DEX"), 525.0)

    def test_damage(self):
        lines = [StatLine("Damage", 15, is_percent=True)]
        self.assertEqual(self.scorer.calculate(lines, "STR", "DEX"), 225.0)

    def test_weapon_attack_type_gates_the_other_stat(self):
        lines = [
            StatLine("Attack Power", 10, is_percent=True),
            StatLine("Magic ATT", 10, is_percent=True),
        ]
        score = self.scorer.calculate(
            lines, "STR", "DEX", weapon_attack_type="Attack Power"
        )
        self.assertEqual(score, 30.0)

    def test_unknown_stat_ignored(self):
        self.assertEqual(self.scorer.calculate([StatLine("Max HP", 100)], "STR", "DEX"), 0.0)

    def test_mixed_stats(self):
        lines = [
            StatLine("STR", 84),
            StatLine("DEX", 48),
            StatLine("All Stats", 5, is_percent=True),
            StatLine("Attack Power", 9, is_percent=True),
        ]
        self.assertAlmostEqual(self.scorer.calculate(lines, "STR", "DEX"), 165.0)

    def test_empty_lines(self):
        self.assertEqual(self.scorer.calculate([], "STR", "DEX"), 0.0)

    def test_calculate_and_format_returns_breakdown(self):
        lines = [StatLine("STR", 84), StatLine("DEX", 48)]
        total, breakdown = self.scorer.calculate_and_format(lines, "STR", "DEX")
        self.assertAlmostEqual(total, 88.0)
        self.assertEqual(len(breakdown), 2)
        self.assertIn("main stat", breakdown[0])
        self.assertIn("secondary stat", breakdown[1])

    def test_custom_rates(self):
        scorer = FlameScorer(
            conversion_config={
                "conversion_rates": {"Attack Power": 5.0},
                "secondary_divisor": 10.0,
            }
        )
        lines = [
            StatLine("Attack Power", 9, is_percent=True),
            StatLine("DEX", 60),
        ]
        self.assertEqual(scorer.calculate(lines, "STR", "DEX"), 51.0)

    def test_different_main_secondary(self):
        lines = [StatLine("STR", 84), StatLine("DEX", 120)]
        self.assertAlmostEqual(self.scorer.calculate(lines, "STR", "DEX"), 94.0)
        self.assertAlmostEqual(self.scorer.calculate(lines, "DEX", "STR"), 127.0)


class TestFlameGoalConfig(unittest.TestCase):
    def test_creation(self):
        config = FlameGoalConfig(
            category="Weapon",
            main_stat="STR",
            secondary_stat="DEX",
            is_better=False,
            base_score=100,
        )
        self.assertEqual(config.category, "Weapon")
        self.assertEqual(config.main_stat, "STR")
        self.assertEqual(config.secondary_stat, "DEX")
        self.assertFalse(config.is_better)
        self.assertEqual(config.base_score, 100)

    def test_str(self):
        config = FlameGoalConfig(
            category="Armor",
            main_stat="DEX",
            secondary_stat="STR",
            is_better=False,
            base_score=80,
        )
        text = str(config)
        self.assertIn("Armor", text)
        self.assertIn("DEX", text)
        self.assertIn("80", text)

    def test_str_better_than_current(self):
        config = FlameGoalConfig(
            category="Armor",
            main_stat="DEX",
            secondary_stat="STR",
            is_better=True,
        )
        self.assertIn("Better than current", str(config))

    def test_score_below_target(self):
        config = FlameGoalConfig("Weapon", "STR", "DEX", False, 200)
        equipment = Equipment(lines=[StatLine("STR", 50)])
        self.assertFalse(config.is_met(equipment))

    def test_score_meets_target(self):
        config = FlameGoalConfig("Weapon", "STR", "DEX", False, 100)
        equipment = Equipment(lines=[StatLine("STR", 100)])
        self.assertTrue(config.is_met(equipment))

    def test_all_stats_contributes(self):
        config = FlameGoalConfig("Armor", "STR", "DEX", False, 50)
        equipment = Equipment(lines=[StatLine("All Stats", 5, is_percent=True)])
        self.assertTrue(config.is_met(equipment))

    def test_boss_damage_contributes(self):
        config = FlameGoalConfig("Weapon", "STR", "DEX", False, 75)
        equipment = Equipment(lines=[StatLine("Boss Damage", 5, is_percent=True)])
        self.assertTrue(config.is_met(equipment))

    def test_better_than_current_requires_baseline(self):
        config = FlameGoalConfig("Weapon", "STR", "DEX", is_better=True)
        equipment = Equipment(lines=[StatLine("STR", 50)])

        self.assertFalse(config.is_met(equipment))
        config.prepare(equipment)
        self.assertEqual(config.base_score, 50.0)
        self.assertFalse(config.is_met(equipment))

        better = Equipment(lines=[StatLine("STR", 60)])
        self.assertTrue(config.is_met(better))

    def test_prepare_is_idempotent(self):
        config = FlameGoalConfig("Weapon", "STR", "DEX", is_better=True)
        config.prepare(Equipment(lines=[StatLine("STR", 50)]))
        config.prepare(Equipment(lines=[StatLine("STR", 90)]))
        self.assertEqual(config.base_score, 50.0)

    def test_describe_state_includes_total(self):
        config = FlameGoalConfig("Weapon", "STR", "DEX", False, 77)
        equipment = Equipment(
            lines=[
                StatLine("All Stats", 5, is_percent=True),
                StatLine("Attack Power", 9, is_percent=True),
            ]
        )
        detail = config.describe_state(equipment)
        self.assertIn("Total: 77.0", detail)


if __name__ == "__main__":
    unittest.main()
