from dataclasses import dataclass
from typing import Any, ClassVar

from .constants import (
    MANUFACTURING_COMMAND_MINIMUM_DATA_LENGTH,
    MAX_8_BIT,
    MAX_16_BIT,
    MAX_32_BIT,
    BioFormatCodes,
    BioQualityCodes,
    BioTypeCodes,
    CommandTags,
    LEDCodes,
    LEDPermControlCodes,
    LEDTempControlCodes,
    ManufacturingTags,
)
from .exceptions import PayloadValidationError
from .payload import OsdpBasePayload


@dataclass
class OsdpPollPayload(OsdpBasePayload):
    """
    osdp_POLL payload.

    Byte structure: Empty payload (0 bytes)
    """

    def to_bytes(self) -> bytes:
        """
        Convert payload to byte representation.

        :return: Empty byte array for POLL command
        """
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpPollPayload":
        """
        Create OsdpPollPayload from byte array.

        :param ba: Input byte array (unused for POLL)
        :return: OsdpPollPayload instance
        """
        _ = ba  # unused but required parameter
        return OsdpPollPayload(tag=CommandTags.POLL)


@dataclass
class OsdpIdReportRequestPayload(OsdpBasePayload):
    """
    osdp_ID payload.

    Byte structure (1 byte):
    [0] pdid_type - PDID block type requested
    """

    DATA_LEN: int = 1
    """
    Expected data length for osdp_ID payload in bytes
    """

    PDID_TYPE_IDX: int = 0
    """
    Index position of PDID type field in payload
    """

    DATA_SEND_STD_PD_ID_BLOCK: int = 0x00
    """
    Standard PDID block request code
    """

    pdid_type: int = 0x00
    """
    pdid block requested.
    """

    def __post_init__(self):
        """
        Validate field values after initialization.
        """
        if self.pdid_type > self.DATA_SEND_STD_PD_ID_BLOCK:
            raise PayloadValidationError("osdp_ID bad pdid_type")

    def to_bytes(self) -> bytes:
        """
        Convert payload to byte representation.

        :return: Single byte containing pdid_type
        """
        return bytes([self.pdid_type])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpIdReportRequestPayload":
        """
        Create OsdpIdReportRequestPayload from byte array.

        :param ba: Input byte array containing pdid_type
        :return: OsdpIdReportRequestPayload instance
        """
        if len(ba) != OsdpIdReportRequestPayload.DATA_LEN:
            raise PayloadValidationError("osdp_ID payload bad length")

        payload: OsdpIdReportRequestPayload = OsdpIdReportRequestPayload(tag=CommandTags.ID, pdid_type=ba[0])

        if payload.pdid_type > OsdpIdReportRequestPayload.DATA_SEND_STD_PD_ID_BLOCK:
            raise PayloadValidationError("osdp_ID bad pdid_type")

        return payload

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for ID payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "pdid_type": {"name": "PDID Type", "transform": "hex", "width": 2},
        }
        return fields


@dataclass
class OsdpCapPayload(OsdpBasePayload):
    """
    osdp_CAP payload.

    Byte structure (1 byte):
    [0] cap_type - Capability type requested
    """

    DATA_LEN: int = 1
    """
    Expected data length for osdp_CAP payload in bytes
    """

    CAP_TYPE_IDX: int = 0
    """
    Index position of capability type field in payload
    """

    CAP_SEND_STD_REPLY: int = 0x00
    """
    Standard capability reply request code
    """

    cap_type: int = 0x00
    """
    Capability type requested (0=standard capability reply)
    """

    def to_bytes(self) -> bytes:
        return bytes([self.cap_type])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpCapPayload":
        if len(ba) != OsdpCapPayload.DATA_LEN:
            raise PayloadValidationError("osdp_CAP payload bad length")

        payload: OsdpCapPayload = OsdpCapPayload(tag=CommandTags.CAP, cap_type=ba[0])
        return payload

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for CAP payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "cap_type": {"name": "Cap Type", "transform": "hex", "width": 2},
        }
        return fields


@dataclass
class OsdpLstatPayload(OsdpBasePayload):
    """
    osdp_LSTAT payload.

    Byte structure: Empty payload (0 bytes)
    """

    def to_bytes(self) -> bytes:
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpLstatPayload":
        _ = ba  # unused but required parameter
        return OsdpLstatPayload(tag=CommandTags.LSTAT)


@dataclass
class OsdpIstatPayload(OsdpBasePayload):
    """
    osdp_ISTAT payload.

    Byte structure: Empty payload (0 bytes)
    """

    def to_bytes(self) -> bytes:
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpIstatPayload":
        _ = ba  # unused but required parameter
        return OsdpIstatPayload(tag=CommandTags.ISTAT)


@dataclass
class OsdpOstatPayload(OsdpBasePayload):
    """
    osdp_OSTAT payload.

    Byte structure: Empty payload (0 bytes)
    """

    def to_bytes(self) -> bytes:
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpOstatPayload":
        _ = ba  # unused but required parameter
        return OsdpOstatPayload(tag=CommandTags.OSTAT)


@dataclass
class OsdpRstatPayload(OsdpBasePayload):
    """
    osdp_RSTAT payload.

    Byte structure: Empty payload (0 bytes)
    """

    def to_bytes(self) -> bytes:
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpRstatPayload":
        _ = ba  # unused but required parameter
        return OsdpRstatPayload(tag=CommandTags.RSTAT)


