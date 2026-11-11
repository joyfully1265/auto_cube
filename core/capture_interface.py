"""Screen capture interface for capturing the enhancement window.

This module defines the abstract interface for screen capture objects.
Concrete implementations can use d3dshot, GDI, or any other capture backend.

The interface mirrors d3dshot's capture model:
- ``capture()`` starts continuous background capture.
- ``get_latest_frame()`` retrieves the most recent frame from the buffer.
- ``stop()`` halts background capture.
"""

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class ScreenCapture(ABC):
    """Abstract base class for screen capture backends.

    Implementations must provide methods to start continuous capture,
    retrieve the latest frame, and stop capture.
    """

    @abstractmethod
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
        pass

    @abstractmethod
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Retrieve the most recent frame from the capture buffer.

        Returns:
            A numpy array containing the latest screenshot, or ``None`` if
            no frame is available yet.
        """
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stop continuous background capture.

        Returns:
            ``True`` if capture was stopped, ``False`` if it was not running.
        """
        pass

    @property
    @abstractmethod
    def is_capturing(self) -> bool:
        """Whether continuous capture is currently running."""
        pass
