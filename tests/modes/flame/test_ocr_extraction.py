"""OCR extraction from flame window fixtures, for both engines."""

import os
import unittest

import cv2

from cube.core.ocr_processor import PaddleOCRProcessor, TesseractOCRProcessor
from cube.core.window_analyzer import WindowAnalyzer
from cube.modes.flame.window_analyzer import OFFSETS
from cube.tests.fixture_cases import add_fixture_tests
from cube.tests.paths import FLAME_FIXTURES, FLAME_RES

# Full bonus-stat-window screenshots collected as a sanity set. Each entry maps
# a fixture name to the stat lines that are written on the screenshot.
SANITY_DIR = os.path.join(FLAME_FIXTURES, "sanity")
SANITY_EXPECTATIONS = {
    "1.PNG": ["STR: 40", "DEX: 24", "INT: 16", "Max HP: 2250", "All Stats: 6%"],
    "2.PNG": ["STR: 96", "DEX: 36", "LUK: 66", "All Stats: 6%"],
    "3.PNG": ["STR: 66", "DEX: 55", "Attack Power: 142", "Boss Damage: 10%"],
    "4.PNG": ["STR: 20", "DEX: 44", "INT: 42", "LUK: 24", "Defense: 21"],
    "5.PNG": [
        "STR: 24",
        "DEX: 24",
        "INT: 20",
        "LUK: 20",
        "Attack Power: 5",
        "All Stats: 5%",
    ],
    "6.PNG": ["Attack Power: 3"],
    "7.PNG": ["STR: 30", "INT: 66", "LUK: 36", "Max HP: 3600", "All Stats: 7%"],
    "8.PNG": [
        "DEX: 54",
        "INT: 30",
        "LUK: 24",
        "Magic ATT: 192",
        "Boss Damage: 10%",
    ],
    "9.PNG": [
        "INT: 20",
        "LUK: 20",
        "Attack Power: 4",
        "Speed: 4",
        "All Stats: 5%",
    ],
    "10.PNG": ["STR: 24", "DEX: 24", "INT: 48", "Attack Power: 5", "All Stats: 7%"],
    "11.PNG": [
        "INT: 44",
        "Attack Power: 114",
        "Magic ATT: 192",
        "Boss Damage: 12%",
    ],
}


class _FlameOCRCases:
    """Fixture expectations shared by the engine-specific subclasses."""

    PROCESSOR_CLASS: type

    @classmethod
    def setUpClass(cls):
        cls.analyzer = WindowAnalyzer(FLAME_RES, OFFSETS)

    def _extract(self, filename):
        path = os.path.join(FLAME_FIXTURES, filename)
        image = cv2.imread(path)
        self.assertIsNotNone(image, f"fixture should be loadable: {path}")
        processor = self.PROCESSOR_CLASS(analyzer=self.analyzer)
        return processor.extract_equipment(image)

    def _assert_stats(self, filename, expected):
        equipment = self._extract(filename)
        stats = [str(line) for line in equipment.lines]
        self.assertEqual(stats, expected, filename)

    def test_blue_window(self):
        self._assert_stats("blue_cube.PNG", ["LUK: 3%", "DEX: 6"])

    def test_black_flame1(self):
        self._assert_stats(
            "black_flame1.PNG",
            ["STR: 90", "DEX: 44", "LUK: 24", "Reduced Level Requirement: 20"],
        )

    def test_black_flame2(self):
        self._assert_stats(
            "black_flame2.PNG",
            ["STR: 36", "Max MP: 1920", "Magic ATT: 6", "Speed: 5"],
        )

    def test_all_stats_5_percent(self):
        self._assert_stats(
            "all_stats_5_percent.PNG",
            ["INT: 36", "Max MP: 2400", "Jump: 5", "All Stats: 5%"],
        )

    def test_all_stats2(self):
        self._assert_stats(
            "allstats2.PNG",
            ["STR: 35", "DEX: 35", "LUK: 70", "Max HP: 4200", "All Stats: 6%"],
        )

    def test_big_list(self):
        self._assert_stats(
            "big_list.PNG",
            [
                "STR: 20",
                "DEX: 25",
                "INT: 25",
                "LUK: 20",
                "Defense: 54",
                "All Stats: 6%",
            ],
        )

    def test_big_list2(self):
        self._assert_stats(
            "big_list2.PNG",
            [
                "STR: 20",
                "DEX: 20",
                "INT: 25",
                "LUK: 25",
                "Defense: 54",
                "Speed: 5",
            ],
        )

    def test_magic_att(self):
        self._assert_stats(
            "magic_att.PNG",
            ["STR: 25", "DEX: 25", "LUK: 45", "Max HP: 2400", "Magic ATT: 6"],
        )

    def test_123stat(self):
        self._assert_stats(
            "123stat.PNG", ["STR: 28", "INT: 35", "LUK: 123", "Magic ATT: 6"]
        )

    def test_stuck1(self):
        self._assert_stats(
            "stuck1.PNG", ["STR: 72", "INT: 24", "Defense: 40", "Magic ATT: 4"]
        )

    def test_stuck2(self):
        self._assert_stats(
            "stuck2.PNG", ["STR: 70", "INT: 77", "LUK: 77", "All Stats: 6%"]
        )

    def test_stuck3(self):
        self._assert_stats(
            "stuck3.PNG", ["STR: 42", "INT: 35", "LUK: 77", "Max HP: 3500", "Speed: 5"]
        )

    def test_stuck4(self):
        self._assert_stats(
            "stuck4.PNG",
            [
                "STR: 35",
                "DEX: 35",
                "Reduced Level Requirement: 25",
                "Jump: 5",
                "All Stats: 6%",
            ],
        )

    def check_sanity(self, name):
        """Assert that *name* reads back its written stat lines."""
        equipment = self._extract(os.path.join("sanity", name))
        self.assertEqual(
            [str(line) for line in equipment.lines],
            SANITY_EXPECTATIONS[name],
            name,
        )


add_fixture_tests(_FlameOCRCases, SANITY_EXPECTATIONS, "check_sanity")


class TestFlameTesseractOCR(_FlameOCRCases, unittest.TestCase):
    """Flame fixtures read with Tesseract."""

    PROCESSOR_CLASS = TesseractOCRProcessor


class TestFlamePaddleOCR(_FlameOCRCases, unittest.TestCase):
    """Flame fixtures read with PaddleOCR (skipped when Paddle is absent)."""

    PROCESSOR_CLASS = PaddleOCRProcessor

    @classmethod
    def setUpClass(cls):
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("paddleocr not installed")
        super().setUpClass()


if __name__ == "__main__":
    unittest.main()
