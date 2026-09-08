"""Utility functions for OSDP protocol operations."""

import logging
from typing import Literal

import crcmod
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import CommandTags, ResponseTags

AES_BLOCK_SIZE: int = 16
"""
Encryption block size used in OSDP comms.
"""


def calc_checksum(message: bytes) -> int:
    """
    Calculates the checksum for an OSDP message.

    :param message: Message bytes to calculate checksum for
    :return: Calculated checksum as int
    """
    checksum = 0
    for byte in message:
        checksum = (checksum + byte) & 0xFF
    return ((~checksum) + 1) & 0xFF


def crc_to_little_endian(crc: int) -> int:
    """
    Convert CRC to little-endian format.

    :param crc: CRC value to convert
    :return: CRC in little-endian format as int
    """
    return ((crc & 0xFF) << 8) | ((crc >> 8) & 0xFF)


def calc_crc(message: bytes) -> int:
    """
    Calculates the CRC for an OSDP message.

    :param message: Message bytes to calculate CRC for
    :return: Calculated CRC as int
    """
    crc16_ccitt = crcmod.mkCrcFun(0x11021, initCrc=0x1D0F, rev=False, xorOut=0x0000)
    crc = crc16_ccitt(message)
    return crc


def encrypt(key, data, mode="ECB", iv=None):
    """
    Encrypts the data using AES encryption with the given key.

    :param key: The encryption key (must be 16, 24, or 32 bytes long)
    :param data: The data to encrypt (bytes, must be a multiple of 16 bytes in length)
    :param mode: The encryption mode (default is 'ECB')
    :param iv: Initialization vector (IV) for modes that require it, can be a hex string or bytes
    :return: The encrypted data as bytes
    """
    if isinstance(key, str):
        key = bytes.fromhex(key)  # Convert hex key back to bytes if necessary
    if isinstance(iv, str):
        iv = bytes.fromhex(iv)  # Convert hex IV back to bytes if necessary
    assert len(key) in [16, 24, 32], "Key length must be 16, 24, or 32 bytes"
    assert len(data) % 16 == 0, "Data length must be a multiple of 16 bytes"

    # Create a new AES cipher object based on the provided mode and iv
    algorithm = algorithms.AES(key)
    cipher_mode = modes.CBC(iv) if mode == "CBC" and iv else modes.ECB()

    cipher = Cipher(algorithm, cipher_mode, backend=default_backend())
    encryptor = cipher.encryptor()

    # Encrypt the data
    encrypted_data = encryptor.update(data) + encryptor.finalize()
    return encrypted_data


def decrypt(key, data, icv=None):
    """
    Decrypts the data using AES encryption with the given key.

    :param key: The encryption key (must be 16, 24, or 32 bytes long, can be hex string or bytes)
    :param data: The data to decrypt (bytes, must be a multiple of 16 bytes in length)
    :param icv: The initialization vector (bytes, must be 16 bytes long, can be hex string or bytes)
    :return: The decrypted data as bytes
    """
    if isinstance(key, str):
        key = bytes.fromhex(key)  # Convert hex string to bytes if necessary
    if icv and isinstance(icv, str):
        icv = bytes.fromhex(icv)  # Convert hex string to bytes if necessary

    # Ensure the key is 16, 24, or 32 bytes long
    assert len(key) in [16, 24, 32], "Key length must be 16, 24, or 32 bytes"

    # Ensure the data length is a multiple of 16 bytes
    assert len(data) % 16 == 0, "Data length must be a multiple of 16 bytes"

    # Create a new AES cipher object
    algorithm = algorithms.AES(key)
    cipher_mode = modes.CBC(icv)
    cipher = Cipher(algorithm, cipher_mode, backend=default_backend())
    decryptor = cipher.decryptor()

    # Decrypt the data
    decrypted_data = decryptor.update(data) + decryptor.finalize()
    logging.debug(f"Raw decrypted data: {decrypted_data.hex()}")

    # trim the end padding, 0x00 and then finally one 0x80
    decrypted_data = decrypted_data.rstrip(b"\x00")

    # the last byte should be 0x80
    if decrypted_data[-1] == 0x80:
        decrypted_data = decrypted_data[:-1]
    else:
        logging.error(f"Invalid padding in decrypted data: {decrypted_data.hex()}")
        raise ValueError("Invalid padding in decrypted data")

    return decrypted_data


def pad_data(data: bytes, block_size: int = 16) -> bytes:
    """
    Pad data to a given block size using the 0x80 followed by 0x00 method.

    :param data: Data to pad
    :param block_size: Block size to pad to (typically 16 for AES)
    :return: Padded data as bytes
    """
    padding_needed = block_size - (len(data) % block_size)
    if padding_needed == block_size:
        padding_needed = 0

    if padding_needed == 0:
        return data + b"\x80" + b"\x00" * (block_size - 1)
    else:
        return data + b"\x80" + b"\x00" * (padding_needed - 1)


