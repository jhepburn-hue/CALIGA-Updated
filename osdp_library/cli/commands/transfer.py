"""File transfer command."""

from argparse import ArgumentParser, Namespace, _SubParsersAction

from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor
from osdp_library.osdp.response_payloads import OsdpAckPayload

from ..constants import FAILURE_RETURN_CODE, NOMINAL_RETURN_CODE
from ..utils.argparse_formatters import HelpFormatter
from ..utils.argparse_validators import file_path
from ..utils.logging import get_logger
from ..utils.progress_bar import FileTransferProgressReporter
from .base import BaseCommand

logger = get_logger(__name__)


class TransferCommand(BaseCommand):
    """Transfer file to device (osdp_FILETRANSFER)."""

    name = "transfer"
    help = "Transfer a file (firmware) to the device"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add transfer-specific arguments."""
        parser.add_argument(
            "--file",
            "-f",
            type=file_path(),
            required=True,
            help="Path to the file to transfer",
        )
        parser.add_argument(
            "--fragment-size",
            type=int,
            default=1024,
            help="Fragment size in bytes",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute file transfer."""
        file_path_str = str(args.file)
        file_size = args.file.stat().st_size

        logger.debug(f"Starting file transfer: {file_path_str} ({file_size} bytes, fragment size: {args.fragment_size})")

        reporter = FileTransferProgressReporter(
            file_path=file_path_str,
            total_bytes=file_size,
            fragment_size=args.fragment_size,
        )
        reporter.start()

        result = conductor.conduct_file_transfer(
            file_path=file_path_str,
            file_fragment_size=args.fragment_size,
            on_progress_callback=reporter.update,
        )
        reporter.finish()

        if isinstance(result, OsdpAckPayload):
            logger.info("File transfer completed")
            return NOMINAL_RETURN_CODE
        else:
            logger.error("File transfer failed")
            return FAILURE_RETURN_CODE


def register_parser(subparsers: _SubParsersAction) -> None:
    """
    Register the transfer command.

    :param subparsers: Parent subparsers to add to
    """
    transfer_parser = subparsers.add_parser(
        "transfer",
        help="Transfer a file (firmware) to the device",
        description="Transfer firmware or configuration files to the device",
        formatter_class=HelpFormatter,
    )
    TransferCommand.add_arguments(transfer_parser)
    transfer_parser.set_defaults(func=TransferCommand.execute)