@dataclass
class OsdpOutputRecord:
    """
    Output control record.

    Byte structure (4 bytes):
    [0] output_number - Output number/identifier
    [1] control_code - Control operation (0=NOP, 1=off, 2=on, 3=toggle)
    [2] timer_lsb - Timer LSB (100ms units)
    [3] timer_msb - Timer MSB (100ms units)
    """

    output_number: int
    """
    Output number/identifier (0-255)
    """
    control_code: int
    """
    Output control code (0=NOP, 1=off/reset, 2=on/set, 3=current state inverted)
    """
    timer: int
    """
    Timer value in milliseconds for temporary output control
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.output_number < 0 or self.output_number > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid output_number: {self.output_number}")
        if self.control_code < 0 or self.control_code > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid control_code: {self.control_code}")
        if self.timer < 0 or self.timer > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid timer: {self.timer}")

    def to_bytes(self) -> bytes:
        timer_lsb = self.timer & 0xFF
        timer_msb = (self.timer >> 8) & 0xFF
        return bytes([self.output_number, self.control_code, timer_lsb, timer_msb])

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "OsdpOutputRecord":
        timer = data[offset + 2] | (data[offset + 3] << 8)
        return cls(
            output_number=data[offset],
            control_code=data[offset + 1],
            timer=timer,
        )


@dataclass
class OsdpOutPayload(OsdpBasePayload):
    """
    osdp_OUT payload.

    Byte structure (variable length, multiple of 4 bytes):
    Multiple OsdpOutputRecord structures concatenated
    """

    records: list[OsdpOutputRecord]
    """
    List of output control records to be processed
    """

    RECORD_SIZE: int = 4
    """
    Size in bytes of each output control record
    """

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for OUT payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "_record_count": {"name": "Records", "compute": lambda p: len(p.records)},
        }

        if not format_short:
            fields = {
                **fields,
                "_output": {"name": "Output", "compute": lambda p: p.records[0].output_number if p.records else None},
                "_control": {"name": "Control", "compute": lambda p: p.records[0].control_code if p.records else None},
            }

        return fields

    def to_bytes(self) -> bytes:
        data = bytearray()
        for record in self.records:
            data.extend(record.to_bytes())
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpOutPayload":
        if len(ba) < OsdpOutPayload.RECORD_SIZE or len(ba) % OsdpOutPayload.RECORD_SIZE != 0:
            raise PayloadValidationError("osdp_OUT payload bad length")

        records = []
        for i in range(0, len(ba), OsdpOutPayload.RECORD_SIZE):
            records.append(OsdpOutputRecord.from_bytes(bytes(ba), i))

        return OsdpOutPayload(tag=CommandTags.OUT, records=records)


@dataclass
class OsdpLedRecord:
    """
    LED control record.

    Byte structure (14 bytes):
    [0] reader_number - Reader number
    [1] led_number - LED number on reader
    [2] temp_control_code - Temporary control (0=noop, 1=cancel, 2=start)
    [3] temp_on_time - Temporary on time (100ms units)
    [4] temp_off_time - Temporary off time (100ms units)
    [5] temp_on_color - Temporary on color
    [6] temp_off_color - Temporary off color
    [7] temp_timer_lsb - Temporary timer LSB (seconds)
    [8] temp_timer_msb - Temporary timer MSB (seconds)
    [9] perm_control_code - Permanent control (0=noop, 1=enable)
    [10] perm_on_time - Permanent on time (100ms units)
    [11] perm_off_time - Permanent off time (100ms units)
    [12] perm_on_color - Permanent on color
    [13] perm_off_color - Permanent off color
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """
    led_number: int
    """
    LED number/identifier on the specified reader (0-255)
    """
    temp_control_code: LEDTempControlCodes
    """
    Temporary LED control code (0=noop, 1=cancel, 2=start)
    """

    temp_on_time: int
    """
    Temporary LED on time in 100ms intervals
    """

    temp_off_time: int
    """
    Temporary LED off time in 100ms intervals
    """

    temp_on_color: LEDCodes
    """
    Temporary LED on color (0=black, 1=red, 2=green, 3=amber, 4=blue)
    """

    temp_off_color: LEDCodes
    """
    Temporary LED off color (0=black, 1=red, 2=green, 3=amber, 4=blue)
    """

    temp_timer: int
    """
    Temporary LED timer in seconds
    """

    perm_control_code: LEDPermControlCodes
    """
    Permanent LED control code (0=noop, 1=enable)
    """

    perm_on_time: int
    """
    Permanent LED on time in 100ms intervals
    """

    perm_off_time: int
    """
    Permanent LED off time in 100ms intervals
    """

    perm_on_color: LEDCodes
    """
    Permanent LED on color (0=black, 1=red, 2=green, 3=amber, 4=blue)
    """

    perm_off_color: LEDCodes
    """
    Permanent LED off color (0=black, 1=red, 2=green, 3=amber, 4=blue)
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.reader_number < 0 or self.reader_number > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid reader_number: {self.reader_number}")
        if self.led_number < 0 or self.led_number > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid led_number: {self.led_number}")
        if self.temp_on_time < 0 or self.temp_on_time > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid temp_on_time: {self.temp_on_time}")
        if self.temp_off_time < 0 or self.temp_off_time > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid temp_off_time: {self.temp_off_time}")
        if self.temp_timer < 0 or self.temp_timer > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid temp_timer: {self.temp_timer}")
        if self.perm_on_time < 0 or self.perm_on_time > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid perm_on_time: {self.perm_on_time}")
        if self.perm_off_time < 0 or self.perm_off_time > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid perm_off_time: {self.perm_off_time}")

    def to_bytes(self) -> bytes:
        temp_timer_lsb = self.temp_timer & 0xFF
        temp_timer_msb = (self.temp_timer >> 8) & 0xFF
        return bytes(
            [
                self.reader_number,
                self.led_number,
                self.temp_control_code,
                self.temp_on_time,
                self.temp_off_time,
                self.temp_on_color,
                self.temp_off_color,
                temp_timer_lsb,
                temp_timer_msb,
                self.perm_control_code,
                self.perm_on_time,
                self.perm_off_time,
                self.perm_on_color,
                self.perm_off_color,
            ]
        )

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "OsdpLedRecord":
        temp_timer = data[offset + 7] | (data[offset + 8] << 8)
        return cls(
            reader_number=data[offset],
            led_number=data[offset + 1],
            temp_control_code=LEDTempControlCodes(data[offset + 2]),
            temp_on_time=data[offset + 3],
            temp_off_time=data[offset + 4],
            temp_on_color=LEDCodes(data[offset + 5]),
            temp_off_color=LEDCodes(data[offset + 6]),
            temp_timer=temp_timer,
            perm_control_code=LEDPermControlCodes(data[offset + 9]),
            perm_on_time=data[offset + 10],
            perm_off_time=data[offset + 11],
            perm_on_color=LEDCodes(data[offset + 12]),
            perm_off_color=LEDCodes(data[offset + 13]),
        )


