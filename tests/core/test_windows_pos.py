
import os
import unittest

import cv2
import numpy as np

from cube.core.window_pos import get_classname, process_coords

class TestWindowsPos(unittest.TestCase):
    def test_process_coords(self):
        cname = get_classname("MapleStory")
        x0, y0, x1, y1 = process_coords(cname)
        print(f"window coords: ({x0}, {y0}) - ({x1}, {y1})")
        assert(x0 >= 0)
        assert(y0 >= 0)
        assert(x1 >= 0)
        assert(y1 >= 0)