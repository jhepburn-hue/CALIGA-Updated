"""Progress helpers for CLI commands."""

from __future__ import annotations

import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from osdp_library.osdp.file_transfer import FileTransferProgress

from .logging import get_logger, set_progress_bar_active

logger = get_logger(__name__)

# Default values for the progress bar.
DEFAULT_MIN_UPDATE_INTERVAL_SECONDS = 0.25
DEFAULT_MIN_PERCENT_DELTA = 1.0
DEFAULT_LOG_PERCENT_STEP = 10.0

# Initial values for the progress bar.
INITIAL_LAST_PERCENT = -1.0
INITIAL_LAST_LOGGED_PERCENT = -1.0
INITIAL_LAST_LINE_LEN = 0

# Constants for the progress bar.
MIN_ELAPSED_SECONDS = 0.0001
TERMINAL_FALLBACK_COLUMNS = 80
TERMINAL_FALLBACK_ROWS = 20
FIXED_STATUS_WIDTH = 64
MIN_BAR_WIDTH = 10
MAX_BAR_WIDTH = 30
PERCENT_FIELD_WIDTH = 5
PERCENT_PRECISION = 1
BYTES_PRECISION = 2
RATE_PRECISION = 1
TIME_FIELD_WIDTH = 2

# Standard units.
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
KIBIBYTE = 1024
MEBIBYTE = KIBIBYTE**2
GIBIBYTE = KIBIBYTE**3
PERCENT_COMPLETE_MAX = 100.0
ZERO_SECONDS = 0.0
ZERO_COUNT = 0


@dataclass
class FileTransferProgressReporter:
    """Render compact progress updates for file transfer."""

    file_path: str
    """Path to the file being transferred."""
    total_bytes: int
    """Total bytes in the file."""
    fragment_size: int
    """Fragment size in bytes."""
    min_update_interval: float = DEFAULT_MIN_UPDATE_INTERVAL_SECONDS
    """Minimum interval between updates in seconds."""
    min_percent_delta: float = DEFAULT_MIN_PERCENT_DELTA
    """Minimum percentage change between updates."""
    log_percent_step: float = DEFAULT_LOG_PERCENT_STEP
    """Percentage step to log a new line."""

    def __post_init__(self) -> None:
        """Initialize the reporter."""
        self._start_time = time.monotonic()
        self._last_update_time = ZERO_SECONDS
        self._last_percent = INITIAL_LAST_PERCENT
        self._last_logged_percent = INITIAL_LAST_LOGGED_PERCENT
        self._last_line_len = INITIAL_LAST_LINE_LEN
        self._use_tty = sys.stdout.isatty()

    def start(self) -> None:
        """Print one-time starting summary."""

        file_name = str(Path(self.file_path))
        size_label = _format_bytes(self.total_bytes)
        lines = [
            "File transfer",
            f"  File ............... {file_name}",
            f"  Size ............... {size_label}",
            f"  Fragment ........... {self.fragment_size}B",
        ]
        logger.info("\n".join(lines))
        if self._use_tty:
            sys.stdout.write("\n\n")
            sys.stdout.flush()

    def update(self, progress: FileTransferProgress) -> None:
        """Update progress bar or log line.

        Args:
            progress: The current progress of the file transfer.
        """
        percent = progress.percent_complete
        now = time.monotonic()
        if (
            percent < PERCENT_COMPLETE_MAX
            and (now - self._last_update_time) < self.min_update_interval
            and (percent - self._last_percent) < self.min_percent_delta
        ):
            return

        self._last_update_time = now
        self._last_percent = percent

        if not self._use_tty:
            if percent - self._last_logged_percent >= self.log_percent_step or percent >= PERCENT_COMPLETE_MAX:
                logger.info(self._render_line(progress, now))
                self._last_logged_percent = percent
            return

        line = self._render_line(progress, now)
        padded = line.ljust(self._last_line_len)
        set_progress_bar_active(True)
        sys.stdout.write(f"\r{padded}")
        sys.stdout.flush()
        self._last_line_len = len(line)

    def finish(self) -> None:
        """Finish progress reporting and clean up the display."""
        if self._use_tty and self._last_line_len:
            sys.stdout.write("\n\n")
            sys.stdout.flush()
        if self._use_tty:
            set_progress_bar_active(False)

    def _render_line(self, progress: FileTransferProgress, now: float) -> str:
        percent = progress.percent_complete
        bytes_sent = progress.bytes_sent
        total_bytes = progress.total_bytes or self.total_bytes
        rate = bytes_sent / max(now - self._start_time, MIN_ELAPSED_SECONDS)
        eta = _format_eta(bytes_sent, total_bytes, rate)
        elapsed = _format_duration(max(now - self._start_time, ZERO_SECONDS))
        progress_pair = _format_bytes_pair(bytes_sent, total_bytes)
        rate_label = _format_rate(bytes_sent, max(now - self._start_time, MIN_ELAPSED_SECONDS))
        status_label = progress.status.name

        term_width = shutil.get_terminal_size((TERMINAL_FALLBACK_COLUMNS, TERMINAL_FALLBACK_ROWS)).columns
        bar_width = max(MIN_BAR_WIDTH, min(MAX_BAR_WIDTH, term_width - FIXED_STATUS_WIDTH))

        filled = int(round((percent / PERCENT_COMPLETE_MAX) * bar_width))
        bar = "#" * filled + "-" * (bar_width - filled)

        return (
            f"[{bar}] {percent:{PERCENT_FIELD_WIDTH}.{PERCENT_PRECISION}f}%  "
            f"{progress_pair}  {rate_label}  "
            f"ETA {eta}  Time {elapsed}  Status {status_label}"
        )


def _format_bytes_pair(current: int, total: int) -> str:
    unit, scale = _pick_unit(total)
    return f"{current / scale:.{BYTES_PRECISION}f}{unit}/{total / scale:.{BYTES_PRECISION}f}{unit}"


def _format_bytes(value: int) -> str:
    unit, scale = _pick_unit(value)
    return f"{value / scale:.{BYTES_PRECISION}f}{unit}"


def _format_rate(bytes_sent: int, elapsed: float) -> str:
    rate = bytes_sent / elapsed
    unit, scale = _pick_unit(rate)
    return f"{rate / scale:.{RATE_PRECISION}f}{unit}/s"


def _format_eta(bytes_sent: int, total_bytes: int, rate: float) -> str:
    remaining = total_bytes - bytes_sent
    return _format_duration(remaining / rate)


def _format_duration(seconds: float) -> str:
    total_seconds = int(round(seconds))
    minutes, sec = divmod(total_seconds, SECONDS_PER_MINUTE)
    hours, minutes = divmod(minutes, MINUTES_PER_HOUR)
    if hours > ZERO_COUNT:
        return f"{hours:d}:{minutes:0{TIME_FIELD_WIDTH}d}:{sec:0{TIME_FIELD_WIDTH}d}"
    return f"{minutes:0{TIME_FIELD_WIDTH}d}:{sec:0{TIME_FIELD_WIDTH}d}"


def _pick_unit(value: float) -> tuple[str, float]:
    if value >= GIBIBYTE:
        return "GB", GIBIBYTE
    if value >= MEBIBYTE:
        return "MB", MEBIBYTE
    if value >= KIBIBYTE:
        return "KB", KIBIBYTE
    return "B", 1