@dataclass
class OsdpLedPayload(OsdpBasePayload):
    """
    osdp_LED payload.

    Byte structure (variable length, multiple of 14 bytes):
    Multiple OsdpLedRecord structures concatenated
    """

    records: list[OsdpLedRecord]
    """
    List of LED control records to be processed
    """

    RECORD_SIZE: int = 14
    """
    Size in bytes of each LED control record
    """

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for LED payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "_record_count": {"name": "Records", "compute": lambda p: len(p.records)},
        }

        if not format_short:
            fields = {
                **fields,
                "_reader": {"name": "Reader", "compute": lambda p: p.records[0].reader_number if p.records else None},
                "_led": {"name": "LED", "compute": lambda p: p.records[0].led_number if p.records else None},
                "_temp_color": {"name": "Temp Color", "compute": lambda p: p.records[0].temp_on_color.value if p.records else None},
                "_perm_color": {"name": "Perm Color", "compute": lambda p: p.records[0].perm_on_color.value if p.records else None},
            }

        return fields

    def to_bytes(self) -> bytes:
        data = bytearray()
        for record in self.records:
            data.extend(record.to_bytes())
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpLedPayload":
        if len(ba) < OsdpLedPayload.RECORD_SIZE or len(ba) % OsdpLedPayload.RECORD_SIZE != 0:
            raise PayloadValidationError("osdp_LED payload bad length")

        records = []
        for i in range(0, len(ba), OsdpLedPayload.RECORD_SIZE):
            records.append(OsdpLedRecord.from_bytes(bytes(ba), i))

        return OsdpLedPayload(tag=CommandTags.LED, records=records)


@dataclass
class OsdpBuzPayload(OsdpBasePayload):
    """
    osdp_BUZ payload.

    Byte structure (5 bytes):
    [0] reader_number - Reader number
    [1] tone_code - Tone code (0=none, 1=off, 2=default)
    [2] on_time - On time (100ms units)
    [3] off_time - Off time (100ms units)
    [4] count - Number of on/off cycles
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """
    tone_code: int
    """
    Wavelynx has a non standard implementation of the tone code
    that customers have adopted and we support.
    That is (0=off, 1=on, 2=buzz on read)
    However, SIA OSDP 2.2-2 Specifies the following tone codes:
    (0=deprecated, 1=off, 2=default)
    """
    on_time: int
    """
    Buzzer on time in 100ms intervals
    """
    off_time: int
    """
    Buzzer off time in 100ms intervals
    """
    count: int
    """
    Number of buzzer on/off cycles
    """

    DATA_LEN: int = 5
    """
    Expected data length for osdp_BUZ payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.reader_number < 0 or self.reader_number > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid reader_number: {self.reader_number}")
        if self.tone_code < 0 or self.tone_code > 2:
            raise PayloadValidationError(f"Invalid tone_code: {self.tone_code}")
        if self.on_time < 0 or self.on_time > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid on_time: {self.on_time}")
        if self.off_time < 0 or self.off_time > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid off_time: {self.off_time}")
        if self.count < 0 or self.count > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid count: {self.count}")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for BUZ payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "reader_number": {"name": "Reader"},
            "tone_code": {"name": "Tone"},
        }

        if not format_short:
            fields = {
                **fields,
                "on_time": {"name": "On Time"},
                "off_time": {"name": "Off Time"},
                "count": {"name": "Count"},
            }

        return fields

    def to_bytes(self) -> bytes:
        return bytes(
            [
                self.reader_number,
                self.tone_code,
                self.on_time,
                self.off_time,
                self.count,
            ]
        )

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpBuzPayload":
        if len(ba) != OsdpBuzPayload.DATA_LEN:
            raise PayloadValidationError("osdp_BUZ payload bad length")

        return OsdpBuzPayload(
            tag=CommandTags.BUZ,
            reader_number=ba[0],
            tone_code=ba[1],
            on_time=ba[2],
            off_time=ba[3],
            count=ba[4],
        )


@dataclass
class OsdpTextPayload(OsdpBasePayload):
    """
    osdp_TEXT payload.

    Byte structure (6 + text_length bytes):
    [0] reader_number - Reader number
    [1] text_command - Text command (1=permanent, 2=temporary)
    [2] temp_text_time - Temporary text time (seconds)
    [3] row - Display row position
    [4] column - Display column position
    [5] text_length - Length of text string
    [6...6+text_length-1] display_string - Text to display
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """
    text_command: int
    """
    Text display command (1=permanent text, 2=temporary text)
    """
    temp_text_time: int
    """
    Temporary text display time in seconds (only used for temporary text)
    """
    row: int
    """
    Display row position (0-255)
    """
    column: int
    """
    Display column position (0-255)
    """
    text_length: int
    """
    Length of the display string in bytes
    """
    display_string: bytes
    """
    Text string to be displayed
    """

    MIN_DATA_LEN: int = 6
    """
    Minimum data length for osdp_TEXT payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.reader_number < 0 or self.reader_number > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid reader_number: {self.reader_number}")
        if self.text_command < 1 or self.text_command > 2:
            raise PayloadValidationError(f"Invalid text_command: {self.text_command}")
        if self.temp_text_time < 0 or self.temp_text_time > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid temp_text_time: {self.temp_text_time}")
        if self.row < 0 or self.row > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid row: {self.row}")
        if self.column < 0 or self.column > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid column: {self.column}")
        if self.text_length < 0 or self.text_length > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid text_length: {self.text_length}")
        if len(self.display_string) != self.text_length:
            raise PayloadValidationError(
                f"text_length ({self.text_length}) does not match display_string length ({len(self.display_string)})"
            )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for TEXT payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "reader_number": {"name": "Reader"},
            "text_command": {"name": "Command"},
        }

        if not format_short:
            fields = {
                **fields,
                "temp_text_time": {"name": "Temp Text Time"},
                "row": {"name": "Row"},
                "column": {"name": "Column"},
                "text_length": {"name": "Text Length"},
                "display_string": {
                    "name": "Text",
                    "transform": lambda v: v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v),
                },
            }

        return fields

    def to_bytes(self) -> bytes:
        data = bytearray(
            [
                self.reader_number,
                self.text_command,
                self.temp_text_time,
                self.row,
                self.column,
                self.text_length,
            ]
        )
        data.extend(self.display_string)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpTextPayload":
        if len(ba) < OsdpTextPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_TEXT payload too short")

        text_length = ba[5]
        if len(ba) != OsdpTextPayload.MIN_DATA_LEN + text_length:
            raise PayloadValidationError("osdp_TEXT payload length mismatch")

        return OsdpTextPayload(
            tag=CommandTags.TEXT,
            reader_number=ba[0],
            text_command=ba[1],
            temp_text_time=ba[2],
            row=ba[3],
            column=ba[4],
            text_length=ba[5],
            display_string=bytes(ba[6 : 6 + text_length]),
        )


