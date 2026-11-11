"""Anchor-based window analyzer.

Uses master anchor templates to reliably locate UI elements in a
MapleStory enhancement window without hardcoding absolute coordinates.

Two window layouts are supported, selected automatically by which anchor
is found:

    - Purple window: has a BEFORE/AFTER stats comparison area
    - Blue window: no comparison area, only the current stats

Master anchors:
    1. AFTER text  - top of the "after stats" area (purple only)
    2. Enhance     - window title/button anchor (blue only)
    3. Reset       - reset button (blue)
    4. Reset purple- reset button (purple)

All other elements are derived from these anchors using offsets that are
supplied by the caller, because the offsets differ per game mode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

import cv2
import numpy as np

from .template_matcher import load_template, single_template_match

# Overlay colours for ``WindowAnalyzer.draw_boxes`` (BGR).
ANCHOR_COLOR = (0, 255, 0)
REGION_COLOR = (255, 128, 0)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned rectangle defined by (x0, y0, x1, y1) corners."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def top_left(self) -> tuple[int, int]:
        return (self.x0, self.y0)

    @property
    def center(self) -> tuple[int, int]:
        return (self.x0 + self.width // 2, self.y0 + self.height // 2)

    @classmethod
    def from_xywh(cls, x: int, y: int, w: int, h: int) -> "BoundingBox":
        return cls(x0=x, y0=y, x1=x + w, y1=y + h)


@dataclass
class Anchor:
    """A located anchor point with its bounding box and match score."""

    name: str
    box: BoundingBox
    score: float = 0.0


@dataclass
class WindowInfo:
    """All information extracted from a window screenshot."""

    after_anchor: Optional[Anchor] = None
    enhance_anchor: Optional[Anchor] = None
    reset_button_anchor: Optional[Anchor] = None
    reset_purple_anchor: Optional[Anchor] = None

    after_stats_region: Optional[BoundingBox] = None
    rank_region: Optional[BoundingBox] = None
    reset_button_region: Optional[BoundingBox] = None
    reset_purple_region: Optional[BoundingBox] = None

    @property
    def is_valid(self) -> bool:
        """Whether the anchors required for some window layout were found."""
        return bool(
            (self.reset_button_anchor or self.reset_purple_anchor)
            and (self.enhance_anchor or self.after_anchor)
        )


@dataclass(frozen=True)
class WindowOffsets:
    """Region offsets and matching settings for one window layout.

    Offsets are relative to each anchor's top-left corner. The template
    filenames are included so a mode package can describe its window layout
    in one place.
    """

    after_stats_region: Dict[str, int]
    purple_rank_region: Dict[str, int]
    blue_stats_region: Dict[str, int]
    blue_rank_region: Dict[str, int]
    reset_button_offset: Dict[str, int]
    reset_purple_offset: Dict[str, int]
    templates: Dict[str, str]
    match_threshold: float = 0.05


# ---------------------------------------------------------------------------
# Anchor finder - handles template loading and matching
# ---------------------------------------------------------------------------


class AnchorFinder:
    """Loads template images and finds them in screenshots via template matching.

    Args:
        res_dir: Path to the directory containing template images.
        match_threshold: Minimum template matching score (0-1) to accept a match.
    """

    def __init__(self, res_dir: str, match_threshold: float):
        self.res_dir = res_dir
        self.match_threshold = match_threshold
        self._cache: Dict[str, Optional[np.ndarray]] = {}

    def load_template(self, filename: str) -> Optional[np.ndarray]:
        """Load a template image in BGR (cached)."""
        if filename not in self._cache:
            path = os.path.join(self.res_dir, filename)
            self._cache[filename] = load_template(path)
        return self._cache[filename]

    def find(
        self,
        frame: np.ndarray,
        template_name: str,
        filename: str,
    ) -> Optional[Anchor]:
        """Find a single anchor template in the frame.

        Args:
            frame: Screenshot as numpy array (BGR).
            template_name: Human-readable name for the anchor.
            filename: Template image filename in res_dir.

        Returns:
            Anchor if found above threshold, else None.
        """
        template = self.load_template(filename)
        if template is None:
            return None

        result = single_template_match(
            frame,
            template,
            method=cv2.TM_SQDIFF_NORMED,
            threshold=self.match_threshold,
        )
        if result is None:
            return None

        box, score = result
        return Anchor(name=template_name, box=BoundingBox(*box), score=score)


# ---------------------------------------------------------------------------
# Region deriver - computes UI element regions from anchors
# ---------------------------------------------------------------------------


class RegionDeriver:
    """Derives UI element bounding boxes from located anchors.

    Regions are derived best-effort: a missing anchor leaves its regions as
    ``None`` so a live loop can retry instead of crashing on a partial frame.
    """

    def __init__(self, offsets: WindowOffsets):
        self._offsets = offsets

    def derive(self, anchors: Dict[str, Optional[Anchor]]) -> WindowInfo:
        """Derive all regions from the located anchors."""
        info = WindowInfo(
            after_anchor=anchors.get("after"),
            enhance_anchor=anchors.get("enhance"),
            reset_button_anchor=anchors.get("reset_button"),
            reset_purple_anchor=anchors.get("reset_button_purple"),
        )

        if info.after_anchor is not None:
            info.after_stats_region = self._region_from(
                info.after_anchor, self._offsets.after_stats_region
            )
            info.rank_region = self._region_from(
                info.after_anchor, self._offsets.purple_rank_region
            )
            if info.reset_purple_anchor is not None:
                info.reset_purple_region = self._region_from(
                    info.reset_purple_anchor, self._offsets.reset_purple_offset
                )

        elif info.enhance_anchor is not None:
            info.after_stats_region = self._region_from(
                info.enhance_anchor, self._offsets.blue_stats_region
            )
            info.rank_region = self._region_from(
                info.enhance_anchor, self._offsets.blue_rank_region
            )
            if info.reset_button_anchor is not None:
                info.reset_button_region = self._region_from(
                    info.reset_button_anchor, self._offsets.reset_button_offset
                )

        return info

    @staticmethod
    def _region_from(anchor: Anchor, offsets: Dict[str, int]) -> BoundingBox:
        """Compute a region relative to an anchor's top-left corner."""
        return BoundingBox.from_xywh(
            anchor.box.x0 + offsets["x_offset"],
            anchor.box.y0 + offsets["y_offset"],
            offsets["width"],
            offsets["height"],
        )


