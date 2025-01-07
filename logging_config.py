# kaltura_uploader/logging_config.py

import re
import logging
from typing import Optional
import os

try:
    import colorlog
except ImportError:
    colorlog = None  # Handle absence gracefully

class KalturaLogFilter(logging.Filter):
    """
    Custom log filter that scrubs the 'ks=' parameter from any log messages
    to avoid leaking Kaltura session info (KS).
    """

    KS_REGEX = re.compile(r"ks=[^&\s]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg:
            # Replace any 'ks=' param with 'ks=<REDACTED>'
            record.msg = self.KS_REGEX.sub("ks=<REDACTED>", str(record.msg))
        return True

def configure_logging(json_file_path: str, verbose: bool = False) -> None:
    """
    Sets up dual logging:
      1) Console handler (color if colorlog is installed, else plain text).
      2) File handler (pure JSON).

    Additionally, applies KalturaLogFilter to scrub KS from log lines.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    # Apply the filter that scrubs out 'ks='
    log_filter = KalturaLogFilter()

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.addFilter(log_filter)
    if colorlog:
        console_formatter = colorlog.ColoredFormatter(
            fmt="%(log_color)s%(levelname)s%(reset)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red"
            }
        )
    else:
        console_formatter = logging.Formatter(
            fmt="%(levelname)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Ensure the directory for the JSON log file exists
    os.makedirs(os.path.dirname(os.path.abspath(json_file_path)), exist_ok=True)

    # File Handler (JSON)
    file_handler = logging.FileHandler(json_file_path, mode="a", encoding="utf-8")
    file_handler.addFilter(log_filter)
    file_formatter = logging.Formatter(
        '{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Reduce verbosity of third-party loggers to avoid extra noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
