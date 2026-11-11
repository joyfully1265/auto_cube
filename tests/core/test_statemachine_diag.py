"""Diagnostic: render the unified state machine graph.

Writes ``statemachine.png`` next to the test output. Skipped unless
``VISUAL_DEBUG=1`` because it needs the pydot/graphviz toolchain.
"""

import os
import unittest
from unittest.mock import patch

from cube.core.controller import Controller
from cube.core.mode_profile import ModeProfile
from cube.modes.cube.window_analyzer import OFFSETS

_VISUAL_DEBUG = bool(os.environ.get("VISUAL_DEBUG"))


@unittest.skipUnless(_VISUAL_DEBUG, "set VISUAL_DEBUG=1 to render the graph")
class TestStateMachineGraph(unittest.TestCase):
    def test_generate_diagram(self):
        profile = ModeProfile(
            name="Cube",
            action_label="Cubing",
            res_dir="unused",
            data_dir="unused",
            offsets=OFFSETS,
            ocr_processor_factory=lambda analyzer: None,
        )
        with patch("cube.core.controller.D3DShotScreenCapture"), patch(
            "cube.core.controller.MouseTrackerAbsolute"
        ), patch("cube.core.controller.SocketKeySender"), patch(
            "cube.core.controller.SocketMouseSender"
        ):
            machine = Controller(profile)

        machine._graph().write_png("statemachine.png")


if __name__ == "__main__":
    unittest.main()
