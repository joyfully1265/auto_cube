"""Shared filesystem locations for tests."""

from __future__ import annotations

import os

_PACKAGE_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
CUBE_FIXTURES = os.path.join(FIXTURES_DIR, "cube")
FLAME_FIXTURES = os.path.join(FIXTURES_DIR, "flame")

RES_DIR = os.path.join(_PACKAGE_ROOT, "res")
CUBE_RES = os.path.join(RES_DIR, "cube")
FLAME_RES = os.path.join(RES_DIR, "flame")


def fixture(fixtures_dir: str, name: str) -> str:
    """Absolute path to a screenshot fixture."""
    return os.path.join(fixtures_dir, name)


def template(res_dir: str, name: str) -> str:
    """Absolute path to a template image."""
    return os.path.join(res_dir, name)
