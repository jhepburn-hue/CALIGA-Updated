"""Device information commands (id, cap, lstat)."""

from argparse import ArgumentParser, Namespace, _SubParsersAction

from osdp_library.osdp.constants import CommandTags
from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor

from ..utils.argparse_formatters import HelpFormatter
from .base import BaseCommand


class IdCommand(BaseCommand):
    """Get device identification (osdp_ID)."""

    name = "id"
    help = "Get device identification information"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """No additional arguments for ID command."""
        pass

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute osdp_ID command."""
        message = conductor.conduct_command_transaction(CommandTags.ID)
        return cls.output(args, message, "ID")


class CapCommand(BaseCommand):
    """Get device capabilities (osdp_CAP)."""

    name = "cap"
    help = "Get device capabilities"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """No additional arguments for CAP command."""
        pass

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute osdp_CAP command."""
        message = conductor.conduct_cap_transaction()
        return cls.output(args, message, "Capabilities")


class LstatCommand(BaseCommand):
    """Get local status (osdp_LSTAT)."""

    name = "lstat"
    help = "Get local status (tamper, power)"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """No additional arguments for LSTAT command."""
        pass

    @classmethod
    def execute(cls, args: Namespace, conductor: OsdpTrafficConductor) -> int:
        """Execute osdp_LSTAT command."""
        message = conductor.conduct_command_transaction(CommandTags.LSTAT)
        return cls.output(args, message, "Local Status")


def register_parser(subparsers: _SubParsersAction) -> None:
    """
    Register the info command group.

    :param subparsers: Parent subparsers to add to
    """
    info_parser = subparsers.add_parser(
        "info",
        help="Device identification and status commands",
        description="Commands for retrieving device identification and status",
        formatter_class=HelpFormatter,
    )

    info_subparsers = info_parser.add_subparsers(
        dest="info_command",
        title="info commands",
        description="Available info commands",
    )

    commands: list[type[BaseCommand]] = [IdCommand, CapCommand, LstatCommand]

    for cmd_class in commands:
        cmd_parser = info_subparsers.add_parser(
            cmd_class.name,
            help=cmd_class.help,
            formatter_class=HelpFormatter,
        )
        cmd_class.add_arguments(cmd_parser)
        cmd_parser.set_defaults(func=cmd_class.execute)
