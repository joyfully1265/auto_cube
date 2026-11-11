"""Tests for the unified workspace controller."""

import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from cube.core.controller import Controller
from cube.core.mode_profile import ModeProfile
from cube.core.window_analyzer import BoundingBox, WindowAnalyzer, WindowInfo
from cube.models.equipment import Equipment
from cube.models.goal import Goal
from cube.models.stat_line import StatLine
from cube.modes.cube.window_analyzer import OFFSETS
from cube.tests.paths import CUBE_FIXTURES, CUBE_RES, fixture


class StubGoal(Goal):
    """Goal whose result is decided by a callable."""

    def __init__(self, is_met_fn):
        self._is_met_fn = is_met_fn
        self.prepared = []
        self.evaluated = []

    def is_met(self, equipment):
        self.evaluated.append(equipment)
        return self._is_met_fn(equipment)

    def describe(self):
        return "stub goal"

    def prepare(self, equipment):
        self.prepared.append(equipment)


def make_profile(**overrides):
    defaults = dict(
        name="Cube",
        action_label="Cubing",
        res_dir=CUBE_RES,
        data_dir="unused",
        offsets=OFFSETS,
        ocr_processor_factory=lambda analyzer: MagicMock(),
        retry_wait_ms=0,
        is_changed_timeout_s=0.05,
        click_gap_s=0.0,
        reset_clicks=2,
        # The confirm phase must not add wall-clock time to unrelated tests.
        confirm_poll_interval_ms=0,
        confirm_repress_delay_ms=0,
        confirm_key_hold_s=0.0,
        confirm_timeout_s=0.0,
        confirm_absent_s=0.0,
    )
    defaults.update(overrides)
    return ModeProfile(**defaults)


def make_equipment(value):
    return Equipment(rank="Legendary", lines=[StatLine("STR", value)])


class ControllerTestBase(unittest.TestCase):
    """Builds a controller with every external dependency mocked."""

    profile_overrides = {}

    def setUp(self):
        self.profile = make_profile(**self.profile_overrides)
        with patch("cube.core.controller.D3DShotScreenCapture") as capture_cls, patch(
            "cube.core.controller.MouseTrackerAbsolute"
        ) as mouse_cls, patch("cube.core.controller.SocketKeySender"), patch(
            "cube.core.controller.SocketMouseSender"
        ):
            self.controller = Controller(self.profile)

        self.controller.screen_capture = capture_cls.return_value
        self.controller.screen_capture.is_capturing = True
        self.controller.screen_capture.get_latest_frame.return_value = np.zeros(
            (100, 100, 3), dtype=np.uint8
        )
        self.controller.screen_capture.get_coords.return_value = (0, 0, 100, 100)

        self.controller.mouse_tracker = mouse_cls.return_value
        self.controller.mouse_tracker.window_offset = (100, 200)
        self.controller.mouse_tracker.refresh.return_value = (10, 10)
        self.controller.mouse_tracker.click_at = MagicMock()

        self.controller.ocr_processor = MagicMock()
        self.controller._window_analyzer = MagicMock()
        self.controller._window_analyzer.analyze.return_value = WindowInfo(
            reset_button_region=BoundingBox.from_xywh(10, 20, 40, 10)
        )
        self.controller._find_template = MagicMock(return_value=None)

    def clicks(self):
        return [
            call.args for call in self.controller.mouse_tracker.click_at.call_args_list
        ]


class TestEvaluate(ControllerTestBase):
    def test_goal_met_stops_capture(self):
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(
            10
        )
        goal = StubGoal(lambda equipment: True)

        self.controller.run(goal)

        self.controller.screen_capture.stop.assert_called()
        self.assertEqual(len(goal.prepared), 1)
        self.assertEqual(len(goal.evaluated), 1)

    def test_missing_goal_transitions_to_finished(self):
        self.controller.run(None)

        self.assertTrue(self.controller.finished.is_active)

    def test_capture_failure_retries_then_aborts(self):
        self.controller.screen_capture.get_latest_frame.return_value = None
        goal = StubGoal(lambda equipment: True)

        self.controller.run(goal)

        self.assertEqual(len(goal.evaluated), 0)
        self.assertTrue(self.controller.finished.is_active)


class TestReroll(ControllerTestBase):
    def test_reset_clicked_configured_times_at_region_centre(self):
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(1)
        goal = StubGoal(lambda equipment: False)

        self.controller.run(goal)

        # Region centre (30, 25) + window offset (100, 200) + button offset 35
        expected = (165, 225)
        self.assertEqual(self.clicks(), [expected, expected])

    def test_reset_click_count_follows_profile(self):
        self.profile_overrides = {"reset_clicks": 1}
        self.setUp()
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(1)

        self.controller.run(StubGoal(lambda equipment: False))

        self.assertEqual(len(self.clicks()), 1)

    def test_purple_region_is_preferred(self):
        self.controller._window_analyzer.analyze.return_value = WindowInfo(
            reset_button_region=BoundingBox.from_xywh(10, 20, 40, 10),
            reset_purple_region=BoundingBox.from_xywh(50, 60, 20, 10),
        )
        self.controller.mouse_tracker.window_offset = (0, 0)
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(1)

        self.controller.run(StubGoal(lambda equipment: False))

        # Purple centre (60, 65) + button offset 35
        self.assertEqual(self.clicks()[0], (95, 65))

    def test_missing_region_never_clicks(self):
        self.controller._window_analyzer.analyze.return_value = WindowInfo()
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(1)

        self.controller.run(StubGoal(lambda equipment: False))

        self.assertEqual(self.clicks(), [])
        self.assertTrue(self.controller.finished.is_active)

    def test_cursor_not_found_transitions_to_finished(self):
        self.controller.mouse_tracker.refresh.return_value = None
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(1)

        self.controller.run(StubGoal(lambda equipment: False))

        self.assertTrue(self.controller.finished.is_active)
        self.assertEqual(self.clicks(), [])