@dataclass
class OsdpComsetPayload(OsdpBasePayload):
    """
    osdp_COMSET payload.

    Byte structure (5 bytes):
    [0] address - New device address
    [1] baud_rate_lsb - Baud rate byte 0 (little-endian)
    [2] baud_rate_b1 - Baud rate byte 1
    [3] baud_rate_b2 - Baud rate byte 2
    [4] baud_rate_msb - Baud rate byte 3 (little-endian)
    """

    address: int
    """
    New device address to set (0-127)
    """
    baud_rate: bytes
    """
    New baud rate as 4-byte little-endian value
    """

    DATA_LEN: int = 5
    """
    Expected data length for osdp_COMSET payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.address < 0 or self.address > 127:
            raise PayloadValidationError(f"Invalid address: {self.address}")
        if len(self.baud_rate) != 4:
            raise PayloadValidationError(f"baud_rate must be 4 bytes, got {len(self.baud_rate)}")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for COMSET payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "address": {"name": "Address"},
            "_baud": {"name": "Baud", "compute": lambda p: int.from_bytes(p.baud_rate, byteorder="little")},
        }

        if not format_short:
            fields = {
                **fields,
                "baud_rate": {"name": "Baud Rate", "transform": "hex_bytes"},
            }

        return fields

    def to_bytes(self) -> bytes:
        data = bytearray([self.address])
        data.extend(self.baud_rate)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpComsetPayload":
        if len(ba) != OsdpComsetPayload.DATA_LEN:
            raise PayloadValidationError("osdp_COMSET payload bad length")

        return OsdpComsetPayload(
            tag=CommandTags.COMSET,
            address=ba[0],
            baud_rate=bytes(ba[1:5]),
        )


@dataclass
class OsdpBioreadPayload(OsdpBasePayload):
    """
    osdp_BIOREAD payload.

    Byte structure (4 bytes):
    [0] reader_number - Reader number
    [1] bio_type - Biometric type code
    [2] bio_format - Biometric format code
    [3] bio_quality - Biometric quality code
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """

    bio_type: BioTypeCodes
    """
    Biometric type code (0=default, 1=right_thumb, etc.)
    """

    bio_format: BioFormatCodes
    """
    Biometric format code (0=default)
    """

    bio_quality: BioQualityCodes
    """
    Biometric quality code (0=default)
    """

    DATA_LEN: int = 4
    """
    Expected data length for osdp_BIOREAD payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.reader_number < 0 or self.reader_number > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid reader_number: {self.reader_number}")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for BIOREAD payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "reader_number": {"name": "Reader"},
            "bio_type": {"name": "Bio Type", "transform": "enum"},
            "bio_format": {"name": "Bio Format", "transform": "enum"},
        }

        if not format_short:
            fields = {
                **fields,
                "bio_quality": {"name": "Bio Quality", "transform": "enum"},
            }

        return fields

    def to_bytes(self) -> bytes:
        return bytes([self.reader_number, self.bio_type, self.bio_format, self.bio_quality])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpBioreadPayload":
        if len(ba) != OsdpBioreadPayload.DATA_LEN:
            raise PayloadValidationError("osdp_BIOREAD payload bad length")

        return OsdpBioreadPayload(
            tag=CommandTags.BIOREAD,
            reader_number=ba[0],
            bio_type=BioTypeCodes(ba[1]),
            bio_format=BioFormatCodes(ba[2]),
            bio_quality=BioQualityCodes(ba[3]),
        )


