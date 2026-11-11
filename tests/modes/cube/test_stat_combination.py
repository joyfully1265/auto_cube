"""Tests for StatCombination."""

import unittest

from cube.modes.cube.potential_line import PotentialLine
from cube.modes.cube.stat_combination import StatCombination


class TestStatCombination(unittest.TestCase):
    def setUp(self):
        self.lines = [
            PotentialLine("Attack Power", 12),
            PotentialLine("Attack Power", 9),
            PotentialLine("Boss Damage", 40),
        ]
        self.combo = StatCombination(lines=self.lines)

    def test_total_for(self):
        self.assertEqual(self.combo.total_for("Attack Power"), 21)
        self.assertEqual(self.combo.total_for("Boss Damage"), 40)
        self.assertEqual(self.combo.total_for("STR"), 0)

    def test_contains_stat(self):
        self.assertTrue(self.combo.contains_stat("Attack Power"))
        self.assertTrue(self.combo.contains_stat("Boss Damage"))
        self.assertFalse(self.combo.contains_stat("STR"))

    def test_line_count_for_stats(self):
        count = self.combo.line_count_for_stats(
            frozenset({"Attack Power", "Boss Damage"})
        )
        self.assertEqual(count, 3)

    def test_line_count_partial(self):
        count = self.combo.line_count_for_stats(frozenset({"Attack Power"}))
        self.assertEqual(count, 2)

    def test_len(self):
        self.assertEqual(len(self.combo), 3)

    def test_str(self):
        s = str(self.combo)
        self.assertIn("Attack Power", s)
        self.assertIn("Boss Damage", s)

    def test_empty_combo(self):
        empty = StatCombination()
        self.assertEqual(len(empty), 0)
        self.assertEqual(str(empty), "Empty Combination")

    def test_equality(self):
        a = StatCombination(lines=[PotentialLine("STR", 12)])
        b = StatCombination(lines=[PotentialLine("STR", 12)])
        self.assertEqual(a, b)

    def test_inequality_different_value(self):
        a = StatCombination(lines=[PotentialLine("STR", 12)])
        b = StatCombination(lines=[PotentialLine("STR", 9)])
        self.assertNotEqual(a, b)

    def test_inequality_different_stat(self):
        a = StatCombination(lines=[PotentialLine("STR", 12)])
        b = StatCombination(lines=[PotentialLine("DEX", 12)])
        self.assertNotEqual(a, b)

    def test_inequality_different_line_count(self):
        a = StatCombination(lines=[PotentialLine("STR", 12)])
        b = StatCombination(
            lines=[
                PotentialLine("STR", 12),
                PotentialLine("STR", 9),
            ]
        )
        self.assertNotEqual(a, b)

    def test_inequality_different_order(self):
        """Order of lines matters since lines is a list."""
        line_a = PotentialLine("Attack Power", 12)
        line_b = PotentialLine("Boss Damage", 40)
        combo_ab = StatCombination(lines=[line_a, line_b])
        combo_ba = StatCombination(lines=[line_b, line_a])
        self.assertNotEqual(combo_ab, combo_ba)

    def test_equality_empty(self):
        self.assertEqual(StatCombination(), StatCombination())

    def test_not_equal_to_non_combo(self):
        combo = StatCombination(lines=[PotentialLine("STR", 12)])
        self.assertNotEqual(combo, "not a combo")
        self.assertNotEqual(combo, None)


if __name__ == "__main__":
    unittest.main()
