"""Shared backend for both automation modes."""

from .capture_interface import ScreenCapture
from .config_loader import ConfigLoader
from .d3dshot_capture import D3DShotScreenCapture
from .ocr import OCR, PaddleOCR, TesseractOCR
from .ocr_processor import OCRProcessor, PaddleOCRProcessor, TesseractOCRProcessor
from .template_matcher import load_template, single_template_match
from .window_analyzer import (
    Anchor,
    AnchorFinder,
    BoundingBox,
    RegionDeriver,
    WindowAnalyzer,
    WindowInfo,
    WindowOffsets,
)

__all__ = [
    "Anchor",
    "AnchorFinder",
    "BoundingBox",
    "ConfigLoader",
    "D3DShotScreenCapture",
    "OCR",
    "OCRProcessor",
    "PaddleOCR",
    "PaddleOCRProcessor",
    "RegionDeriver",
    "ScreenCapture",
    "TesseractOCR",
    "TesseractOCRProcessor",
    "WindowAnalyzer",
    "WindowInfo",
    "WindowOffsets",
    "load_template",
    "single_template_match",
]
