"""Manufacturing (MFG) commands."""

from argparse import ArgumentParser, Namespace, _SubParsersAction

from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import (
    OsdpTrafficConductor,
)

from ...osdp.constants import (
    BleAdvertising,
    BleTxPower,
    ManufacturingTags,
)
from ..utils.argparse_formatters import HelpFormatter
from ..utils.argparse_validators import hex_bytearray, hex_bytes, hex_string, int_range, parse_true_false
from ..utils.logging import get_logger
from .base import BaseCommand

logger = get_logger(__name__)


class ExtIdCommand(BaseCommand):
    """Get extended reader ID information (MFG 0x9C)."""

    name = "ext-id"
    help = "Get extended reader identification (WaveLynx)"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """No additional arguments."""
        pass

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute manufacturer extended ID command"""
        message = conductor.conduct_get_extended_id_transaction()
        return cls.output(args, message, "Extended Reader ID")


class DeviceDescriptionCommand(BaseCommand):
    """Get device description information (MFG 0x98)."""

    name = "device-desc"
    help = "Get device description (WaveLynx MFG 0x98)"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """No additional arguments."""
        pass

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute manufacturer device description command."""
        message = conductor.conduct_host_get_device_description_transaction()
        return cls.output(args, message, "Device Description")


class SerializeCommand(BaseCommand):
    """Set serial number (MFG serialize)."""

    name = "serialize"
    help = "Set device serial number (WaveLynx)"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add serialize-specific arguments."""
        parser.add_argument(
            "--serial-number",
            "-s",
            type=hex_string(max_length=16),
            required=True,
            help="Serial number as hex string (up to 16 chars, e.g., 0102030405060708)",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute MFG serialize command."""
        message = conductor.conduct_set_extended_id_transaction(args.serial_number)

        return cls.output(args, message, "Serialize")


class RawMfgCommand(BaseCommand):
    """Send a raw MFG command with arbitrary data."""

    name = "raw"
    help = "Send raw MFG command with custom vendor code and data"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add raw MFG-specific arguments."""
        parser.add_argument(
            "--vendor-code",
            "-v",
            type=hex_bytes(exact_bytes=3),
            default="5C2623",
            help="Vendor code as 6-char hex string (default: 5C2623 for WaveLynx)",
        )
        parser.add_argument(
            "--data",
            "-d",
            type=hex_bytearray(),
            required=True,
            help="Raw data as hex string (e.g., 579C00)",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute raw MFG command."""
        logger.debug(f"Sending raw MFG command: vendor={args.vendor_code.hex()}, data={args.data.hex()}")

        message = conductor.conduct_mfg_raw_transaction(args.vendor_code, args.data)
        return cls.output(args, message, "Raw MFG")


class MfgBleCommand(BaseCommand):
    """Control BLE settings via WaveLynx manufacturer command."""

    name = "ble"
    help = "Control BLE settings"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add BLE arguments."""
        parser.add_argument(
            "--advertising-name",
            type=str,
            default="APEX",
            dest="advertising_name",
            metavar="STRING",
            help="Advertising name: exactly 4 uppercase ASCII characters (ex: APEX)",
        )
        parser.add_argument(
            "--tx-power",
            type=lambda x: BleTxPower(int(x)),  # Lambda function to convert string to int
            choices=list(BleTxPower),
            default=BleTxPower.ZERO_DBM,
            dest="tx_power",
            metavar="NUM",
            help="TX power: 0=-30dBm, 1=-20dBm, 2=-16dBm, 3=-12dBm, 4=-8dBm, 5=-4dBm, 6=0dBm",
        )
        parser.add_argument(
            "--advertising-interval-min",
            type=int_range(BleAdvertising.ADVERTISING_INTERVAL_MIN, BleAdvertising.ADVERTISING_INTERVAL_MAX),
            default=BleAdvertising.ADVERTISING_INTERVAL_MIN,
            dest="advertising_interval_min",
            metavar="NUM",
            help=f"Min advertising interval ({BleAdvertising.ADVERTISING_INTERVAL_MIN}-{BleAdvertising.ADVERTISING_INTERVAL_MAX})",
        )
        parser.add_argument(
            "--advertising-interval-max",
            type=int_range(BleAdvertising.ADVERTISING_INTERVAL_MIN, BleAdvertising.ADVERTISING_INTERVAL_MAX),
            default=BleAdvertising.ADVERTISING_INTERVAL_MAX,
            dest="advertising_interval_max",
            metavar="NUM",
            help=f"Max advertising interval ({BleAdvertising.ADVERTISING_INTERVAL_MIN}-{BleAdvertising.ADVERTISING_INTERVAL_MAX})",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute BLE command (MFG 0xB1)."""
        message = conductor.conduct_mfg_set_ble(
            advertising_name=args.advertising_name,
            tx_power=args.tx_power,
            advertising_interval_min=args.advertising_interval_min,
            advertising_interval_max=args.advertising_interval_max,
        )
        return cls.output(args, message, "BLE")


