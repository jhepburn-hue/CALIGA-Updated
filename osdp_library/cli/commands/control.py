"""Device control commands (led, buzzer, comset)."""

from argparse import ArgumentParser, Namespace, _SubParsersAction

from osdp_library.osdp.constants import MAX_8_BIT, BuzToneCodes, LEDCodes
from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor

from ..utils.argparse_formatters import HelpFormatter
from ..utils.argparse_validators import int_range
from ..utils.logging import get_logger
from .base import BaseCommand

logger = get_logger(__name__)


# LED color name to code mapping
LED_COLOR_MAP = {
    "black": LEDCodes.LED_BLACK,
    "red": LEDCodes.LED_RED,
    "green": LEDCodes.LED_GREEN,
    "amber": LEDCodes.LED_AMBER,
    "blue": LEDCodes.LED_BLUE,
    "magenta": LEDCodes.LED_MAGENTA,
    "cyan": LEDCodes.LED_CYAN,
    "white": LEDCodes.LED_WHITE,
}


class LedCommand(BaseCommand):
    """Set LED color (osdp_LED)."""

    name = "led"
    help = "Set LED color"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add LED-specific arguments."""
        color_choices = list(LED_COLOR_MAP.keys())
        parser.add_argument(
            "--color",
            "-c",
            type=str,
            required=True,
            choices=color_choices,
            metavar="COLOR",
            help=f"LED color ({', '.join(color_choices)})",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute osdp_LED command."""
        color_code = LED_COLOR_MAP.get(args.color, LEDCodes.LED_GREEN)
        message = conductor.conduct_set_led_transaction(color_code)

        return cls.output(args, message, "LED")


class BuzCommand(BaseCommand):
    """OSDP protocol command to control buzzer."""

    name = "buz"
    help = "Control buzzer with OSDP BUZ command"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add buzzer arguments."""
        parser.add_argument(
            "--reader-number",
            type=int_range(0, MAX_8_BIT),
            default=0,
            dest="reader_number",
            metavar="NUM",
            help=f"Reader number (0-{MAX_8_BIT})",
        )
        parser.add_argument(
            "--tone-code",
            type=int_range(BuzToneCodes.NONE, BuzToneCodes.DEFAULT),
            default=BuzToneCodes.DEFAULT,
            dest="tone_code",
            metavar="CODE",
            help=f"Tone code ({BuzToneCodes.NONE}=none, {BuzToneCodes.OFF}=off, {BuzToneCodes.DEFAULT}=default)",
        )
        parser.add_argument(
            "--on-time",
            type=int_range(0, MAX_8_BIT),
            default=1,
            dest="on_time",
            metavar="TIME",
            help=f"Buzzer on time in 100ms units (0-{MAX_8_BIT})",
        )
        parser.add_argument(
            "--off-time",
            type=int_range(0, MAX_8_BIT),
            default=0,
            dest="off_time",
            metavar="TIME",
            help=f"Buzzer off time in 100ms units (0-{MAX_8_BIT})",
        )
        parser.add_argument(
            "--count",
            type=int_range(0, MAX_8_BIT),
            default=1,
            dest="count",
            metavar="COUNT",
            help=f"Number of on/off cycles (0-{MAX_8_BIT})",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute osdp_BUZ command."""
        message = conductor.conduct_buz_transaction(
            reader_number=args.reader_number,
            tone_code=args.tone_code,
            on_time=args.on_time,
            off_time=args.off_time,
            count=args.count,
        )
        return cls.output(args, message, "BUZ")


class ComsetCommand(BaseCommand):
    """
    Set communication parameters (osdp_COMSET).

    Note that only Apex readers and modules support 230400 and 460800 rates.
    Maximum baud for Ethos is 115200.
    Selecting a baud that is too high for the reader will result in a valid
    response but the reader will not get set to that baud. Validate the comset
    response separately for best results.
    """

    name = "comset"
    help = "Set device address and baud rate"

    VALID_BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800]

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add comset-specific arguments."""
        parser.add_argument(
            "--address",
            "-a",
            type=int_range(0, 127),
            required=True,
            dest="target_address",
            metavar="ADDR",
            help="Target device address to set (0-127). Device will switch to this address after COMSET.",
        )
        parser.add_argument(
            "--baud",
            "-b",
            type=int,
            required=True,
            dest="target_baud",
            choices=cls.VALID_BAUD_RATES,
            metavar="RATE",
            help="Target baud rate to set (device will switch to this rate after COMSET)",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """
        Execute osdp_COMSET command.

        Uses existing connection settings (baud rate, address) to send COMSET command.
        Device responds at current baud rate. After successful COMSET, user must update
        connection baud rate for future commands (e.g., reconnect with new -b/--baud value).
        """
        message = conductor.conduct_comset_transaction(
            address=args.target_address,
            baud_rate=args.target_baud,
        )

        return cls.output(args, message, "COMSET")


def register_parser(subparsers: _SubParsersAction) -> None:
    """
    Register the control command group.

    :param subparsers: Parent subparsers to add to
    """
    control_parser = subparsers.add_parser(
        "control",
        help="Device control commands (led, buz, comset)",
        description="Commands for controlling device outputs and settings",
        formatter_class=HelpFormatter,
    )

    control_subparsers = control_parser.add_subparsers(
        dest="control_command",
        title="control commands",
        description="Available control commands",
    )

    commands: list[type[BaseCommand]] = [LedCommand, ComsetCommand, BuzCommand]

    for cmd_class in commands:
        cmd_parser = control_subparsers.add_parser(
            cmd_class.name,
            help=cmd_class.help,
            formatter_class=HelpFormatter,
        )
        cmd_class.add_arguments(cmd_parser)
        cmd_parser.set_defaults(func=cmd_class.execute)
