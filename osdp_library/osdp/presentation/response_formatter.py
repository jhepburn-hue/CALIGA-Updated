"""OSDP response formatter for display/presentation."""

import sys
from dataclasses import dataclass, fields

from ..constants import MessagingConstants
from ..message import OsdpMessage, OsdpMessageDirection
from ..response_payloads import OsdpAckPayload
from ..utils import format_bytes_hex, format_hex, get_command_name, get_response_name


@dataclass
class OsdpResponseFormatter:
    """
    Formats OSDP responses for display/presentation.

    Handles formatting decisions like ACK suppression during polling
    and provides multiple format options (short, long, verbose).
    """

    message: OsdpMessage
    """The parsed OSDP message structure"""

    def format_display(self, verbose: bool = False, short: bool = False) -> str | None:
        """
        Format response for display based on context.

        Handles display decisions like ACK suppression during polling.

        :param verbose: If True, use verbose format (full message structure)
        :param short: If True, use short format (for polling) - ACKs are suppressed in short format
        :return: Formatted string, or None if should be suppressed (e.g., ACK during polling)
        """
        # Suppress ACKs when using short format (polling)
        if isinstance(self.message.payload, OsdpAckPayload) and short:
            return None

        if verbose:
            return self.format_verbose()
        elif short:
            return self.format_short()
        else:
            return self.format_long()

    def format_short(self) -> str:
        """
        Format as short pipe-separated string for polling.

        Example: "Device ID | Vendor: 0x23265C | Model: 164 | Serial: 0x00000000"

        :return: Formatted short string, or empty string if no fields
        """
        if self.message.payload is None:
            return ""

        data = self.message.payload._build_dict(format_short=True)  # Short format
        if not data:
            return ""
        items = [f"{k}: {v}" for k, v in data.items()]
        return f"{self.message.payload.TITLE} | " + " | ".join(items)

    def format_medium(self) -> str:
        """
        Format as medium format for INFO log file.

        Single-line format with summary and short format fields.
        This is the format used for INFO-level logging to regular log files.

        Example output:
            → ID (addr=0, seq=0, len=9, Message ID=0x61, bytes=53000900046100c066)

        :return: Formatted single-line string
        """
        # Build summary parts directly (direction, name, addr, seq, len)
        direction = "←" if self.message.direction == OsdpMessageDirection.REPLY else "→"

        # Get message name using utility functions
        if self.message.direction == OsdpMessageDirection.COMMAND:
            name = get_command_name(self.message.command_reply_code)
        else:
            name = get_response_name(self.message.command_reply_code)

        # Extract message metadata
        address = self.message.address
        sequence = self.message.message_control_info.sequence if self.message.message_control_info else None
        length = (
            len(self.message.raw_bytes)
            if self.message.raw_bytes
            else (len(self.message.to_bytearray()) if hasattr(self.message, "to_bytearray") else 0)
        )

        # Build context parts
        context_parts = [
            f"addr={address}" if address is not None else None,
            f"seq={sequence}" if sequence is not None else None,
            f"len={length}",
        ]

        # Get short format fields from payload (if payload exists)
        if self.message.payload:
            data = self.message.payload._build_dict(format_short=True)
            if data:
                for key, value in data.items():
                    context_parts.append(f"{key}={value}")

        # Add raw bytes representation
        if self.message.raw_bytes:
            bytes_hex = self.message.raw_bytes.hex()
            context_parts.append(f"bytes={bytes_hex}")

        # Combine all parts
        context = ", ".join(part for part in context_parts if part is not None)
        return f"{direction} {name} ({context})"

    def format_long(self, field_padding: int = 4) -> str:
        """
        Format as multi-line aligned string for single commands.
        Indents the entire response by 2 spaces for use under command headers.
        This uses python format specification mini language to align the field names with "." padding.

        Example:
          Device ID:
            Vendor Code .......... 0x23265C
            Model Number ......... 164
            Version .............. 1

        :param field_padding: Padding for the field names. Default is 4.
        :return: Formatted multi-line string, or empty string if no fields
        """
        if self.message.payload is None:
            return ""

        data = self.message.payload._build_dict()  # Long format (default, format_short=False)
        if not data:
            return ""
        lines = [f"  {self.message.payload.TITLE}:"]

        # Calculate maximum field name length for alignment
        max_name_length = 0
        for key, value in data.items():
            if not isinstance(value, list):
                max_name_length = max(max_name_length, len(key))

        # Use a consistent total width (field name + dots + space before value)
        total_width = max_name_length + field_padding

        for key, value in data.items():
            if isinstance(value, list):
                # Multi-line value - format each line with proper indentation
                lines.append(f"    {key}:")
                for line in value:
                    lines.append(f"      {line}")
            else:
                # Calculate dots needed: total_width - name_length - 1 (for space before value)
                dots_needed = total_width - len(key) - 1
                dots = "." * dots_needed if dots_needed > 0 else " "
                lines.append(f"    {key} {dots} {value}")

        return "\n".join(lines)

    def format_verbose(self) -> str:
        """
        Format as full message structure for debugging.

        Shows complete message structure including headers, security blocks,
        and formatted payload data.

        :return: Multi-line formatted string showing full message structure
        """

        if self.message.payload is None:
            return ""

        lines = [f"\n  {self.message.payload.TITLE}:"]
        lines.append(f"     - start_of_message:  {format_hex(MessagingConstants.SOM, width=2)}")
        lines.append(f"     - address:  {format_hex(self.message.address, width=2)}")

        # Calculate length from message
        length = len(self.message.to_bytearray())
        lines.append(f"     - length:  {format_hex(length, width=2)} ({length} bytes)")

        # Format control information
        if self.message.message_control_info:
            bytearray = self.message.message_control_info.to_bytearray()
            lines.append("     - control:  | ControlInformation")
            lines.append(f"                 | bits: {bin(int.from_bytes(bytearray, byteorder=sys.byteorder))}")
            lines.append(f"                 | sqn:  {self.message.message_control_info.sequence}")
            lines.append(f"                 | crc_enabled:  {self.message.message_control_info.crc_enabled_flag.value}")
            lines.append(f"                 | scb:  {int(self.message.message_control_info.has_security_control_block)}")

        # Format security block if present
        if self.message.security_block:
            lines.append("     - security_block:  | SecurityBlock")
            lines.append(f"                        | length:  {self.message.security_block.length}")
            lines.append(f"                        | type:  {format_hex(self.message.security_block.type.value, width=2)}")

        # Format command/reply code
        lines.append(f"     - command_reply_code:  {format_hex(self.message.command_reply_code, width=2)}")

        # Format data/payload
        if self.message.payload:
            # Format payload in original style
            lines.append(f"     - data:  | {self.message.payload.__class__.__name__}")

            # Get format fields configuration for long format
            format_config = self.message.payload._get_format_fields()  # Long format (default, format_short=False)

            # Iterate through payload fields
            for field_def in fields(self.message.payload):
                field_name = field_def.name
                if field_name.startswith("_") or field_name == "tag":
                    continue

                # Check if this field should be formatted
                if field_name not in format_config:
                    continue

                try:
                    value = getattr(self.message.payload, field_name, None)
                    if value is None:
                        continue

                    config = format_config[field_name]
                    display_name = config.get("name", field_name.replace("_", " ").title())

                    # Transform value according to config
                    formatted_value = self.message.payload._transform_value(value, config)

                    # Format bytes fields with size annotation
                    if isinstance(value, bytes):
                        size_annotation = f" ({len(value)} bytes)"
                        lines.append(f"              | {display_name.lower().replace(' ', '_')}:  {formatted_value}{size_annotation}")
                    else:
                        lines.append(f"              | {display_name.lower().replace(' ', '_')}:  {formatted_value}")
                except Exception:
                    # Skip fields that can't be formatted
                    continue
        elif self.message.data:
            # Show as raw bytes with size
            if len(self.message.data) <= 16:
                data_hex = format_bytes_hex(self.message.data)
            else:
                data_hex = f"{format_bytes_hex(self.message.data[:16], prefix=False)}... ({len(self.message.data)} bytes)"
            lines.append(f"     - data:  {data_hex}")
        else:
            lines.append("     - data:  (empty)")

        # Format MAC if present
        if self.message.mac:
            lines.append(f"     - mac:  {format_bytes_hex(self.message.mac)}")

        return "\n".join(lines)
