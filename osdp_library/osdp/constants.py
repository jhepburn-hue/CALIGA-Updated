"""
OSDP constants module.
Defines various constants and enumerations used in OSDP communication.
"""

from enum import IntEnum


# Messaging constants
class MessagingConstants(IntEnum):
    """
    Constants related to OSDP messaging.
    """

    SOM = 0x53
    DEFAULT_ADDR = 0
    DEFAULT_CNTRL = 0
    OVERHEAD = 7
    SQN = 0


# Command Tags
class CommandTags(IntEnum):
    """
    Tags representing various OSDP commands.
    """

    POLL = 0x60
    ID = 0x61
    CAP = 0x62
    LSTAT = 0x64
    ISTAT = 0x65
    OSTAT = 0x66
    RSTAT = 0x67
    OUT = 0x68
    LED = 0x69
    BUZ = 0x6A
    TEXT = 0x6B
    COMSET = 0x6E
    BIOREAD = 0x73
    BIOMATCH = 0x74
    KEYSET = 0x75
    CHLNG = 0x76
    SCRYPT = 0x77
    ACURXSIZE = 0x78
    FILETRANSFER = 0x7C
    MFG = 0x80
    XWR = 0xA1
    ABORT = 0xA2
    PIVDATA = 0xA3
    GENAUTH = 0xA4
    CRAUTH = 0xA5
    MFGSTAT = 0xA6
    KEEPACTIVE = 0xA7


# Response Tags
class ResponseTags(IntEnum):
    """
    Tags representing various OSDP responses.
    """

    ACK = 0x40
    NAK = 0x41
    PDID = 0x45
    PDCAP = 0x46
    LSTATR = 0x48
    ISTATR = 0x49
    OSTATR = 0x4A
    RSTATR = 0x4B
    RAW = 0x50
    FMT = 0x51
    KEYPAD = 0x53
    COM = 0x54
    BIOREADR = 0x57
    BIOMATCHR = 0x58
    CCRYPT = 0x76
    RMAC_I = 0x78
    BUSY = 0x79
    FTSTAT = 0x7A
    PIVDATAR = 0x80
    GENAUTHR = 0x81
    CRAUTHR = 0x82
    MFGSTATR = 0x83
    MFGERRR = 0x84
    MFGREP = 0x90
    XRD = 0xB1
    EXT_READER_ID = 0x90


