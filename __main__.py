"""Entry point for running the cube package as a module.

Usage:
    python -m cube          # settings window
    python -m cube --cli    # terminal workflow
"""

import sys

from .interface.application import Application
import logging
from .logging_config import configure_logging


def main() -> None:
    # Logs contain typographic dashes and box drawing; consoles default to cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    configure_logging(logging.INFO)

    application = Application()
    if "--cli" in sys.argv[1:]:
        application.run()
    else:
        application.run_gui()


if __name__ == "__main__":
    main()
