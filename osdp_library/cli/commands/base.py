"""Base command handler with common functionality."""

from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace

from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor
from osdp_library.osdp.message import OsdpMessage
from osdp_library.osdp.presentation.response_formatter import OsdpResponseFormatter
from osdp_library.osdp.response_payloads import OsdpNakPayload

from ..constants import FAILURE_RETURN_CODE, NOMINAL_RETURN_CODE
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BaseCommand(ABC):
    """
    Abstract base class for all CLI commands.

    This abstract object defines the necessary attributes and functions of all valid OSDP commands.

    Subclasses must define:
    - name: Command name for CLI
    - help: Help text for --help
    - add_arguments(): Add command-specific arguments
    - execute(): Execute the command
    """

    name: str
    """Command name used in CLI."""

    help: str
    """Help text shown in --help."""

    @classmethod
    @abstractmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """
        Add command-specific arguments to the parser.

        :param parser: ArgumentParser for this command
        """
        pass

    @classmethod
    @abstractmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """
        Execute the command.

        :param args: Parsed command-line arguments
        :param conductor: Traffic conductor for OSDP communication
        :return: Exit code (0 for success, non-zero for failure)
        """
        pass

    @classmethod
    def format_response(cls, args: Namespace, message: OsdpMessage | None) -> str:
        """
        Format the response using the appropriate formatter.

        :param args: Parsed arguments
        :param message: OSDP message to format
        :return: Formatted string
        """
        if message is None:
            return "Error: No response received from device"

        formatter = OsdpResponseFormatter(message=message)
        if args.verbose:
            return formatter.format_verbose()
        else:
            return formatter.format_long()

    @classmethod
    def output(cls, args: Namespace, message: OsdpMessage | None, command_name: str = "") -> int:
        """
        Format and print response, return exit code.

        :param args: Parsed arguments
        :param message: OSDP message to output
        :param command_name: Optional command name for header
        :return: Exit code (0 for success, 1 for failure)
        """
        if message is None:
            logger.error("No response from device")
            return FAILURE_RETURN_CODE

        # Check for NAK response
        if isinstance(message.payload, OsdpNakPayload):
            output = cls.format_response(args, message)
            logger.warning(f"Device returned NAK:\n{output}")
            return FAILURE_RETURN_CODE

        output = cls.format_response(args, message)

        command_header = f"\n{command_name} Command:\n" if command_name else ""
        logger.info(f"{command_header}{output}\n")
        return NOMINAL_RETURN_CODE