class ManufacturingTags(IntEnum):
    """
    Tags for the WaveLynx Manufacturing command.
    """

    LED_SETTINGS = 0x41
    EXTENDED_ID = 0x9C
    EXTENDED_ID_SERIALIZE = 0x99  # Dummy tag for serialization
    BUZZER = 0x42
    TECHNOLOGY = 0x43
    CREDENTIALS = 0x44
    MOBILE = 0x45
    """
    WaveLynx Manufacturer code for setting mobile settings.
    """
    MOBILE_COMMAND_LENGTH = 0x06
    """Length of the mobile command."""

    """ Features byte breakdown:
    Bit 0: Key rolling
    Bit 1: MyPass credentials
    Bit 2: BLE credentials
    Bit 3-7: Reserved
    """
    FEATURES_RESERVED_MASK = 0xF8
    """Reserved mask for the features byte."""
    KEY_ROLLING_BIT_INDEX = 0
    """index positionfor the key rolling bit."""
    MYPASS_CRED_BIT_INDEX = 1
    """index position for the MyPass credentials bit."""
    BLE_CRED_BIT_INDEX = 2
    """index position for the BLE credentials bit."""

    """ Keysets byte breakdown:
    Bit 0: Keyset 1
    Bit 1: Keyset 2
    Bit 2-7: Reserved
    """
    KEYSETS_RESERVED_MASK = 0x00
    """Reserved mask for the keysets byte."""
    KEYSET_ONE_BIT_INDEX = 0
    """index position for the Keyset 1 bit."""
    KEYSET_TWO_BIT_INDEX = 1
    """index position for the Keyset 2 bit."""

    METADATA_BYTE = 0xFF
    """Metadata byte."""

    KEYS = 0x47
    OSDP = 0x49

    VENDOR_CODE = 0x5C2623
    """
    WaveLynx designated vendor code.
    """

    WL_FORMAT = 0x57
    """
    Format used primarily for consumption of the extended reader info command.  Translates in ASCII to a "W"
    """

    WL_MANUFACTURING_CODE_SET_BUZZER = 0x42
    """
    WaveLynx Manufacturer Code for APEX buzzer setting.
    """

    WL_MANUFACTURING_CODE_EXTENDED_ID = 0x9C
    """
    WaveLynx Manufacturer code for getting the extended reader id.
    """

    WL_MANUFACTURING_CODE_GET_DEVICE_DESCRIPTION = 0x98
    """
    WaveLynx Manufacturer code for getting the extended reader id.
    """

    WL_MANUFACTURING_CODE_SET_BLE = 0xB1
    """
    WaveLynx Manufacturer code to set BLE settings.
    """

    """
    Note: This is the current implementation of Wavelynx's manufacturer buzzer_control
    command for Apex readers.

    See table visualization below.
    +-------+-------+-------+-------------------+-----------------+
    | Value | Bit 1 | Bit 2 | Beep on Card Read | Beep on Startup |
    +-------+-------+-------+-------------------+-----------------+
    | 0x00  | 0     | 0     | no                | no              |
    | 0x01  | 0     | 1     | no                | yes             |
    | 0x02  | 1     | 0     | yes               | no              |
    | 0x03  | 1     | 1     | yes               | yes             |
    +-------+-------+-------+-------------------+-----------------+
    """

    DISABLE_APEX_BUZZER_BOTH = 0x00
    """
    Value for disabling the Apex buzzer on startup and card read.
    """

    APEX_STARTUP_BUZZER_ONLY = 0x1
    """
    Value for enabling the Apex buzzer on startup only.
    """

    APEX_CARD_READ_BUZZER_ONLY = 0x02
    """
    Value for enabling the Apex buzzer on card read only.
    """

    ENABLE_APEX_BUZZER_BOTH = 0x03
    """
    Value for enabling Apex buzzer on startup and card read.
    """

    APEX_BUZZER_BAD_VALUE = 0xFF
    """
    Value for intentionally sending a bad value to toggle the buzzer to confirm device error handling.
    """

    APEX_BUZZER_LENGTH = 0x01
    """
    Indicates the amount of bytes used to zone in on the buzzer transaction for APEX.
    """

    APEX_EXTENDED_ID_GET_LENGTH = 0x0
    """
    This is called "length" in wavelynx documentation and denotes getting extended reader info.
    """

    APEX_EXTENDED_ID_SET_LENGTH = 0x0B
    """
    This flag is for setting the extended manufacturing info for Wavelynx. This is the serial number,
    BLE, HF, and LF respectively.
    """


class ManufacturingResponseTags(IntEnum):
    """
    Tags for the WaveLynx Manufacturing response.
    """

    EXTENDED_ID = 0x9C


class NAKCodes(IntEnum):
    """
    NAK (Negative Acknowledgment) error codes.
    """

    NO_ERROR = 0x00
    MESSAGE_CHECKSUM_ERROR = 0x01
    COMMAND_LENGTH_ERROR = 0x02
    UNKNOWN_COMMAND = 0x03
    UNEXPECTED_HEADER = 0x04
    SECURITY_BLOCK_UNSUPPORTED = 0x05
    ENCRYPTION_REQUIRED = 0x06
    BIO_TYPE_UNSUPPORTED = 0x07
    BIO_FORMAT_UNSUPPORTED = 0x08
    UNABLE_TO_PROCESS = 0x09


# LED color codes
class LEDCodes(IntEnum):
    """
    LED color codes.
    """

    LED_BLACK = 0
    LED_RED = 1
    LED_GREEN = 2
    LED_AMBER = 3
    LED_BLUE = 4
    LED_MAGENTA = 5
    LED_CYAN = 6
    LED_WHITE = 7
    LED_ORANGE = 8
    LED_YELLOW = 9
    LED_PURPLE = 10
    LED_PINK = 11
    LED_LIME = 12
    LED_TEAL = 13
    LED_SILVER = 14
    LED_GRAY = 15
    BAD_LED = -1


