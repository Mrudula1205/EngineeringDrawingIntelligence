from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

DEFAULT_LOG_LEVEL = "INFO"


def get_log_level() -> str:
    level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    return level if level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else DEFAULT_LOG_LEVEL


def load_env() -> None:
    load_dotenv()


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, get_log_level(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
