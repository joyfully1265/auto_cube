"""Unified state machine for both automation modes.

The controller is identical for cube and flame mode; everything that differs
is supplied by a :class:`~cube.core.mode_profile.ModeProfile`.

States:

* ``IDLE`` - capture has not started yet.
* ``EVALUATING`` - the current equipment is compared against the goal.
* ``WORKING`` - a re-roll is applied:
  ``rerolling`` -> ``confirming`` -> ``is_changed`` -> ``done``.
* ``FINISHED`` - the goal has been reached or the session was aborted.
"""

from __future__ import annotations

import cProfile
import io
import logging
import os
import pstats
import threading
import time
from typing import Optional

import cv2
import numpy as np
from statemachine import StateChart, State

from .d3dshot_capture import D3DShotScreenCapture
from .mode_profile import ModeProfile
from .mouse import MouseTrackerAbsolute
from .io_interface import SocketKeySender, SocketMouseSender
from .template_matcher import load_template, single_template_match
from .window_analyzer import WindowAnalyzer
from ..models.equipment import Equipment
from ..models.goal import Goal


class Controller(StateChart):
    """State machine that orchestrates the re-roll workflow.

    Handles screen capture, OCR, and sending input to the game via a USB
    device. The mode profile decides which window layout, OCR engine and
    click behaviour are used.
    """

    def __init__(
        self,
        profile: ModeProfile,
        host: str = "192.168.1.132",
        port: int = 9999,
    ):
        super().__init__()
        self.profile = profile
        self.logger = logging.getLogger(__name__)

        # Set by stop() from another thread; checked on every state entry.
        self._stop_requested = threading.Event()

        # Templates are decoded once and reused instead of hitting disk on every poll
        self._template_cache: dict[str, Optional[np.ndarray]] = {}

        self._window_analyzer = WindowAnalyzer(profile.res_dir, profile.offsets)
        self.screen_capture = D3DShotScreenCapture(
            profile.res_dir, window_class_name="MapleStory"
        )
        self.key_sender = SocketKeySender(host, port)
        self.mouse_sender = SocketMouseSender(host, port)
        self.mouse_tracker = MouseTrackerAbsolute(
            self.screen_capture, self.mouse_sender
        )
        self.ocr_processor = profile.ocr_processor_factory(self._window_analyzer)

        self.equipment: Optional[Equipment] = None
        self.equipment_before: Optional[Equipment] = None
        self.goal_config: Optional[Goal] = None

        self._apply_retry_count = 0
        self._evaluate_count = 0
        self._is_changed_deadline = 0.0
        # Equipment read by ``is_changed``; consumed by the next evaluate pass
        # so the same screen is not OCR'd twice.
        self._pending_equipment: Optional[Equipment] = None
        # Confirm-phase bookkeeping for the ``confirming`` state.
        self._confirm_deadline = 0.0
        self._confirm_last_seen = 0.0
        self._cursor_ready = False

    # States

    class working(State.Compound):
        rerolling = State(initial=True)
        confirming = State()
        is_changed = State()
        done = State(final=True)

        reroll = rerolling.to.itself() | is_changed.to(rerolling)
        verify = rerolling.to(confirming)
        poll_confirm = confirming.to.itself()
        confirm_done = confirming.to(is_changed)
        finish = is_changed.to(done)
        retry_if_unchanged = is_changed.to.itself()
        error_execution = rerolling.to(done) | confirming.to(done) | is_changed.to(done)

    idle = State(initial=True)
    evaluating = State()
    finished = State(final=True)

    # Transitions
    evaluate = idle.to(evaluating) | evaluating.to(evaluating) | working.to(evaluating)
    apply = evaluating.to(working.rerolling)
    abort = evaluating.to(finished) | working.to(finished)
    error_execution = evaluating.to(finished) | working.to(finished)

    # ── lifecycle hooks ────────────────────────────────────────────────

    def on_exit_idle(self):
        self.screen_capture.capture(target_fps=self.profile.capture_fps)
        time.sleep(1)

    def on_enter_evaluating(self):
        self.logger.info("Evaluating")

        if self._abort_if_stopped():
            return

        if self.goal_config is None:
            raise RuntimeError("Goal configuration not set before execution")

        self._evaluate_count += 1
        if self._evaluate_count > self.profile.max_evaluate_loops:
            self.logger.error(
                f"Exceeded max evaluate loops "
                f"({self.profile.max_evaluate_loops}) – aborting"
            )
            self.abort()
            return

        equipment = self._take_pending_equipment()
        if equipment is None:
            frame = self.screen_capture.get_latest_frame()
            if frame is None:
                self.logger.error("Failed to capture")
                self.send("evaluate", delay=self.profile.retry_wait_ms)
                return

            equipment = self._get_current_stats(frame)
            if equipment is None:
                self.logger.error("Failed to extract equipment stats from frame")
                self.send("evaluate", delay=self.profile.retry_wait_ms)
                return

        self.equipment = equipment
        self.goal_config.prepare(self.equipment)
        self.logger.info(f"Current equipment {self.equipment}")
        self._log_goal_state()

        if self.goal_config.is_met(self.equipment):
            self.logger.info("Goal met")
            self.abort()
        else:
            self.logger.info("Goal not met")
            self.apply()

    def on_enter_working(self):
        """Record the pre-roll state before the reset is applied."""
        self.logger.info(self.profile.action_label)

        # Save current equipment so we can verify the re-roll changed it
        self.equipment_before = self.equipment
        self._pending_equipment = None
        self._apply_retry_count = 0
        self._is_changed_deadline = 0.0
        self._confirm_deadline = 0.0
        self._confirm_last_seen = 0.0
        self._cursor_ready = False

    def on_enter_rerolling(self):
        self.logger.info("Rerolling")

        if self._abort_if_stopped():
            return

        self._apply_retry_count += 1
        if self._apply_retry_count > self.profile.max_apply_retries:
            self.logger.error(
                f"Exceeded max reroll retries "
                f"({self.profile.max_apply_retries}) – aborting"
            )
            self.abort()
            return

        if self.mouse_tracker is None or self.key_sender is None:
            self.logger.error("Input devices not available – aborting")
            self.abort()
            return

        if not self._cursor_ready:
            # Click is relative to the cursor
            if self.mouse_tracker.refresh() is None:
                self.logger.error("Cursor not found – aborting")
                self.abort()
                return
            self._cursor_ready = True

        frame = self.screen_capture.get_latest_frame()
        if frame is None:
            self.logger.error("Failed to capture frame for window analysis")
            self.send("reroll", delay=self.profile.retry_wait_ms)
            return

        window_info = self._window_analyzer.analyze(frame)
        if window_info.reset_purple_region is not None:
            button = window_info.reset_purple_region
        elif window_info.reset_button_region is not None:
            button = window_info.reset_button_region
        else:
            self.logger.warning("Could not find reset button")
            self.send("reroll", delay=self.profile.retry_wait_ms)
            return

        try:
            win_off_x, win_off_y = self.mouse_tracker.window_offset
            button_x = button.center[0] + win_off_x + self.profile.button_offset_x
            button_y = button.center[1] + win_off_y
            for click_index in range(self.profile.reset_clicks):
                self.mouse_tracker.click_at(button_x, button_y)
                if click_index + 1 < self.profile.reset_clicks:
                    time.sleep(self.profile.click_gap_s)
        except Exception as error:
            self.logger.error(f"Failed to click reset button: {error}")
            raise

        self.verify()

    def on_enter_confirming(self):
        """Dismiss the reset confirmation dialog from inside the state machine.

        Each pass performs a single poll: if the confirm button is visible,
        Enter is sent and the state re-enters itself after a short delay so
        stacked dialogs are dismissed one after another.  The machine advances
        to ``is_changed`` once the dialog has been gone for
        ``confirm_absent_s``, or once ``confirm_timeout_s`` elapses without any
        dialog appearing.  If the dialog is still visible when the timeout
        elapses the run is aborted rather than OCR-ing a covered screen.
        """
        self.logger.info("Confirming")

        if self._abort_if_stopped():
            return

        now = time.time()
        if self._confirm_deadline == 0.0:
            self._confirm_deadline = now + self.profile.confirm_timeout_s

        frame = self._get_cropped_frame()
        dialog_visible = frame is not None and self._find_template(
            frame, self.profile.confirm_template
        )

        if dialog_visible:
            if now >= self._confirm_deadline:
                self.logger.error(
                    f"Confirm dialog still visible after "
                    f"{self.profile.confirm_timeout_s}s – aborting"
                )
                self.abort()
                return

            self.logger.debug("Confirm dialog found – sending enter key")
            self._confirm_last_seen = now
            self.key_sender.send_key(self.profile.enter_key_code)
            time.sleep(self.profile.confirm_key_hold_s)
            self.key_sender.release_all_keys()
            # Let the dialog close before pressing again
            self.send("poll_confirm", delay=self.profile.confirm_repress_delay_ms)
            return

        if self._confirm_last_seen == 0.0:
            # Nothing has shown up yet; wait briefly before giving up on it.
            if now >= self._confirm_deadline:
                self.logger.debug("No confirm dialog appeared – continuing")
                self.confirm_done()
            else:
                self.send("poll_confirm", delay=self.profile.confirm_poll_interval_ms)
            return

        if now - self._confirm_last_seen >= self.profile.confirm_absent_s:
            self.logger.debug("Confirm dialog dismissed")
            self.confirm_done()
        else:
            self.send("poll_confirm", delay=self.profile.confirm_poll_interval_ms)

    def on_enter_is_changed(self):
        """Wait until the stats differ from the pre-reroll stats.

        The confirmation dialog is dismissed by the ``confirming`` state, so
        the stats on screen may still be the old ones (or be covered by the
        dialog). Poll until they change; abort once the timeout elapses so we
        never re-roll over an unread result.
        """
        self.logger.info("IsChanged")

        if self._abort_if_stopped():
            return

        if self._is_changed_deadline == 0.0:
            self._is_changed_deadline = time.time() + self.profile.is_changed_timeout_s

        new_equipment = None
        frame = self.screen_capture.get_latest_frame()
        if frame is not None:
            new_equipment = self._get_current_stats(frame)

        if new_equipment is None or new_equipment == self.equipment_before:
            if time.time() >= self._is_changed_deadline:
                self.logger.error(
                    f"Equipment stats did not change within "
                    f"{self.profile.is_changed_timeout_s}s – cannot safely "
                    "determine current stats, exiting to avoid rolling over "
                    "the desired stats"
                )
                self.abort()
                return
            self.send("retry_if_unchanged", delay=self.profile.retry_wait_ms)
            return

        self.equipment = new_equipment
        self.logger.info(f"Equipment changed {self.equipment}")
        self._log_goal_state()
        # Hand the settled reading to the next evaluate pass: it is the same
        # screen, so OCR does not need to run again.
        self._pending_equipment = new_equipment
        self.finish()

    def on_enter_done(self):
        if self.profile.settle_delay_s > 0:
            time.sleep(self.profile.settle_delay_s)
        self._evaluate_count = 0
        self.evaluate()

    def on_enter_finished(self):
        self._log_goal_state()
        self._shutdown()

    def on_error_execution(self, error):
        self.logger.error(
            f"Execution failed due to: {error}. Transitioning to final state."
        )

    # ── shutdown ───────────────────────────────────────────────────────

    def stop(self) -> None:
        """Request an abort; safe to call from another thread."""
        self.logger.info("Stop requested")
        self._stop_requested.set()

    @property
    def stop_requested(self) -> bool:
        """Whether stop() was called; safe to read from another thread."""
        return self._stop_requested.is_set()

    def _abort_if_stopped(self) -> bool:
        """Abort when stop() was called; returns True if the run ended."""
        if not self._stop_requested.is_set():
            return False
        self.logger.info("Stop requested – aborting")
        self.abort()
        return True

    def _shutdown(self) -> None:
        """Stop every background resource owned by the controller."""
        if getattr(self, "screen_capture", None) is not None:
            self._stop_capture()

    def _stop_capture(self):
        """Safely stop the screen capture if it is running."""
        try:
            if self.screen_capture.is_capturing:
                self.screen_capture.stop()
                self.logger.info("Screen capture stopped")
        except Exception as error:
            self.logger.error(f"Error stopping screen capture: {error}")

    # ── template / OCR helpers ─────────────────────────────────────────

    def _get_cropped_frame(self):
        """Crop the frame to the region where the confirm window appears."""
        frame = self.screen_capture.get_latest_frame()
        if frame is None:
            return None

        coords = self.screen_capture.get_coords()
        half = self.profile.confirm_crop_half_size
        width = coords[2] - coords[0]
        height = coords[3] - coords[1]

        return frame[
            height // 2 - half : height // 2 + half,
            width // 2 - half : width // 2 + half,
        ]

    def _find_template(self, frame, template_name: str):
        """Locate a template in the frame, caching decoded images."""
        template = self._template_cache.get(template_name)
        if template is None:
            template_path = self.profile.res_path(f"{template_name}.PNG")
            template = load_template(template_path)
            if template is None:
                self.logger.debug(f"Template not found: {template_path}")
                return None
            self._template_cache[template_name] = template

        result = single_template_match(
            frame,
            template,
            threshold=self.profile.offsets.match_threshold,
            method=cv2.TM_SQDIFF_NORMED,
        )
        if result is None:
            return None
        return result[0]

    def _get_current_stats(self, frame) -> Optional[Equipment]:
        """Run OCR on a frame, returning None if the read failed."""
        try:
            equipment = self.ocr_processor.extract_equipment(frame)
            self.logger.debug(
                f"OCR extracted equipment: rank={equipment.rank}, "
                f"lines={len(equipment.lines)}"
            )
            return equipment
        except Exception as error:
            self.logger.error(f"Error during capture/OCR: {error}")
            return None

    def _take_pending_equipment(self) -> Optional[Equipment]:
        """Return the equipment read by ``is_changed``, consuming it.

        ``is_changed`` OCRs the settled screen to prove the stats changed. The
        following ``evaluating`` pass would read the exact same screen, so the
        cached result is reused to avoid a second, expensive OCR run.
        """
        equipment = self._pending_equipment
        self._pending_equipment = None
        if equipment is not None:
            self.logger.debug("Reusing is_changed reading for evaluation")
        return equipment

    def _log_goal_state(self) -> None:
        """Log optional per-evaluation detail supplied by the goal."""
        if self.goal_config is None or self.equipment is None:
            return

        detail = self.goal_config.describe_state(self.equipment)
        if detail:
            self.logger.info(detail)

    # ── execution ──────────────────────────────────────────────────────

    def run(
        self,
        goal_config: Goal,
        profile: bool = False,
        profile_output: str = "controller_profile.stats",
    ) -> None:
        """Execute the full state machine loop."""
        if profile:
            self._run_profiled(goal_config, profile_output)
        else:
            self._run_inner(goal_config)

    def _run_inner(self, goal_config: Goal) -> None:
        """Core state-machine execution (no profiling)."""
        self.goal_config = goal_config
        self._stop_requested.clear()
        self._pending_equipment = None
        try:
            self.logger.info(f"Starting {self.profile.name.lower()} controller")
            self.evaluate()
            self.logger.info(f"{self.profile.name} controller finished")
        finally:
            self._shutdown()

    def _run_profiled(self, goal_config: Goal, profile_output: str) -> None:
        """Execute the state machine under cProfile and dump stats."""
        self.logger.info(f"Profiling enabled – stats will be saved to {profile_output}")
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            self._run_inner(goal_config)
        finally:
            profiler.disable()
            profiler.dump_stats(profile_output)

            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.strip_dirs()
            stats.sort_stats(pstats.SortKey.CUMULATIVE)
            stats.print_stats(30)
            self.logger.info(
                f"Profile summary (top 30 by cumulative time):\n{stream.getvalue()}"
            )
