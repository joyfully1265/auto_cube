"""Flame window analyzer tests against real screenshots."""

import os
import unittest

import cv2

from cube.core.window_analyzer import WindowAnalyzer
from cube.modes.flame.window_analyzer import OFFSETS
from cube.tests.paths import FLAME_FIXTURES, FLAME_RES

_VISUAL_DEBUG = bool(os.environ.get("VISUAL_DEBUG"))


def _load(filename):
    image = cv2.imread(os.path.join(FLAME_FIXTURES, filename))
    if image is None:
        raise unittest.SkipTest(f"fixture missing: {filename}")
    return image


class TestFlameWindowAnalyzerPurple(unittest.TestCase):
    """Purple (before/after) flame window."""

    @classmethod
    def setUpClass(cls):
        cls.image = _load("black_flame.PNG")

    def setUp(self):
        self.analyzer = WindowAnalyzer(FLAME_RES, OFFSETS)

    def test_all_anchors_found(self):
        self.assertTrue(self.analyzer.analyze(self.image).is_valid)

    def test_after_stats_region_exists(self):
        info = self.analyzer.analyze(self.image)
        self.assertIsNotNone(info.after_stats_region)

    def test_reset_button_region_absent_when_button_missing(self):
        info = self.analyzer.analyze(_load("black_flame_none.PNG"))
        self.assertIsNone(info.reset_purple_region)

    def test_reset_button_region(self):
        info = self.analyzer.analyze(self.image)
        self.assertIsNotNone(info.reset_purple_region)
        self.assertEqual(info.reset_purple_region.top_left, (214, 486))
        self.assertEqual(info.reset_purple_region.width, 56)
        self.assertEqual(info.reset_purple_region.height, 12)

    def test_reset_button_region_full(self):
        info = self.analyzer.analyze(_load("black_flame_full.PNG"))
        self.assertIsNotNone(info.reset_purple_region)
        self.assertEqual(info.reset_purple_region.top_left, (659, 627))

    def test_extract_after_stats_image(self):
        info = self.analyzer.analyze(self.image)
        region = self.analyzer.get_after_stats_image(self.image, info)
        self.assertIsNotNone(region)
        self.assertGreater(region.shape[0], 0)
        self.assertGreater(region.shape[1], 0)


class TestFlameWindowAnalyzerBlue(unittest.TestCase):
    """Blue (single stats block) flame window."""

    @classmethod
    def setUpClass(cls):
        cls.image = _load("magic_att.PNG")

    def setUp(self):
        self.analyzer = WindowAnalyzer(FLAME_RES, OFFSETS)

    def test_reset_button_region_derived(self):
        info = self.analyzer.analyze(self.image)
        self.assertIsNotNone(info.reset_button_anchor)
        self.assertIsNotNone(info.reset_button_region)
        self.assertEqual(info.reset_button_region.top_left, (340, 687))
        self.assertEqual(info.reset_button_region.width, 36)
        self.assertEqual(info.reset_button_region.height, 12)

    def test_extract_region_none(self):
        self.assertIsNone(self.analyzer.extract_region(self.image, None))


@unittest.skipUnless(_VISUAL_DEBUG, "set VISUAL_DEBUG=1 to draw detections")
class TestFlameWindowAnalyzerVisual(unittest.TestCase):
    """Interactive visualization of detected anchors and regions."""

    CASES = ("black_flame.PNG", "black_flame_full.PNG", "magic_att.PNG")

    def test_visualize(self):
        analyzer = WindowAnalyzer(FLAME_RES, OFFSETS)
        for filename in self.CASES:
            image = _load(filename)
            info = analyzer.analyze(image)
            canvas = image.copy()
            for anchor in (
                info.after_anchor,
                info.enhance_anchor,
                info.reset_button_anchor,
                info.reset_purple_anchor,
            ):
                if anchor is None:
                    continue
                box = anchor.box
                cv2.rectangle(
                    canvas, (box.x0, box.y0), (box.x1, box.y1), (255, 0, 0), 2
                )
            for region in (
                info.after_stats_region,
                info.rank_region,
                info.reset_button_region,
                info.reset_purple_region,
            ):
                if region is None:
                    continue
                cv2.rectangle(
                    canvas, (region.x0, region.y0), (region.x1, region.y1), (0, 255, 0), 2
                )
            cv2.imshow(filename, canvas)

        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    unittest.main()
