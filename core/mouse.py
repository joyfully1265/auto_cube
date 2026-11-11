"""Mouse tracking and movement for the enhancement controller.

Cursor matching is delegated to :class:`mouse_finder.CursorFinder`.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import numpy as np

from mouse_finder import CursorFinder
from .capture_interface import ScreenCapture
from .io_interface import MouseSender
from .window_pos import get_classname, process_coords
from ..logging_config import configure_logging

DEBUG = False


class MouseTracker:
    """Track the on-screen cursor and compute relative move deltas.

    Args:
        screen_capture: A ``ScreenCapture`` backend used to grab screenshots.
        mouse_sender: ``MouseSender`` used to dispatch relative mouse moves
            and button clicks.
        cursor_finder: Optional ``CursorFinder`` instance.  When *None* (the
            default), a ``CursorFinder`` with the built-in composites is used.
            Inject a custom instance (e.g. with different templates) for
            testing.
    """

    _cached_window_coords: Optional[Tuple[int, int, int, int]] = None

    def __init__(
        self,
        screen_capture: ScreenCapture,
        mouse_sender: MouseSender,
        cursor_finder: Optional[CursorFinder] = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        configure_logging()
        self._capture = screen_capture
        self._mouse_sender = mouse_sender
        self._cursor_pos: Optional[Tuple[int, int]] = None  # (cx, cy)
        self._threshold: float = 0.05
        self._finder: CursorFinder = cursor_finder or CursorFinder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def cursor_position(self) -> Optional[Tuple[int, int]]:
        """Last known cursor centre ``(x, y)``, or ``None`` if not yet found."""
        return self._cursor_pos

    def calibrate(self, window_class: str = "MapleStory") -> None:
        """Recalibrate cursor position by moving to origin then to the game window.

        Args:
            window_class: Window class name to look up via ``get_classname``.
                Defaults to ``"MapleStory"``.
        """
        import time

        self._send_relative_move(self._mouse_sender, -2560, -1440, steps=1, delay_ms=20)
        time.sleep(0.1)

        coords = MouseTracker._cached_window_coords
        if coords is None:
            cname = get_classname(window_class)
            coords = process_coords(cname)

        x0, y0, x1, y1 = coords
        if any(c < 0 for c in coords):
            raise ValueError(f"Window coordinates contain negative values: {coords}")

        if MouseTracker._cached_window_coords is None:
            MouseTracker._cached_window_coords = coords

        centre_x = (x0 + x1) // 2
        centre_y = (y0 + y1) // 2

        if DEBUG:
            print(
                f"[MouseTracker] window coords: ({x0}, {y0}) - ({x1}, {y1}) centre=({centre_x}, {centre_y})"
            )

        self._send_relative_move(
            self._mouse_sender, centre_x, centre_y, steps=10, delay_ms=20
        )
        time.sleep(0.1)

        self._cursor_pos = (centre_x, centre_y)

    def jiggle(
        self,
        delta: int = 5,
        cycles: int = 2,
        delay_ms: float = 50.0,
    ) -> None:
        """Jiggle the mouse back and forth to force the cursor to render.

        Sends a small alternating relative move so the OS re-renders the
        cursor sprite.  Used as a recovery step when the cursor was not
        found in a fresh screenshot.

        Args:
            delta: Pixels to move each direction per half-cycle.
            cycles: Number of back-and-forth cycles.  Each cycle is one
                move positive and one move negative.
            delay_ms: Delay in milliseconds between each half-cycle move.
        """

        for _ in range(cycles):
            self._mouse_sender.move_mouse(delta, 0)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            self._mouse_sender.move_mouse(-delta, 0)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    def refresh(self) -> Optional[Tuple[int, int]]:
        """Re-localise the cursor in a fresh screenshot.

        If the initial search fails, the cursor is jiggled to provoke a
        re-render before falling back to a full calibration.

        Returns:
            Cursor centre ``(x, y)`` or ``None`` if the cursor was not found.
        """
        frame = self._capture.get_latest_frame()
        if frame is None:
            return None

        pos = self._find_cursor(frame)
        if pos is not None:
            self._cursor_pos = pos
            return pos

        self.jiggle()
        frame = self._capture.get_latest_frame()
        if frame is not None:
            pos = self._find_cursor(frame)
            if pos is not None:
                self._cursor_pos = pos
                return pos

        self.calibrate()
        time.sleep(0.5)
        frame = self._capture.get_latest_frame()
        if frame is not None:
            pos = self._find_cursor(frame)
            if pos is not None:
                self._cursor_pos = pos

        return pos

    def move_to(
        self,
        target_x: int,
        target_y: int,
        steps: int = 1,
        delay_ms: float = 0.0,
    ) -> Tuple[int, int]:
        """Move the cursor to an absolute screen position.

        Args:
            target_x: Absolute x-coordinate on screen.
            target_y: Absolute y-coordinate on screen.
            steps: Number of intermediate move steps.
            delay_ms: Delay in milliseconds between steps.

        Returns:
            The ``(dx, dy)`` delta that was sent.

        Raises:
            RuntimeError: If the cursor position is unknown.
        """
        if self._cursor_pos is None:
            self.refresh()

        if self._cursor_pos is None:
            raise RuntimeError("Cannot determine cursor position for relative move")

        cur_x, cur_y = self._cursor_pos
        dx = target_x - cur_x
        dy = target_y - cur_y

        if dx == 0 and dy == 0:
            return (0, 0)

        self._send_relative_move(self._mouse_sender, dx, dy, steps, delay_ms)

        self._cursor_pos = (target_x, target_y)
        return (dx, dy)

    def click_at(
        self,
        target_x: int,
        target_y: int,
    ) -> None:
        """Move the cursor to ``(target_x, target_y)`` and click.

        Args:
            target_x: Absolute x-coordinate on screen.
            target_y: Absolute y-coordinate on screen.
        """
        self.move_to(target_x, target_y)
        time.sleep(0.15)
        self._mouse_sender.click_button(1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_cursor(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        """Delegate to :meth:`CursorFinder.find_first` and return screen-absolute coordinates.

        The cursor finder returns coordinates relative to the captured frame
        (which may be cropped to the game window).  We add the stored window
        offset to convert to full-screen coordinates.
        """

        box = self._finder.find_first(screenshot, threshold=self._threshold)
        if box is None:
            return None
        x0, y0, x1, y1 = box
        # Convert from window-relative to screen-absolute
        offset_x, offset_y = getattr(self, "_window_offset", (0, 0))
        return x0 + offset_x, y0 + offset_y

    @staticmethod
    def _send_relative_move(
        mouse_sender: "MouseSender",
        dx: int,
        dy: int,
        steps: int = 1,
        delay_ms: float = 0.0,
    ) -> None:
        """Break a large delta into *steps* relative moves and send them.

        Each step is clamped to the int8 range (-127 to 127) so that USB HID
        relative mouse reports never overflow.  Any remainder is carried over
        to subsequent steps.
        """

        _INT8_MIN = -127
        _INT8_MAX = 127

        if steps < 1:
            steps = 1

        remaining_x = dx
        remaining_y = dy

        print(
            f"[MouseTracker] move_mouse dx={dx} dy={dy} "
            f"steps={steps} delay_ms={delay_ms}"
        )

        i = 0
        while remaining_x != 0 or remaining_y != 0:
            # Divide remaining delta across remaining steps (at least 1)
            steps_left = max(steps - i, 1)
            step_dx = remaining_x // steps_left
            step_dy = remaining_y // steps_left
            remaining_x -= step_dx
            remaining_y -= step_dy

            # Clamp to int8 range and carry over the remainder
            if step_dx > _INT8_MAX:
                remaining_x += step_dx - _INT8_MAX
                step_dx = _INT8_MAX
            elif step_dx < _INT8_MIN:
                remaining_x += step_dx - _INT8_MIN
                step_dx = _INT8_MIN

            if step_dy > _INT8_MAX:
                remaining_y += step_dy - _INT8_MAX
                step_dy = _INT8_MAX
            elif step_dy < _INT8_MIN:
                remaining_y += step_dy - _INT8_MIN
                step_dy = _INT8_MIN

            if step_dx == 0 and step_dy == 0:
                i += 1
                print(f"  step {i}/{steps}: skipped (zero delta)")
                continue

            i += 1
            print(
                f"  step {i}/{steps}: "
                f"step_dx={step_dx} step_dy={step_dy} "
                f"remaining_x={remaining_x} remaining_y={remaining_y}"
            )
            mouse_sender.move_mouse(step_dx, step_dy)

            if delay_ms > 0 and (remaining_x != 0 or remaining_y != 0):
                time.sleep(delay_ms / 1000.0)


class MouseTrackerAbsolute(MouseTracker):
    """Mouse tracker that uses absolute HID mouse positioning instead of relative deltas.

    All coordinates are in **full screen** pixel space.  The driver handles
    conversion to the HID absolute range (0-32767).

    Args:
        screen_capture: A ``ScreenCapture`` backend used to grab screenshots.
        mouse_sender: ``MouseSender`` used to dispatch absolute mouse moves
            and button clicks.
        cursor_finder: Optional ``CursorFinder`` instance.  When *None* (the
            default), a ``CursorFinder`` with the built-in composites is used.
            Inject a custom instance (e.g. with different templates) for
            testing.
    """

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._window_offset: Tuple[int, int] = (0, 0)

    @property
    def window_offset(self) -> Tuple[int, int]:
        """The top-left corner of the captured window in screen coordinates."""
        return self._window_offset

    def calibrate(self, window_class: str = "MapleStory") -> None:
        """Move the cursor to the centre of the game window using screen coordinates.

        Stores the window offset so that cursor positions found in
        window-relative screenshots can be converted back to screen coordinates.

        Args:
            window_class: Window class name to look up via ``get_classname``.
                Defaults to ``"MapleStory"``.
        """
        coords = MouseTracker._cached_window_coords
        if coords is None:
            try:
                cname = get_classname(window_class)
                coords = process_coords(cname)
            except Exception:
                self._cursor_pos = (0, 0)
                self._window_offset = (0, 0)
                return

        x0, y0, x1, y1 = coords
        if any(c < 0 for c in coords):
            raise ValueError(f"Window coordinates contain negative values: {coords}")

        if MouseTracker._cached_window_coords is None:
            MouseTracker._cached_window_coords = coords

        # Store window top-left so we can convert window-relative coords to screen coords
        self._window_offset = (x0, y0)

        centre_x = (x0 + x1) // 2
        centre_y = (y0 + y1) // 2

        if DEBUG:
            print(
                f"[MouseTrackerAbsolute] window coords: ({x0}, {y0}) - ({x1}, {y1}) centre=({centre_x}, {centre_y})"
            )

        self._mouse_sender.move_mouse_absolute(centre_x, centre_y)
        self._cursor_pos = (centre_x, centre_y)

    def move_to(
        self,
        target_x: int,
        target_y: int,
        steps: int = 1,
        delay_ms: float = 0.0,
    ) -> Tuple[int, int]:
        """Move the cursor to an absolute screen position (in pixels).

        Args:
            target_x: Absolute x-coordinate on screen in pixels.
            target_y: Absolute y-coordinate on screen in pixels.
            steps: Ignored (kept for API compatibility).
            delay_ms: Ignored (kept for API compatibility).

        Returns:
            The ``(target_x, target_y)`` position that was sent.
        """
        self.logger.debug(f"move_to ({target_x}, {target_y})")
        self._mouse_sender.move_mouse_absolute(target_x, target_y)
        self._cursor_pos = (target_x, target_y)
        return (target_x, target_y)

    def refresh(self) -> Optional[Tuple[int, int]]:
        """Re-localise the cursor, calibrating the window offset first if needed.

        Unlike the base class, this ensures ``_window_offset`` is populated
        (via :meth:`calibrate`) before attempting template matching so that
        cursor coordinates are always returned in screen-absolute space.
        """
        if self._window_offset == (0, 0):
            self.calibrate()
        return super().refresh()
