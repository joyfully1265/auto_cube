"""Tests for CombinationGenerator."""

import unittest

from cube.modes.cube.combination_goal import (
    AndGoal,
    DumpAllGoal,
    LineCountGoal,
    SumGoal,
)
from cube.modes.cube.combination_generator import CombinationGenerator


class TestCombinationGeneratorSum(unittest.TestCase):
    def setUp(self):
        self.gen = CombinationGenerator("71-150")

    def test_generate_for_sum_18pct(self):
        goal = SumGoal("Attack Power", 18)
        combos = self.gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        # Every combo should have total >= 18
        for combo in combos:
            total = combo.total_for("Attack Power")
            self.assertGreaterEqual(total, 18)

    def test_generate_for_sum_21pct(self):
        goal = SumGoal("Attack Power", 21)
        combos = self.gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            total = combo.total_for("Attack Power")
            self.assertGreaterEqual(total, 21)

    def test_no_combo_exceeds_3_lines(self):
        goal = SumGoal("Attack Power", 18)
        combos = self.gen.generate_for_goal(goal)
        for combo in combos:
            self.assertLessEqual(len(combo), 3)

    def test_all_stats_included_for_primary(self):
        """All Stats lines should appear in STR combos."""
        goal = SumGoal("STR", 12)
        combos = self.gen.generate_for_goal(goal)
        has_all_stats = any(combo.contains_stat("All Stats") for combo in combos)
        self.assertTrue(has_all_stats)

    def test_level_151_values(self):
        gen = CombinationGenerator("151+")
        goal = SumGoal("Attack Power", 13)
        combos = gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        # With 151+ best value 13, a single line should suffice
        single_line_combos = [c for c in combos if len(c) == 1]
        self.assertTrue(len(single_line_combos) > 0)


class TestCombinationGeneratorTier(unittest.TestCase):
    def test_defaults_to_legendary(self):
        gen = CombinationGenerator("71-150")
        self.assertEqual(gen.line_values_for("STR"), [12, 9])

    def test_line_values_follow_tier(self):
        self.assertEqual(
            CombinationGenerator("71-150", "Unique").line_values_for("STR"), [9, 6]
        )
        self.assertEqual(
            CombinationGenerator("151+", "Epic").line_values_for("Attack Power"),
            [7, 4],
        )
        self.assertEqual(
            CombinationGenerator("71-150", "Epic").line_values_for("STR"), [6, 3]
        )

    def test_all_stats_uses_one_rank_lower_values(self):
        self.assertEqual(
            CombinationGenerator("151+", "Legendary").line_values_for("All Stats"),
            [10, 7],
        )
        self.assertEqual(
            CombinationGenerator("151+", "Unique").line_values_for("All Stats"),
            [7, 4],
        )

    def test_fixed_values_ignore_tier(self):
        gen = CombinationGenerator("71-150", "Epic")
        self.assertEqual(gen.line_values_for("Boss Damage"), [30, 35, 40])
        self.assertEqual(gen.line_values_for("Ignore Defense"), [30, 35, 40])

    def test_critical_damage_is_eight_percent_legendary_only(self):
        self.assertEqual(
            CombinationGenerator("71-150", "Legendary").line_values_for(
                "Critical Damage"
            ),
            [8],
        )
        self.assertEqual(
            CombinationGenerator("71-150", "Unique").line_values_for("Critical Damage"),
            [],
        )
        self.assertEqual(
            CombinationGenerator("151+", "Epic").line_values_for("Critical Damage"),
            [],
        )

    def test_critical_damage_goal_is_reachable(self):
        gen = CombinationGenerator("71-150", "Legendary")
        combos = gen.generate_for_goal(SumGoal("Critical Damage", 8))
        self.assertTrue(combos)

    def test_cooldown_candidates_are_two_and_one_second(self):
        gen = CombinationGenerator("71-150", "Legendary")
        combos = gen.generate_for_goal(SumGoal("Skill Cooldowns", 2))
        self.assertTrue(combos)
        values = {line.value for combo in combos for line in combo.lines}
        self.assertEqual(values, {2, 1})

    def test_max_possible_value_follows_tier(self):
        self.assertEqual(
            CombinationGenerator("71-150", "Unique").get_max_possible_value(), 27
        )
        self.assertEqual(
            CombinationGenerator("151+", "Legendary").get_max_possible_value(), 39
        )

    def test_all_stats_candidates_use_lower_tier_values(self):
        gen = CombinationGenerator("151+", "Legendary")
        combos = gen.generate_all_combinations(["All Stats"])
        self.assertTrue(combos)
        values = {line.value for combo in combos for line in combo.lines}
        self.assertEqual(values, {10, 7})


