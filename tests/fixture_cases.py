"""Helpers for expanding fixture expectations into individual test methods."""

from __future__ import annotations

import os


def add_fixture_tests(cls, expectations, check_method):
    """Add one ``test_sanity_<NN>`` method per fixture in *expectations*.

    unittest subtests cannot be selected on their own, so every fixture becomes
    a real test method that can be run or debugged individually. Numbers are
    zero padded so a ``-k test_sanity_07`` filter cannot also match ``17``.
    """
    for name in expectations:
        test_name = f"test_sanity_{os.path.splitext(name)[0].zfill(2)}"

        def test(self, fixture=name):
            getattr(self, check_method)(fixture)

        test.__name__ = test_name
        setattr(cls, test_name, test)

    return cls
