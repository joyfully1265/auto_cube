"""Test cases for the MouseTracker class."""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from cube.core.mouse import MouseTracker
from cube.core.capture_interface import ScreenCapture
from cube.core.io_interface import MouseSender

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class MockScreenCapture(ScreenCapture):
    """Screen capture mock that returns a pre-set frame."""

    def __init__(self, frame=None):
        self._frame = frame
        self._capturing = False

    def capture(self, target_fps=60, region=None):
        self._capturing = True
        return True

    def get_latest_frame(self):
        return self._frame

    def stop(self):
        self._capturing = False
        return True

    @property
    def is_capturing(self):
        return self._capturing


class MockMouseSender(MouseSender):
    """Mouse sender mock that records all mouse move and click events."""

    def __init__(self):
        self.mouse_moves = []
        self.absolute_moves = []
        self.click_count = 0

    def move_mouse(self, x, y):
        self.mouse_moves.append((x, y))

    def press_button(self, button):
        pass

    def release_button(self, button):
        pass

    def click_button(self, button):
        self.click_count += 1

    def move_mouse_absolute(self, x, y):
        self.absolute_moves.append((x, y))


def _make_finder(box):
    """Create a mock ``CursorFinder`` that returns the given box."""
    finder = MagicMock()
    finder.find_first.return_value = box
    return finder


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMouseTrackerInit(unittest.TestCase):
    """Test MouseTracker initialisation."""

    def test_init_loads_default_finder(self):
        """MouseTracker should create a default CursorFinder on init."""
        screen = MockScreenCapture()
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender)
        self.assertIsNotNone(tracker._finder)

    def test_cursor_position_initially_none(self):
        """Cursor position should be None before the first refresh."""
        screen = MockScreenCapture()
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender)
        self.assertIsNone(tracker.cursor_position)


class TestMouseTrackerRefresh(unittest.TestCase):
    """Test cursor localisation via refresh()."""

    def test_refresh_finds_cursor(self):
        """refresh() should locate the cursor in a screenshot."""
        screen = MockScreenCapture(np.zeros((200, 300, 3), dtype=np.uint8))
        finder = _make_finder((93, 70, 108, 90))
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)

        pos = tracker.refresh()
        self.assertIsNotNone(pos)
        self.assertEqual(pos, (93, 70))

    def test_refresh_returns_none_on_blank_screen(self):
        """refresh() should return None when the cursor is not present."""
        screen = MockScreenCapture(np.zeros((200, 300, 3), dtype=np.uint8))
        finder = _make_finder(None)
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)

        # Prevent calibrate() from hitting the real Windows API when the
        # cursor is not found after the jiggle recovery step.
        with patch.object(MouseTracker, "calibrate"):
            pos = tracker.refresh()
        self.assertIsNone(pos)

    def test_refresh_returns_none_on_failed_capture(self):
        """refresh() should return None when screen capture fails."""
        screen = MockScreenCapture(None)
        finder = _make_finder((0, 0, 10, 10))
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)

        pos = tracker.refresh()
        self.assertIsNone(pos)

    def test_refresh_jiggles_when_initial_find_fails_then_recovers(self):
        """refresh() should jiggle between the initial find and calibrate.

        The cursor is not visible on the first two captures, but is found
        on the third (after jiggle re-captures).  refresh() should return
        the recovered position and have issued the jiggle moves.
        """
        finder = MagicMock()
        # No cursor initially, then a hit once jiggle has re-rendered it.
        finder.find_first.side_effect = [None, (93, 70, 108, 90)]

        frames = [
            np.zeros((200, 300, 3), dtype=np.uint8),
            np.zeros((200, 300, 3), dtype=np.uint8),
        ]
        screen = MockScreenCapture(frames)
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)

        pos = tracker.refresh()

        self.assertEqual(pos, (93, 70))
        # Default jiggle: delta=5, cycles=2 -> 4 mouse moves (5,0),(-5,0),(5,0),(-5,0)
        self.assertEqual(
            mouse_sender.mouse_moves,
            [(5, 0), (-5, 0), (5, 0), (-5, 0)],
        )