class TestIsChanged(ControllerTestBase):
    def test_timeout_aborts_when_stats_do_not_change(self):
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(
            10
        )

        self.controller.run(StubGoal(lambda equipment: False))

        self.assertTrue(self.controller.finished.is_active)
        self.assertEqual(len(self.clicks()), 2)

    def test_changed_stats_are_evaluated_next_round(self):
        # The evaluate pass after a roll reuses the is_changed reading, so only
        # two OCR runs happen: the initial evaluate and the change detection.
        self.controller.ocr_processor.extract_equipment.side_effect = [
            make_equipment(10),
            make_equipment(25),
        ]
        goal = StubGoal(lambda equipment: equipment.lines[0].value == 25)

        self.controller.run(goal)

        self.assertEqual(
            [equipment.lines[0].value for equipment in goal.evaluated], [10, 25]
        )
        self.assertEqual(len(self.clicks()), 2)

    def test_evaluate_reuses_is_changed_reading(self):
        self.controller.ocr_processor.extract_equipment.side_effect = [
            make_equipment(10),
            make_equipment(25),
        ]
        goal = StubGoal(lambda equipment: equipment.lines[0].value == 25)

        self.controller.run(goal)

        self.assertEqual(self.controller.ocr_processor.extract_equipment.call_count, 2)


class TestConfirming(ControllerTestBase):
    def test_presses_enter_when_dialog_visible_then_advances(self):
        # A positive timeout is needed because the first poll already sees the
        # dialog, and the timeout bounds how long Enter may be retried.
        self.profile_overrides = {"confirm_timeout_s": 5.0}
        self.setUp()
        self.controller._find_template = MagicMock(side_effect=[(0, 0, 10, 10), None])
        self.controller.ocr_processor.extract_equipment.side_effect = [
            make_equipment(10),
            make_equipment(25),
        ]
        goal = StubGoal(lambda equipment: equipment.lines[0].value == 25)

        self.controller.run(goal)

        self.controller.key_sender.send_key.assert_called_once_with(
            self.profile.enter_key_code
        )
        self.controller.key_sender.release_all_keys.assert_called()
        self.assertEqual(
            [equipment.lines[0].value for equipment in goal.evaluated], [10, 25]
        )

    def test_no_dialog_advances_without_pressing_enter(self):
        self.controller.ocr_processor.extract_equipment.side_effect = [
            make_equipment(10),
            make_equipment(25),
        ]
        goal = StubGoal(lambda equipment: equipment.lines[0].value == 25)

        self.controller.run(goal)

        self.controller.key_sender.send_key.assert_not_called()
        self.assertEqual(
            [equipment.lines[0].value for equipment in goal.evaluated], [10, 25]
        )

    def test_stuck_dialog_aborts_after_timeout(self):
        self.profile_overrides = {
            "confirm_timeout_s": 0.03,
            "confirm_poll_interval_ms": 5,
            "confirm_repress_delay_ms": 5,
        }
        self.setUp()
        self.controller._find_template = MagicMock(return_value=(0, 0, 10, 10))
        self.controller.ocr_processor.extract_equipment.return_value = make_equipment(
            10
        )

        self.controller.run(StubGoal(lambda equipment: False))

        self.assertTrue(self.controller.finished.is_active)
        self.controller.key_sender.send_key.assert_called()

    def test_confirm_template_found_in_blue_dialog_frame(self):
        """Real cropping plus template matching must detect the blue dialog."""
        frame = cv2.imread(fixture(CUBE_FIXTURES, "confirm_blue1.PNG"))
        self.assertIsNotNone(frame)
        self.controller.screen_capture.get_latest_frame.return_value = frame
        self.controller.screen_capture.get_coords.return_value = (
            0,
            0,
            frame.shape[1],
            frame.shape[0],
        )
        # Earlier tests stub this out; use the real crop and matching here.
        del self.controller._find_template

        cropped = self.controller._get_cropped_frame()
        self.assertIsNotNone(cropped)
        self.assertIsNotNone(
            self.controller._find_template(cropped, self.profile.confirm_template)
        )

    def test_shutdown_stops_capture(self):
        self.controller._shutdown()

        self.controller.screen_capture.stop.assert_called()


class TestCubeProfile(unittest.TestCase):
    def test_profile_uses_cube_templates_and_reads_rank(self):
        from cube.modes.cube.profile import build_profile

        profile = build_profile()
        self.assertEqual(profile.name, "Cube")
        self.assertEqual(profile.reset_clicks, 2)
        self.assertTrue(profile.res_dir.endswith("cube"))

        analyzer = WindowAnalyzer(profile.res_dir, profile.offsets)
        processor = profile.ocr_processor_factory(analyzer)
        self.assertTrue(processor.read_rank)


if __name__ == "__main__":
    unittest.main()
