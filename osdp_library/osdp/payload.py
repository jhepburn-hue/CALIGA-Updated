from dataclasses import dataclass
from typing import Dict, Any, Callable, Union, ClassVar

from .utils import format_hex, format_bytes_hex


@dataclass
class OsdpBasePayload:
    """
    Defines a simple base payload for a osdp message data field. This should be
    subclassed by every OSDP message type to provide serialization/deserialization
    functionality for all OSDP messages.
    """

    tag: int
    """
    Defines the command/reply tag associated with the payload. This is to easily identify
    the payload type based on the raw command/reply code found in the OSDP message.
    """

    TITLE: ClassVar[str] = "Base Payload"
    """
    Title for this payload type. Should be clear but concise.
    Override in subclasses to set a custom title.
    """

    def to_bytes(self) -> bytes:
        """
        Serializes the payload into its byte form.

        Each child class of `OsdpBasePayload` should serialize itself into the correct
        byte structure according to the OSDP specification.

        This method will be called on the payload when constructing a message.
        """
        raise NotImplementedError("payload subclasses must implement to_bytes method")

    @classmethod
    def from_bytearray(cls, ba: bytearray):
        """
        Deserialize the payload from its byte form.

        When receiving a message, this method should be called to deserialize and validate
        the contents of an OSDP message and return the payload subclass. This allows for
        easy operation on the payload data by the implementing application instead of
        tracking/performing the raw byte manipulation.
        """
        raise NotImplementedError(
            "payload subclass must implement from_bytearray class method"
        )

    # =========================================================================
    # Formatting Support - Override in subclasses for custom formatting
    # =========================================================================

    def _get_format_fields(self, format_short: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Override in subclasses to define which fields to include and how to format them.

        :param format_short: If True, return short format fields; if False, return long format fields (default)
        :return: Dict mapping field_name -> config dict

        Recommended pattern:
            fields = {
                # Short format fields
                "field1": {"name": "Field 1", "transform": "hex"},
            }
            if not format_short:  # Long format (default)
                fields = {
                    **fields,  # Start with short fields
                    "field2": {"name": "Field 2"},  # Long-only fields
                }
            return fields

        Config options:
          - "name": Display name (default: field_name.replace("_", " ").title())
          - "transform": "hex", "hex_bytes", "enum", or a callable(value) -> str
            - "hex": Format as hex (converts bytes to int first, then formats)
            - "hex_bytes": Format bytes/bytearray as raw hex string (e.g., "0xA1B2C3")
          - "width": Hex width for zero-padding (e.g., 6 for 0x23265C)
          - "compute": callable(self) -> value, for computed/virtual fields (use "_fieldname")

        Example:
            fields = {
                "vendor_code": {"name": "Vendor", "transform": "hex", "width": 6},
            }
            if format_long:
                fields = {
                    **fields,
                    "tag": {"name": "Message ID", "transform": "hex", "width": 2},
                }
            return fields
        """
        # Default: just show the tag as hex
        return {"tag": {"name": "Message ID", "transform": "hex", "width": 2}}



    def _transform_value(
        self, value: Any, config: Dict[str, Any]
    ) -> str:
        """
        Apply transformation to a field value based on config.

        Format fields specify the transform type. Util functions enforce
        types strictly and will raise TypeError if wrong types are passed.

        :param value: The raw field value
        :param config: Field configuration dict
        :return: Formatted string
        :raises TypeError: If value type doesn't match transform type (indicates incorrect format field spec)
        """
        transform = config.get("transform")

        if transform == "hex":
            width = config.get("width", 0)
            byteorder = config.get("byteorder", "little")
            return format_hex(value, width=width, byteorder=byteorder)
        elif transform == "hex_bytes":
            return format_bytes_hex(value)
        elif transform == "enum":
            if hasattr(value, "name") and hasattr(value, "value"):
                return f"{value.value} ({value.name})"
        elif callable(transform):
            return str(transform(value))

        return str(value)

    def _build_dict(self, format_short: bool = False) -> Dict[str, Any]:
        """
        Build dictionary of formatted field values for the given format type.

        :param format_short: If True, use short format; if False, use long format (default)
        :return: Ordered dict of display_name -> formatted_value (or list of lines for multi-line)
        """
        field_config = self._get_format_fields(format_short)
        result = {}

        for field_name, config in field_config.items():
            # Handle computed/virtual fields (start with _)
            if field_name.startswith("_"):
                compute_fn = config.get("compute")
                if compute_fn and callable(compute_fn):
                    value = compute_fn(self)
                else:
                    continue
            else:
                if not hasattr(self, field_name):
                    continue
                value = getattr(self, field_name)
                if value is None:
                    continue

            display_name = config.get("name", field_name.replace("_", " ").title())

            # Check if this is a multi-line value (contains newlines)
            if isinstance(value, str) and "\n" in value:
                # Store as list of lines for special formatting
                result[display_name] = value.split("\n")
            else:
                formatted_value = self._transform_value(value, config)
                result[display_name] = formatted_value

        return result

