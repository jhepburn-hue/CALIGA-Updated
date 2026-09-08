from typing import List, Optional, Type, ClassVar
from enum import Enum
from dataclasses import dataclass, field


class ByteOrder(Enum):
    BIG = "big"
    LITTLE = "little"


@dataclass
class ByteField:
    """
    ByteField represents a field in an OSDP message.
    """

    value: bytearray = field(default_factory=bytearray)
    num_bytes: int = field(default=0)
    byteorder: ByteOrder = ByteOrder.BIG

    def __post_init__(self):
        """
        Handle num_bytes and value initialization.
        """
        if self.num_bytes == 0:
            # Derive num_bytes from value
            self.num_bytes = len(self.value)
        else:
            # Ensure value matches specified num_bytes
            if len(self.value) < self.num_bytes:
                # Pad with zeros
                self.value.extend([0] * (self.num_bytes - len(self.value)))
            elif len(self.value) > self.num_bytes:
                # Truncate to specified length
                self.value = self.value[:self.num_bytes]

    @classmethod
    def from_int(cls, value: int, num_bytes: int, byteorder: ByteOrder = ByteOrder.BIG) -> "ByteField":
        """
        Create ByteField from integer with specified byte order.
        """
        byte_data = value.to_bytes(num_bytes, byteorder=byteorder.value)
        return cls(value=bytearray(byte_data), num_bytes=num_bytes, byteorder=byteorder)

    def __eq__(self, other):
        """
        Ensure that the `num_bytes` and `value` fields both match.
        """
        if not isinstance(other, ByteField):
            return False

        if not self.num_bytes == other.num_bytes:
            return False

        return self.value == other.value

    def to_int(self) -> int:
        """
        Convert to integer with correct byte order.
        """
        if self.num_bytes > 8:
            raise ValueError("Value too large to convert to int (max 8 bytes)")
        return int.from_bytes(self.value[:self.num_bytes], byteorder=self.byteorder.value)

    def to_bytes(self) -> bytes:
        """
        Return as bytes.
        """
        return bytes(self.value[:self.num_bytes])

    def to_hex(self) -> str:
        """
        Return as hex string.
        """
        return self.value[:self.num_bytes].hex()

    def __repr__(self):
        """
        Simply print the hex value for the byte field.
        """
        return self.value[:self.num_bytes].hex()


def little_endian_32(indata: int) -> bytes:
    """
    Get a little endian 32 bit byte array from an int.
    """
    return bytes(
        [
            indata & 0xFF,
            (indata & 0xFF00) >> 8,
            (indata & 0xFF0000) >> 16,
            (indata & 0xFF000000) >> 24,
        ]
    )


def little_endian_16(indata: int) -> bytes:
    """
    Get a little endian 16 bit byte array from an int.
    """
    return bytes([indata & 0xFF, (indata & 0xFF00) >> 8])


def parse_little_endian_16(indata: bytes) -> int:
    """
    Parse a little endian 16 bit byte array into an int.
    """
    return indata[0] | (indata[1] << 8)


def int_to_little_endian(intdata: int, num_bytes: int) -> bytes:
    """
    Convert an integer to a little endian byte array.
    """
    return intdata.to_bytes(num_bytes, byteorder="little")


def little_endian_to_int(data: bytes) -> int:
    """
    Convert a little endian byte array to an integer.
    """
    return int.from_bytes(data, byteorder="little")
