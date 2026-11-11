"""Tests for the shared equipment models: StatLine and Equipment."""

import unittest

from cube.models.equipment import Equipment
from cube.models.stat_line import StatLine


class TestStatLine(unittest.TestCase):
    def test_creation(self):
        line = StatLine("Attack Power", 15)
        self.assertEqual(line.stat, "Attack Power")
        self.assertEqual(line.value, 15)
        self.assertTrue(line.is_percent)

    def test_str_percent(self):
        self.assertEqual(str(StatLine("Attack Power", 15)), "Attack Power: 15%")

    def test_str_flat(self):
        line = StatLine("Skill Cooldowns", 2, is_percent=False)
        self.assertFalse(line.is_percent)
        self.assertEqual(str(line), "Skill Cooldowns: 2")


class TestEquipment(unittest.TestCase):
    def setUp(self):
        self.stat_line = StatLine("Attack Power", 15)
        self.equipment = Equipment("Legendary", [self.stat_line])

    def test_creation(self):
        self.assertEqual(self.equipment.rank, "Legendary")
        self.assertEqual(len(self.equipment.lines), 1)

    def test_str(self):
        s = str(self.equipment)
        self.assertIn("Legendary", s)
        self.assertIn("Attack Power", s)


if __name__ == "__main__":
    unittest.main()