@dataclass
class OsdpBiomatchPayload(OsdpBasePayload):
    """
    osdp_BIOMATCH payload.

    Byte structure (6 + bio_data_length bytes):
    [0] reader_number - Reader number
    [1] bio_type - Biometric type code
    [2] bio_format - Biometric format code
    [3] bio_quality - Biometric quality code
    [4] bio_length_lsb - Bio data length LSB
    [5] bio_length_msb - Bio data length MSB
    [6...6+bio_length-1] bio_data - Biometric template data
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """

    bio_type: BioTypeCodes
    """
    Biometric type code (0=default, 1=right_thumb, etc.)
    """

    bio_format: BioFormatCodes
    """
    Biometric format code (0=default)
    """

    bio_quality: BioQualityCodes
    """
    Biometric quality code (0=default)
    """

    bio_data: bytes
    """
    Biometric template data
    """

    MIN_DATA_LEN: int = 6
    """
    Minimum data length for osdp_BIOMATCH payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.reader_number < 0 or self.reader_number > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid reader_number: {self.reader_number}")
        if len(self.bio_data) > MAX_16_BIT:
            raise PayloadValidationError(f"bio_data length ({len(self.bio_data)}) exceeds maximum of 65535")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for BIOMATCH payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "reader_number": {"name": "Reader"},
            "bio_type": {"name": "Bio Type", "transform": "enum"},
            "bio_format": {"name": "Bio Format", "transform": "enum"},
            "_bio_data_len": {"name": "Bio Data Len", "compute": lambda p: len(p.bio_data)},
        }

        if not format_short:
            fields = {
                **fields,
                "bio_quality": {"name": "Bio Quality", "transform": "enum"},
                "bio_data": {"name": "Bio Data", "transform": "hex_bytes"},
            }

        return fields

    def to_bytes(self) -> bytes:
        bio_length = len(self.bio_data)
        bio_length_lsb = bio_length & 0xFF
        bio_length_msb = (bio_length >> 8) & 0xFF
        data = bytearray(
            [
                self.reader_number,
                self.bio_type,
                self.bio_format,
                self.bio_quality,
                bio_length_lsb,
                bio_length_msb,
            ]
        )
        data.extend(self.bio_data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpBiomatchPayload":
        if len(ba) < OsdpBiomatchPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_BIOMATCH payload too short")

        bio_length = ba[4] | (ba[5] << 8)
        if len(ba) != OsdpBiomatchPayload.MIN_DATA_LEN + bio_length:
            raise PayloadValidationError("osdp_BIOMATCH payload length mismatch")

        return OsdpBiomatchPayload(
            tag=CommandTags.BIOMATCH,
            reader_number=ba[0],
            bio_type=BioTypeCodes(ba[1]),
            bio_format=BioFormatCodes(ba[2]),
            bio_quality=BioQualityCodes(ba[3]),
            bio_data=bytes(ba[6 : 6 + bio_length]),
        )


@dataclass
class OsdpMfgPayload(OsdpBasePayload):
    """
    osdp_MFG payload.

    Byte structure (3 + data_length bytes):
    [0] vendor_code_0 - Vendor code byte 0
    [1] vendor_code_1 - Vendor code byte 1
    [2] vendor_code_2 - Vendor code byte 2
    [3...3+data_length-1] data - Manufacturer-specific data
    """

    vendor_code: bytes
    """
    3-byte vendor identification code
    """

    data: bytes
    """
    Manufacturer-specific data payload
    """

    MIN_DATA_LEN: int = MANUFACTURING_COMMAND_MINIMUM_DATA_LENGTH
    """
    Minimum data length for osdp_MFG payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if len(self.vendor_code) != 3:
            raise PayloadValidationError(f"vendor_code must be 3 bytes, got {len(self.vendor_code)}")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for MFG payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "data": {"name": "Data", "transform": "hex_bytes"},
        }

        if not format_short:
            fields = {
                **fields,
                "vendor_code": {"name": "Vendor Code", "transform": "hex_bytes"},
            }

        return fields

    def to_bytes(self) -> bytes:
        data = bytearray(self.vendor_code)
        data.extend(self.data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpMfgPayload":
        if len(ba) < OsdpMfgPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_MFG payload too short")

        return OsdpMfgPayload(
            tag=CommandTags.MFG,
            vendor_code=bytes(ba[0:3]),
            data=bytes(ba[3:]),
        )


@dataclass
class OsdpMfgMobilePayload(OsdpBasePayload):
    """
    OSDP MFG Mobile Set/Get Command data.

    Byte structure for the data portion of the OSDP MFG Mobile Set Command.
    [0] features_byte - Features byte
    Bit 0: Key rolling
    Bit 1: MyPass credentials
    Bit 2: BLE credentials
    Bit 3-7: Reserved
    [1] keyset_byte - Keyset byte
    Bit 0: Keyset 1
    Bit 1: Keyset 2
    Bit 2-7: Reserved
    [2] metadata_byte - Metadata byte
    [3] metadata_byte - Metadata byte
    [4] metadata_byte - Metadata byte
    [5] metadata_byte - Metadata byte
    """

    vendor_code: bytes
    """Vendor code"""
    mfg_code: int = ManufacturingTags.MOBILE
    """MFG code"""
    wavelynx_format: int = ManufacturingTags.WL_FORMAT
    """WaveLynx format"""
    length: int = 0
    """Length"""
    features: int = 0
    """Features"""
    keysets: int = 0
    """Keysets"""
    key_rolling: bool = False
    """Key rolling"""
    mypass_cred: bool = False
    """MyPass credentials"""
    ble_cred: bool = False
    """BLE credentials"""
    keyset_one: bool = True
    """Keyset 1"""
    keyset_two: bool = False
    """Keyset 2"""
    metadata: bytes = bytes([0xFF, 0xFF, 0xFF, 0xFF])
    """Metadata"""

    TITLE: ClassVar[str] = "OSDP MFG Mobile Settings"

    def __post_init__(self):
        """Validate field combinations."""
        if not self.keyset_one:
            raise PayloadValidationError(
                "Invalid keyset combination. Only 0x01 (keyset 1 active only) or 0x03 (keysets 1 and 2 active) are valid combinations.\n"
            )

    def to_bytes(self) -> bytes:
        """Serialize the payload to a byte array."""
        if self.length == 0:
            # Get command
            return self.vendor_code + bytes(
                [
                    ManufacturingTags.WL_FORMAT,
                    ManufacturingTags.MOBILE,
                    0x00,
                ]
            )
        else:
            # Set command
            features_byte = (
                ManufacturingTags.FEATURES_RESERVED_MASK
                | ((self.key_rolling & 1) << ManufacturingTags.KEY_ROLLING_BIT_INDEX)
                | ((self.mypass_cred & 1) << ManufacturingTags.MYPASS_CRED_BIT_INDEX)
                | ((self.ble_cred & 1) << ManufacturingTags.BLE_CRED_BIT_INDEX)
            )
        keysets_byte = (
            ManufacturingTags.KEYSETS_RESERVED_MASK
            | ((self.keyset_one & 1) << ManufacturingTags.KEYSET_ONE_BIT_INDEX)
            | ((self.keyset_two & 1) << ManufacturingTags.KEYSET_TWO_BIT_INDEX)
        )
        return self.vendor_code + bytes(
            [
                ManufacturingTags.WL_FORMAT,
                ManufacturingTags.MOBILE,
                ManufacturingTags.MOBILE_COMMAND_LENGTH,
                features_byte,
                keysets_byte,
                ManufacturingTags.METADATA_BYTE,
                ManufacturingTags.METADATA_BYTE,
                ManufacturingTags.METADATA_BYTE,
                ManufacturingTags.METADATA_BYTE,
            ]
        )

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpMfgMobilePayload":
        """
        Deserialize the payload from its byte form.
        """
        return cls(
            tag=CommandTags.MFG,
            vendor_code=bytes(ba[0:3]),
            wavelynx_format=ba[3],
            mfg_code=ba[4],
            length=ba[5],
            features=ba[6],
            keysets=ba[7],
            metadata=bytes(ba[8:12]),
        )

    @classmethod
    def _get_format_fields(cls, format_short: bool = False) -> dict[str, Any]:
        """Return field configuration for display formatting."""
        fields = {
            "vendor_code": {"name": "Vendor", "transform": "hex_bytes"},
        }
        if not format_short:
            fields = {
                "vendor_code": {"name": "Vendor Code", "transform": "hex_bytes"},
                "wavelynx_format": {"name": "WaveLynx Format", "transform": "hex", "width": 2},
                "mfg_code": {"name": "MFG Code", "transform": "hex", "width": 2},
                "length": {"name": "Length", "transform": "hex", "width": 2},
                "features": {"name": "Features", "transform": "hex", "width": 2},
                "keysets": {"name": "Keysets", "transform": "hex", "width": 2},
                "metadata": {"name": "Metadata", "transform": "hex_bytes"},
            }
        return fields


@dataclass
class OsdpAcurxsizePayload(OsdpBasePayload):
    """
    osdp_ACURXSIZE payload.

    Byte structure (2 bytes):
    [0] acurx_bufsize_lsb - Buffer size LSB
    [1] acurx_bufsize_msb - Buffer size MSB
    """

    acurx_bufsize: int
    """
    ACU receive buffer size in bytes (0-65535)
    """

    DATA_LEN: int = 2
    """
    Expected data length for osdp_ACURXSIZE payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.acurx_bufsize < 0 or self.acurx_bufsize > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid acurx_bufsize: {self.acurx_bufsize}")

    def to_bytes(self) -> bytes:
        acurx_bufsize_lsb = self.acurx_bufsize & 0xFF
        acurx_bufsize_msb = (self.acurx_bufsize >> 8) & 0xFF
        return bytes([acurx_bufsize_lsb, acurx_bufsize_msb])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpAcurxsizePayload":
        if len(ba) != OsdpAcurxsizePayload.DATA_LEN:
            raise PayloadValidationError("osdp_ACURXSIZE payload bad length")

        acurx_bufsize = ba[0] | (ba[1] << 8)
        return OsdpAcurxsizePayload(tag=CommandTags.ACURXSIZE, acurx_bufsize=acurx_bufsize)

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for ACURXSIZE payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "acurx_bufsize": {"name": "Buffer Size"},
        }
        return fields


@dataclass
class OsdpKeepactivePayload(OsdpBasePayload):
    """
    osdp_KEEPACTIVE payload.

    Byte structure (2 bytes):
    [0] kp_act_time_lsb - Keep active time LSB (seconds)
    [1] kp_act_time_msb - Keep active time MSB (seconds)
    """

    kp_act_time: int
    """
    Keep active time in seconds (0-65535)
    """

    DATA_LEN: int = 2
    """
    Expected data length for osdp_KEEPACTIVE payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.kp_act_time < 0 or self.kp_act_time > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid kp_act_time: {self.kp_act_time}")

    def to_bytes(self) -> bytes:
        kp_act_time_lsb = self.kp_act_time & 0xFF
        kp_act_time_msb = (self.kp_act_time >> 8) & 0xFF
        return bytes([kp_act_time_lsb, kp_act_time_msb])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpKeepactivePayload":
        if len(ba) != OsdpKeepactivePayload.DATA_LEN:
            raise PayloadValidationError("osdp_KEEPACTIVE payload bad length")

        kp_act_time = ba[0] | (ba[1] << 8)
        return OsdpKeepactivePayload(tag=CommandTags.KEEPACTIVE, kp_act_time=kp_act_time)

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for KEEPACTIVE payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "kp_act_time": {"name": "Keep Active Time"},
        }
        return fields


