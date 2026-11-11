"""OCR extraction from cube window fixtures, for both engines.

Every fixture is read through the production pipeline (window analysis, OCR,
stat parsing) and the extracted stat lines are asserted here, so goal tests can
work with written-out stats instead of screenshots.
"""

import os
import unittest

import cv2
import numpy as np

from cube.core.ocr_processor import PaddleOCRProcessor, TesseractOCRProcessor
from cube.core.window_analyzer import WindowAnalyzer
from cube.modes.cube.window_analyzer import OFFSETS
from cube.tests.fixture_cases import add_fixture_tests
from cube.tests.paths import CUBE_FIXTURES, CUBE_RES

# Full potential-window screenshots collected as a sanity set. Each entry maps
# a fixture name to the (rank, stat lines) that are written on the screenshot.
SANITY_DIR = os.path.join(CUBE_FIXTURES, "sanity")
SANITY_EXPECTATIONS = {
    "1.PNG": ("Legendary", ["Item Drop Rate: 20%", "Max HP: 13%", "Max HP: 10%"]),
    "2.PNG": ("Legendary", ["All Stats: 10%", "LUK: 13%", "LUK: 10%"]),
    "3.PNG": ("Epic", ["STR: 7%", "Attack Power: 3%", "Attack Power: 13"]),
    "4.PNG": (
        "Legendary",
        ["LUK: 13%", "All Stats: 7%", "Skill Cooldowns: 2"],
    ),
    "5.PNG": (
        "Legendary",
        ["Attack Power: 13%", "Attack Power: 10%", "Attack Power: 10%"],
    ),
    "6.PNG": ("Legendary", ["Item Drop Rate: 20%", "Max HP: 9%", "LUK: 9%"]),
    "7.PNG": ("Legendary", ["Item Drop Rate: 20%", "Skill Mp Cost: 30%", "DEX: 9%"]),
    "8.PNG": (
        "Legendary",
        [
            "Mesos Obtained: 20%",
            "HP Recovery Items and Skills Efficiency: 30%",
            "DEX: 9%",
        ],
    ),
    "9.PNG": ("Legendary", ["Boss Damage: 40%", "Damage: 10%", "Magic ATT: 10%"]),
    "10.PNG": (
        "Legendary",
        ["Magic ATT: 12%", "Ignore Defense: 30%", "Magic ATT: 9%"],
    ),
    "11.PNG": (
        "Legendary",
        ["Magic ATT: 13%", "Magic ATT: 13%", "Boss Damage: 30%"],
    ),
    "12.PNG": ("Legendary", ["INT: 12%", "30% Chance To Reflect: 50%", "INT: 9%"]),
    "13.PNG": (
        "Unique",
        ["DEX: 9%", "Max MP: 6%", "Chance to Ignore Damage: 30%"],
    ),
    "14.PNG": ("Legendary", ["Skill Cooldowns: 1", "DEX: 9%", "DEX: 9%"]),
    "15.PNG": ("Legendary", ["All Stats: 9%", "DEX: 9%", "DEX: 9%"]),
    "16.PNG": ("Unique", ["All Stats: 6%", "All Stats: 6%"]),
    "17.PNG": ("Unique", ["DEX: 10%", "Def: 7%", "Max HP: 7%"]),
    "18.PNG": ("Unique", ["All Stats: 7%", "All Stats: 4%", "STR: 7%"]),
    "19.PNG": ("Unique", ["STR: 9%", "Skill Cooldowns: 7", "STR: 6%"]),
    "20.PNG": (
        "Unique",
        ["Skill Cooldowns: 2", "STR: 9%", "All Stats: 3%"],
    ),
}


def _load_fixture(filename: str) -> np.ndarray:
    """Read *filename* from the cube fixtures."""
    path = os.path.join(CUBE_FIXTURES, filename)
    image = cv2.imread(path)
    if image is None:
        raise RuntimeError(f"fixture should be loadable: {path}")
    return image


class _CubeOCRCases:
    """Fixture expectations shared by the engine-specific subclasses."""

    PROCESSOR_CLASS: type

    @classmethod
    def setUpClass(cls):
        cls.analyzer = WindowAnalyzer(CUBE_RES, OFFSETS)

    def _extract(self, filename):
        processor = self.PROCESSOR_CLASS(analyzer=self.analyzer, read_rank=True)
        equipment = processor.extract_equipment(_load_fixture(filename))
        return equipment

    def _assert_stats(self, filename, expected, expected_rank=None):
        equipment = self._extract(filename)
        self.assertEqual(equipment.rank, expected_rank, f"{filename} rank")
        stats = [str(line) for line in equipment.lines]
        self.assertEqual(stats, expected, filename)

    def test_blue_window(self):
        self._assert_stats("blue_cube.PNG", ["LUK: 3%", "DEX: 6"])

    def test_purple_cube(self):
        self._assert_stats(
            "purple_cube.PNG",
            ["All Stats: 10%", "Max MP: 10%", "All Stats: 7%"],
            "Legendary",
        )

    def test_critdam(self):
        self._assert_stats(
            "critdam.PNG",
            ["Critical Damage: 8%", "LUK: 10%", "Critical Damage: 8%"],
            "Legendary",
        )

    def test_trashlines(self):
        self._assert_stats(
            "trashlines.PNG",
            [
                "HP Recovery Items and Skills Efficiency: 30%",
                "Chance to Ignore Damage: 20%",
                "Chance to Ignore Damage: 20%",
            ],
            "Unique",
        )

    def test_background(self):
        self._assert_stats(
            "background.PNG",
            ["Max MP: 7%", "Max MP: 125", "Def: 4%"],
            "Epic",
        )

    def test_allstats(self):
        self._assert_stats(
            "allstats.PNG",
            ["All Stats: 10%", "All Stats: 10%", "LUK: 10%"],
            "Legendary",
        )

    def test_allstats2(self):
        self._assert_stats(
            "allstats2.PNG",
            ["All Stats: 7%", "All Stats: 4%", "STR: 7%"],
            "Unique",
        )

    def test_allstats3(self):
        self._assert_stats(
            "allstats3.PNG",
            ["All Stats: 7%", "STR: 7%", "All Stats: 4%"],
            "Unique",
        )

    def test_cooldown(self):
        self._assert_stats(
            "cooldown.PNG",
            ["LUK: 13%", "Skill Cooldowns: 2", "Skill Cooldowns: 2"],
            "Legendary",
        )

    def check_sanity(self, name):
        """Assert that *name* reads back its written rank and stat lines."""
        expected_rank, expected_stats = SANITY_EXPECTATIONS[name]
        equipment = self._extract(os.path.join("sanity", name))
        self.assertEqual(
            (equipment.rank, [str(line) for line in equipment.lines]),
            (expected_rank, expected_stats),
            name,
        )


add_fixture_tests(_CubeOCRCases, SANITY_EXPECTATIONS, "check_sanity")


class TestCubeTesseractOCR(_CubeOCRCases, unittest.TestCase):
    """Cube fixtures read with Tesseract."""

    PROCESSOR_CLASS = TesseractOCRProcessor


class TestCubePaddleOCR(_CubeOCRCases, unittest.TestCase):
    """Cube fixtures read with PaddleOCR (skipped when Paddle is absent)."""

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
