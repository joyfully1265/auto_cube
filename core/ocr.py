"""OCR interface and implementations for the enhancement controller."""

from abc import ABC, abstractmethod
from typing import List, Optional
import cv2
import numpy as np

DEBUG = False


def _to_three_channel(image: np.ndarray) -> np.ndarray:
    """Convert an image to a 3-channel BGR array.

    PaddleOCR's document pipeline (orientation classification and unwarping)
    indexes ``shape[2]`` unconditionally, so grayscale regions must be
    expanded to three channels before inference.

    Args:
        image: Image as a numpy array of 2, 3 or 4 channels.

    Returns:
        Image as a 3-channel BGR numpy array.
    """
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 1:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def _show_debug_boxes(image: np.ndarray, texts: List[str], boxes: np.ndarray) -> None:
    """Draw detected text boxes and their labels for debugging."""
    canvas = image
    if canvas.ndim == 2:
        canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    elif canvas.shape[2] == 4:
        canvas = cv2.cvtColor(canvas, cv2.COLOR_BGRA2BGR)
    else:
        canvas = canvas.copy()
    if canvas.dtype != np.uint8:
        canvas = cv2.normalize(canvas, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    for text, box in zip(texts, boxes):
        x_min, y_min, x_max, y_max = (int(value) for value in box)
        cv2.rectangle(canvas, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        cv2.putText(
            canvas,
            text,
            (x_min, max(y_min - 5, 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
        )

    cv2.imshow("PaddleOCR detections", canvas)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


_ROW_ALIGNMENT_TOLERANCE = 12


def _group_text_by_row(texts: List[str], boxes: np.ndarray) -> List[str]:
    """Group OCR text fragments into reading-order lines.

    PaddleOCR returns fragments in detection order, which can place a value
    before the stat name it belongs to. Fragments of the same text row share a
    top or bottom edge, so a fragment joins the current row when either edge is
    within ``_ROW_ALIGNMENT_TOLERANCE`` of the row's edge. Rows are then
    ordered left to right.

    Args:
        texts: Detected text fragments.
        boxes: Axis-aligned boxes (``x_min, y_min, x_max, y_max``) matching
            ``texts``.

    Returns:
        One string per row, ordered top to bottom.
    """
    fragments = []
    for text, box in zip(texts, boxes):
        x_min, y_min, x_max, y_max = (float(value) for value in box)
        fragments.append((y_min, y_max, x_min, text))
    fragments.sort(key=lambda fragment: (fragment[0], fragment[2]))

    rows: List[List[tuple]] = []
    for fragment in fragments:
        if rows:
            row = rows[-1]
            row_top = min(item[0] for item in row)
            row_bottom = max(item[1] for item in row)
            edge_delta = min(abs(fragment[0] - row_top), abs(fragment[1] - row_bottom))
            if edge_delta <= _ROW_ALIGNMENT_TOLERANCE:
                row.append(fragment)
                continue
        rows.append([fragment])

    return [
        " ".join(item[3] for item in sorted(row, key=lambda item: item[2]))
        for row in rows
    ]


class OCR(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def extract_text(self, image: np.ndarray, psm: Optional[int] = None) -> str:
        """Extract text from an image.

        Args:
            image: Image as a numpy array (height, width, channels).
            psm: Tesseract page segmentation mode (0-13). If None, uses
                the engine's default config.

        Returns:
            Extracted text as a string.
        """
        pass


class TesseractOCR(OCR):
    """OCR implementation using pytesseract."""

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
    ):
        """Initialize the Tesseract OCR engine.

        Args:
            tesseract_cmd: Path to the tesseract executable. If None, assumes
                tesseract is in the system PATH.
        """
        try:
            import pytesseract
        except ImportError as e:
            raise ImportError(
                "pytesseract is required for TesseractOCR. Install it with: "
                "pip install pytesseract"
            ) from e

        self._pytesseract = pytesseract
        if tesseract_cmd is not None:
            self._pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract_text(self, image: np.ndarray, psm: Optional[int] = None) -> str:
        """Extract text from an image using pytesseract.

        Args:
            image: Image as a numpy array (height, width, channels).
            psm: Tesseract page segmentation mode (0-13).

        Returns:
            Extracted text as a string.
        """
        whitelist = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-%: "
        )
        if psm is not None:
            config = f'--psm {psm} -c tessedit_char_whitelist="{whitelist}"'
        else:
            config = f'-c tessedit_char_whitelist="{whitelist}"'
        text = self._pytesseract.image_to_string(image, config=config)

        return text


class PaddleOCR(OCR):
    """OCR implementation using PaddleOCR."""

    def __init__(self):
        """Initialize the PaddleOCR engine."""
        try:
            from paddleocr import PaddleOCR as PaddleOCR
        except ImportError as e:
            raise ImportError(
                "paddleocr is required for PaddleOCR. Install it with: "
                "pip install paddleocr"
            ) from e

        self._ocr_engine = PaddleOCR(
            engine="paddle_static",
        )

    def extract_text(self, image: np.ndarray, psm: Optional[int] = None) -> str:
        """Extract text from an image using PaddleOCR.

        Fragments are grouped into rows using their bounding boxes so each
        row reads left to right, e.g. "STR +28" rather than "+28 STR".

        Args:
            image: Image as a numpy array (height, width, channels).
            psm: Not used in PaddleOCR. Included for interface compatibility.

        Returns:
            Extracted text as a string with one row per line.
        """
        image = _to_three_channel(image)
        results = self._ocr_engine.predict(image)
        result = results[0]
        if DEBUG:
            _show_debug_boxes(image, result["rec_texts"], result["rec_boxes"])
        rows = _group_text_by_row(result["rec_texts"], result["rec_boxes"])
        return "\n".join(rows)