# TODO: The following commands require additional conductor methods to be implemented:
# - IbeaconCommand (conduct_mfg_ibeacon_transaction)
# - ResetCommand (conduct_mfg_reset_transaction)
# - TechnologyCommand (conduct_mfg_technology_transaction)
# - LedSettingsCommand (conduct_mfg_led_settings_transaction)
# See ticket: AUT-128 for implementation


def register_parser(subparsers: _SubParsersAction) -> None:
    """
    Register the MFG command group.

    :param subparsers: Parent subparsers to add to
    """
    mfg_parser = subparsers.add_parser(
        "mfg",
        help="WaveLynx manufacturer commands",
        description="WaveLynx-specific manufacturing commands",
        formatter_class=HelpFormatter,
    )

    mfg_subparsers = mfg_parser.add_subparsers(
        dest="mfg_command",
        title="mfg commands",
        description="Available manufacturing commands",
    )

    commands: list[type[BaseCommand]] = [
        ExtIdCommand,
        DeviceDescriptionCommand,
        SerializeCommand,
        RawMfgCommand,
        MfgBuzzerCommand,
        MfgBleCommand,
        MfgMobileSetCommand,
        MfgMobileGetCommand,
    ]

    for cmd_class in commands:
        cmd_parser = mfg_subparsers.add_parser(
            cmd_class.name,
            help=cmd_class.help,
            formatter_class=HelpFormatter,
        )
        cmd_class.add_arguments(cmd_parser)
        cmd_parser.set_defaults(func=cmd_class.execute)


class MfgBuzzerCommand(BaseCommand):
    """Control buzzer via WaveLynx manufacturer command."""

    name = "buzzer"
    help = "Control buzzer setting"

    # Map CLI arg names to existing ManufacturingTags constants
    MODE_MAP = {
        "off": ManufacturingTags.DISABLE_APEX_BUZZER_BOTH,
        "startup-only": ManufacturingTags.APEX_STARTUP_BUZZER_ONLY,
        "card-read-only": ManufacturingTags.APEX_CARD_READ_BUZZER_ONLY,
        "on": ManufacturingTags.ENABLE_APEX_BUZZER_BOTH,
    }

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add buzzer-specific arguments."""
        mode_choices = list(cls.MODE_MAP.keys())
        parser.add_argument(
            "--mode",
            "-m",
            type=str,
            required=True,
            choices=mode_choices,
            metavar="MODE",
            help=f"Buzzer mode ({', '.join(mode_choices)})",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute buzzer command (via WaveLynx's osdp_MFG)."""
        buzzer_mode = cls.MODE_MAP[args.mode]
        message = conductor.conduct_mfg_flip_buzzer(buzzer_mode)
        return cls.output(args, message, "Buzzer")


class MfgMobileSetCommand(BaseCommand):
    """Set mobile settings via WaveLynx manufacturer command."""

    name = "mobile-set"
    help = "Set mobile settings"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add mobile-specific arguments."""
        parser.add_argument(
            "--key-rolling",
            "-kr",
            type=parse_true_false,
            required=True,
            dest="key_rolling",
            metavar="true/false",
            help="Allow key rolling (disable after 1 min) (true, false)",
        )
        parser.add_argument(
            "--mypass-cred",
            "-mc",
            type=parse_true_false,
            required=True,
            dest="mypass_cred",
            metavar="true/false",
            help="Allow MyPass credentials (true, false)",
        )
        parser.add_argument(
            "--ble-cred",
            "-bc",
            type=parse_true_false,
            required=True,
            dest="ble_cred",
            metavar="true/false",
            help="Allow BLE credentials (true, false)",
        )
        parser.add_argument(
            "--keyset-one",
            "-ko",
            type=parse_true_false,
            required=True,
            dest="keyset_one",
            metavar="true/false",
            help="Keyset 1 activation (true, false)",
        )
        parser.add_argument(
            "--keyset-two",
            "-kt",
            type=parse_true_false,
            required=True,
            dest="keyset_two",
            metavar="true/false",
            help="Keyset 2 activation (true, false)",
        )

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute mobile command (via WaveLynx's osdp_MFG)."""
        message = conductor.conduct_mfg_set_mobile(
            key_rolling=args.key_rolling,
            mypass_cred=args.mypass_cred,
            ble_cred=args.ble_cred,
            keyset_one=args.keyset_one,
            keyset_two=args.keyset_two,
        )
        return cls.output(args, message, "OSDP MFG Mobile Control")


class MfgMobileGetCommand(BaseCommand):
    """Get mobile settings via WaveLynx manufacturer command."""

    name = "mobile-get"
    help = "Get mobile settings"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """No additional arguments."""
        pass

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute mobile-get command (via WaveLynx's osdp_MFG)."""
        message = conductor.conduct_mfg_get_mobile()
        return cls.output(args, message, "")
