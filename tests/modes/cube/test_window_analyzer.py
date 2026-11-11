"""Cube window analyzer tests against real screenshots."""

import unittest

import cv2

from cube.core.window_analyzer import BoundingBox, WindowAnalyzer
from cube.modes.cube.window_analyzer import OFFSETS
from cube.tests.paths import CUBE_FIXTURES, CUBE_RES


class TestCubeWindowAnalyzerPurple(unittest.TestCase):
    """Purple window (BEFORE/AFTER comparison) analysis."""

    @classmethod
    def setUpClass(cls):
        cls.image = cv2.imread(f"{CUBE_FIXTURES}/purple_cube.PNG", cv2.IMREAD_COLOR)
        if cls.image is None:
            raise unittest.SkipTest("purple_cube.PNG fixture missing")

    def setUp(self):
        self.analyzer = WindowAnalyzer(CUBE_RES, OFFSETS)

    def test_find_after_anchor(self):
        info = self.analyzer.analyze(self.image)
        self.assertIsNotNone(info.after_anchor)
        self.assertLessEqual(info.after_anchor.score, 0.05)

    def test_all_anchors_found(self):
        info = self.analyzer.analyze(self.image)
        self.assertTrue(info.is_valid)

    def test_after_stats_region_exists(self):
        info = self.analyzer.analyze(self.image)
        self.assertIsNotNone(info.after_stats_region)

    def test_reset_purple_region_exists(self):
        info = self.analyzer.analyze(self.image)
        self.assertIsNotNone(info.reset_purple_region)

    def test_extract_after_stats_image(self):
        info = self.analyzer.analyze(self.image)
        region = self.analyzer.get_after_stats_image(self.image, info)
        self.assertIsNotNone(region)
        self.assertGreater(region.shape[0], 0)
        self.assertGreater(region.shape[1], 0)

    def test_no_cubes(self):
        """Test that a window with no cubes or meso returns no anchors."""
        image = cv2.imread(f"{CUBE_FIXTURES}/purple_no_cubes.PNG", cv2.IMREAD_COLOR)
        if image is None:
            raise unittest.SkipTest("blue_no_cubes.PNG fixture missing")
        info = self.analyzer.analyze(image)
        self.assertIsNone(info.reset_button_anchor)
        self.assertIsNone(info.reset_button_region)


class TestCubeWindowAnalyzerBlue(unittest.TestCase):
    """Blue window (single stats block) analysis."""

    @classmethod
    def setUpClass(cls):
        cls.image = cv2.imread(f"{CUBE_FIXTURES}/blue_cube.PNG", cv2.IMREAD_COLOR)
        if cls.image is None:
            raise unittest.SkipTest("blue_cube.PNG fixture missing")

    def setUp(self):
        self.analyzer = WindowAnalyzer(CUBE_RES, OFFSETS)

    def test_reset_button_region_derived(self):
        info = self.analyzer.analyze(self.image)
        self.assertIsNotNone(info.reset_button_anchor)
        self.assertIsNotNone(info.reset_button_region)

    def test_extract_region_bounds_checking(self):
        height, width = self.image.shape[:2]
        region = BoundingBox.from_xywh(width - 10, height - 10, 110, 110)
        result = self.analyzer.extract_region(self.image, region)
        self.assertIsNotNone(result)
        self.assertLessEqual(result.shape[1], width)
        self.assertLessEqual(result.shape[0], height)

    def test_extract_region_none(self):
        self.assertIsNone(self.analyzer.extract_region(self.image, None))

    def test_no_cubes(self):
        """Test that a window with no cubes or meso returns no anchors."""
        image = cv2.imread(f"{CUBE_FIXTURES}/blue_no_cubes.PNG", cv2.IMREAD_COLOR)
        if image is None:
            raise unittest.SkipTest("blue_no_cubes.PNG fixture missing")
        info = self.analyzer.analyze(image)
        self.assertIsNone(info.reset_button_anchor)
        self.assertIsNone(info.reset_button_region)


if __name__ == "__main__":
    unittest.main()
