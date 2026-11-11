"""Logging bootstrap shared by the entry points.

Provides a single place to define the log line format so that every module
that configures logging produces identical output, including millisecond
timestamps.

Only application loggers (``cube.*``) honour the requested level. The root
logger and third-party loggers are pinned to ``WARNING`` so a DEBUG run does
not drown in library internals such as ``statemachine.engines.base``.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

APP_LOGGER_NAME = "cube"

# Libraries that are noisy below WARNING and/or call ``setLevel`` themselves,
# which would otherwise bypass the root logger level.
THIRD_PARTY_LOGGERS = (
    "asyncio",
    "d3dshot",
    "PIL",
    "paddle",
    "paddleocr",
    "statemachine",
    "urllib3",
)

MIN_THIRD_PARTY_LEVEL = logging.WARNING


def configure_logging(level: int = logging.INFO) -> None:
    """Configure logging so only application loggers honour ``level``.

    The root logger is set to ``WARNING`` and the ``cube`` logger to ``level``,
    so ``level=logging.DEBUG`` shows application debug output only. Third-party
    loggers are explicitly raised to ``WARNING`` because a library that calls
    ``setLevel`` on itself would still emit records to the root handler.

    Only the first call has an effect; later calls (for example the default
    ``configure_logging()`` in ``cube.core.mouse``) must not lower the level
    chosen by the entry point.
    """
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    if app_logger.level != logging.NOTSET:
        return

    logging.basicConfig(
        level=MIN_THIRD_PARTY_LEVEL,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    app_logger.setLevel(level)
    for name in THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(MIN_THIRD_PARTY_LEVEL)