class TestCombinationGeneratorLineCount(unittest.TestCase):
    def setUp(self):
        self.gen = CombinationGenerator("71-150")

    def test_any_2_of_damage(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}),
            min_lines=2,
        )
        combos = self.gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            count = combo.line_count_for_stats(goal.stats)
            self.assertGreaterEqual(count, 2)

    def test_any_3_of_damage(self):
        goal = LineCountGoal(
            stats=frozenset({"Attack Power", "Boss Damage", "Ignore Defense"}),
            min_lines=3,
        )
        combos = self.gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            self.assertEqual(len(combo), 3)


class TestCombinationGeneratorPairedLines(unittest.TestCase):
    def setUp(self):
        self.gen = CombinationGenerator("71-150")

    def test_1l_atk_1l_boss(self):
        goal = AndGoal(
            [
                LineCountGoal(frozenset({"Attack Power"}), 1),
                LineCountGoal(frozenset({"Boss Damage"}), 1),
            ]
        )
        combos = self.gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            self.assertGreaterEqual(
                combo.total_for("Attack Power"), 1
            )  # at least 1 line
            self.assertGreaterEqual(
                combo.total_for("Boss Damage"), 1
            )  # at least 1 line


class TestCombinationGeneratorAnd(unittest.TestCase):
    def setUp(self):
        self.gen = CombinationGenerator("71-150")

    def test_21_atk_with_ied(self):
        goal = AndGoal(
            [
                SumGoal("Attack Power", 21),
                LineCountGoal(frozenset({"Ignore Defense"}), 1),
            ]
        )
        combos = self.gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            self.assertGreaterEqual(combo.total_for("Attack Power"), 21)
            self.assertTrue(combo.contains_stat("Ignore Defense"))


class TestGenerateAllCombinations(unittest.TestCase):
    def setUp(self):
        self.gen = CombinationGenerator("71-150")

    def test_only_2_and_3_line_combos(self):
        """No single-line combinations should be returned."""
        combos = self.gen.generate_all_combinations(["Attack Power", "Boss Damage"])
        for combo in combos:
            self.assertGreaterEqual(len(combo), 2)
            self.assertLessEqual(len(combo), 3)

    def test_no_single_line_combos(self):
        combos = self.gen.generate_all_combinations(["Attack Power"])
        for combo in combos:
            self.assertGreaterEqual(len(combo), 2)

    def test_two_stats_produces_combos(self):
        combos = self.gen.generate_all_combinations(["Attack Power", "Boss Damage"])
        self.assertTrue(len(combos) > 0)

    def test_all_combos_have_valid_lines(self):
        """Every line in every combo should be one of the allowed stats."""
        allowed = ["Attack Power", "Boss Damage"]
        combos = self.gen.generate_all_combinations(allowed)
        for combo in combos:
            for line in combo.lines:
                self.assertIn(line.stat, allowed)

    def test_both_line_values_appear(self):
        """Both possible Attack Power values should be present."""
        combos = self.gen.generate_all_combinations(["Attack Power"])
        values = {line.value for combo in combos for line in combo.lines}
        self.assertEqual(values, {12, 9})

    def test_level_151_plus(self):
        gen = CombinationGenerator("151+")
        combos = gen.generate_all_combinations(["Attack Power", "Boss Damage"])
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            self.assertGreaterEqual(len(combo), 2)
            self.assertLessEqual(len(combo), 3)

    def test_three_stats(self):
        stats = ["Attack Power", "Boss Damage", "Ignore Defense"]
        combos = self.gen.generate_all_combinations(stats)
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            self.assertGreaterEqual(len(combo), 2)
            self.assertLessEqual(len(combo), 3)

    def test_dump_all_goal_dispatch(self):
        """generate_for_goal should dispatch DumpAllGoal to generate_all_combinations."""
        goal = DumpAllGoal(stats=frozenset({"Attack Power", "Boss Damage"}))
        combos = self.gen.generate_for_goal(goal)
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            self.assertGreaterEqual(len(combo), 2)

    def test_empty_stats_returns_empty(self):
        combos = self.gen.generate_all_combinations([])
        self.assertEqual(combos, [])

    def test_single_stat_produces_combos(self):
        """Even with one stat, 2-3 line combos should be generated."""
        combos = self.gen.generate_all_combinations(["Attack Power"])
        self.assertTrue(len(combos) > 0)
        for combo in combos:
            self.assertGreaterEqual(len(combo), 2)
            self.assertLessEqual(len(combo), 3)


if __name__ == "__main__":
    unittest.main()
