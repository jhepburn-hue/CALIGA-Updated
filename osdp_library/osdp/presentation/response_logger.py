"""
OSDP response logger for file handlers.

Handles logging of OSDP messages to file handlers, using OsdpResponseFormatter
for all formatting concerns.
"""

import logging

from ..message import OsdpMessage
from .response_formatter import OsdpResponseFormatter

# Dedicated logger for OSDP protocol messages
# This logger is filtered from console output to preserve CLI formatting
# but still appears in log files at appropriate levels
osdp_message_logger = logging.getLogger("osdp_library.osdp.messages")
osdp_message_logger.setLevel(logging.DEBUG)  # Allow all levels
osdp_message_logger.propagate = True  # Propagate to root logger for file handlers


class OsdpResponseLogger:
    """
    Logger for OSDP messages to file handlers.

    Handles all file logging logic, using OsdpResponseFormatter for formatting.
    Separates logging concerns from formatting concerns.
    """

    @staticmethod
    def log(message: OsdpMessage) -> None:
        """
        Log message to file handlers at appropriate levels.

        - INFO level: Medium format (summary + display) - if not suppressed
        - DEBUG level: Single-line verbose format

        :param message: Parsed OsdpMessage object
        """
        try:
            formatter = OsdpResponseFormatter(message=message)

            # Log INFO: Medium format (summary + display)
            medium_format = formatter.format_medium()
            osdp_message_logger.info(medium_format)

            # Log DEBUG: Multi-line verbose format
            debug_format = formatter.format_verbose()
            osdp_message_logger.debug(debug_format)

        except Exception as e:
            # Minimal fallback - log error but don't break application
            osdp_message_logger.debug(f"Failed to log OSDP message:\n{e}")
