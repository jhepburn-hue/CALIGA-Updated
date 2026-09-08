"""Poll command for device communication."""

import time
from argparse import ArgumentParser, Namespace, _SubParsersAction

from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor
from osdp_library.osdp.message import OsdpMessage
from osdp_library.osdp.presentation.response_formatter import OsdpResponseFormatter
from osdp_library.osdp.response_payloads import OsdpAckPayload

from ..constants import NOMINAL_RETURN_CODE
from ..utils.argparse_formatters import HelpFormatter
from ..utils.logging import get_logger
from .base import BaseCommand

logger = get_logger(__name__)


class PollCommand(BaseCommand):
    """Poll device (osdp_POLL)."""

    name = "poll"
    help = "Poll the device for events"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add poll-specific arguments."""
        parser.add_argument(
            "--continuous",
            "-c",
            action="store_true",
            help="Poll continuously until interrupted (Ctrl+C)",
        )
        parser.add_argument(
            "--interval",
            "-i",
            type=float,
            default=0.1,
            help="Poll interval in seconds for continuous mode",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute osdp_POLL command."""
        if args.continuous:
            return cls._poll_continuous(args, conductor)
        else:
            return cls._poll_once(args, conductor)

    @classmethod
    def _poll_once(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute single poll."""
        message = conductor.conduct_polling_transaction()
        return cls.output(args, message, "Poll")

    @classmethod
    def _poll_continuous(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute continuous polling."""
        logger.info("Polling continuously... (Ctrl+C to stop)\n")

        try:
            while True:
                message: OsdpMessage | None = conductor.conduct_polling_transaction()

                # Suppress ACK responses in continuous mode (normal idle response)
                if message and message.payload and not isinstance(message.payload, OsdpAckPayload):
                    formatter = OsdpResponseFormatter(message=message)
                    output = formatter.format_short()
                    if output:
                        logger.info(output)

                time.sleep(args.interval)

        except KeyboardInterrupt:
            logger.info("\nPolling stopped.")
            return NOMINAL_RETURN_CODE


def register_parser(subparsers: _SubParsersAction) -> None:
    """
    Register poll as a top-level command.

    :param subparsers: Parent subparsers to add to
    """
    poll_parser = subparsers.add_parser(
        "poll",
        help="Poll the device for events",
        description="Poll the device for card reads, keypad input, and other events",
        formatter_class=HelpFormatter,
    )
    PollCommand.add_arguments(poll_parser)
    poll_parser.set_defaults(func=PollCommand.execute)
