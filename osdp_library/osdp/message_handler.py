"""OSDP message handler for processing incoming and outgoing messages."""

from collections.abc import Callable

from ..utils.byte_util import ByteField
from .constants import DEFAULT_SCB_LENGTH, DEFAULT_SCB_TYPE, ManufacturingTags, ResponseTags
from .exceptions import (
    BadMessageSequenceError,
    PayloadValidationError,
    UnknownMessageTypeError,
)
from .message import (
    CrcEnabledFlag,
    OsdpMessage,
    OsdpMessageControlInformation,
    OsdpMessageDirection,
    OsdpSecurityBlock,
)
from .payload import OsdpBasePayload
from .presentation.response_logger import OsdpResponseLogger
from .secure_channel import OsdpSecureChannelContext
from .utils import format_hex


class OsdpMessageHandler:
    """
    Handles OSDP message processing including secure channel operations and payload parsing.

    Manages secure channel state and provides methods to process incoming raw bytes
    into parsed payload dataclasses and create outgoing raw bytes from payload dataclasses.

    Payload classes must be explicitly registered using register_payload_class() before
    they can be used for message processing.
    """

    MSG_RESET_SEQUENCE: int = 0
    """
    Number for resetting the message sequence.
    """

    MSG_MAX_SEQUENCE: int = 3
    """
    Max allowed sequence number for OSDP messages.
    """

    secure_channel_context: OsdpSecureChannelContext | None
    """
    Secure channel context for encryption/decryption operations.
    """

    _payload_registry: dict[tuple[int, int | None], type[OsdpBasePayload]]
    """
    Registry mapping (tag, mfg_code) tuples to their payload classes.
    For regular payloads, mfg_code is None. For MFG-specific payloads, mfg_code is the manufacturing code (e.g., 0x98, 0x9C).
    """

    __sequence: int = 0
    """
    Message sequence tracker.
    """

    _on_sequence_reset_callback: Callable[[], None] | None
    """
    Optional callback invoked when a sequence reset is detected.
    """

    def __init__(
        self,
        secure_channel_context: OsdpSecureChannelContext | None = None,
        on_sequence_reset: Callable[[], None] | None = None,
        use_crc: bool = True,
    ):
        """
        Initialize the message handler.

        :param secure_channel_context: Optional secure channel context for encrypted messaging
        :param on_sequence_reset: Optional callback invoked when sequence reset is detected
        """
        self.secure_channel_context = secure_channel_context
        self._payload_registry = {}
        self._on_sequence_reset_callback = on_sequence_reset
        self._use_crc = use_crc

    def process_incoming_message(self, raw_bytes: bytearray) -> "OsdpMessage":
        """
        Process incoming raw bytes into a parsed message.
        The parsed payload is attached to the message via the `payload` property.

        :param raw_bytes: Raw byte array containing OSDP message
        :return: OsdpMessage with payload property set
        :raises PayloadValidationError: If message parsing fails
        :raises UnknownMessageTypeError: If message type is not registered
        """
        try:
            # Parse raw bytes into OsdpMessage
            message = OsdpMessage.from_bytearray(raw_bytes)

            # Handle sequence reset (incoming sequence 0) for both commands and replies
            # This can occur after a PD reboot or resync request.
            if message.message_control_info.sequence == self.MSG_RESET_SEQUENCE:
                # Only call the callback if we are in a valid sequence
                if self._on_sequence_reset_callback and self.__sequence != self.MSG_RESET_SEQUENCE:
                    self._on_sequence_reset_callback()
                self.reset_sequence()
                # Per spec, SQN 0 indicates a reset of an active secure session; do not
                # clear pending handshake state (SCS_11..SCS_13).
                if self.secure_channel_context and self.secure_channel_context.state.is_active():
                    self.secure_channel_context.reset()
            else:
                # Verify the sequence is what we expect for non-reset messages
                if self.__sequence != message.message_control_info.sequence:
                    raise BadMessageSequenceError(
                        f"expected sequence {self.__sequence}, got sequence: {message.message_control_info.sequence}"
                    )

            # Advance sequence after processing messages:
            # - For replies: advance after successful processing (ACU side - completes exchange)
            # - For commands: advance after processing (PD side - for next exchange)
            if message.direction == OsdpMessageDirection.REPLY:
                # ACU side: advance after successfully processing reply
                self.__advance_sequence()
            elif message.direction == OsdpMessageDirection.COMMAND:
                # PD side: advance after processing command (but reply uses current sequence)
                # We need to advance AFTER creating the reply, not here
                pass

            # Unwrap message if in secure channel
            if self.secure_channel_context and message.security_block:
                message = self.secure_channel_context.unwrap_message(message)

            # Find payload class for this message type
            # THE MAPPING OF A MESSAGE RESPONSE TO AN ACTUAL PAYLOAD OCCURS HERE.
            payload_class = None
            mfg_code = None
            vendor_code_bytes = ManufacturingTags.VENDOR_CODE.to_bytes(length=3, byteorder="big")
            mfg_code_index = 4  # mfg_code is found at byte 4 (after vendor_code 3 bytes + wavelynx_format 1 byte)

            # For MFG responses, extract mfg_code from payload data
            # MFG payload structure: vendor_code (3 bytes) + wavelynx_format (1 byte) + mfg_code (1 byte)
            if message.data and len(message.data) >= 5 and message.data[:3] == vendor_code_bytes:
                mfg_code = message.data[mfg_code_index]
                # Find payload class registered with (tag, mfg_code)
                payload_class = self._payload_registry.get((message.command_reply_code, mfg_code))

            # If no mfg_code-specific registration found, fall back to (tag, None)
            if not payload_class:
                payload_class = self._payload_registry.get((message.command_reply_code, None))

            if not payload_class:
                error_msg = f"Unknown message type/tag: {format_hex(message.command_reply_code, width=2)}"
                if mfg_code is not None:
                    error_msg += f" with mfg_code: {format_hex(mfg_code, width=2)}"
                raise UnknownMessageTypeError(error_msg)

            # Parse payload data and attach to message
            payload = payload_class.from_bytearray(message.data) if message.data else payload_class.from_bytearray(bytearray())

            # Assign payload directly
            message.payload = payload

            # Log incoming message
            OsdpResponseLogger.log(message)

            return message

        except UnknownMessageTypeError:
            # Re-raise UnknownMessageTypeError as-is
            raise
        except Exception as e:
            # Wrap other exceptions in PayloadValidationError
            raise PayloadValidationError(f"Failed to process incoming message: {e}") from e

    def create_outgoing_message(
        self,
        address: int,
        payload: OsdpBasePayload,
    ) -> bytearray:
        """
        Create raw bytes from a payload dataclass.

        :param address: Target device address
        :param payload: Payload dataclass to serialize
        :param use_crc: Whether to use CRC (True) or checksum (False)
        :return: Raw bytes ready for transmission
        """
        # Check if this payload is a response type by checking the enum type
        direction = OsdpMessageDirection.REPLY if isinstance(payload.tag, ResponseTags) else OsdpMessageDirection.COMMAND

        # Create control information using current sequence.
        # Note that the sequence is pre-determined in this class.
        control_info = OsdpMessageControlInformation(
            sequence=self.__sequence,
            crc_enabled_flag=(CrcEnabledFlag.CRC if self._use_crc else CrcEnabledFlag.CHECKSUM),
            has_security_control_block=self.secure_channel_context is not None and not self.secure_channel_context.state.is_inactive(),
        )

        # Serialize payload data
        payload_data = payload.to_bytes()
        message_data = bytearray(payload_data) if payload_data else None

        # Create security block if secure channel is active
        security_block = None
        if self.secure_channel_context and not self.secure_channel_context.state.is_inactive():
            security_block = OsdpSecurityBlock(
                length=DEFAULT_SCB_LENGTH,  # Will be updated during wrap
                type=DEFAULT_SCB_TYPE,  # Will be updated during wrap
                data=ByteField(value=bytearray(), num_bytes=0),
                requires_mac=False,  # Will be updated during wrap
            )

        # Create message
        message = OsdpMessage(
            direction=direction,
            address=address,
            command_reply_code=payload.tag,
            message_control_info=control_info,
            security_block=security_block,
            data=message_data,
            mac=None,
            payload=payload,
        )

        # Wrap message if in secure channel
        if self.secure_channel_context and security_block:
            message = self.secure_channel_context.wrap_message(message)

        # Serialize to bytes
        msg_bytes: bytearray = message.to_bytearray()

        # Set raw_bytes on message
        message.raw_bytes = bytes(msg_bytes)

        # Log outgoing message
        OsdpResponseLogger.log(message)

        # For replies, advance sequence after creating the message (PD side)
        if direction == OsdpMessageDirection.REPLY:
            self.__advance_sequence()

        return msg_bytes

    def register_payload_class(self, tag: int, payload_class: type[OsdpBasePayload]) -> None:
        """
        Register a payload class for a specific tag.

        :param tag: Command or response tag
        :param payload_class: Payload class to register
        """
        self._payload_registry[(tag, None)] = payload_class

    def mfg_reply_class(self, tag: int, payload_class: type[OsdpBasePayload], mfg_code: int) -> None:
        """
        Register a payload class for a specific tag and manufacturing code.
        This is used for MFG responses that share the same response tag but have different
        payload structures based on the manufacturing code.

        :param tag: Response tag (e.g., ResponseTags.EXT_READER_ID)
        :param payload_class: Payload class to register
        :param mfg_code: Manufacturing code (e.g., 0x98, 0x9C)
        """
        self._payload_registry[(tag, mfg_code)] = payload_class

    def get_registered_tags(self) -> dict[tuple[int, int | None], type[OsdpBasePayload]]:
        """
        Get all registered payload classes.

        :return: Dictionary mapping (tag, mfg_code) tuples to payload classes
        """
        return self._payload_registry.copy()

    def reset_sequence(self):
        """
        Reset the messaging sequence.
        """
        self.__sequence = self.MSG_RESET_SEQUENCE

    def __advance_sequence(self):
        """
        Advance the message sequence number to the next value. OSDP messages
        start at sequence 0 for restarting message exchanges and then increment
        from 1 to 3 repeating.

        0 -> 1 -> 2 -> 3 -> 1 -> 2 -> 3
        """
        if self.__sequence == self.MSG_MAX_SEQUENCE:
            self.__sequence = 1
        else:
            self.__sequence += 1