@dataclass
class OsdpAbortPayload(OsdpBasePayload):
    """
    osdp_ABORT payload.

    Byte structure: Empty payload (0 bytes)
    """

    def to_bytes(self) -> bytes:
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpAbortPayload":
        _ = ba  # unused but required parameter
        return OsdpAbortPayload(tag=CommandTags.ABORT)


@dataclass
class OsdpPivdataPayload(OsdpBasePayload):
    """
    osdp_PIVDATA payload.

    Byte structure (5 bytes):
    [0] piv_object_id_0 - PIV object ID byte 0
    [1] piv_object_id_1 - PIV object ID byte 1
    [2] piv_object_id_2 - PIV object ID byte 2
    [3] piv_element_id - PIV element ID
    [4] data_offset - Data offset within element
    """

    piv_object_id: bytes
    """
    3-byte PIV object identifier
    """
    piv_element_id: int
    """
    PIV element identifier (0-255)
    """
    data_offset: int
    """
    Data offset within the PIV element (0-255)
    """

    DATA_LEN: int = 5
    """
    Expected data length for osdp_PIVDATA payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if len(self.piv_object_id) != 3:
            raise PayloadValidationError(f"piv_object_id must be 3 bytes, got {len(self.piv_object_id)}")
        if self.piv_element_id < 0 or self.piv_element_id > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid piv_element_id: {self.piv_element_id}")
        if self.data_offset < 0 or self.data_offset > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid data_offset: {self.data_offset}")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for PIVDATA payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "piv_object_id": {"name": "Object ID", "transform": "hex_bytes"},
            "piv_element_id": {"name": "Element ID"},
        }

        if not format_short:
            fields = {
                **fields,
                "data_offset": {"name": "Data Offset"},
            }

        return fields

    def to_bytes(self) -> bytes:
        data = bytearray(self.piv_object_id)
        data.extend([self.piv_element_id, self.data_offset])
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpPivdataPayload":
        if len(ba) != OsdpPivdataPayload.DATA_LEN:
            raise PayloadValidationError("osdp_PIVDATA payload bad length")

        return OsdpPivdataPayload(
            tag=CommandTags.PIVDATA,
            piv_object_id=bytes(ba[0:3]),
            piv_element_id=ba[3],
            data_offset=ba[4],
        )


@dataclass
class OsdpGenauthPayload(OsdpBasePayload):
    """
    osdp_GENAUTH payload.

    Byte structure (9 + challenge_length bytes):
    [0] total_lsb - Total challenge length LSB
    [1] total_msb - Total challenge length MSB
    [2] offset_lsb - Challenge offset LSB
    [3] offset_msb - Challenge offset MSB
    [4] data_len_lsb - This message data length LSB
    [5] data_len_msb - This message data length MSB
    [6] algorithm_lsb - Algorithm ID LSB
    [7] algorithm_msb - Algorithm ID MSB
    [8] key - Key identifier
    [9...9+challenge_length-1] challenge - Challenge data
    """

    total: int
    """
    Total challenge length in bytes (0-65535)
    """
    offset: int
    """
    Offset within the challenge data (0-65535)
    """
    data_len: int
    """
    Length of challenge data in this message (0-65535)
    """
    algorithm: int
    """
    Authentication algorithm identifier (0-65535)
    """
    key: int
    """
    Key identifier for authentication (0-255)
    """
    challenge: bytes
    """
    Challenge data for authentication
    """

    MIN_DATA_LEN: int = 10
    """
    Minimum data length for osdp_GENAUTH payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.total < 0 or self.total > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid total: {self.total}")
        if self.offset < 0 or self.offset > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid offset: {self.offset}")
        if self.data_len < 0 or self.data_len > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid data_len: {self.data_len}")
        if self.algorithm < 0 or self.algorithm > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid algorithm: {self.algorithm}")
        if self.key < 0 or self.key > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid key: {self.key}")
        if len(self.challenge) + 6 != self.data_len:
            raise PayloadValidationError(f"data_len ({self.data_len}) does not match challenge length + 6 ({len(self.challenge) + 6})")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for GENAUTH payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "algorithm": {"name": "Algorithm"},
            "key": {"name": "Key"},
            "data_len": {"name": "Data Len"},
        }

        if not format_short:
            fields = {
                **fields,
                "total": {"name": "Total"},
                "offset": {"name": "Offset"},
                "challenge": {"name": "Challenge", "transform": "hex_bytes"},
            }

        return fields

    def to_bytes(self) -> bytes:
        total_lsb = self.total & 0xFF
        total_msb = (self.total >> 8) & 0xFF
        offset_lsb = self.offset & 0xFF
        offset_msb = (self.offset >> 8) & 0xFF
        data_len_lsb = self.data_len & 0xFF
        data_len_msb = (self.data_len >> 8) & 0xFF
        algorithm_lsb = self.algorithm & 0xFF
        algorithm_msb = (self.algorithm >> 8) & 0xFF
        data = bytearray(
            [
                total_lsb,
                total_msb,
                offset_lsb,
                offset_msb,
                data_len_lsb,
                data_len_msb,
                algorithm_lsb,
                algorithm_msb,
                self.key,
            ]
        )
        data.extend(self.challenge)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpGenauthPayload":
        if len(ba) < OsdpGenauthPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_GENAUTH payload too short")

        total = ba[0] | (ba[1] << 8)
        offset = ba[2] | (ba[3] << 8)
        data_len = ba[4] | (ba[5] << 8)
        algorithm = ba[6] | (ba[7] << 8)
        return OsdpGenauthPayload(
            tag=CommandTags.GENAUTH,
            total=total,
            offset=offset,
            data_len=data_len,
            algorithm=algorithm,
            key=ba[8],
            challenge=bytes(ba[9:]),
        )


