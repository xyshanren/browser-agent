"""日志模块"""

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

_console = Console()


def create_logger(name: str = "browser-agent", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_path=False,
            show_time=False,
            console=_console,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False

    return logger


logger = create_logger()