class TestMouseTrackerJiggle(unittest.TestCase):
    """Test the jiggle() recovery helper."""

    def test_jiggle_sends_alternating_moves(self):
        """jiggle() should send ``+delta`` followed by ``-delta`` for each cycle."""
        screen = MockScreenCapture()
        finder = _make_finder(None)
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)

        tracker.jiggle(delta=3, cycles=2, delay_ms=0)

        # 2 cycles * 2 half-moves = 4 total moves, alternating +/- 3 on x.
        self.assertEqual(
            mouse_sender.mouse_moves,
            [(3, 0), (-3, 0), (3, 0), (-3, 0)],
        )

    def test_jiggle_default_uses_five_pixel_delta(self):
        """jiggle() with default args should use a 5-pixel delta and 2 cycles."""
        screen = MockScreenCapture()
        finder = _make_finder(None)
        mouse_sender = MockMouseSender()
        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)

        tracker.jiggle()

        self.assertEqual(len(mouse_sender.mouse_moves), 4)
        for dx, _ in mouse_sender.mouse_moves:
            self.assertIn(abs(dx), (5,))


class TestMouseTrackerMoveTo(unittest.TestCase):
    """Test move_to computes correct relative deltas."""

    def test_move_to_sends_relative_delta(self):
        """move_to should send the correct (dx, dy) to the mouse sender."""
        screen = MockScreenCapture(np.zeros((200, 300, 3), dtype=np.uint8))
        finder = _make_finder((93, 70, 108, 90))  # centre ~(100, 80)
        mouse_sender = MockMouseSender()

        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)
        tracker.refresh()

        dx, dy = tracker.move_to(150, 120)
        self.assertEqual(dx, 57)
        self.assertEqual(dy, 50)
        self.assertEqual(mouse_sender.mouse_moves, [(57, 50)])

    def test_move_to_no_movement_when_already_there(self):
        """move_to should not send any mouse moves when already at target."""
        screen = MockScreenCapture(np.zeros((200, 300, 3), dtype=np.uint8))
        finder = _make_finder((93, 70, 108, 90))
        mouse_sender = MockMouseSender()

        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)
        tracker.refresh()

        dx, dy = tracker.move_to(tracker.cursor_position[0], tracker.cursor_position[1])
        self.assertEqual(dx, 0)
        self.assertEqual(dy, 0)
        self.assertEqual(mouse_sender.mouse_moves, [])

    @patch("cube.core.mouse.get_classname", return_value="MapleStory")
    @patch("cube.core.mouse.process_coords", return_value=(0, 0, 800, 600))
    def test_move_to_calibrates_when_cursor_unknown(self, mock_coords, mock_classname):
        """move_to should attempt calibration via refresh when cursor position
        is unknown."""
        screen = MockScreenCapture(np.zeros((200, 300, 3), dtype=np.uint8))
        finder = _make_finder(None)
        mouse_sender = MockMouseSender()

        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)
        dx, dy = tracker.move_to(150, 120)
        # process_coords is mocked to return (0, 0, 800, 600) -> centre (400, 300)
        # dx = 150 - 400 = -250, dy = 120 - 300 = -180
        self.assertEqual(dx, -250)
        self.assertEqual(dy, -180)
        self.assertTrue(len(mouse_sender.mouse_moves) > 0)


class TestMouseTrackerClickAt(unittest.TestCase):
    """Test click_at moves and clicks."""

    def test_click_at_sends_move_and_click(self):
        """click_at should move to target and then send a mouse click."""
        screen = MockScreenCapture(np.zeros((200, 300, 3), dtype=np.uint8))
        finder = _make_finder((93, 70, 108, 90))
        mouse_sender = MockMouseSender()

        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)
        tracker.refresh()

        tracker.click_at(150, 120)

        self.assertTrue(len(mouse_sender.mouse_moves) >= 1)
        self.assertEqual(mouse_sender.click_count, 1)


class TestMouseTrackerMultiStep(unittest.TestCase):
    """Test multi-step relative moves."""

    def test_multi_step_move_breaks_delta(self):
        """With steps > 1, the delta should be split across multiple calls."""
        screen = MockScreenCapture(np.zeros((200, 300, 3), dtype=np.uint8))
        finder = _make_finder((93, 70, 108, 90))
        mouse_sender = MockMouseSender()

        tracker = MouseTracker(screen, mouse_sender=mouse_sender, cursor_finder=finder)
        tracker.refresh()

        tracker.move_to(130, 100, steps=3)

        self.assertEqual(len(mouse_sender.mouse_moves), 3)

        total_dx = sum(m[0] for m in mouse_sender.mouse_moves)
        total_dy = sum(m[1] for m in mouse_sender.mouse_moves)
        self.assertEqual(total_dx, 37)
        self.assertEqual(total_dy, 30)


if __name__ == "__main__":
    unittest.main()
