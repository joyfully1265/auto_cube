"""Flame mode profile."""

from __future__ import annotations

import os

from ...core.mode_profile import ModeProfile
from ...core.ocr_processor import PaddleOCRProcessor
from ...core.window_analyzer import WindowAnalyzer
from .window_analyzer import OFFSETS

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
RES_DIR = os.path.join(_ROOT, "res", "flame")
DATA_DIR = os.path.join(_ROOT, "data", "flame")


def _build_ocr_processor(analyzer: WindowAnalyzer) -> PaddleOCRProcessor:
    return PaddleOCRProcessor(analyzer=analyzer)


def build_profile() -> ModeProfile:
    """Return the profile used by the flame (bonus stat) workflow."""
    return ModeProfile(
        name="Flame",
        action_label="Enhancing",
        res_dir=RES_DIR,
        data_dir=DATA_DIR,
        offsets=OFFSETS,
        ocr_processor_factory=_build_ocr_processor,
        reset_clicks=2,
        data_files=("item_category.json", "stats.json"),
    )