# ---------------------------------------------------------------------------
# Debug helpers
# ---------------------------------------------------------------------------


def _draw_box(
    image: np.ndarray,
    box: BoundingBox,
    label: str,
    color: tuple[int, int, int],
) -> None:
    """Outline *box* on *image* in place, labelling it outside the box."""
    height, width = image.shape[:2]
    x0 = max(0, box.x0)
    y0 = max(0, box.y0)
    x1 = min(width - 1, box.x1)
    y1 = min(height - 1, box.y1)
    if x1 <= x0 or y1 <= y0:
        return

    cv2.rectangle(image, (x0, y0), (x1, y1), color, 1)
    text_y = y0 - 4 if y0 >= 14 else y1 + 12
    cv2.putText(
        image,
        label,
        (x0, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        color,
        1,
        cv2.LINE_AA,
    )


# ---------------------------------------------------------------------------
# Main analyzer - orchestrates anchor finding and region derivation
# ---------------------------------------------------------------------------


class WindowAnalyzer:
    """Analyzes window screenshots using master anchors.

    Coordinates an :class:`AnchorFinder` and a :class:`RegionDeriver` to
    locate all UI elements from a screenshot.

    Args:
        res_dir: Directory holding the mode's template images.
        offsets: Region offsets, templates and threshold for the window layout.
    """

    def __init__(self, res_dir: str, offsets: WindowOffsets):
        self._finder = AnchorFinder(res_dir, offsets.match_threshold)
        self._deriver = RegionDeriver(offsets)
        self._templates = offsets.templates

    def analyze(self, frame: np.ndarray) -> WindowInfo:
        """Find anchors and derive all regions."""
        return self._deriver.derive(self.find_anchors(frame))

    def find_anchors(self, frame: np.ndarray) -> Dict[str, Optional[Anchor]]:
        """Find every anchor defined for this layout."""
        return {
            name: self._finder.find(frame, name, filename)
            for name, filename in self._templates.items()
        }

    def extract_region(
        self,
        frame: np.ndarray,
        region: Optional[BoundingBox],
    ) -> Optional[np.ndarray]:
        """Extract a region from the frame, clamping to image bounds."""
        if region is None:
            return None
        h, w = frame.shape[:2]
        x0 = max(0, region.x0)
        y0 = max(0, region.y0)
        x1 = min(w, region.x1)
        y1 = min(h, region.y1)
        if x1 <= x0 or y1 <= y0:
            return None
        return frame[y0:y1, x0:x1]

    def get_after_stats_image(
        self, frame: np.ndarray, info: WindowInfo
    ) -> Optional[np.ndarray]:
        """Extract the after-stats region from the frame."""
        return self.extract_region(frame, info.after_stats_region)

    def get_reset_button_image(
        self, frame: np.ndarray, info: WindowInfo
    ) -> Optional[np.ndarray]:
        """Extract the reset button region from the frame."""
        return self.extract_region(frame, info.reset_button_region)

    def get_reset_purple_image(
        self, frame: np.ndarray, info: WindowInfo
    ) -> Optional[np.ndarray]:
        """Extract the reset purple button region from the frame."""
        return self.extract_region(frame, info.reset_purple_region)

    def get_rank_image(
        self, frame: np.ndarray, info: WindowInfo
    ) -> Optional[np.ndarray]:
        """Extract the rank label region from the frame."""
        return self.extract_region(frame, info.rank_region)

    def draw_boxes(
        self,
        frame: np.ndarray,
        info: Optional[WindowInfo] = None,
        output_path: Optional[str] = None,
    ) -> np.ndarray:
        """Return a copy of the frame with every anchor and region outlined.

        Anchors are drawn in green with their match score, derived regions in
        blue with their name. When *info* is omitted the frame is analyzed
        first, so this can be called on a raw screenshot. Setting
        *output_path* also writes the annotated image to disk.
        """
        if info is None:
            info = self.analyze(frame)

        canvas = frame.copy()
        if canvas.ndim == 3 and canvas.shape[2] == 4:
            canvas = cv2.cvtColor(canvas, cv2.COLOR_BGRA2BGR)

        layers = (
            (
                ANCHOR_COLOR,
                [
                    (anchor.name, anchor.box, anchor.score)
                    for anchor in (
                        info.after_anchor,
                        info.enhance_anchor,
                        info.reset_button_anchor,
                        info.reset_purple_anchor,
                    )
                    if anchor is not None
                ],
            ),
            (
                REGION_COLOR,
                [
                    (name, region, None)
                    for name, region in (
                        ("after_stats", info.after_stats_region),
                        ("rank", info.rank_region),
                        ("reset_button", info.reset_button_region),
                        ("reset_purple", info.reset_purple_region),
                    )
                    if region is not None
                ],
            ),
        )
        for color, boxes in layers:
            for name, box, score in boxes:
                label = name if score is None else f"{name} {score:.2f}"
                _draw_box(canvas, box, label, color)

        if output_path is not None:
            cv2.imwrite(output_path, canvas)
        return canvas
