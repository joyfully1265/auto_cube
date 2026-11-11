"""Tests for the ValueProfile constants used to interpret cube stat values."""

import unittest

from cube.modes.cube.value_profile import ValueProfile


class TestValueProfile(unittest.TestCase):
    def test_level_71_150(self):
        vp = ValueProfile.for_level_range("71-150")
        self.assertEqual(vp.tier, "Legendary")
        self.assertEqual(vp.prime, 12)
        self.assertEqual(vp.non_prime, 9)

    def test_level_151_plus(self):
        vp = ValueProfile.for_level_range("151+")
        self.assertEqual(vp.prime, 13)
        self.assertEqual(vp.non_prime, 10)

    def test_unique_tier_values(self):
        vp = ValueProfile.for_level_range("71-150", "Unique")
        self.assertEqual(vp.prime, 9)
        self.assertEqual(vp.non_prime, 6)
        self.assertEqual(vp.line_values, (9, 6))

    def test_epic_tier_values(self):
        vp = ValueProfile.for_level_range("71-150", "Epic")
        self.assertEqual(vp.line_values, (6, 3))

    def test_rare_tier_not_supported(self):
        with self.assertRaises(ValueError):
            ValueProfile.for_level_range("71-150", "Rare")

    def test_all_tiers_151_plus(self):
        expected = {
            "Epic": (7, 4),
            "Unique": (10, 7),
            "Legendary": (13, 10),
        }
        for tier, values in expected.items():
            with self.subTest(tier=tier):
                vp = ValueProfile.for_level_range("151+", tier)
                self.assertEqual(vp.line_values, values)
                self.assertEqual(vp.max_single_stat, values[0] * 3)

    def test_all_stats_rolls_one_rank_lower_151_plus(self):
        expected = {
            "Epic": (4,),
            "Unique": (7, 4),
            "Legendary": (10, 7),
        }
        for tier, values in expected.items():
            with self.subTest(tier=tier):
                vp = ValueProfile.for_level_range("151+", tier)
                self.assertEqual(vp.all_stats_line_values, values)

    def test_all_stats_rolls_one_rank_lower_71_150(self):
        expected = {
            "Epic": (3,),
            "Unique": (6, 3),
            "Legendary": (9, 6),
        }
        for tier, values in expected.items():
            with self.subTest(tier=tier):
                vp = ValueProfile.for_level_range("71-150", tier)
                self.assertEqual(vp.all_stats_line_values, values)

    def test_unknown_level_raises(self):
        with self.assertRaises(ValueError):
            ValueProfile.for_level_range("1-70")

    def test_unknown_tier_raises(self):
        with self.assertRaises(ValueError):
            ValueProfile.for_level_range("71-150", "Mythic")

    def test_max_single_stat(self):
        vp = ValueProfile.for_level_range("71-150")
        self.assertEqual(vp.max_single_stat, 36)  # 12*3

    def test_is_flat_stat(self):
        self.assertTrue(ValueProfile.is_flat_stat("Skill Cooldowns"))
        self.assertFalse(ValueProfile.is_flat_stat("Attack Power"))
        self.assertFalse(ValueProfile.is_flat_stat("STR"))

    def test_critical_damage_values_are_legendary_only(self):
        self.assertEqual(
            ValueProfile.for_level_range(
                "71-150", "Legendary"
            ).critical_damage_line_values,
            (8,),
        )
        self.assertEqual(
            ValueProfile.for_level_range(
                "71-150", "Unique"
            ).critical_damage_line_values,
            (),
        )

    def test_frozen(self):
        vp = ValueProfile.for_level_range("71-150")
        with self.assertRaises(AttributeError):
            vp.prime = 99


if __name__ == "__main__":
    unittest.main()
