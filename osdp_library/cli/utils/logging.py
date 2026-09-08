"""Logging configuration for OSDP CLI."""

import logging
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

LOG_DIRECTORY: str = "./logs"


class OsdpMessageFilter(logging.Filter):
    """Filter to exclude OSDP protocol messages from console output."""

    def filter(self, record):
        # Allow OSDP messages in file handlers, but not console
        return not record.name.startswith("osdp_library.osdp.messages")


class ProgressBarLineBreakFilter(logging.Filter):
    """Ensure log output starts on a new line when a progress bar is active."""

    def __init__(self) -> None:
        super().__init__()
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active

    def filter(self, record):
        if self._active:
            message = record.getMessage()
            if not message.startswith("\n"):
                record.msg = f"\n{message}"
                record.args = ()
        return True


def set_progress_bar_active(active: bool) -> None:
    """Toggle progress bar console line handling."""
    logger = logging.getLogger()
    for handler in logger.handlers:
        for handler_filter in handler.filters:
            if isinstance(handler_filter, ProgressBarLineBreakFilter):
                handler_filter.set_active(active)
                return


def setup_logging(log_level: str = "INFO") -> dict[str, Path]:
    """
    Set up file and console logging.

    Creates two log files:
    - A regular log file at the configured log level
    - A debug log file that always captures DEBUG level messages

    :param log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    :return: Dictionary with 'log' and 'debug_log' file paths
    """
    logger = logging.getLogger()

    # Clear any existing handlers
    logger.handlers.clear()

    # Root logger must be at DEBUG to allow debug file handler to capture all
    logger.setLevel(logging.DEBUG)

    log_format = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Create log directory if it doesn't exist
    log_path = Path(LOG_DIRECTORY)
    if not log_path.exists():
        log_path.mkdir(parents=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Regular log file at configured level
    log_filename = Path(f"{LOG_DIRECTORY}/osdp_{timestamp}.log")
    log_handler = logging.FileHandler(log_filename)
    log_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)

    # Debug log file - always captures everything at DEBUG level
    debug_log_filename = Path(f"{LOG_DIRECTORY}/osdp_{timestamp}_debug.log")
    debug_handler = logging.FileHandler(debug_log_filename)
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(log_format)
    logger.addHandler(debug_handler)

    # Console handler for terminal output (stdout for normal messages)
    # Note: Error messages are printed directly to stderr, not through this handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    # Filter OSDP protocol messages from console output to preserve CLI formatting
    # OSDP messages will still appear in log files at appropriate levels
    console_handler.addFilter(OsdpMessageFilter())
    console_handler.addFilter(ProgressBarLineBreakFilter())
    logger.addHandler(console_handler)

    return {"log": log_filename, "debug_log": debug_log_filename}


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    :param name: Logger name (typically __name__)
    :return: Logger instance
    """
    return logging.getLogger(name)


@contextmanager
def suppress_console_logging(logger: logging.Logger):
    """
    Temporarily suppress console logging, restore after.

    Context manager that suppresses console output during exception logging,
    ensuring detailed errors go to debug log only, not console.

    :param logger: Logger instance to manage
    :yields: None
    """
    console_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler) and h.stream in (sys.stdout, sys.stderr)]
    original_levels = {h: h.level for h in console_handlers}

    try:
        # Suppress all console output
        for handler in console_handlers:
            handler.setLevel(logging.CRITICAL + 1)
        yield
    finally:
        # Restore original levels
        for handler, level in original_levels.items():
            handler.setLevel(level)
