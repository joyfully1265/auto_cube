"""Tests for PotentialLine."""

import unittest

from cube.modes.cube.potential_line import PotentialLine


class TestPotentialLine(unittest.TestCase):
    def test_basic_creation(self):
        pl = PotentialLine("Attack Power", 12)
        self.assertEqual(pl.stat, "Attack Power")
        self.assertEqual(pl.value, 12)
        self.assertTrue(pl.is_percent)

    def test_str_percent(self):
        pl = PotentialLine("Attack Power", 12)
        self.assertEqual(str(pl), "Attack Power: 12%")

    def test_flat_stat_is_percent(self):
        pl = PotentialLine("Skill Cooldowns", 2)
        self.assertFalse(pl.is_percent)
        self.assertEqual(str(pl), "Skill Cooldowns: 2")

    def test_frozen(self):
        pl = PotentialLine("STR", 12)
        with self.assertRaises(AttributeError):
            pl.value = 99


if __name__ == "__main__":
    unittest.main()
