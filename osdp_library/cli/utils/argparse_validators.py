"""Argparse validator type functions."""

import argparse
from pathlib import Path


def int_range(min_val: int, max_val: int):
    """
    Create a type function for argparse that validates an integer is within a range.

    :param min_val: Minimum allowed value (inclusive)
    :param max_val: Maximum allowed value (inclusive)
    :return: Type function that validates and returns the integer
    :raises argparse.ArgumentTypeError: If value is outside the range

    Example:
        parser.add_argument("--address", type=int_range(0, 127), help="Device address (0-127)")
    """

    def validate(value: str) -> int:
        try:
            int_value = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{value} is not a valid integer") from None

        if not min_val <= int_value <= max_val:
            raise argparse.ArgumentTypeError(f"{value} is not in the valid range [{min_val}, {max_val}]")

        return int_value

    return validate


def hex_string(max_length: int | None = None, min_length: int | None = None, exact_length: int | None = None):
    """
    Create a type function for argparse that validates a hex string.

    :param max_length: Maximum allowed hex string length (in characters)
    :param min_length: Minimum allowed hex string length (in characters)
    :param exact_length: Exact required hex string length (in characters)
    :return: Type function that validates and returns the hex string
    :raises argparse.ArgumentTypeError: If value is not valid hex or length constraints are violated

    Example:
        parser.add_argument("--serial", type=hex_string(max_length=16), help="Serial number (max 16 hex chars)")
        parser.add_argument("--vendor", type=hex_string(exact_length=6), help="Vendor code (exactly 6 hex chars)")
    """

    def validate(value: str) -> str:
        # Validate hex format
        try:
            int(value, 16)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{value} is not a valid hexadecimal string (must contain only 0-9, A-F)") from None

        # Validate length constraints
        length = len(value)
        if exact_length is not None:
            if length != exact_length:
                raise argparse.ArgumentTypeError(f"{value} must be exactly {exact_length} hexadecimal characters (got {length})")
        else:
            if min_length is not None and length < min_length:
                raise argparse.ArgumentTypeError(f"{value} must be at least {min_length} hexadecimal characters (got {length})")
            if max_length is not None and length > max_length:
                raise argparse.ArgumentTypeError(f"{value} must be at most {max_length} hexadecimal characters (got {length})")

        return value

    return validate


def hex_bytes(exact_bytes: int | None = None):
    """
    Create a type function for argparse that validates a hex string and converts it to bytes.

    :param exact_bytes: Exact required number of bytes (hex string length must be 2 * exact_bytes)
    :return: Type function that validates and returns bytes
    :raises argparse.ArgumentTypeError: If value is not valid hex or byte length constraint is violated

    Example:
        parser.add_argument("--vendor", type=hex_bytes(exact_bytes=3), help="Vendor code (6 hex chars = 3 bytes)")
    """

    def validate(value: str) -> bytes:
        # Validate hex format
        try:
            result = bytes.fromhex(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{value} is not a valid hexadecimal string (must contain only 0-9, A-F)") from None

        # Validate byte length
        if exact_bytes is not None and len(result) != exact_bytes:
            raise argparse.ArgumentTypeError(
                f"{value} must represent exactly {exact_bytes} bytes (got {len(value)} hex chars = {len(result)} bytes)"
            )

        return result

    return validate


def hex_bytearray():
    """
    Create a type function for argparse that validates a hex string and converts it to bytearray.

    :return: Type function that validates and returns bytearray
    :raises argparse.ArgumentTypeError: If value is not valid hex

    Example:
        parser.add_argument("--data", type=hex_bytearray(), help="Data as hex string")
    """

    def validate(value: str) -> bytearray:
        try:
            return bytearray.fromhex(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{value} is not a valid hexadecimal string (must contain only 0-9, A-F)") from None

    return validate


def file_path(must_exist: bool = True, must_be_file: bool = True, must_not_be_empty: bool = True):
    """
    Create a type function for argparse that validates a file path.

    :param must_exist: If True, file must exist
    :param must_be_file: If True, path must be a regular file (not directory)
    :param must_not_be_empty: If True, file must not be empty
    :return: Type function that validates and returns the Path object
    :raises argparse.ArgumentTypeError: If file validation fails

    Example:
        parser.add_argument("--file", type=file_path(), help="Path to file")
    """

    def validate(value: str) -> Path:
        path = Path(value)

        if must_exist and not path.exists():
            raise argparse.ArgumentTypeError(f"File not found: {value}")

        if must_be_file and not path.is_file():
            raise argparse.ArgumentTypeError(f"Not a file: {value}")

        if must_not_be_empty and path.exists() and path.stat().st_size == 0:
            raise argparse.ArgumentTypeError(f"File is empty: {value}")

        return path

    return validate


def parse_true_false(value: str) -> bool:
    """
    Create a type function for argparse that validates a true/false string value.

    :param value: The value to validate.
    :return: The boolean value (True or False).
    :raises argparse.ArgumentTypeError: If value is not a valid true/false string value.
    """
    converted_value = value.lower().strip()
    if converted_value == "true":
        return True
    elif converted_value == "false":
        return False
    else:
        raise argparse.ArgumentTypeError(f"Invalid string value. Expected true or false. Got: {value}")