def unpad_data(padded_data: bytes) -> bytes:
    """
    Remove padding from data that was padded using the 0x80 followed by 0x00 method.

    :param padded_data: Padded data to unpad
    :return: Unpadded data as bytes
    """
    # Remove trailing 0x00 bytes
    data = padded_data.rstrip(b"\x00")

    # Check if the last byte is 0x80 and remove it
    if data and data[-1] == 0x80:
        return data[:-1]
    else:
        raise ValueError("Invalid padding in data")


def ones_complement(byte_array):
    """
    Calculate the one's complement of a byte array.

    :param byte_array: Input byte array
    :return: One's complement as bytearray
    """
    # Create a new bytearray to store the one's complement
    complement = bytearray()

    # Iterate through each byte in the input bytearray
    for byte in byte_array:
        # Apply bitwise NOT and mask with 0xFF to get the one's complement of the byte
        complement.append(~byte & 0xFF)

    return complement


def _format_hex_int(value: int, width: int = 0) -> str:
    """
    Format an integer as a hexadecimal string.

    :param value: Integer to format
    :param width: Minimum width for zero-padding (0 = no padding)
    :return: Formatted hex string (e.g., "0x53", "0x0053")
    """
    return f"0x{value:0{width}X}" if width else f"0x{value:X}"


def _format_hex_bytes_numeric(value: bytes | bytearray, width: int = 0, byteorder: Literal["little", "big"] = "little") -> str:
    """
    Format bytes/bytearray as a hexadecimal string (numeric interpretation).

    Converts bytes to integer first, then formats as hex.
    Useful for single-byte or multi-byte values that represent a single number.

    Note: For raw byte sequences, use format_bytes_hex() instead.

    :param value: Bytes or bytearray to format
    :param width: Minimum width for zero-padding (0 = no padding)
    :param byteorder: Byte order for conversion ("little" or "big")
    :return: Formatted hex string (e.g., "0x53", "0x23265C")
    """
    int_val = int.from_bytes(value, byteorder=byteorder)
    return f"0x{int_val:0{width}X}" if width else f"0x{int_val:X}"


def format_hex(value: int | bytes | bytearray, width: int = 0, byteorder: Literal["little", "big"] = "little") -> str:
    """
    Format a value as a hexadecimal string with consistent formatting.

    Format: 0x{value:0{width}X} (uppercase, with 0x prefix, zero-padded if width specified)

    For bytes/bytearray, this converts to an integer first (useful for single-byte or multi-byte
    values that represent a single number). For displaying raw byte sequences as hex strings,
    use format_bytes_hex() instead.

    :param value: Integer, bytes, or bytearray to format
    :param width: Minimum width for zero-padding (0 = no padding)
    :param byteorder: Byte order for bytes/bytearray conversion ("little" or "big")
    :return: Formatted hex string (e.g., "0x53", "0x0053", "0x23265C")
    :raises TypeError: If value is not int, bytes, or bytearray
    """
    if isinstance(value, int):
        return _format_hex_int(value, width)
    elif isinstance(value, (bytes, bytearray)):
        return _format_hex_bytes_numeric(value, width, byteorder)
    else:
        raise TypeError(f"format_hex() requires int, bytes, or bytearray, got {type(value)}")


def format_bytes_hex(data: bytes | bytearray, prefix: bool = True) -> str:
    """
    Format bytes/bytearray as a continuous hexadecimal string.

    This is for displaying raw byte sequences (e.g., card data, keypad input).
    Format: 0x{hex_string} (uppercase, with optional 0x prefix)

    :param data: Bytes or bytearray to format
    :param prefix: Whether to include "0x" prefix (default: True)
    :return: Formatted hex string (e.g., "0xA1B2C3D4" or "A1B2C3D4")
    :raises TypeError: If data is not bytes or bytearray
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"format_bytes_hex() requires bytes or bytearray, got {type(data)}")
    hex_str = data.hex().upper()
    return f"0x{hex_str}" if prefix else hex_str


def format_bytes_hex_reversed(data: bytes | bytearray, prefix: bool = True) -> str:
    """
    Format bytes/bytearray as a hexadecimal string with bytes reversed.

    Useful for displaying little-endian wire data in big-endian (human-readable) format.
    For example, OSDP serial numbers are transmitted LSB-first but should display MSB-first.

    :param data: Bytes or bytearray to format (will be reversed for display)
    :param prefix: Whether to include "0x" prefix (default: True)
    :return: Formatted hex string with bytes reversed (e.g., wire 0x78220D00 -> display 0x000D2278)
    :raises TypeError: If data is not bytes or bytearray
    """
    return format_bytes_hex(bytes(reversed(data)), prefix)


def get_command_name(tag: int) -> str:
    """
    Get human-readable command name from tag.

    :param tag: Command tag value
    :return: Command name (e.g., "POLL") or "UNKNOWN_CMD(0xXX)" if not found
    """
    try:
        return CommandTags(tag).name
    except ValueError:
        return f"UNKNOWN_CMD(0x{tag:02x})"


def get_response_name(tag: int) -> str:
    """
    Get human-readable response name from tag.

    :param tag: Response tag value
    :return: Response name (e.g., "ACK") or "UNKNOWN_RSP(0xXX)" if not found
    """

    try:
        return ResponseTags(tag).name
    except ValueError:
        return f"UNKNOWN_RSP(0x{tag:02x})"
