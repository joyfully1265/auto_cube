"""OCR processing service: screenshot -> stat lines (+ rank).

Separated from the controller for testability. The window analyzer is
injected so each game mode can supply its own anchors and offsets.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

import cv2
import numpy as np

from .ocr import OCR, PaddleOCR, TesseractOCR
from .window_analyzer import WindowAnalyzer, WindowInfo
from ..models.equipment import Equipment
from ..models.stat_line import StatLine
from ..models.stat_parser import (
    extract_rank,
    parse_stat_lines,
    parse_stat_lines_paddle,
)

DEBUG = False


class OCRProcessor(ABC):
    """Base class for extracting stats from MapleStory window screenshots.

    Subclasses configure engine-specific handling, most notably how a
    cropped region is formatted before it is handed to the OCR engine.

    Args:
        ocr_engine: OCR engine to use.
        analyzer: Window analyzer supplying the mode's anchors and offsets.
    """

    def __init__(
        self,
        ocr_engine: OCR,
        analyzer: WindowAnalyzer,
        read_rank: bool = True,
    ):
        self.ocr_engine = ocr_engine
        self.analyzer = analyzer
        self.read_rank = read_rank

    @abstractmethod
    def _format_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """Prepare a cropped region for the underlying OCR engine."""

    def process_image(self, image: np.ndarray) -> List[StatLine]:
        """Extract stat lines from a window screenshot."""
        info = self.analyzer.analyze(image)
        return self._process_stats(image, info)

    def _process_stats(self, image: np.ndarray, info: WindowInfo) -> List[StatLine]:
        """Read and parse the stats region.

        Raises:
            ValueError: If no stats region could be determined from the anchors.
        """
        region_img = self.analyzer.get_after_stats_image(image, info)
        if region_img is None:
            raise ValueError("Could not determine stats region")

        return self._parse_stat_lines(self._ocr_region(region_img))

    def _parse_stat_lines(self, lines: List[str]) -> List[StatLine]:
        """Parse OCR text lines into stat lines for the configured engine."""
        return parse_stat_lines(lines)

    def _ocr_region(self, region: np.ndarray, psm: int = 4) -> List[str]:
        """Run OCR on a cropped region and return raw text lines."""
        if DEBUG:
            cv2.imshow("DEBUG: OCR region before", region)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        region = self._format_for_ocr(region)
        if DEBUG:
            cv2.imshow("DEBUG: OCR region after", region)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        text = self.ocr_engine.extract_text(region, psm=psm)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if DEBUG:
            print(f"DEBUG: OCR raw text:\n{text}")
            print(f"DEBUG: OCR parsed lines:\n{lines}")
        return lines

    def _extract_rank(self, image: np.ndarray, info: WindowInfo) -> Optional[str]:
        """Extract the rank label from the dedicated rank region.

        The rank strip is read without the engine-specific formatting used for
        stat lines: inverting and thresholding it destroys the coloured rank
        text.
        """
        rank_img = self.analyzer.get_rank_image(image, info)
        if rank_img is None:
            return None

        text = self.ocr_engine.extract_text(rank_img, psm=7)
        return extract_rank([line.strip() for line in text.split("\n") if line.strip()])

    def extract_equipment(self, image: np.ndarray) -> Equipment:
        """Extract equipment (rank + stat lines) from a window screenshot."""
        info = self.analyzer.analyze(image)
        rank = self._extract_rank(image, info) if self.read_rank else None
        # print(f"process start {time.perf_counter_ns() / 1000000}")
        stat_lines = self._process_stats(image, info)
        # print(f"process end   {time.perf_counter_ns() / 1000000}")
        if not stat_lines:
            raise ValueError("No stat lines could be extracted from the image")

        return Equipment(rank=rank, lines=stat_lines)

    @staticmethod
    def _to_grayscale(image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale."""
        if len(image.shape) == 3:
            if image.shape[2] == 4:
                return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    @staticmethod
    def _resize_for_ocr(image: np.ndarray, scale: int = 3) -> np.ndarray:
        """Upscale an image so small game text is legible to the engine."""
        h, w = image.shape[:2]
        return cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def _threshold_image(image: np.ndarray) -> np.ndarray:
        """Binarize a grayscale image with Otsu's method."""
        _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh


class TesseractOCRProcessor(OCRProcessor):
    """OCR processor tuned for Tesseract.

    Tesseract needs upscaled, inverted and thresholded text to read the small
    game font reliably, so regions are preprocessed before recognition.
    """

    def __init__(
        self,
        ocr_engine: Optional[OCR] = None,
        analyzer: Optional[WindowAnalyzer] = None,
        read_rank: bool = True,
    ):
        if analyzer is None:
            raise ValueError("WindowAnalyzer is required")
        super().__init__(ocr_engine or TesseractOCR(), analyzer, read_rank)

    def _format_for_ocr(self, image: np.ndarray) -> np.ndarray:
        resize = self._resize_for_ocr(image)
        invert = cv2.bitwise_not(resize)
        grayscale = self._to_grayscale(invert)
        return self._threshold_image(grayscale)


class PaddleOCRProcessor(OCRProcessor):
    """OCR processor for PaddleOCR.

    PaddleOCR has its own detection and preprocessing pipeline, so regions are
    passed through after upscaling. The engine is created lazily so importing
    this module never pulls in Paddle.
    """

    # Border added around a region so glyphs touching the region edge are not
    # clipped by PaddleOCR's detector, which drops the leading character when
    # text starts at pixel zero.
    _PADDING = 20

    def __init__(
        self,
        ocr_engine: Optional[OCR] = None,
        analyzer: Optional[WindowAnalyzer] = None,
        read_rank: bool = False,
    ):
        if analyzer is None:
            raise ValueError("WindowAnalyzer is required")
        super().__init__(ocr_engine or PaddleOCR(), analyzer, read_rank)

    def _format_for_ocr(self, image: np.ndarray) -> np.ndarray:
        resize = self._resize_for_ocr(image)
        invert = cv2.bitwise_not(resize)
        grayscale = self._to_grayscale(invert)
        threshold = self._threshold_image(grayscale)
        return cv2.copyMakeBorder(
            threshold,
            self._PADDING,
            self._PADDING,
            self._PADDING,
            self._PADDING,
            cv2.BORDER_REPLICATE,
        )

    def _parse_stat_lines(self, lines: List[str]) -> List[StatLine]:
        return parse_stat_lines_paddle(lines)
