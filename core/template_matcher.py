"""Template matching utilities for locating UI elements in MapleStory.

This module provides functions for finding the potential window and extracting
stat lines using OpenCV template matching.
"""

import cv2
import numpy as np
from typing import Optional, Tuple


def load_template(path: str) -> Optional[np.ndarray]:
    """Load a template image from the given path.

    Args:
        path: Path to the template image.

    Returns:
        The loaded template image, or None if loading failed.
    """
    template = cv2.imread(path, cv2.COLOR_RGBA2BGR)
    if template is None:
        return None
    return template


def single_template_match(
    image: np.ndarray,
    template: np.ndarray,
    method: int = cv2.TM_CCOEFF_NORMED,
    threshold: float = 0.8,
    mask: Optional[np.ndarray] = None,
) -> Optional[Tuple[Tuple[int, int, int, int], float]]:
    """Find the best match of a template in an image.

    Args:
        image: Source image
        template: Template image
        method: OpenCV template matching method.
        threshold: For TM_SQDIFF / TM_SQDIFF_NORMED, the maximum allowed
            difference (lower is better). For all other methods, the minimum
            match score to consider valid (higher is better).
        mask: Optional grayscale mask (H x W) same size as template.
            White (255) = match this pixel, black (0) = ignore.
            Only supported with TM_SQDIFF and TM_CCORR_NORMED methods.

    Returns:
        (x0, y0, x1, y1) and score, or None if no match found.
    """
    # Ensure both have the same number of channels
    if len(image.shape) != len(template.shape):
        raise ValueError("Image and template must have the same number of channels.")

    if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
        return None

    if mask is not None:
        result = cv2.matchTemplate(image, template, method, mask=mask)
    else:
        result = cv2.matchTemplate(image, template, method)

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    is_sqdiff = method in (cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED)

    if is_sqdiff:
        if min_val > threshold:
            return None
        score = float(min_val)
        top_left = min_loc
    else:
        if max_val < threshold:
            return None
        score = float(max_val)
        top_left = max_loc

    h, w = template.shape[:2]
    bottom_right = (top_left[0] + w, top_left[1] + h)
    bbox = (top_left[0], top_left[1], bottom_right[0], bottom_right[1])

    return bbox, score
