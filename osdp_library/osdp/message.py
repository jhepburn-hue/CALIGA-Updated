"""OSDP message structures for serialization and parsing."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from ..utils.byte_util import ByteField, ByteOrder
from .constants import MessagingConstants, SecurityBlockType
from .exceptions import ChecksumVerificationError, CrcVerificationError
from .payload import OsdpBasePayload
from .utils import calc_checksum, calc_crc, format_hex


class CrcEnabledFlag(IntEnum):
    """
    Flag indicating whether message uses CRC or checksum.
    Specified in SIA OSDP 2.2-2 Table 2
    The 3rd control bit is either 0 for checksum or 1 for CRC.
    """

    CRC = 1

    CHECKSUM = 0


class OsdpMessageDirection(IntEnum):
    """
    Flag used to indicate command/reply direction for message operations.
    """

    COMMAND = 0
    """
    ACU->PD direction.
    """
    REPLY = 1
    """
    PD->ACU direction.
    """


@dataclass
class OsdpMessageControlInformation:
    """
    Control information for OSDP messages.
    """

    sequence: int
    """
    Message sequence number.
    """
    crc_enabled_flag: CrcEnabledFlag
    """
    Flag indicating checksum or CRC usage.
    """
    has_security_control_block: bool
    """
    Whether security control block is present.
    """

    SEQ_MASK: int = 0x03
    """
    Mask for sequence bits.
    """
    CHKSM_CRC_MASK: int = 0x04
    """
    Mask for checksum/CRC flag.
    """
    SCB_MASK: int = 0x08
    """
    Mask for security control block flag.
    """

    def to_bytearray(self) -> bytearray:
        """
        Convert control information to byte representation.

        :return: Control information as bytearray
        """
        control_byte = 0
        control_byte |= self.sequence & self.SEQ_MASK
        control_byte |= (self.crc_enabled_flag.value << 2) & self.CHKSM_CRC_MASK
        control_byte |= (int(self.has_security_control_block) << 3) & self.SCB_MASK
        return bytearray([control_byte])

    @classmethod
    def from_control_block(cls, block: int) -> "OsdpMessageControlInformation":
        """
        Parse field from the raw osdp control block contained in a message.

        :param block: Raw control block byte
        :return: OsdpMessageControlInformation instance
        """

        # Determine the current sequence
        sequence = block & cls.SEQ_MASK

        # THIS WILL DETERMINE WHETHER THE CRC SHOULD BE ON OR OFF
        # Use the bitwise AND comparator and then shift the bits 2 spaces to the right.
        # This will result in a flag of the crc being on or off (1 for on, 0 for off)
        crc_enabled_flag = CrcEnabledFlag((block & cls.CHKSM_CRC_MASK) >> 2)

        # Similar procedure as above to determine the security control block (SCB).
        has_security_control_block = bool((block & cls.SCB_MASK) >> 3)

        return cls(
            sequence=sequence,
            crc_enabled_flag=crc_enabled_flag,
            has_security_control_block=has_security_control_block,
        )


@dataclass
class OsdpSecurityBlock:
    """
    Security control block for OSDP messages.
    """

    length: int
    """
    Length of security block.
    """
    type: SecurityBlockType
    """
    Type of security block.
    """
    data: ByteField
    """
    Security block data.
    """
    requires_mac: bool
    """
    Whether MAC is required.
    """

    SCB_OVERHEAD: int = 2
    """
    Overhead bytes for security block header.
    """

    def total_len(self) -> int:
        """
        Complete length of the security block len + type + data.

        :return: Total length as int
        """
        return self.SCB_OVERHEAD + self.data.num_bytes

    def to_bytearray(self) -> bytearray:
        """
        Convert security block to byte representation.

        :return: Security block as bytearray
        """
        result = bytearray([self.length, self.type])
        result.extend(self.data.value)
        return result

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpSecurityBlock":
        """
        Parse the security block from the provided bytearray.

        :param ba: Byte array containing security block data
        :return: OsdpSecurityBlock instance
        """
        if len(ba) < cls.SCB_OVERHEAD:
            raise ValueError("Bytearray too short: need at least 2 bytes for length and type")

        if len(ba) < ba[0]:
            raise ValueError(f"Bytearray too short: expected {ba[0]} bytes but got {len(ba)}")

        # Flag if the message type is one of these and therefore requires a mac to be present
        requires_mac: bool = ba[1] in [
            SecurityBlockType.SCS_15,
            SecurityBlockType.SCS_16,
            SecurityBlockType.SCS_17,
            SecurityBlockType.SCS_18,
        ]

        data_bytes = ba[cls.SCB_OVERHEAD : ba[0]]
        data = ByteField(value=data_bytes) if data_bytes else ByteField(value=bytearray(), num_bytes=0)

        return cls(
            length=ba[0],
            type=SecurityBlockType(ba[1]),
            data=data,
            requires_mac=requires_mac,
        )


@dataclass
class OsdpMessage:
    """
    Base class for OSDP messages for serializing/deserializing to and from raw bytes.
    """

    direction: OsdpMessageDirection
    """
    Direction of message (i.e. cmd/reply).
    """
    address: int
    """
    Target device address.
    """
    command_reply_code: int
    """
    Command or reply code.
    """
    message_control_info: OsdpMessageControlInformation
    """
    Message control information.
    """
    security_block: OsdpSecurityBlock | None
    """
    Optional security control block.
    """
    data: bytearray | None
    """
    Optional message data payload.
    """
    mac: bytearray | None
    """
    Optional message authentication code.
    """
    raw_bytes: bytes | None = field(default=None, repr=False)
    """
    The original raw byte sequence used to create this message.
    """
    payload: Optional["OsdpBasePayload"] = field(default=None, repr=False)
    """
    Parsed payload object.
    Set by OsdpMessageHandler.process_incoming_message().
    """
    SOM_IDX: int = 0
    """
    Start of message byte index.
    """
    ADDR_IDX: int = 1
    """
    Address byte index.
    """
    LEN_LSB_IDX: int = 2
    """
    Length LSB index.
    """
    LEN_MSB_IDX: int = 3
    """
    Length MSB index.
    """
    CNTRL_IDX: int = 4
    """
    Control byte index.
    """
    SCB_IDX: int = 5
    """
    Security control block index.
    """
    MAC_LEN: int = 4
    """
    MAC length in bytes.
    """

    @classmethod
    def convert_byte_to_consumable_value(cls, byte_field: int) -> str:
        return format_hex(byte_field, width=2)

    def _build_message_pre_mac(self) -> bytearray:
        """
        Build the common message including SOM, address, length placeholders,
        control info, security block, command/reply code, and data payload.

        This is the data used for mac calculation.

        :return: Message header as bytearray with length field set to 0
        """
        # Set highest bit of address for replies (OSDP spec requirement)
        address_byte = self.address | 0x80 if self.direction == OsdpMessageDirection.REPLY else self.address
        # First establishment of the byte array.  This will be established as follows:
        # bytearray(b'S\x80\x00\x00')
        msg_ba: bytearray = bytearray([MessagingConstants.SOM, address_byte, 0, 0])

        # Add the message control info to the msg_ba in the form of bytes
        msg_ba += self.message_control_info.to_bytearray()

        # Add the security block (if it exists in the message control info) to the msg_ba
        if self.message_control_info.has_security_control_block and self.security_block:
            msg_ba += self.security_block.to_bytearray()

        # append the command reply code to the byte at the end of the array
        msg_ba.append(self.command_reply_code)

        # add data (which is already in the form of bytes) to the msg_ba byte array.
        if self.data:
            msg_ba += self.data

        return msg_ba

    def to_bytearray(self) -> bytearray:
        """
        Encode the message into a byte array.

        :return: Message as bytearray
        """
        msg_ba = self._build_message_pre_mac()

        if self.message_control_info.has_security_control_block and self.security_block and self.security_block.requires_mac and self.mac:
            # only include the first 4 bytes of the mac, even if the full 16 byte mac is set
            # in the mac field
            msg_ba += self.mac[: self.MAC_LEN]

        # Update length field first to include checksum/CRC length
        length = len(msg_ba) + 2 if self.message_control_info.crc_enabled_flag else len(msg_ba) + 1

        msg_ba[self.LEN_LSB_IDX] = length & 0xFF
        msg_ba[self.LEN_MSB_IDX] = (length >> 8) & 0xFF

        # Calculate and append checksum or CRC
        if self.message_control_info.crc_enabled_flag:
            # Calculate CRC and append as little-endian 2 bytes
            crc_value = calc_crc(bytes(msg_ba))  # Include SOM byte
            msg_ba.append(crc_value & 0xFF)
            msg_ba.append((crc_value >> 8) & 0xFF)
        else:
            # Calculate checksum and append as single byte
            checksum_value = calc_checksum(bytes(msg_ba))  # Include SOM byte
            msg_ba.append(checksum_value)

        return msg_ba

    def get_mac_calc_bytes(self) -> bytes:
        """
        Convenience method for getting the exact byte sequence of a message to be used
        for MAC calculation (omitting the mac itself and crc/checksum.

        :return: Mac calc bytes
        :raises AttributeError: If security_block is None (MAC calculation requires a security block)
        """
        if self.security_block is None:
            raise AttributeError("security_block is required for MAC calculation")

        msg_ba = self._build_message_pre_mac()

        length = len(msg_ba)

        # Update the length field to include the mac bytes.
        if self.security_block.requires_mac:
            length += self.MAC_LEN

        # Update length field to include checksum/CRC length
        if self.message_control_info.crc_enabled_flag:
            length += 2  # Add 2 bytes for CRC
        else:
            length += 1  # Add 1 byte for checksum

        msg_ba[self.LEN_LSB_IDX] = length & 0xFF
        msg_ba[self.LEN_MSB_IDX] = (length >> 8) & 0xFF

        return bytes(msg_ba)

    @classmethod
    def from_bytearray(
        cls,
        ba: bytearray | None = None,
    ) -> "OsdpMessage":
        """
        Decode a byte string into a Message object.

        :param ba: Byte array containing message data
        :return: OsdpMessage instance with values obtained throughout the byte processing of this method.
        """
        if ba is None:
            ba = bytearray([])

        if ba == bytearray([]):
            raise ValueError("Cannot parse empty osdp message")

        # Capture the raw state before we start stripping/parsing
        # We slice it to create a 'bytes' copy so it's immutable
        original_bytes = bytes(ba)

        # Strip any proceeding FF bytes before the SOM
        while ba[0] == 0xFF:
            ba = ba[1:]

        # Mask out the highest bit to get the actual address
        #    10000000  (0x80)
        # &  01111111  (0x7F)
        # RESULT: 00000000  (0x00)
        addr = ba[cls.ADDR_IDX] & 0x7F

        # Get the 3rd and 4th values in the resulting byte data and organize them as a single value
        # in little endian (bit value count right to left)
        length = ByteField(value=ba[2:4], num_bytes=2, byteorder=ByteOrder.LITTLE)

        control = ba[cls.CNTRL_IDX]
        # Obtain the Message control information utilizing the control byte or 5th byte of the
        # byte array.
        message_control_info: OsdpMessageControlInformation = OsdpMessageControlInformation.from_control_block(control)

        # Utilize this if the security block is in play.
        security_info: OsdpSecurityBlock | None = None
        if message_control_info.has_security_control_block:
            security_info = OsdpSecurityBlock.from_bytearray(ba[cls.SCB_IDX :])

        # We need calculate the message overhead to find the end of the data, mac, and chksm/crc
        # som + addr + len + control + cmd/reply + chksm
        # MessagingConstants.OVERHEAD VAL is 7
        len_overhead: int = MessagingConstants.OVERHEAD

        if security_info:
            len_overhead += security_info.total_len()
            if security_info and security_info.requires_mac:
                len_overhead += cls.MAC_LEN

        if message_control_info.crc_enabled_flag:
            # add an additional overhead byte if crc is included
            len_overhead += 1

        # calc indexes of next fields for convenience
        # Set the command reply index to the integer value 5 IF the security control block is on.
        # Otherwise, set this value to integer value 5 PLUS the value of the total_len() method from the
        # OSDP security block.
        command_reply_index: int = cls.SCB_IDX + security_info.total_len() if security_info else cls.SCB_IDX

        # Get the index of where the command response data byte resides.
        data_index: int = command_reply_index + 1

        # Calculate the data length by getting the previously established length byte field and subtract
        # the value of the len_overhead.
        data_len: int = length.to_int() - len_overhead

        # Get the command reply code.  This is determined on behalf of the command reply index, whose
        # value is determined earlier in the procedure.
        command_reply_code = ba[command_reply_index]

        # Command response data.  Procedure is currently as follows:
        # If the data_len field (determined earlier up the chain) is greater than 0, set the data to the bytes
        # starting from the data index and going up to the byte array's index at the data_len.
        # Otherwise, just set this to an empty byte array.
        data = ba[data_index : data_index + data_len] if data_len > 0 else bytearray()

        mac = None
        if security_info is not None and security_info.requires_mac:
            # Get the and MAC index IF and only if the message control info index (5th byte in the byte array that
            # determines the control info) has the security control block enabled AND the security info calculation
            # requires a command message authentication code (MAC) index.
            mac_index: int = data_index + data_len
            mac = ba[mac_index : mac_index + cls.MAC_LEN]

        # Verify cyclical redundancy check or CRC (error-detection code used to ensure the integrity of data transmitted
        # between devices like card readers and control panels)
        # If the CRC flag is in play, get the received CRC by getting the final 2 bytes of the byte array response,
        # organize them to 1 value and calculate the value via little endian (right to left).
        if message_control_info.crc_enabled_flag:
            # Verify CRC
            received_crc = ByteField(value=ba[-2:], num_bytes=2, byteorder=ByteOrder.LITTLE).to_int()

            # Calculate the message without the CRC.  Utilize the utilit calc_crc method to confirm.
            message_without_crc = ba[:-2]
            calculated_crc = calc_crc(bytes(message_without_crc))
            if received_crc != calculated_crc:
                raise CrcVerificationError(
                    f"CRC verification failed: received {format_hex(received_crc, width=4)}, "
                    f"calculated {format_hex(calculated_crc, width=4)}"
                )
        # If the CRC is not in play, then verify the checksum (used to ensure the integrity of the data being exchanged
        # between devices).
        else:
            # Verify checksum
            received_checksum = ba[-1]
            message_without_checksum = ba[:-1]
            calculated_checksum = calc_checksum(bytes(message_without_checksum))
            if received_checksum != calculated_checksum:
                raise ChecksumVerificationError(
                    f"Checksum verification failed: received {format_hex(received_checksum, width=2)}, "
                    f"calculated {format_hex(calculated_checksum, width=2)}"
                )

        # Determine direction based on address byte array's address index (index 1, 2nd value in the byte array).
        # Reply messages have the high bit (0x80) set in the address byte.
        direction = OsdpMessageDirection.REPLY if ba[cls.ADDR_IDX] & 0x80 else OsdpMessageDirection.COMMAND

        # Create the message object
        return cls(
            direction=direction,
            address=addr,
            command_reply_code=command_reply_code,
            message_control_info=message_control_info,
            security_block=security_info,
            data=data,
            mac=mac,
            raw_bytes=original_bytes,
        )
