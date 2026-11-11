"""Per-mode configuration for the unified controller.

Everything that differs between cube and flame mode lives here: template
directory, window offsets, OCR engine, click behaviour and retry policy. The
controller itself is identical for both modes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from .ocr_processor import OCRProcessor
from .window_analyzer import WindowAnalyzer, WindowOffsets

PACKAGE_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

OCREngineFactory = Callable[[WindowAnalyzer], OCRProcessor]


@dataclass(frozen=True)
class ModeProfile:
    """Mode-specific configuration consumed by :class:`Controller`.

    Args:
        name: Mode name shown in the CLI (``"Cube"`` / ``"Flame"``).
        action_label: Verb for log lines (``"Cubing"`` / ``"Enhancing"``).
        res_dir: Directory holding this mode's template images.
        data_dir: Directory holding this mode's JSON data.
        offsets: Window layout offsets and template filenames.
        ocr_processor_factory: Builds the mode's OCR processor for an analyzer.
        reset_clicks: How many times to click the reset button per roll.
        click_gap_s: Gap between reset clicks.
        settle_delay_s: Delay after confirming before verifying new stats.
        is_changed_timeout_s: How long to wait for the stats to change.
        retry_wait_ms: Delay before retrying a failed evaluate/reroll.
        capture_fps: Target capture frame rate.
        max_apply_retries: Maximum reset attempts per roll.
        max_evaluate_loops: Maximum evaluate passes before aborting.
        confirm_template: Template name used by the confirm watcher.
        confirm_poll_interval_ms: Delay between confirm-dialog polls.
        confirm_repress_delay_ms: Delay after Enter before polling again.
        confirm_key_hold_s: How long Enter is held for the game to poll it.
        confirm_timeout_s: Max time spent dismissing the confirm dialog(s).
        confirm_absent_s: How long the dialog must stay gone before advancing.
        enter_key_code: Virtual key code used to dismiss dialogs.
        button_offset_x: X offset applied to the reset button centre.
        confirm_crop_half_size: Half-size of the centre crop for the watcher.
    """

    name: str
    action_label: str
    res_dir: str
    data_dir: str
    offsets: WindowOffsets
    ocr_processor_factory: OCREngineFactory
    reset_clicks: int = 2
    click_gap_s: float = 0.08
    settle_delay_s: float = 0.0
    is_changed_timeout_s: float = 3.0
    retry_wait_ms: int = 100
    capture_fps: int = 20
    max_apply_retries: int = 5
    max_evaluate_loops: int = 3
    confirm_template: str = "confirm"
    confirm_poll_interval_ms: int = 50
    confirm_repress_delay_ms: int = 200
    confirm_key_hold_s: float = 0.2
    confirm_timeout_s: float = 1.0
    confirm_absent_s: float = 0.3
    enter_key_code: int = 0x28
    button_offset_x: int = 35
    confirm_crop_half_size: int = 300
    data_files: tuple[str, ...] = ("item_category.json", "stats.json")

    def res_path(self, filename: str) -> str:
        """Absolute path to a template in this mode's resource directory."""
        return os.path.join(self.res_dir, filename)