@dataclass
class OsdpCrauthPayload(OsdpBasePayload):
    """
    osdp_CRAUTH payload.

    Byte structure (9 + challenge_length bytes):
    [0] total_lsb - Total challenge length LSB
    [1] total_msb - Total challenge length MSB
    [2] offset_lsb - Challenge offset LSB
    [3] offset_msb - Challenge offset MSB
    [4] data_len_lsb - This message data length LSB
    [5] data_len_msb - This message data length MSB
    [6] algorithm_lsb - Algorithm ID LSB
    [7] algorithm_msb - Algorithm ID MSB
    [8] key - Key identifier
    [9...9+challenge_length-1] challenge - Challenge data
    """

    total: int
    """
    Total challenge length in bytes (0-65535)
    """
    offset: int
    """
    Offset within the challenge data (0-65535)
    """
    data_len: int
    """
    Length of challenge data in this message (0-65535)
    """
    algorithm: int
    """
    Authentication algorithm identifier (0-65535)
    """
    key: int
    """
    Key identifier for authentication (0-255)
    """
    challenge: bytes
    """
    Challenge data for authentication
    """

    MIN_DATA_LEN: int = 10
    """
    Minimum data length for osdp_CRAUTH payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.total < 0 or self.total > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid total: {self.total}")
        if self.offset < 0 or self.offset > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid offset: {self.offset}")
        if self.data_len < 0 or self.data_len > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid data_len: {self.data_len}")
        if self.algorithm < 0 or self.algorithm > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid algorithm: {self.algorithm}")
        if self.key < 0 or self.key > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid key: {self.key}")
        if len(self.challenge) + 6 != self.data_len:
            raise PayloadValidationError(f"data_len ({self.data_len}) does not match challenge length + 6 ({len(self.challenge) + 6})")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for CRAUTH payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "algorithm": {"name": "Algorithm"},
            "key": {"name": "Key"},
            "data_len": {"name": "Data Len"},
        }

        if not format_short:
            fields = {
                **fields,
                "total": {"name": "Total"},
                "offset": {"name": "Offset"},
                "challenge": {"name": "Challenge", "transform": "hex_bytes"},
            }

        return fields

    def to_bytes(self) -> bytes:
        total_lsb = self.total & 0xFF
        total_msb = (self.total >> 8) & 0xFF
        offset_lsb = self.offset & 0xFF
        offset_msb = (self.offset >> 8) & 0xFF
        data_len_lsb = self.data_len & 0xFF
        data_len_msb = (self.data_len >> 8) & 0xFF
        algorithm_lsb = self.algorithm & 0xFF
        algorithm_msb = (self.algorithm >> 8) & 0xFF
        data = bytearray(
            [
                total_lsb,
                total_msb,
                offset_lsb,
                offset_msb,
                data_len_lsb,
                data_len_msb,
                algorithm_lsb,
                algorithm_msb,
                self.key,
            ]
        )
        data.extend(self.challenge)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpCrauthPayload":
        if len(ba) < OsdpCrauthPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_CRAUTH payload too short")

        total = ba[0] | (ba[1] << 8)
        offset = ba[2] | (ba[3] << 8)
        data_len = ba[4] | (ba[5] << 8)
        algorithm = ba[6] | (ba[7] << 8)
        return OsdpCrauthPayload(
            tag=CommandTags.CRAUTH,
            total=total,
            offset=offset,
            data_len=data_len,
            algorithm=algorithm,
            key=ba[8],
            challenge=bytes(ba[9:]),
        )


@dataclass
class OsdpFiletransferPayload(OsdpBasePayload):
    """
    osdp_FILETRANSFER payload.

    Byte structure (11 + ft_fragment_size bytes):
    [0] ft_type - File transfer type
    [1] ft_size_total_0 - Total file size byte 0 (little-endian)
    [2] ft_size_total_1 - Total file size byte 1
    [3] ft_size_total_2 - Total file size byte 2
    [4] ft_size_total_3 - Total file size byte 3 (little-endian)
    [5] ft_offset_0 - File offset byte 0 (little-endian)
    [6] ft_offset_1 - File offset byte 1
    [7] ft_offset_2 - File offset byte 2
    [8] ft_offset_3 - File offset byte 3 (little-endian)
    [9] ft_fragment_size_lsb - Fragment size LSB
    [10] ft_fragment_size_msb - Fragment size MSB
    [11...11+ft_fragment_size-1] ft_data - File fragment data
    """

    ft_type: int
    """
    File transfer type (1=opaque file)
    """
    ft_size_total: int
    """
    Total file size in bytes (0-4294967295)
    """
    ft_offset: int
    """
    File offset in bytes (0-4294967295)
    """
    ft_fragment_size: int
    """
    Size of this file fragment in bytes (0-65535)
    """
    ft_data: bytes
    """
    File fragment data
    """

    MIN_DATA_LEN: int = 11
    """
    Minimum data length for osdp_FILETRANSFER payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.ft_type < 0 or self.ft_type > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid ft_type: {self.ft_type}")
        if self.ft_size_total < 0 or self.ft_size_total > MAX_32_BIT:
            raise PayloadValidationError(f"Invalid ft_size_total: {self.ft_size_total}")
        if self.ft_offset < 0 or self.ft_offset > MAX_32_BIT:
            raise PayloadValidationError(f"Invalid ft_offset: {self.ft_offset}")
        if self.ft_fragment_size < 0 or self.ft_fragment_size > MAX_16_BIT:
            raise PayloadValidationError(f"Invalid ft_fragment_size: {self.ft_fragment_size}")
        if len(self.ft_data) != self.ft_fragment_size:
            raise PayloadValidationError(f"ft_fragment_size ({self.ft_fragment_size}) does not match ft_data length ({len(self.ft_data)})")

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for FILETRANSFER payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "tag": {"name": "Message ID", "transform": "hex", "width": 2},
            "ft_type": {"name": "Type"},
            "ft_fragment_size": {"name": "Fragment Size"},
        }

        if not format_short:
            fields = {
                **fields,
                "ft_size_total": {"name": "Total Size"},
                "ft_offset": {"name": "Offset"},
            }

        return fields

    def to_bytes(self) -> bytes:
        ft_size_total_bytes = self.ft_size_total.to_bytes(4, byteorder="little")
        ft_offset_bytes = self.ft_offset.to_bytes(4, byteorder="little")
        ft_fragment_size_lsb = self.ft_fragment_size & MAX_8_BIT
        ft_fragment_size_msb = (self.ft_fragment_size >> 8) & MAX_8_BIT
        data = bytearray([self.ft_type])
        data.extend(ft_size_total_bytes)
        data.extend(ft_offset_bytes)
        data.extend([ft_fragment_size_lsb, ft_fragment_size_msb])
        data.extend(self.ft_data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpFiletransferPayload":
        if len(ba) < OsdpFiletransferPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_FILETRANSFER payload too short")

        fragment_size = ba[9] | (ba[10] << 8)
        if len(ba) != (cls.MIN_DATA_LEN + fragment_size):
            raise PayloadValidationError("osdp_FILETRANSFER payload length mismatch")

        ft_size_total = int.from_bytes(ba[1:5], byteorder="little")
        ft_offset = int.from_bytes(ba[5:9], byteorder="little")
        return OsdpFiletransferPayload(
            tag=CommandTags.FILETRANSFER,
            ft_type=ba[0],
            ft_size_total=ft_size_total,
            ft_offset=ft_offset,
            ft_fragment_size=fragment_size,
            ft_data=bytes(ba[cls.MIN_DATA_LEN :]),
        )


@dataclass
class OsdpXwrPayload(OsdpBasePayload):
    """
    osdp_XWR payload.

    Byte structure (2 + xwr_pdata_length bytes):
    [0] xrw_mode - Extended read/write mode
    [1] xwr_pcmnd - Extended write protocol command
    [2...2+xwr_pdata_length-1] xwr_pdata - Extended write protocol data
    """

    xrw_mode: int
    """
    Extended read/write mode (0-255)
    """
    xwr_pcmnd: int
    """
    Extended write protocol command (0-255)
    """
    xwr_pdata: bytes
    """
    Extended write protocol data
    """

    MIN_DATA_LEN: int = 2
    """
    Minimum data length for osdp_XWR payload in bytes
    """

    def __post_init__(self):
        """Validate field values after initialization."""
        if self.xrw_mode < 0 or self.xrw_mode > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid xrw_mode: {self.xrw_mode}")
        if self.xwr_pcmnd < 0 or self.xwr_pcmnd > MAX_8_BIT:
            raise PayloadValidationError(f"Invalid xwr_pcmnd: {self.xwr_pcmnd}")

    def to_bytes(self) -> bytes:
        data = bytearray([self.xrw_mode, self.xwr_pcmnd])
        data.extend(self.xwr_pdata)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpXwrPayload":
        if len(ba) < OsdpXwrPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_XWR payload too short")

        return OsdpXwrPayload(
            tag=CommandTags.XWR,
            xrw_mode=ba[0],
            xwr_pcmnd=ba[1],
            xwr_pdata=bytes(ba[2:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for XWR payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "xrw_mode": {"name": "Mode"},
            "xwr_pcmnd": {"name": "Command"},
            "_pdata_len": {"name": "Data Len", "compute": lambda p: len(p.xwr_pdata)},
        }
        return fields
