"""Tests for StatGroup."""

import unittest

from cube.modes.cube.stat_group import StatGroup


class TestStatGroup(unittest.TestCase):
    def test_damage_group(self):
        g = StatGroup.damage_group()
        self.assertEqual(g.name, "Damage")
        self.assertIn("Attack Power", g.stats)
        self.assertIn("Boss Damage", g.stats)
        self.assertIn("Ignore Defense", g.stats)
        self.assertIn("Magic ATT", g.stats)
        self.assertIn("Damage", g.stats)

    def test_primary_stat_group(self):
        g = StatGroup.primary_stat_group()
        self.assertEqual(g.stats, frozenset({"STR", "DEX", "INT", "LUK"}))

    def test_contains(self):
        g = StatGroup.damage_group()
        self.assertIn("Attack Power", g)
        self.assertNotIn("STR", g)

    def test_frozen(self):
        g = StatGroup.damage_group()
        with self.assertRaises(AttributeError):
            g.name = "Other"

    def test_str(self):
        g = StatGroup.damage_group()
        self.assertEqual(str(g), "Damage")


if __name__ == "__main__":
    unittest.main()