LED_NUMBER_TO_NAME: dict = {
    LEDCodes.LED_BLACK: "black",
    LEDCodes.LED_RED: "red",
    LEDCodes.LED_GREEN: "green",
    LEDCodes.LED_AMBER: "amber",
    LEDCodes.LED_BLUE: "blue",
    LEDCodes.LED_MAGENTA: "magenta",
    LEDCodes.LED_CYAN: "cyan",
    LEDCodes.LED_WHITE: "white",
    LEDCodes.LED_ORANGE: "orange",
    LEDCodes.LED_YELLOW: "yellow",
    LEDCodes.LED_PURPLE: "purple",
    LEDCodes.LED_PINK: "pink",
    LEDCodes.LED_LIME: "lime",
    LEDCodes.LED_TEAL: "teal",
    LEDCodes.LED_SILVER: "silver",
    LEDCodes.LED_GRAY: "gray",
}


# LED temp control codes
class LEDTempControlCodes(IntEnum):
    """
    LED temporary control codes.
    """

    LED_TEMP_NOOP = 0
    LED_TEMP_CANCEL = 1
    LED_TEMP_START = 2


# LED perm control codes
class LEDPermControlCodes(IntEnum):
    """
    LED permanent control codes.
    """

    LED_PERM_NOOP = 0
    LED_PERM_ENABLE = 1
    LED_PERM_DISABLE = 2
    LED_PERM_SET_COLOR = 3
    LED_PERM_SET_PATTERN = 4
    LED_PERM_SET_RATE = 5
    LED_PERM_SET_BRIGHTNESS = 6
    LED_PERM_SET_TIMING = 7
    LED_PERM_SET_TEMP = 8
    LED_PERM_SET_CONFIG = 9


# OSDP file fragment size
class FileFragmentConstants(IntEnum):
    """
    Constants related to file transfer fragments.
    """

    FILE_FRAGMENT_MAX = 128 - 18  # MAX_PACKET_SIZE - OSDP_OVERHEAD
    FILE_TYPE_OPAQUE = 1


# File Transfer status
class FileTransferStatus(IntEnum):
    """
    File transfer status codes.
    """

    FT_OK = 0
    FT_PROCESSED = 1
    FT_REBOOTING = 2
    FT_FINISHING = 3


class FileTransferStatusDetails(IntEnum):
    """
    File transfer status details.
    """

    OK = 0
    FILE_PROCESSED = 1
    REBOOTING = 2
    FINISHING = 3
    ABORT_FILE_TRANSFER = -1
    UNRECOGNIZED_FILE_CONTENTS = -2
    FILE_DATA_UNACCEPTABLE = -3


# Control block masks
class ControlBlockMasks(IntEnum):
    """
    Masks for control block flags.
    """

    SQN_MASK = 0x03
    CRC_MASK = 0x04  # Set this mask for CRC, don't set for checksum
    SCB_MASK = 0x08  # Set this mask if security block is present


# Security control block types
class SecurityBlockType(IntEnum):
    """
    Possible types for the security block field.
    """

    SCS_11 = 0x11
    SCS_12 = 0x12
    SCS_13 = 0x13
    SCS_14 = 0x14
    SCS_15 = 0x15
    SCS_16 = 0x16
    SCS_17 = 0x17
    SCS_18 = 0x18


# Security constants
class SecurityConstants(IntEnum):
    """
    Security-related constants.
    """

    SCBK = 0x01
    SCBK_D = 0x00
    S_ENC_KEY_TYPE = 0x82
    S_MAC1_KEY_TYPE = 0x01
    S_MAC2_KEY_TYPE = 0x02
    SCS_11 = 0x11
    SCS_13 = 0x13
    SCS_15 = 0x15
    SCS_16 = 0x16
    SCS_17 = 0x17
    SCS_18 = 0x18


class FunctionCodes(IntEnum):
    """
    Function codes for secure channel.
    """

    CONTACT_STATUS_MONITORING = 1
    OUTPUT_CONTROL = 2
    CARD_DATA_FORMAT = 3
    READER_LED_CONTROL = 4
    READER_AUDIBLE_OUTPUT = 5
    READER_TEST_OUTPUT = 6
    TIME_KEEPING = 7
    CHECK_CHARACTER_SUPPORT = 8
    COMMUNICATION_SECURITY = 9
    RECEIVE_BUFFER_SIZE = 10
    LARGEST_COMBINED_MESSAGE_SIZE = 11
    SMART_CARD_SUPPORT = 12
    READERS = 13
    BIOMETRICS = 14
    SECURE_PIN_ENTRY_SUPPORT = 15
    OSDP_VERSION = 16


