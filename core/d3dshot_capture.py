"""D3DShot-based screen capture implementation.

This module provides a concrete implementation of the ScreenCapture interface
using d3dshot for screen capture and OpenCV template matching to locate
the enhancement window.
"""

import logging
import os
from typing import Optional

import cv2
import numpy as np

import d3dshot

from .capture_interface import ScreenCapture
from .template_matcher import load_template
from .window_pos import get_classname, process_coords


class D3DShotScreenCapture(ScreenCapture):
    """Screen capture backend using d3dshot and template matching.

    Captures the full display via d3dshot, then uses OpenCV template matching
    to locate and crop the enhancement window.

    Mimics the d3dshot interface: call ``capture()`` once to start continuous
    background capture, then use ``get_latest_frame()`` to retrieve frames.
    """

    def __init__(
        self,
        res_dir: str,
        template_name: str = "enhance_window.PNG",
        window_class_name: Optional[str] = None,
    ):
        """Initialize the D3DShot screen capture.

        Args:
            res_dir: Directory holding this mode's templates.
            template_name: Window anchor template used to crop the screenshot.
            window_class_name: Windows class name of the MapleStory window.
                When provided, ``capture()`` will crop the screenshot to this
                window's bounds. When ``None``, the full screenshot is returned.
        """
        template_path = os.path.join(res_dir, template_name)
        self._template_path = template_path
        self._template = load_template(template_path)
        if self._template is None:
            raise FileNotFoundError(
                f"Failed to load enhancement window template from {template_path}"
            )

        self.logger = logging.getLogger(__name__)
        self._window_class_name = (
            get_classname(window_class_name) if window_class_name else None
        )
        self._d3dshot = d3dshot.create(capture_output="numpy", frame_buffer_size=20)
        coords = None
        if self._window_class_name is not None:
            coords = process_coords(self._window_class_name)
        self.logger.info(f"[D3DShotScreenCapture] coords({coords})")
        self._coords = coords

    def capture(self, target_fps: int = 60, region=None) -> bool:
        """Start continuous background capture.

        Args:
            target_fps: Target frames per second for the capture loop.
            region: Optional ``(left, top, right, bottom)`` tuple to crop
                the capture area.

        Returns:
            ``True`` if capture started successfully, ``False`` if already
            capturing.
        """
        if region is None:
            region = self._coords
        return self._d3dshot.capture(target_fps=target_fps, region=region)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Retrieve the most recent frame from the capture buffer.

        Returns:
            A numpy array (BGR, OpenCV-compatible) containing the latest
            screenshot, or ``None`` if no frame is available yet.
        """
        try:
            frame = self._d3dshot.get_latest_frame()
            if frame is None:
                return None

            # d3dshot returns RGB; convert to BGR for OpenCV compatibility
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return frame
        except Exception:
            return None

    def get_coords(self):
        return self._coords

    def stop(self) -> bool:
        """Stop continuous background capture.

        Returns:
            ``True`` if capture was stopped, ``False`` if it was not running.
        """
        return self._d3dshot.stop()

    @property
    def is_capturing(self) -> bool:
        """Whether continuous capture is currently running."""
        return self._d3dshot.is_capturing
