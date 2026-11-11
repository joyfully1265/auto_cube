"""Test template matching against sample screenshots.

Verifies that template images in ``res/`` can be reliably found in
known-good screenshots from the tests/res directory.
"""

import os
import unittest
from typing import Optional

import cv2
import numpy as np

from cube.core.template_matcher import load_template, single_template_match
from cube.tests.paths import CUBE_FIXTURES, CUBE_RES


def _load_mask(path: str) -> Optional[np.ndarray]:
    """Load the alpha channel of a BGRA mask image as a grayscale mask."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None or img.shape[2] != 4:
        return None
    return img[:, :, 3].copy()


class TestConfirmResetTemplateMatching(unittest.TestCase):
    """Test template matching for confirm/reset dialog templates.

    Each test case specifies a screenshot, a template, an optional mask,
    and whether a match is expected.  Positive cases verify that required
    UI elements are found; negative cases guard against false positives.
    """

    #  (screenshot, template, mask, expect_match)
    CASES = [
        {
            "name": "reset_confirm2 found in purple_confirm2",
            "screenshot": "purple_confirm2.PNG",
            "template": "reset_confirm2.PNG",
            # "mask": "reset_confirm2_mask.PNG",
            "expect_match": True,
        },
        {
            "name": "reset_confirm1 not found in purple_confirm2",
            "screenshot": "purple_confirm2.PNG",
            "template": "reset_confirm1.PNG",
            # "mask": "reset_confirm1_mask.PNG",
            "expect_match": False,
        },
        {
            "name": "confirm button found in purple_confirm2",
            "screenshot": "purple_confirm2.PNG",
            "template": "confirm.PNG",
            # "mask": "confirm_mask.PNG",
            "expect_match": True,
        },
        {
            "name": "reset_confirm1 found in purple_confirm",
            "screenshot": "purple_confirm.PNG",
            "template": "reset_confirm1.PNG",
            # "mask": "reset_confirm1_mask.PNG",
            "expect_match": True,
        },
        {
            "name": "reset_confirm2 not found in purple_confirm",
            "screenshot": "purple_confirm.PNG",
            "template": "reset_confirm2.PNG",
            # "mask": "reset_confirm2_mask.PNG",
            "expect_match": False,
        },
        {
            "name": "reset_confirm2 found in confirm_blue1",
            "screenshot": "confirm_blue1.PNG",
            "template": "reset_confirm2.PNG",
            # "mask": "reset_confirm2_mask.PNG",
            "expect_match": True,
        },
        {
            # The controller's confirm watcher matches this template.
            "name": "confirm button found in confirm_blue1",
            "screenshot": "confirm_blue1.PNG",
            "template": "confirm.PNG",
            # "mask": "confirm_mask.PNG",
            "expect_match": True,
        },
    ]

    @classmethod
    def setUpClass(cls):
        cls.res_dir = CUBE_RES
        cls._screenshots = {}
        cls._templates = {}
        cls._masks = {}

        for case in cls.CASES:
            # Load screenshot
            ss_path = os.path.join(CUBE_FIXTURES, case["screenshot"])
            ss = cv2.imread(ss_path, cv2.COLOR_RGB2BGR)
            assert ss is not None, f"Failed to load screenshot: {ss_path}"
            cls._screenshots[case["screenshot"]] = ss

            # Load template
            tmpl_path = os.path.join(cls.res_dir, case["template"])
            tmpl = load_template(tmpl_path)
            assert tmpl is not None, f"Failed to load template: {tmpl_path}"
            cls._templates[case["template"]] = tmpl

            # Load mask (optional)
            if case.get("mask"):
                mask = _load_mask(os.path.join(cls.res_dir, case["mask"]))
                cls._masks[case["mask"]] = mask

    @staticmethod
    def _draw_bbox(image, bbox, label=""):
        """Draw a green rectangle and optional label on a copy of the image."""
        debug_img = image.copy()
        x0, y0, x1, y1 = bbox
        cv2.rectangle(debug_img, (x0, y0), (x1, y1), (0, 255, 0), 2)
        if label:
            cv2.putText(
                debug_img,
                label,
                (x0, max(y0 - 10, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
        return debug_img

    def _run_case(self, case):
        screenshot = self._screenshots[case["screenshot"]]
        template = self._templates[case["template"]]
        mask = self._masks.get(case["mask"]) if case.get("mask") else None

        result = single_template_match(
            screenshot, template, mask=mask, method=cv2.TM_SQDIFF_NORMED, threshold=0.1
        )

        if case["expect_match"]:
            self.assertIsNotNone(
                result,
                f"{case['name']}: expected a match but none found",
            )
            bbox, score = result
            print(f"  bbox = {bbox}, score = {score:.4f}")
        else:
            self.assertIsNone(
                result,
                f"{case['name']}: expected no match but got {result}",
            )

    @unittest.skip("Debug visualization test, not part of automated test suite")
    def test_debug_visualization(self):
        """Show each screenshot with matched bbox drawn (for manual inspection)."""
        for case in self.CASES:
            screenshot = self._screenshots[case["screenshot"]]
            template = self._templates[case["template"]]
            mask = self._masks.get(case.get("mask")) if case.get("mask") else None

            result = single_template_match(
                screenshot,
                template,
                # mask=mask,
                method=cv2.TM_SQDIFF_NORMED,
                threshold=0.1,
            )
            if result is None:
                print(f"[DEBUG] {case['name']}: no match, skipping")
                continue

            bbox, score = result
            label = f"{case['name']}  score={score:.4f}"
            debug_img = self._draw_bbox(screenshot, bbox, label)
            window_name = case["name"][:40]
            cv2.imshow(window_name, debug_img)

        print("[DEBUG] Press any key to close all windows...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def test_all_cases(self):
        """Run every confirm/reset template matching case."""
        for case in self.CASES:
            with self.subTest(name=case["name"]):
                self._run_case(case)


if __name__ == "__main__":
    unittest.main()