class TamperStatus(IntEnum):
    """
    Tamper status codes. LSTATR
    """

    NORMAL = 0
    TAMPER_ACTIVE = 1
    TAMPER_RESOLVED = 2
    TAMPER_ERROR = 3


class PowerStatus(IntEnum):
    """
    Power status codes. LSTATR
    """

    NORMAL = 0
    POWER_FAILURE = 1


class BuzToneCodes(IntEnum):
    """
    OSDP Buz Tone Codes.
    """

    NONE = 0
    OFF = 1
    DEFAULT = 2


class BioTypeCodes(IntEnum):
    """
    BIOREAD bio type codes
    """

    DEFAULT = 0x00
    RIGHT_THUMB = 0x01
    RIGHT_INDEX = 0x02
    RIGHT_MIDDLE = 0x03
    RIGHT_RING = 0x04
    RIGHT_LITTLE = 0x05
    LEFT_THUMB = 0x06
    LEFT_INDEX = 0x07
    LEFT_MIDDLE = 0x08
    LEFT_RING = 0x09
    LEFT_LITTLE = 0x0A
    RIGHT_IRIS = 0x0B
    LEFT_IRIS = 0x0C
    FACE = 0x0D
    RIGHT_HAND_GEOMETRY = 0x0E
    LEFT_HAND_GEOMETRY = 0x0F


class BioFormatCodes(IntEnum):
    """
    Possible values for biometric format templates.
    """

    DEFAULT = 0x00


class BioQualityCodes(IntEnum):
    """
    Possible values dictating bio read quality.
    """

    DEFAULT = 0x00
    POOR = 0x10
    FAIR = 0x20
    GOOD = 0x40
    VERY_GOOD = 0x60
    EXCELLENT = 0x80
    PERFECT = 0xFF


class BleAdvertising(IntEnum):
    ADVERTISING_INTERVAL_MIN = 0x0020
    ADVERTISING_INTERVAL_MAX = 0x4000


class BleTxPower(IntEnum):
    """
    Values to set the TX power when setting BLE.
    """

    NEGATIVE_30_DBM = 0x00
    NEGATIVE_20_DBM = 0x01
    NEGATIVE_16_DBM = 0x02
    NEGATIVE_12_DBM = 0x03
    NEGATIVE_8_DBM = 0x04
    NEGATIVE_4_DBM = 0x05
    ZERO_DBM = 0x06


# Integer range constants
MAX_8_BIT: int = 255
"""
Maximum value for 8-bit unsigned integer
"""

MAX_16_BIT: int = 65535
"""
Maximum value for 16-bit unsigned integer
"""

MAX_32_BIT: int = 0xFFFFFFFF
"""
Maximum value for 32-bit unsigned integer
"""

MAXIMUM_SERIAL_NUMBER: int = 0xFFFFFFFFFFFFFFFF
"""
Maximum serial number value, which is the largest 64 bit unsigned hex integer.
Equal to 18,446,744,073,709,551,615 in decimal. This probably gives us enough
serial numbers for our readers for awhile.
"""

# Security block initialization constants
DEFAULT_SCB_LENGTH: int = 2
"""
Default security control block length for initialization
"""

DEFAULT_SCB_TYPE: SecurityBlockType = SecurityBlockType.SCS_15
"""
Default security control block type for initialization
"""

# Manufacturer-specific OIDs and keys
MFG_OID: bytes = bytes([0x5C, 0x26, 0x23])
MFG_WL_ID: bytes = bytes([0x57])
SCBK_D_KEY: bytes = b"\x30\x31\x32\x33\x34\x35\x36\x37\x38\x39\x3a\x3b\x3c\x3d\x3e\x3f"
SCBK_KEY_2: bytes = b"\x40\x41\x42\x43\x44\x45\x46\x47\x48\x49\x4a\x4b\x4c\x4d\x4e\x4f"

MANUFACTURING_COMMAND_MINIMUM_DATA_LENGTH = 3
