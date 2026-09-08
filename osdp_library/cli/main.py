"""
OSDP CLI - Main entry point.

WaveLynx OSDP Command Line Interface with subparser-based command structure.
"""

import argparse
import sys
from pathlib import Path

from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor

from .commands import control, info, mfg, poll, transfer
from .connection import ConnectionException, ConnectionManager
from .constants import FAILURE_RETURN_CODE, KEYBOARD_INTERRUPT_RETURN_CODE, NOMINAL_RETURN_CODE
from .exceptions import OsdpCliException
from .utils.argparse_formatters import HelpFormatter
from .utils.argparse_validators import hex_string
from .utils.logging import get_logger, setup_logging, suppress_console_logging

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point for OSDP CLI.

    :param argv: Command-line arguments (defaults to sys.argv[1:])
    :return: Exit code (0 for success, non-zero for failure)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return FAILURE_RETURN_CODE

    # Setup logging and print banner
    log_files = setup_logging(log_level=args.log_level)
    _print_banner(log_files)

    # Create connection and get conductor
    conn_manager = None
    try:
        conn_manager, conductor = _create_connection(args)
    except ConnectionException as e:
        return _handle_error(e, log_files, "Connection error")

    # Execute command
    try:
        return _execute_command(args, conductor, parser)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        logger.warning("Interrupted by user")
        return KEYBOARD_INTERRUPT_RETURN_CODE
    except OsdpCliException as e:
        return _handle_error(e, log_files, "Command error")
    except Exception as e:
        return _handle_error(e, log_files, "Unexpected error")
    finally:
        if conn_manager:
            logger.debug("Closing connection")
            conn_manager.close()
        logger.debug("WaveLynx OSDP Library CLI - finished")
        logger.info("")  # Newline separator

    return NOMINAL_RETURN_CODE


def create_parser() -> argparse.ArgumentParser:
    """
    Create the main argument parser with subparsers.

    :return: Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="osdp-cli",
        description="WaveLynx OSDP Command Line Interface",
        formatter_class=HelpFormatter,
        epilog="""
Examples:
  hatch run osdp-cli -P ttyAMA2 info id                  Get device ID
  hatch run osdp-cli -P ttyAMA2 info cap                 Get capabilities
  hatch run osdp-cli -P ttyAMA2 poll                     Single poll
  hatch run osdp-cli -P ttyAMA2 poll --continuous        Monitor for events
  hatch run osdp-cli -P ttyAMA2 control led -c green     Set LED color
  hatch run osdp-cli -P ttyAMA2 mfg buzzer -m on         Enable buzzer
  hatch run osdp-cli -P ttyAMA2 mfg ext-id               Get extended reader info
  hatch run osdp-cli -P ttyAMA2 -S --scbk <key>  poll    Poll with custom secure channel key
  hatch run osdp-cli -P ttyAMA2 control comset --address 1 --baud 115200   Set device address and baud rate
""",
    )

    # Define output options
    output_group = parser.add_argument_group("output options")
    output_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output with detailed information",
    )
    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    output_group.add_argument(
        "-l",
        "--log-level",
        default="INFO",
        choices=log_levels,
        metavar="LEVEL",
        help=f"Logging level ({', '.join(log_levels)})",
    )

    # Define device options
    device_group = parser.add_argument_group("device options")
    device_group.add_argument(
        "-P",
        "--port",
        type=str,
        help="Serial port (e.g., ttyUSB0, ttyAMA2)",
    )
    device_group.add_argument(
        "-b",
        "--baud",
        type=int,
        default=9600,
        dest="connection_baud",
        help=(
            "Device's current baud rate for connection (default: 9600). "
            "For COMSET, this should match the device's current rate, not the target rate."
        ),
    )
    device_group.add_argument(
        "-c",
        "--config",
        type=str,
        help="Use named device configuration from config.json",
    )
    device_group.add_argument(
        "-a",
        "--address",
        type=int,
        default=0,
        dest="connection_address",
        metavar="ADDR",
        help=(
            "Device's current address for connection (default: 0). "
            "For COMSET, this should match the device's current address, not the target address."
        ),
    )
    device_group.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=2.0,
        metavar="SEC",
        help="Read timeout in seconds",
    )
    device_group.add_argument(
        "-S",
        "--secure",
        action="store_true",
        help="Use secure channel (handshake performed automatically)",
    )
    device_group.add_argument(
        "--scbk",
        type=hex_string(exact_length=32),
        help="Secure Channel Base Key (32 hex chars = 16 bytes). Required when using -S with custom key.",
    )
    device_group.add_argument(
        "-C", "--use-checksum", action="store_true", help="Override the default CRC message check and use a checksum instead."
    )

    # Create subparsers for command groups
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available command groups",
        help="Use '<command> --help' for more information",
    )

    # Register command groups into their respective module.
    info.register_parser(subparsers)  # info id, cap, lstat
    control.register_parser(subparsers)  # control led, buzzer, comset
    poll.register_parser(subparsers)  # poll (top-level)
    transfer.register_parser(subparsers)  # transfer (top-level)
    mfg.register_parser(subparsers)  # mfg ext-id, serialize, ...

    return parser


def _print_banner(log_files: dict[str, Path]) -> None:
    """
    Print startup banner with log file information.

    :param log_files: Dictionary with log file paths
    """
    absolute_log_path = str(log_files["log"].resolve())
    absolute_debug_log_path = str(log_files["debug_log"].resolve())
    banner_string = str(
        "\n\n========== WaveLynx OSDP Library CLI ==========\n"
        + f"Log file:       {absolute_log_path}\n"
        + f"Debug log file: {absolute_debug_log_path}\n\n"
    )
    logger.info(banner_string)


def _create_connection(args: argparse.Namespace) -> tuple[ConnectionManager, "OsdpTrafficConductor"]:
    """
    Create connection manager and get traffic conductor.

    :param args: Parsed command-line arguments
    :return: Tuple of (ConnectionManager, OsdpTrafficConductor)
    :raises ConnectionException: If connection fails
    """
    conn_manager = ConnectionManager(args)
    conductor = conn_manager.get_conductor()
    return conn_manager, conductor


def _handle_error(exception: Exception, log_files: dict[str, Path], error_type: str = "Error") -> int:
    """
    Handle exceptions consistently: log full details to debug log, print clean message to console.

    :param exception: The exception that occurred
    :param log_files: Dictionary with log file paths
    :param error_type: Type label for the error (default: "Error")
    :return: Exit code (FAILURE_CODE for errors)
    """
    # Log full details to debug log only (not console)
    with suppress_console_logging(logger):
        logger.debug(f"{error_type}: {exception}", exc_info=True)

    logger.error(f"{error_type}: {exception}")
    logger.info(f"See debug log for details: {log_files['debug_log']}")
    return FAILURE_RETURN_CODE


def _execute_command(args: argparse.Namespace, conductor: "OsdpTrafficConductor", parser: argparse.ArgumentParser) -> int:
    """
    Execute the requested command.

    :param args: Parsed command-line arguments
    :param conductor: Traffic conductor for OSDP communication
    :param parser: Argument parser (for showing help if needed)
    :return: Exit code (0 for success, non-zero for failure)
    """
    # The command's execute function is set via set_defaults(func=...)
    if hasattr(args, "func"):
        logger.debug(f"Executing command: {args.command}, Args: {vars(args)}")
        #breakpoint()
        result = args.func(args, conductor)
        logger.debug(f"Completed command: {args.command},  Exit code: {result}")
        return result
    else:
        # Subcommand group without specific subcommand
        parser.parse_args([args.command, "--help"])
        return FAILURE_RETURN_CODE


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
