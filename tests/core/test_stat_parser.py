"""Stat parser unit tests (shared by both modes)."""

import unittest

from cube.models.stat_parser import (
    extract_rank,
    normalize_stat_name,
    parse_stat_line,
    parse_stat_lines,
    parse_stat_lines_paddle,
)


class TestParseStatLine(unittest.TestCase):
    def test_main_stat_value(self):
        result = parse_stat_line("STR: 12%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "STR")
        self.assertEqual(result.value, 12)
        self.assertTrue(result.is_percent)

    def test_boss_damage_value(self):
        result = parse_stat_line("Boss Damage: 10%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Boss Damage")
        self.assertEqual(result.value, 10)
        self.assertTrue(result.is_percent)

    def test_plus_format(self):
        result = parse_stat_line("STR +5%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "STR")
        self.assertEqual(result.value, 5)

    def test_colon_with_plus(self):
        result = parse_stat_line("luk: +3%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "LUK")
        self.assertEqual(result.value, 3)

    def test_flat_stat(self):
        result = parse_stat_line("dex +6")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "DEX")
        self.assertEqual(result.value, 6)
        self.assertFalse(result.is_percent)

    def test_flat_cooldown_stat(self):
        result = parse_stat_line("SKill Cooldowns -2 sec")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Skill Cooldowns")
        self.assertEqual(result.value, 2)
        self.assertFalse(result.is_percent)

    def test_cooldown_second_value(self):
        result = parse_stat_line("Skill Cooldowns: -1 sec")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Skill Cooldowns")
        self.assertEqual(result.value, 1)
        self.assertFalse(result.is_percent)

    def test_cooldown_without_name_is_still_a_cooldown(self):
        result = parse_stat_line("-2 sec")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Skill Cooldowns")
        self.assertEqual(result.value, 2)
        self.assertFalse(result.is_percent)

    def test_space_format(self):
        result = parse_stat_line("Damage 12%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Damage")
        self.assertEqual(result.value, 12)

    def test_invalid_line(self):
        self.assertIsNone(parse_stat_line("This is not a stat line"))

    def test_empty_line(self):
        self.assertIsNone(parse_stat_line("   "))

    # -- B/6/8 OCR confusion corrections ---------------------------------

    def test_all_stats_ocr_b_resolves_to_six(self):
        result = parse_stat_line("All Stats +B%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "All Stats")
        self.assertEqual(result.value, 6)

    def test_critical_damage_ocr_b_resolves_to_eight(self):
        result = parse_stat_line("Critical Damage +B%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Critical Damage")
        self.assertEqual(result.value, 8)

    def test_all_stats_ocr_eight_corrected_to_six(self):
        result = parse_stat_line("All Stats +8%")
        self.assertIsNotNone(result)
        self.assertEqual(result.value, 6)

    def test_critical_damage_ocr_six_corrected_to_eight(self):
        result = parse_stat_line("Critical Damage +6%")
        self.assertIsNotNone(result)
        self.assertEqual(result.value, 8)

    def test_all_stats_values(self):
        for value in (10, 7):
            result = parse_stat_line(f"All Stats: {value}%")
            self.assertIsNotNone(result)
            self.assertEqual(result.value, value)

    # -- trash potential lines -------------------------------------------

    def test_leading_percent_trash_line(self):
        result = parse_stat_line("20% chance to ignore 26 damage when attacked")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Chance to Ignore Damage")
        self.assertEqual(result.value, 20)
        self.assertTrue(result.is_percent)

    def test_leading_percent_trash_line_clipped(self):
        result = parse_stat_line("20% chance to ignore 26 damage w")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "Chance to Ignore Damage")
        self.assertEqual(result.value, 20)

    def test_hp_recovery_efficiency_line(self):
        result = parse_stat_line("HP Recovery Items and Skills Efficiency: +20%")
        self.assertIsNotNone(result)
        self.assertEqual(result.stat, "HP Recovery Items and Skills Efficiency")
        self.assertEqual(result.value, 20)


class TestParseStatLines(unittest.TestCase):
    def test_multiple_lines(self):
        results = parse_stat_lines(
            ["STR: 12%", "Boss Damage: 10%", "Ignore Defense: 20%"]
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].stat, "STR")
        self.assertEqual(results[1].stat, "Boss Damage")
        self.assertEqual(results[2].stat, "Ignore Defense")

    def test_unparseable_lines_are_skipped(self):
        results = parse_stat_lines(["STR: 12%", "garbage", "DEX: 6%"])
        self.assertEqual(len(results), 2)
        self.assertEqual([line.stat for line in results], ["STR", "DEX"])


class TestNormalizeStatName(unittest.TestCase):
    def test_known_aliases(self):
        self.assertEqual(normalize_stat_name("attack power"), "Attack Power")
        self.assertEqual(normalize_stat_name("ATT"), "Attack Power")
        self.assertEqual(normalize_stat_name("boss damage"), "Boss Damage")
        self.assertEqual(normalize_stat_name("ied"), "Ignore Defense")
        self.assertEqual(normalize_stat_name("str"), "STR")
        self.assertEqual(normalize_stat_name("all stats"), "All Stats")
        self.assertEqual(normalize_stat_name("crit dmg"), "Critical Damage")


class TestExtractRank(unittest.TestCase):
    def test_legendary(self):
        self.assertEqual(extract_rank(["Attack Power: 15%", "Legendary"]), "Legendary")

    def test_epic(self):
        self.assertEqual(extract_rank(["Boss Damage: 10%", "EPIC"]), "Epic")

    def test_unique(self):
        self.assertEqual(extract_rank(["Unique"]), "Unique")

    def test_rare_not_supported(self):
        self.assertIsNone(extract_rank(["Rare"]))

    def test_not_found(self):
        self.assertIsNone(extract_rank(["Attack Power: 15%", "Boss Damage: 10%"]))


class TestParseStatLinesPaddle(unittest.TestCase):
    def test_name_before_value(self):
        results = parse_stat_lines_paddle(["STR +28"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].stat, "STR")
        self.assertEqual(results[0].value, 28)

    def test_value_before_name(self):
        results = parse_stat_lines_paddle(["+28 STR"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].stat, "STR")
        self.assertEqual(results[0].value, 28)

    def test_percent_line(self):
        results = parse_stat_lines_paddle(["All Stats 6%"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].stat, "All Stats")
        self.assertEqual(results[0].value, 6)
        self.assertTrue(results[0].is_percent)

    def test_leading_percent_trash_line(self):
        results = parse_stat_lines_paddle(
            ["20% chance to ignore 26 damage when attacked"]
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].stat, "Chance to Ignore Damage")
        self.assertEqual(results[0].value, 20)
        self.assertTrue(results[0].is_percent)

    def test_cooldown_line(self):
        results = parse_stat_lines_paddle(["Skill Cooldowns -2 sec"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].stat, "Skill Cooldowns")
        self.assertEqual(results[0].value, 2)
        self.assertFalse(results[0].is_percent)


if __name__ == "__main__":
    unittest.main()
