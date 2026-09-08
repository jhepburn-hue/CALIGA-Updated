import ctypes
from dataclasses import dataclass
from typing import Any, ClassVar

from .constants import (
    MAX_8_BIT,
    MAX_16_BIT,
    BioQualityCodes,
    BioTypeCodes,
    FileTransferStatusDetails,
    FunctionCodes,
    NAKCodes,
    PowerStatus,
    ResponseTags,
    TamperStatus,
)
from .exceptions import PayloadValidationError
from .payload import OsdpBasePayload
from .utils import format_bytes_hex_reversed, format_hex


@dataclass
class OsdpAckPayload(OsdpBasePayload):
    """
    osdp_ACK payload.

    Byte structure: Empty payload (0 bytes)
    """

    # start_of_message: int

    TITLE: ClassVar[str] = "ACK Response"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpAckPayload":
        _ = ba  # unused but required parameter

        return OsdpAckPayload(tag=ResponseTags.ACK)

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        return {"tag": {"name": "Message ID", "transform": "hex", "width": 2}}


@dataclass
class OsdpNakPayload(OsdpBasePayload):
    """
    osdp_NAK payload.

    Byte structure (1 + data_length bytes):
    [0] error_code - NAK error code
    [1...1+data_length-1] data - Additional error data (optional)
    """

    error_code: NAKCodes
    """
    NAK error code indicating the type of error
    """
    data: bytes = b""
    """
    Additional NAK error data (optional)
    """

    MIN_DATA_LEN: int = 1
    """
    Minimum data length for osdp_NAK payload in bytes
    """

    TITLE: ClassVar[str] = "NAK Response"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        data = bytearray([self.error_code])
        data.extend(self.data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpNakPayload":
        if len(ba) < OsdpNakPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_NAK payload too short")

        return OsdpNakPayload(tag=ResponseTags.NAK, error_code=NAKCodes(ba[0]), data=bytes(ba[1:]))

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {"error_code": {"name": "Error", "transform": "enum"}}
        if not format_short:
            fields = {
                **fields,
                "tag": {"name": "Message ID", "transform": "hex", "width": 2},
                "error_code": {"name": "Error Code", "transform": "enum"},
            }
        return fields


@dataclass
class OsdpPdidPayload(OsdpBasePayload):
    """
    osdp_PDID payload.

    Byte structure (12 bytes):
    [0] vendor_code_0 - Vendor code byte 0
    [1] vendor_code_1 - Vendor code byte 1
    [2] vendor_code_2 - Vendor code byte 2
    [3] model_number - Model number
    [4] version - Version number
    [5] serial_number_0 - Serial number byte 0
    [6] serial_number_1 - Serial number byte 1
    [7] serial_number_2 - Serial number byte 2
    [8] serial_number_3 - Serial number byte 3
    [9] firmware_major - Firmware major version
    [10] firmware_minor - Firmware minor version
    [11] firmware_build - Firmware build number
    """

    vendor_code: bytes
    """
    3-byte vendor identification code
    """
    model_number: int
    """
    Device model number (0-255)
    """
    version: int
    """
    Device version number (0-255)
    """
    serial_number: bytes
    """
    4-byte device serial number
    """
    firmware_major: int
    """
    Firmware major version number (0-255)
    """
    firmware_minor: int
    """
    Firmware minor version number (0-255)
    """
    firmware_build: int
    """
    Firmware build number (0-255)
    """

    DATA_LEN: int = 12
    """
    Expected data length for osdp_PDID payload in bytes
    """

    TITLE: ClassVar[str] = "Device ID Report"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        data = bytearray(self.vendor_code)
        data.extend([self.model_number, self.version])
        data.extend(self.serial_number)
        data.extend([self.firmware_major, self.firmware_minor, self.firmware_build])
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpPdidPayload":
        """
        Returns an instance of the object.  The ba parameter provides the basis for populating
        all the data fields within the object.

        NOTE: This method and all others like it are called within the process_incoming_message method on the
        OsdpMessageHandler class.

        :param ba: Byte array that contains relevant information to the object regarding its identification components
        (EX, serial number, firmware version, model number, etc.).

        :return: Instance of OsdpPdidPayload with the values from the byte array parameter populating the fields.
        """

        if len(ba) != OsdpPdidPayload.DATA_LEN:
            raise PayloadValidationError("osdp_PDID payload bad length")

        return OsdpPdidPayload(
            tag=ResponseTags.PDID,
            vendor_code=bytes(ba[0:3]),
            model_number=ba[3],
            version=ba[4],
            serial_number=bytes(ba[5:9]),
            firmware_major=ba[9],
            firmware_minor=ba[10],
            firmware_build=ba[11],
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "vendor_code": {"name": "Vendor", "transform": "hex_bytes"},
            "model_number": {"name": "Model"},
            "serial_number": {"name": "Serial", "transform": format_bytes_hex_reversed},
        }
        if not format_short:
            fields = {
                **fields,
                "vendor_code": {"name": "Vendor Code", "transform": "hex_bytes"},
                "model_number": {"name": "Model Number"},
                "serial_number": {"name": "Serial Number", "transform": format_bytes_hex_reversed},
                "version": {"name": "Version"},
                "_firmware": {
                    "name": "Firmware Version",
                    "compute": lambda p: f"{p.firmware_major}.{p.firmware_minor}.{p.firmware_build}",
                },
            }
        return fields


@dataclass
class OsdpMFGExtendedReaderInfoPayload(OsdpBasePayload):
    """
    Extended reader information payload (MFG 0x9C).

    Supports both APEX (52-byte) and Ethos (44-byte) payload formats.
    Device type is auto-detected based on payload length.

    Key differences between formats:
    - APEX: supporting_firmware_version_maintenance is u16 (2 bytes)
    - APEX: bootloader_build is u16 (2 bytes)
    - APEX: includes ble_mac_address (6 bytes)
    - Ethos: supporting_firmware_version_maintenance is u8 (1 byte)
    - Ethos: bootloader_build is u8 (1 byte)
    - Ethos: no ble_mac_address field
    """

    # Header fields (6 bytes)
    vendor_code: bytes
    """
    Code of the vendor or carrier of the reader.
    """

    wavelynx_format: int
    """
    Internal value that points to ASCII value of being a "W" for WaveLynx.
    """

    mfg_code: int
    """
    Reflection of the WaveLynx manufacturing command for extended reader id.
    """

    length: int
    """
    Length of data section after header
      (38 for Ethos, 46 for APEX)
    """

    # Data fields
    serial_number: bytes
    """
    Device serial number.
    """

    extended_config_id: bytes
    """
    Configuration ID for the device's listed configuration settings.  Usually provided by SET.
    """

    technologies: int
    """
    LF/HF/Bluetooth.  Specific bits that signify whether the bits are enabled.
    Bit 0: LF
    Bit 1: HF
    Bit 2: Mobile or Bluetooth
    """

    firmware_major: int
    """
    Application major firmware version.
    """

    firmware_minor: int
    """
    Application minor firmware version.
    """

    firmware_maintenance: int
    """
    "Patch" application version.
    """

    firmware_build: int
    """
    Primarily internal consumption value for builds against a SEMver specific build.
    """

    supporting_firmware_version_major: int
    """
    Net app major firmware version.
    """

    supporting_firmware_version_minor: int
    """
    Net app minor firmware version.
    """

    supporting_firmware_version_maintenance: bytes
    """
    Net app "patch" or supporting firmware version.
      (u16 on APEX, u8 on Ethos)
    """

    bootloader_major: int
    """
    Bootloader major firmware version.
    """

    bootloader_minor: int
    """
    Bootloader minor firmware version.
    """

    bootloader_patch: bytes
    """
    Bootloader patch firmware version.
      (u16 on APEX, u8 on Ethos)
    """

    pcb_id: int
    """
    Board type of the device being used.  Determined directly from the hardware.  Mapping values:
    KEY_PAD_EXISTS (mask)            0x80
    PCB_ID_MASK                      0x1F
    PCB_MULLION_REV_2_1              0x03
    PCB_MULLION_REV_2_0              0x01
    PCB_SINGLE_GANG_REV_2_0          0x00
    PCB_REV_1                        0x1F
    PCB_MULLION_REV_2_2              0x05
    PCB_SINGLE_GANG_REV_2_2          0x02
    PCB_MULLION_REV_2_5              0x07
    PCB_SINGLE_GANG_REV_2_5          0x04
    PCB_MULLION_REV_2_6              0x09
    PCB_SINGLE_GANG_REV_2_6          0x08
    PCB_MULLION_REV_3_0              0x0B
    PCB_SINGLE_GANG_REV_3_0          0x0A
    PCB_MullionAPEX_REV_1            0x0C
    PCB_MullionKeypadAPEX_REV_1      0x0D
    PCB_SGAPEX_REV_1                 0x0E
    PCB_SGKeypadAPEX_REV_1           0x0F
    PCB_AX05_Rev_1                   0x10
    PCB_AX02_Rev_1                   0x11
    """

    product_type: int
    """
    Indicates the type of device.  IE: Ethos reader REV 3, or REV 4, etc.  Values:
    ETHOS_READER       1
    SW_READER          2
    IP_READER          3
    F2F_READER         4
    MCLP_READER        5
    ETHOS_15_READER    6
    LOCK_MODULE        7
    LOCK_HUB           8
    APEX_READER        9
    APEX_MODULE        A
    """

    control_line_state: int
    """
    Indicates whether the control lines are active.  Bit Values:
    Bit 0: Red Control line
    Bit 1: Green control line
    Bit 2: Buzzer control line
    Bit 3: tamper state
    """

    operational_mode: int
    """
    Indicates the communication mode that the device is set to.  Bit Values:
    Bit 0: Unknown (F2F/MCLP report this)
    Bit 1: Wiegand or OSDP Offline
    Bit 2: OSDP Online Plain Text
    Bit 3: OSDP Online Secure Channel
    """

    osdp_address: int
    """
    Address set for the OSDP console command.  On this platform, this will almost exclusively be a 0.
    """

    osdp_baud_rate: int
    """
    Indicates the device baud rate.
    """

    nfc_apps_enabled: int
    """
    Indicates which wallet applications are enabled on the reader.  Bit Values:
    Bit 0: None
    Bit 1: Apple Meridian
    Bit 2: MF2GO
    Bit 3: Both the Apple Meridian and MF2GO

    """

    ecp_format: int
    """
    Indicates how the terminal is configured to read data from the device.  Can be either a 1 or 2.  2 is the
    default value.
    """

    terminal_info_mode: int
    """
    Related to express mode.
    """

    terminal_type: int
    """
    Carries a static value of 2.
    """

    terminal_sub_type: int
    """
    Indicates the environmental setting of the device.  Values:
    0: University
    1: Corporate
    2: Hospitality
    3: Residential
    """

    tci_1: int
    """
    Reading of the first tci value Left -> Right.
    """

    tci_2: int
    """
    Reading of the second tci value Left -> Right.
    """

    tci_3: int
    """
    Reading of the third tci value Left -> Right.
    """

    ecp_bit_count: int
    """
    Number of bits of the wallet credential read from Meridian App (Apple Wallet).  This value is typically 40 bits.
    """

    ecp_app_options: int
    """
    ASK DAN.
    """

    post_errors: int
    """
    Errors detected by the reader after startup.  A value of 0 indicates no errors.
    """

    ble_mac_address: bytes | None = None
    """
    Mac address of the BLE chip that resides on the device (6 bytes).
    Only present on APEX devices.
    """

    # Constants
    APEX_LENGTH: ClassVar[int] = 52
    """Total payload length for APEX devices."""

    ETHOS_LENGTH: ClassVar[int] = 44
    """Total payload length for Ethos devices."""

    TITLE: ClassVar[str] = "OSDP MFG Extended Reader Information"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        data = bytearray(self.vendor_code)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpMFGExtendedReaderInfoPayload":
        """
        Returns an instance of the object.  The ba parameter provides the basis for populating
        all the data fields within the object.

        NOTE: This method and all others like it are called within the process_incoming_message method on the
        OsdpMessageHandler class.

        :param ba: Byte array that contains relevant information to the object regarding its identification components
        (EX, serial number, firmware version, model number, etc.).

        :return: Instance of OsdpMFGExtendedReaderInfoPayload with the values from the byte array parameter
        populating the fields.
        """
        payload_len = len(ba)

        if payload_len >= cls.APEX_LENGTH:
            return cls._parse_apex(ba)
        elif payload_len >= cls.ETHOS_LENGTH:
            return cls._parse_ethos(ba)
        else:
            raise PayloadValidationError("osdp_MFG Extended Reader Id payload length invalid")

    @classmethod
    def _parse_apex(cls, ba: bytearray) -> "OsdpMFGExtendedReaderInfoPayload":
        """
        Parse APEX format (52-byte payload).
        APEX uses u16 for supporting_firmware_version_maintenance and bootloader_build,
        and includes a 6-byte ble_mac_address field.
        """
        return cls(
            tag=ResponseTags.EXT_READER_ID,
            vendor_code=bytes(ba[0:3]),
            wavelynx_format=ba[3],
            mfg_code=ba[4],
            length=ba[5],
            serial_number=bytes(ba[6:14]),
            extended_config_id=bytes(ba[14:16]),
            technologies=ba[16],
            firmware_major=ba[17],
            firmware_minor=ba[18],
            firmware_maintenance=ba[19],
            firmware_build=ba[20],
            supporting_firmware_version_major=ba[21],
            supporting_firmware_version_minor=ba[22],
            supporting_firmware_version_maintenance=bytes(ba[23:25]),
            bootloader_major=ba[25],
            bootloader_minor=ba[26],
            bootloader_patch=bytes(ba[27:29]),
            pcb_id=ba[29],
            product_type=ba[30],
            control_line_state=ba[31],
            operational_mode=ba[32],
            osdp_address=ba[33],
            osdp_baud_rate=ba[34],
            nfc_apps_enabled=ba[35],
            ecp_format=ba[36],
            terminal_info_mode=ba[37],
            terminal_type=ba[38],
            terminal_sub_type=ba[39],
            tci_1=ba[40],
            tci_2=ba[41],
            tci_3=ba[42],
            ecp_bit_count=ba[43],
            ecp_app_options=ba[44],
            post_errors=ba[45],
            ble_mac_address=bytes(ba[46:52]),
        )

    @classmethod
    def _parse_ethos(cls, ba: bytearray) -> "OsdpMFGExtendedReaderInfoPayload":
        """
        Parse Ethos format (44-byte payload).
        Ethos uses u8 for supporting_firmware_version_maintenance and bootloader_build,
        and does not include a ble_mac_address field.
        """
        return cls(
            tag=ResponseTags.EXT_READER_ID,
            vendor_code=bytes(ba[0:3]),
            wavelynx_format=ba[3],
            mfg_code=ba[4],
            length=ba[5],
            serial_number=bytes(ba[6:14]),
            extended_config_id=bytes(ba[14:16]),
            technologies=ba[16],
            firmware_major=ba[17],
            firmware_minor=ba[18],
            firmware_maintenance=ba[19],
            firmware_build=ba[20],
            supporting_firmware_version_major=ba[21],
            supporting_firmware_version_minor=ba[22],
            supporting_firmware_version_maintenance=bytes([ba[23]]),
            bootloader_major=ba[24],
            bootloader_minor=ba[25],
            bootloader_patch=bytes([ba[26]]),
            pcb_id=ba[27],
            product_type=ba[28],
            control_line_state=ba[29],
            operational_mode=ba[30],
            osdp_address=ba[31],
            osdp_baud_rate=ba[32],
            nfc_apps_enabled=ba[33],
            ecp_format=ba[34],
            terminal_info_mode=ba[35],
            terminal_type=ba[36],
            terminal_sub_type=ba[37],
            tci_1=ba[38],
            tci_2=ba[39],
            tci_3=ba[40],
            ecp_bit_count=ba[41],
            ecp_app_options=ba[42],
            post_errors=ba[43],
            ble_mac_address=None,
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """Return field configuration for display formatting."""
        fields = {
            "vendor_code": {"name": "Vendor", "transform": "hex_bytes"},
            "serial_number": {"name": "Serial", "transform": "hex_bytes"},
        }
        if not format_short:
            fields = {
                "vendor_code": {"name": "Vendor Code", "transform": "hex_bytes"},
                "wavelynx_format": {"name": "WaveLynx Format", "transform": "hex", "width": 2},
                "mfg_code": {"name": "MFG Code", "transform": "hex", "width": 2},
                "length": {"name": "Length"},
                "serial_number": {"name": "Serial Number", "transform": "hex_bytes"},
                "extended_config_id": {"name": "Extended Config ID", "transform": "hex_bytes"},
                "technologies": {"name": "Technologies", "transform": "hex", "width": 2},
                "firmware_major": {"name": "Firmware Version Major"},
                "firmware_minor": {"name": "Firmware Version Minor"},
                "firmware_maintenance": {"name": "Firmware Version Maintenance"},
                "firmware_build": {"name": "Firmware Version Build"},
                "supporting_firmware_version_major": {"name": "Supporting Firmware Version Major"},
                "supporting_firmware_version_minor": {"name": "Supporting Firmware Version Minor"},
                "supporting_firmware_version_maintenance": {"name": "Supporting Firmware Version Maintenance", "transform": "hex_bytes"},
                "bootloader_major": {"name": "Bootloader Major Version"},
                "bootloader_minor": {"name": "Bootloader Minor Version"},
                "bootloader_patch": {"name": "Bootloader Patch Version", "transform": "hex_bytes"},
                "pcb_id": {"name": "PCB ID", "transform": "hex", "width": 2},
                "product_type": {"name": "Product Type", "transform": "hex", "width": 2},
                "control_line_state": {"name": "Control Line State", "transform": "hex", "width": 2},
                "operational_mode": {"name": "Operational Mode", "transform": "hex", "width": 2},
                "osdp_address": {"name": "OSDP Address"},
                "osdp_baud_rate": {"name": "OSDP Baud Rate"},
                "nfc_apps_enabled": {"name": "NFC Apps Enabled", "transform": "hex", "width": 2},
                "ecp_format": {"name": "ECP Format"},
                "terminal_info_mode": {"name": "Terminal Info Mode", "transform": "hex", "width": 2},
                "terminal_type": {"name": "Terminal Type"},
                "terminal_sub_type": {"name": "Terminal Sub Type"},
                "tci_1": {"name": "TCI 1", "transform": "hex", "width": 2},
                "tci_2": {"name": "TCI 2", "transform": "hex", "width": 2},
                "tci_3": {"name": "TCI 3", "transform": "hex", "width": 2},
                "ecp_bit_count": {"name": "ECP Bit Count"},
                "ecp_app_options": {"name": "ECP App Options", "transform": "hex", "width": 2},
                "post_errors": {"name": "POST Errors", "transform": "hex", "width": 2},
                "ble_mac_address": {"name": "BLE MAC Address", "transform": "hex_bytes"},
            }
        return fields


@dataclass
class OsdpMFGHostGetDeviceDescriptionPayload(OsdpBasePayload):
    """
    Data class that holds all the mapped data returned from the reader for displaying the
    device description information.  This data is returned from the osdp_MFG command for
    requesting device description (WaveLynx manufacturing code 0x98).
    This manufacturer command is specified in detail here:
    https://docs.google.com/spreadsheets/d/1Bu5aJCSQtlBPCqwGM1VsTnQ6vK9KELrS0LJ0RkVoO_4/edit?gid=30219331#gid=30219331
    """

    TITLE: ClassVar[str] = "MFG Device Description"
    """
    Title for this payload type.
    """

    vendor_code: bytes
    """
    Code of the vendor or carrier of the reader.
    """

    wavelynx_format: int
    """
    Internal value that points to ASCII value of being a "W" for WaveLynx.
    """

    mfg_code: int
    """
    Reflection of the WaveLynx manufacturing command for device description (0x98).
    """

    length: int
    """
    Number of bytes of the remainder of the message subtracting the values listed above.
    """

    pcb_id: int
    """
    Board type of the device being used.  Determined directly from the hardware.  Mapping values:
    PCB_Mullion APEX_REV_1: 0x0C
    PCB_Mullion Keypad APEX_REV_1: 0x0D
    PCB_SG APEX_REV_1: 0x0E
    PCB_SG Keypad APEX_REV_1: 0x0F
    PCB_AX 05_Rev_1: 0x0E
    PCB_AX 02_Rev_1: TBD by Product
    PCB_AX 01_Rev_1: TBD by Product
    """

    config_id: int
    """
    Customer Configuration ID. This value is casted from a u_int_16 to a u_int_8 by providing
    the least significant byte as the value.
    """

    pcb_revision: int
    """
    Printed Circuit Board Revision Number. This can be reported back as 1.
    """

    technologies: int
    """
    Technologies bitfield. Breakdowns of Bit Values:
    Bit 0: BLE Enabled
    Bit 1: BLE Credentials Enabled
    Bit 2: ASK Enabled
    Bit 3: FSK Enabled
    Bit 4: Unused bit
    Bit 5: HF Enabled
    Bit 6: BLE MyPass Enabled
    Bit 7: ECP_NFC Card Type Enabled
    """

    cap_touch: bytes
    """
    Captouch. This value can safely be returned as a 0 value universally (2 bytes).
    """

    firmware_major: int
    """
    Major Firmware Version Number.
    """

    firmware_minor: int
    """
    Minor Firmware Version Number.
    """

    firmware_maintenance: int
    """
    Build Firmware Version Number.
    """

    firmware_build: int
    """
    Candidate Firmware Version Number.
    """

    supporting_firmware_version_major: int
    """
    Major BLE Firmware Version from Netapp core.
    """

    supporting_firmware_version_minor: int
    """
    Minor BLE Firmware Version from Netapp core.
    """

    supporting_firmware_version_build: int
    """
    Build BLE Firmware Version from Netapp core.
    """

    special_features_index: int
    """
    Special Features Index. This can be reported back as 0.
    """

    DATA_LENGTH: int = 20
    """
    Expected data length for osdp_MFG Host Get Device Description payload in bytes.
    Based on: vendor_code(3) + wavelynx_format(1) + mfg_code(1) + length(1) +
    pcb_id(1) + config_id(1) + pcb_revision(1) + technologies(1) + cap_touch(2) +
    firmware_major(1) + firmware_minor(1) + firmware_maintenance(1) + firmware_build(1) +
    supporting_firmware_version_major(1) + supporting_firmware_version_minor(1) +
    supporting_firmware_version_build(1) + special_features_index(1) = 20 bytes
    """

    def to_bytes(self) -> bytes:
        data = bytearray(self.vendor_code)
        data.append(self.wavelynx_format)
        data.append(self.mfg_code)
        data.append(self.length)
        data.append(self.pcb_id)
        data.append(self.config_id)
        data.append(self.pcb_revision)
        data.append(self.technologies)
        data.extend(self.cap_touch)
        data.append(self.firmware_major)
        data.append(self.firmware_minor)
        data.append(self.firmware_maintenance)
        data.append(self.firmware_build)
        data.append(self.supporting_firmware_version_major)
        data.append(self.supporting_firmware_version_minor)
        data.append(self.supporting_firmware_version_build)
        data.append(self.special_features_index)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpMFGHostGetDeviceDescriptionPayload":
        """
        Returns an instance of the object.  The ba parameter provides the basis for populating
        all the data fields within the object.

        NOTE: This method and all others like it are called within the process_incoming_message method on the
        OsdpMessageHandler class.

        Byte structure (20 bytes):
        [0:3] vendor_code - 3-byte vendor code (5c 26 23 = Wavelynx)
        [3] wavelynx_format - WL format (57 = 'W')
        [4] mfg_code - Manufacturing code (98)
        [5] length - Length of remaining data (0e = 14)
        [6] pcb_id - PCB ID
        [7] config_id - Config ID
        [8] pcb_revision - PCB revision
        [9] technologies - Technologies
        [10:11] cap_touch - Cap touch (two bytes)
        [12] firmware_major - FW major version
        [13] firmware_minor - FW minor version
        [14] firmware_maintenance - FW build version
        [15] firmware_build - FW candidate version
        [16] supporting_firmware_version_major - BLE FW major
        [17] supporting_firmware_version_minor - BLE FW minor
        [18] supporting_firmware_version_build - BLE FW build
        [19] special_features_index - Special features index (unused byte)

        Note: Checksum bytes are excluded from payload

        :param ba: Byte array that contains relevant information to the object regarding its identification components
        (EX, serial number, firmware version, model number, etc.).

        :return: Instance of OsdpMFGHostGetDeviceDescriptionPayload with the values from the byte array parameter
        populating the fields.
        """

        if len(ba) != OsdpMFGHostGetDeviceDescriptionPayload.DATA_LENGTH:
            raise PayloadValidationError("osdp_MFG Host Get Device Description payload incorrect length")

        return OsdpMFGHostGetDeviceDescriptionPayload(
            tag=ResponseTags.EXT_READER_ID,
            vendor_code=bytes(ba[0:3]),
            wavelynx_format=ba[3],
            mfg_code=ba[4],
            length=ba[5],
            pcb_id=ba[6],
            config_id=ba[7],
            pcb_revision=ba[8],
            technologies=ba[9],
            cap_touch=bytes(ba[10:12]),
            firmware_major=ba[12],
            firmware_minor=ba[13],
            firmware_maintenance=ba[14],
            firmware_build=ba[15],
            supporting_firmware_version_major=ba[16],
            supporting_firmware_version_minor=ba[17],
            supporting_firmware_version_build=ba[18],
            special_features_index=ba[19],
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        if format_short:
            return {
                "vendor_code": {"name": "Vendor", "transform": "hex", "width": 6},
                "pcb_id": {"name": "PCB ID", "transform": "hex", "width": 2},
            }
        else:
            return {
                "vendor_code": {"name": "Vendor Code", "transform": "hex", "width": 6},
                "wavelynx_format": {"name": "WaveLynx Format", "transform": "hex", "width": 2},
                "mfg_code": {"name": "MFG Code", "transform": "hex", "width": 2},
                "length": {"name": "Length"},
                "pcb_id": {"name": "PCB ID", "transform": "hex", "width": 2},
                "config_id": {"name": "Config ID", "transform": "hex", "width": 2},
                "pcb_revision": {"name": "PCB Revision"},
                "technologies": {"name": "Technologies", "transform": "hex", "width": 2},
                "cap_touch": {"name": "Cap Touch", "transform": "hex", "width": 4},
                "firmware_major": {"name": "Firmware Version Major"},
                "firmware_minor": {"name": "Firmware Version Minor"},
                "firmware_maintenance": {"name": "Firmware Version Maintenance"},
                "firmware_build": {"name": "Firmware Version Build"},
                "supporting_firmware_version_major": {"name": "Supporting Firmware Version Major"},
                "supporting_firmware_version_minor": {"name": "Supporting Firmware Version Minor"},
                "supporting_firmware_version_build": {"name": "Supporting Firmware Version Build"},
                "special_features_index": {"name": "Special Features Index", "transform": "hex", "width": 2},
            }


@dataclass
class OsdpCapabilityRecord:
    """
    Device capability record.

    Byte structure (3 bytes):
    [0] function_code - Capability function code
    [1] compliance - Compliance level
    [2] number_of - Number of items supported
    """

    function_code: FunctionCodes
    """
    Device capability function code
    """
    compliance: int
    """
    Device capability compliance level
    """
    number_of: int
    """
    Number of items supported for this capability
    """

    def to_bytes(self) -> bytes:
        return bytes([self.function_code, self.compliance, self.number_of])

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "OsdpCapabilityRecord":
        return cls(
            function_code=FunctionCodes(data[offset]),
            compliance=data[offset + 1],
            number_of=data[offset + 2],
        )


@dataclass
class OsdpPdcapPayload(OsdpBasePayload):
    """
    osdp_PDCAP payload.

    Byte structure (variable length, multiple of 3 bytes):
    Multiple OsdpCapabilityRecord structures concatenated
    """

    records: list[OsdpCapabilityRecord]
    """
    List of device capability records
    """

    RECORD_SIZE: int = 3
    """
    Size in bytes of each capability record
    """

    TITLE: ClassVar[str] = "Device Capabilities Report"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        data = bytearray()
        for record in self.records:
            data.extend(record.to_bytes())
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpPdcapPayload":
        if len(ba) % OsdpPdcapPayload.RECORD_SIZE != 0:
            raise PayloadValidationError("osdp_PDCAP payload bad length")

        records = []
        for i in range(0, len(ba), OsdpPdcapPayload.RECORD_SIZE):
            records.append(OsdpCapabilityRecord.from_bytes(bytes(ba), i))

        return OsdpPdcapPayload(tag=ResponseTags.PDCAP, records=records)

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "_count": {"name": "Count", "compute": lambda p: len(p.records)},
        }
        if not format_short:
            # Format capabilities as a nicely formatted list
            def format_capabilities(payload):
                if not payload.records:
                    return "None"
                lines = []
                for i, record in enumerate(payload.records, 1):
                    func_name = record.function_code.name.replace("_", " ").title()
                    lines.append(f"{i}. {func_name} (Compliance: {record.compliance}, Count: {record.number_of})")
                return "\n".join(lines)

            fields = {
                **fields,
                "_count": {"name": "Capability Count", "compute": lambda p: len(p.records)},
                "_capabilities": {"name": "Capabilities", "compute": format_capabilities},
            }
        return fields


@dataclass
class OsdpLstatrPayload(OsdpBasePayload):
    """
    osdp_LSTATR payload.

    Byte structure (2 bytes):
    [0] tamper_status - Tamper status
    [1] power_status - Power status
    """

    tamper_status: TamperStatus
    """
    Tamper status (0=normal, 1=tamper_active)
    """

    power_status: PowerStatus
    """
    Power status (0=normal, 1=power_failure)
    """

    DATA_LEN: int = 2
    """
    Expected data length for osdp_LSTATR payload in bytes
    """

    TITLE: ClassVar[str] = "Local Status"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        return bytes([self.tamper_status, self.power_status])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpLstatrPayload":
        if len(ba) != OsdpLstatrPayload.DATA_LEN:
            raise PayloadValidationError("osdp_LSTATR payload bad length")

        return OsdpLstatrPayload(
            tag=ResponseTags.LSTATR,
            tamper_status=TamperStatus(ba[0]),
            power_status=PowerStatus(ba[1]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "tamper_status": {"name": "Tamper", "transform": lambda v: str(v.value)},
            "power_status": {"name": "Power", "transform": lambda v: str(v.value)},
        }
        if not format_short:
            fields = {
                **fields,
                "tamper_status": {"name": "Tamper Status", "transform": "enum"},
                "power_status": {"name": "Power Status", "transform": "enum"},
            }
        return fields


@dataclass
class OsdpIstatrPayload(OsdpBasePayload):
    """
    osdp_ISTATR payload.

    Byte structure (variable length):
    [0...n-1] input_statuses - One byte per input status
    """

    input_statuses: list[int]
    """
    List of input status bytes (one per input)
    """

    TITLE: ClassVar[str] = "Input Status Report"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        return bytes(self.input_statuses)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpIstatrPayload":
        return OsdpIstatrPayload(tag=ResponseTags.ISTATR, input_statuses=list(ba))

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "_input_count": {"name": "Inputs", "compute": lambda p: len(p.input_statuses)},
        }
        if not format_short:
            fields = {
                **fields,
                "_input_count": {"name": "Input Count", "compute": lambda p: len(p.input_statuses)},
                "_statuses": {
                    "name": "Statuses",
                    "compute": lambda p: ", ".join(format_hex(s, width=2) for s in p.input_statuses) if p.input_statuses else "None",
                },
            }
        return fields


@dataclass
class OsdpOstatrPayload(OsdpBasePayload):
    """
    osdp_OSTATR payload.

    Byte structure (variable length):
    [0...n-1] output_statuses - One byte per output status
    """

    output_statuses: list[int]
    """
    List of output status bytes (one per output)
    """

    TITLE: ClassVar[str] = "Output Status Report"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        return bytes(self.output_statuses)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpOstatrPayload":
        return OsdpOstatrPayload(tag=ResponseTags.OSTATR, output_statuses=list(ba))

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "_output_count": {"name": "Outputs", "compute": lambda p: len(p.output_statuses)},
        }
        if not format_short:
            fields = {
                **fields,
                "_output_count": {"name": "Output Count", "compute": lambda p: len(p.output_statuses)},
                "_statuses": {
                    "name": "Statuses",
                    "compute": lambda p: ", ".join(format_hex(s, width=2) for s in p.output_statuses) if p.output_statuses else "None",
                },
            }
        return fields


@dataclass
class OsdpRstatrPayload(OsdpBasePayload):
    """
    osdp_RSTATR payload.

    Byte structure (1 byte):
    [0] reader_tamper_status - Reader tamper status
    """

    reader_tamper_status: TamperStatus
    """
    Reader tamper status (0=normal, 1=tamper_active)
    """

    DATA_LEN: int = 1
    """
    Expected data length for osdp_RSTATR payload in bytes
    """

    TITLE: ClassVar[str] = "Reader Status"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        return bytes([self.reader_tamper_status])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpRstatrPayload":
        if len(ba) != OsdpRstatrPayload.DATA_LEN:
            raise PayloadValidationError("osdp_RSTATR payload bad length")

        return OsdpRstatrPayload(tag=ResponseTags.RSTATR, reader_tamper_status=TamperStatus(ba[0]))

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "reader_tamper_status": {"name": "Tamper", "transform": lambda v: str(v.value)},
        }
        if not format_short:
            fields = {
                **fields,
                "reader_tamper_status": {"name": "Tamper Status", "transform": "enum"},
            }
        return fields


@dataclass
class OsdpRawPayload(OsdpBasePayload):
    """
    osdp_RAW payload.

    Byte structure (4 + data_length bytes):
    [0] reader_number - Reader number
    [1] format_code - Card format code
    [2] bit_count_lsb - Bit count LSB
    [3] bit_count_msb - Bit count MSB
    [4...4+data_length-1] data - Raw card data
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """
    format_code: int
    """
    Card format code
    """
    bit_count: int
    """
    Number of bits in the card data
    """
    data: bytes
    """
    Raw card data
    """

    MIN_DATA_LEN: int = 4
    """
    Minimum data length for osdp_RAW payload in bytes
    """

    TITLE: ClassVar[str] = "Raw Card Read"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        bit_count_lsb = self.bit_count & 0xFF
        bit_count_msb = (self.bit_count >> 8) & 0xFF
        data = bytearray(
            [
                self.reader_number,
                self.format_code,
                bit_count_lsb,
                bit_count_msb,
            ]
        )
        data.extend(self.data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpRawPayload":
        if len(ba) < OsdpRawPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_RAW payload too short")

        bit_count = ba[2] | (ba[3] << 8)
        return OsdpRawPayload(
            tag=ResponseTags.RAW,
            reader_number=ba[0],
            format_code=ba[1],
            bit_count=bit_count,
            data=bytes(ba[4:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "reader_number": {"name": "Reader"},
            "bit_count": {"name": "Bit Count"},
            "data": {"name": "Data", "transform": "hex_bytes"},
        }
        if not format_short:
            fields = {
                **fields,
                "reader_number": {"name": "Reader Number"},
                "format_code": {"name": "Format Code", "transform": "hex", "width": 2},
            }
        return fields


@dataclass
class OsdpFmtPayload(OsdpBasePayload):
    """
    osdp_FMT payload.

    Byte structure (3 + data_length bytes):
    [0] reader_number - Reader number
    [1] read_direction - Read direction indicator
    [2] character_count - Number of characters
    [3...3+character_count-1] data - Formatted card data
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """
    read_direction: int
    """
    Card read direction indicator
    """
    character_count: int
    """
    Number of characters in the data
    """
    data: bytes
    """
    Formatted card data
    """

    MIN_DATA_LEN: int = 3
    """
    Minimum data length for osdp_FMT payload in bytes
    """

    TITLE: ClassVar[str] = "Formatted Card Read"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        data = bytearray([self.reader_number, self.read_direction, self.character_count])
        data.extend(self.data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpFmtPayload":
        if len(ba) < OsdpFmtPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_FMT payload too short")

        return OsdpFmtPayload(
            tag=ResponseTags.FMT,
            reader_number=ba[0],
            read_direction=ba[1],
            character_count=ba[2],
            data=bytes(ba[3:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "reader_number": {"name": "Reader"},
            "character_count": {"name": "Chars"},
        }
        if not format_short:
            fields = {
                **fields,
                "reader_number": {"name": "Reader Number"},
                "read_direction": {"name": "Read Direction"},
                "character_count": {"name": "Character Count"},
                "_data": {
                    "name": "Data",
                    "compute": lambda p: p.data.decode("utf-8", errors="replace") if p.data else "",
                },
            }
        return fields


@dataclass
class OsdpKeypadPayload(OsdpBasePayload):
    """
    osdp_KEYPAD payload.

    Byte structure (2 + data_length bytes):
    [0] reader_number - Reader number
    [1] digit_count - Number of digits
    [2...2+digit_count-1] data - Keypad digit data
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """
    digit_count: int
    """
    Number of keypad digits entered
    """
    data: bytes
    """
    Keypad digit data
    """

    MIN_DATA_LEN: int = 2
    """
    Minimum data length for osdp_KEYPAD payload in bytes
    """

    TITLE: ClassVar[str] = "Keypad Input"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        data = bytearray([self.reader_number, self.digit_count])
        data.extend(self.data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpKeypadPayload":
        if len(ba) < OsdpKeypadPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_KEYPAD payload too short")

        return OsdpKeypadPayload(
            tag=ResponseTags.KEYPAD,
            reader_number=ba[0],
            digit_count=ba[1],
            data=bytes(ba[2:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "reader_number": {"name": "Reader"},
            "digit_count": {"name": "Digits"},
        }
        if not format_short:
            fields = {
                **fields,
                "reader_number": {"name": "Reader Number"},
                "digit_count": {"name": "Digit Count"},
                "data": {"name": "Data", "transform": "hex_bytes"},
            }
        return fields


@dataclass
class OsdpComPayload(OsdpBasePayload):
    """
    osdp_COM payload.

    Byte structure (5 bytes):
    [0] address - Device address
    [1] baud_rate_0 - Baud rate byte 0 (little-endian)
    [2] baud_rate_1 - Baud rate byte 1
    [3] baud_rate_2 - Baud rate byte 2
    [4] baud_rate_3 - Baud rate byte 3 (little-endian)
    """

    address: int
    """
    Device address (0-255)
    """
    baud_rate: bytes
    """
    Current baud rate as 4-byte little-endian value
    """

    DATA_LEN: int = 5
    """
    Expected data length for osdp_COM payload in bytes
    """

    TITLE: ClassVar[str] = "Communication Settings"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        data = bytearray([self.address])
        data.extend(self.baud_rate)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpComPayload":
        if len(ba) != OsdpComPayload.DATA_LEN:
            raise PayloadValidationError("osdp_COM payload bad length")

        return OsdpComPayload(
            tag=ResponseTags.COM,
            address=ba[0],
            baud_rate=bytes(ba[1:5]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "address": {"name": "Address"},
            "_baud": {
                "name": "Baud",
                "compute": lambda p: int.from_bytes(p.baud_rate, byteorder="little"),
            },
        }
        if not format_short:
            fields = {
                **fields,
                "_baud": {
                    "name": "Baud Rate",
                    "compute": lambda p: int.from_bytes(p.baud_rate, byteorder="little"),
                },
            }
        return fields


@dataclass
class OsdpBioreadrPayload(OsdpBasePayload):
    """
    osdp_BIOREADR payload.

    Byte structure (6 + bio_template_length bytes):
    [0] reader_number - Reader number
    [1] status - Biometric read status
    [2] bio_type - Biometric type code
    [3] bio_quality - Biometric quality code
    [4] bio_length_lsb - Bio template length LSB
    [5] bio_length_msb - Bio template length MSB
    [6...6+bio_length-1] bio_template - Biometric template data
    """

    TITLE: ClassVar[str] = "Biometric Read Response"
    """
    Title for this payload type.
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """

    status: int
    """
    Biometric read status
    """

    bio_type: BioTypeCodes
    """
    Biometric type code (0=default, 1=right_thumb, etc.)
    """

    bio_quality: BioQualityCodes
    """
    Biometric quality code (0=default)
    """

    bio_template: bytes
    """
    Biometric template data
    """

    MIN_DATA_LEN: int = 7
    """
    Minimum data length for osdp_BIOREADR payload in bytes
    """

    def to_bytes(self) -> bytes:
        bio_length = len(self.bio_template)
        bio_length_lsb = bio_length & 0xFF
        bio_length_msb = (bio_length >> 8) & 0xFF
        data = bytearray(
            [
                self.reader_number,
                self.status,
                self.bio_type,
                self.bio_quality,
                bio_length_lsb,
                bio_length_msb,
            ]
        )
        data.extend(self.bio_template)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpBioreadrPayload":
        if len(ba) < OsdpBioreadrPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_BIOREADR payload too short")

        bio_length = ba[4] | (ba[5] << 8)
        if len(ba) != OsdpBioreadrPayload.MIN_DATA_LEN - 1 + bio_length:
            raise PayloadValidationError("osdp_BIOREADR payload length mismatch")

        return OsdpBioreadrPayload(
            tag=ResponseTags.BIOREADR,
            reader_number=ba[0],
            status=ba[1],
            bio_type=BioTypeCodes(ba[2]),
            bio_quality=BioQualityCodes(ba[3]),
            bio_template=bytes(ba[6:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for BIOREADR payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "reader_number": {"name": "Reader"},
            "status": {"name": "Status"},
            "bio_type": {"name": "Bio Type", "transform": "enum"},
            "_bio_template_len": {"name": "Template Len", "compute": lambda p: len(p.bio_template)},
        }

        if not format_short:
            fields = {
                **fields,
                "bio_quality": {"name": "Bio Quality", "transform": "enum"},
            }

        return fields


@dataclass
class OsdpBiomatchrPayload(OsdpBasePayload):
    """
    osdp_BIOMATCHR payload.

    Byte structure (3 bytes):
    [0] reader_number - Reader number
    [1] status - Biometric match status
    [2] result - Biometric match result
    """

    TITLE: ClassVar[str] = "Biometric Match Response"
    """
    Title for this payload type.
    """

    reader_number: int
    """
    Reader number/identifier (0-255)
    """

    status: int
    """
    Biometric match status
    """

    result: int
    """
    Biometric match result
    """

    DATA_LEN: int = 3
    """
    Expected data length for osdp_BIOMATCHR payload in bytes
    """

    def to_bytes(self) -> bytes:
        return bytes([self.reader_number, self.status, self.result])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpBiomatchrPayload":
        if len(ba) != OsdpBiomatchrPayload.DATA_LEN:
            raise PayloadValidationError("osdp_BIOMATCHR payload bad length")

        return OsdpBiomatchrPayload(tag=ResponseTags.BIOMATCHR, reader_number=ba[0], status=ba[1], result=ba[2])

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for BIOMATCHR payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "reader_number": {"name": "Reader"},
            "status": {"name": "Status"},
            "result": {"name": "Result"},
        }

        return fields


@dataclass
class OsdpMfgrepPayload(OsdpBasePayload):
    """
    osdp_MFGREP payload.

    Byte structure (3 + data_length bytes):
    [0] vendor_code_0 - Vendor code byte 0
    [1] vendor_code_1 - Vendor code byte 1
    [2] vendor_code_2 - Vendor code byte 2
    [3...3+data_length-1] data - Manufacturer-specific response data
    """

    TITLE: ClassVar[str] = "Manufacturing Response"
    """
    Title for this payload type.
    """

    vendor_code: bytes
    """
    3-byte vendor identification code
    """
    data: bytes
    """
    Manufacturer-specific response data
    """

    MIN_DATA_LEN: int = 3
    """
    Minimum data length for osdp_MFGREP payload in bytes
    """

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for MFGREP payload.

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
    def from_bytearray(cls, ba: bytearray) -> "OsdpMfgrepPayload":
        if len(ba) < OsdpMfgrepPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_MFGREP payload too short")

        return OsdpMfgrepPayload(
            tag=ResponseTags.MFGREP,
            vendor_code=bytes(ba[0:3]),
            data=bytes(ba[3:]),
        )


@dataclass
class OsdpBusyPayload(OsdpBasePayload):
    """
    osdp_BUSY payload.

    Byte structure: Empty payload (0 bytes)
    """

    TITLE: ClassVar[str] = "BUSY Response"
    """
    Title for this payload type.
    """

    def to_bytes(self) -> bytes:
        return bytes([])

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpBusyPayload":
        _ = ba  # unused but required parameter
        return OsdpBusyPayload(tag=ResponseTags.BUSY)

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        return {"tag": {"name": "Message ID", "transform": "hex", "width": 2}}


@dataclass
class OsdpPivdatarPayload(OsdpBasePayload):
    """
    osdp_PIVDATAR payload.

    Byte structure (6 + card_data_length bytes):
    [0] total_lsb - Total data length LSB
    [1] total_msb - Total data length MSB
    [2] offset_lsb - Data offset LSB
    [3] offset_msb - Data offset MSB
    [4] data_len_lsb - This message data length LSB
    [5] data_len_msb - This message data length MSB
    [6...6+data_len-1] card_data - PIV card data fragment
    """

    TITLE: ClassVar[str] = "PIV Data Response"
    """
    Title for this payload type.
    """

    total: int
    """
    Total data length in bytes (0-65535)
    """
    offset: int
    """
    Data offset within the PIV object (0-65535)
    """
    data_len: int
    """
    Length of card data in this message (0-65535)
    """
    card_data: bytes
    """
    PIV card data fragment
    """

    MIN_DATA_LEN: int = 6
    """
    Minimum data length for osdp_PIVDATAR payload in bytes
    """

    def to_bytes(self) -> bytes:
        total_lsb = self.total & 0xFF
        total_msb = (self.total >> 8) & 0xFF
        offset_lsb = self.offset & 0xFF
        offset_msb = (self.offset >> 8) & 0xFF
        data_len_lsb = self.data_len & 0xFF
        data_len_msb = (self.data_len >> 8) & 0xFF
        data = bytearray(
            [
                total_lsb,
                total_msb,
                offset_lsb,
                offset_msb,
                data_len_lsb,
                data_len_msb,
            ]
        )
        data.extend(self.card_data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpPivdatarPayload":
        if len(ba) < OsdpPivdatarPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_PIVDATAR payload too short")

        total = ba[0] | (ba[1] << 8)
        offset = ba[2] | (ba[3] << 8)
        data_len = ba[4] | (ba[5] << 8)
        return OsdpPivdatarPayload(
            tag=ResponseTags.PIVDATAR,
            total=total,
            offset=offset,
            data_len=data_len,
            card_data=bytes(ba[6:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for PIVDATAR payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "data_len": {"name": "Data Len"},
            "offset": {"name": "Offset"},
        }

        if not format_short:
            fields = {
                **fields,
                "total": {"name": "Total"},
                "card_data": {"name": "Card Data", "transform": "hex_bytes"},
            }

        return fields


@dataclass
class OsdpGenauthrPayload(OsdpBasePayload):
    """
    osdp_GENAUTHR payload.

    Byte structure (6 + auth_data_length bytes):
    [0] total_lsb - Total auth data length LSB
    [1] total_msb - Total auth data length MSB
    [2] offset_lsb - Data offset LSB
    [3] offset_msb - Data offset MSB
    [4] data_len_lsb - This message data length LSB
    [5] data_len_msb - This message data length MSB
    [6...6+data_len-1] auth_data - Authentication response data fragment
    """

    TITLE: ClassVar[str] = "General Authentication Response"
    """
    Title for this payload type.
    """

    total: int
    """
    Total authentication data length in bytes (0-65535)
    """
    offset: int
    """
    Data offset within the authentication response (0-65535)
    """
    data_len: int
    """
    Length of authentication data in this message (0-65535)
    """
    auth_data: bytes
    """
    Authentication response data fragment
    """

    MIN_DATA_LEN: int = 6
    """
    Minimum data length for osdp_GENAUTHR payload in bytes
    """

    def __post_init__(self):
        """
        Validate OsdpGenauthrPayload fields.
        """
        if not (0 <= self.total <= MAX_16_BIT):
            raise PayloadValidationError("total must be between 0 and 65535")
        if not (0 <= self.offset <= MAX_16_BIT):
            raise PayloadValidationError("offset must be between 0 and 65535")
        if not (0 <= self.data_len <= MAX_16_BIT):
            raise PayloadValidationError("data_len must be between 0 and 65535")
        if self.data_len != len(self.auth_data):
            raise PayloadValidationError("data_len must match auth_data length")

    def to_bytes(self) -> bytes:
        total_lsb = self.total & 0xFF
        total_msb = (self.total >> 8) & 0xFF
        offset_lsb = self.offset & 0xFF
        offset_msb = (self.offset >> 8) & 0xFF
        data_len_lsb = self.data_len & 0xFF
        data_len_msb = (self.data_len >> 8) & 0xFF
        data = bytearray(
            [
                total_lsb,
                total_msb,
                offset_lsb,
                offset_msb,
                data_len_lsb,
                data_len_msb,
            ]
        )
        data.extend(self.auth_data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpGenauthrPayload":
        if len(ba) < OsdpGenauthrPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_GENAUTHR payload too short")

        total = ba[0] | (ba[1] << 8)
        offset = ba[2] | (ba[3] << 8)
        data_len = ba[4] | (ba[5] << 8)
        return OsdpGenauthrPayload(
            tag=ResponseTags.GENAUTHR,
            total=total,
            offset=offset,
            data_len=data_len,
            auth_data=bytes(ba[6:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for GENAUTHR payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "data_len": {"name": "Data Len"},
            "offset": {"name": "Offset"},
        }

        if not format_short:
            fields = {
                **fields,
                "total": {"name": "Total"},
                "auth_data": {"name": "Auth Data", "transform": "hex_bytes"},
            }

        return fields


@dataclass
class OsdpCrauthrPayload(OsdpBasePayload):
    """
    osdp_CRAUTHR payload.

    Byte structure (6 + auth_data_length bytes):
    [0] total_lsb - Total auth data length LSB
    [1] total_msb - Total auth data length MSB
    [2] offset_lsb - Data offset LSB
    [3] offset_msb - Data offset MSB
    [4] data_len_lsb - This message data length LSB
    [5] data_len_msb - This message data length MSB
    [6...6+data_len-1] auth_data - Authentication response data fragment
    """

    TITLE: ClassVar[str] = "Challenge Response Authentication Response"
    """
    Title for this payload type.
    """

    total: int
    """
    Total authentication data length in bytes (0-65535)
    """
    offset: int
    """
    Data offset within the authentication response (0-65535)
    """
    data_len: int
    """
    Length of authentication data in this message (0-65535)
    """
    auth_data: bytes
    """
    Authentication response data fragment
    """

    MIN_DATA_LEN: int = 6
    """
    Minimum data length for osdp_CRAUTHR payload in bytes
    """

    def __post_init__(self):
        """
        Validate OsdpCrauthrPayload fields.
        """
        if not (0 <= self.total <= MAX_16_BIT):
            raise PayloadValidationError("total must be between 0 and 65535")
        if not (0 <= self.offset <= MAX_16_BIT):
            raise PayloadValidationError("offset must be between 0 and 65535")
        if not (0 <= self.data_len <= MAX_16_BIT):
            raise PayloadValidationError("data_len must be between 0 and 65535")
        if self.data_len != len(self.auth_data):
            raise PayloadValidationError("data_len must match auth_data length")

    def to_bytes(self) -> bytes:
        total_lsb = self.total & 0xFF
        total_msb = (self.total >> 8) & 0xFF
        offset_lsb = self.offset & 0xFF
        offset_msb = (self.offset >> 8) & 0xFF
        data_len_lsb = self.data_len & 0xFF
        data_len_msb = (self.data_len >> 8) & 0xFF
        data = bytearray(
            [
                total_lsb,
                total_msb,
                offset_lsb,
                offset_msb,
                data_len_lsb,
                data_len_msb,
            ]
        )
        data.extend(self.auth_data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpCrauthrPayload":
        if len(ba) < OsdpCrauthrPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_CRAUTHR payload too short")

        total = ba[0] | (ba[1] << 8)
        offset = ba[2] | (ba[3] << 8)
        data_len = ba[4] | (ba[5] << 8)
        return OsdpCrauthrPayload(
            tag=ResponseTags.CRAUTHR,
            total=total,
            offset=offset,
            data_len=data_len,
            auth_data=bytes(ba[6:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for CRAUTHR payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "data_len": {"name": "Data Len"},
            "offset": {"name": "Offset"},
        }

        if not format_short:
            fields = {
                **fields,
                "total": {"name": "Total"},
                "auth_data": {"name": "Auth Data", "transform": "hex_bytes"},
            }

        return fields


@dataclass
class OsdpFtstatPayload(OsdpBasePayload):
    """
    osdp_FTSTAT payload.

    Byte structure (7 bytes):
    [0] ft_action - File transfer action/status
      - bit 0: Ok to interleave
      - bit 1: Leave secure channel
      - bit 2: Separate poll response is available
    [1] ft_delay_lsb - File transfer delay LSB (seconds)
    [2] ft_delay_msb - File transfer delay MSB (seconds)
    [3] ft_status_detail_lsb - Status detail LSB
    [4] ft_status_detail_msb - Status detail MSB
    [5] ft_update_msg_max_lsb - Max update message size LSB
    [6] ft_update_msg_max_msb - Max update message size MSB
    """

    ft_ok_to_interleave: bool
    """
    True=OK to interleave, False=dedicate for filetransfer
    """

    ft_leave_secure_channel: bool
    """
    True=shall leave secure channel for file transfer, False=stay in secure channel if SC is active
    """

    ft_separate_poll_response_available: bool
    """
    True=A separate poll response is available, False=no other activity
    """

    ft_delay: int
    """
    File transfer delay in milliseconds
    """

    ft_status_detail: FileTransferStatusDetails
    """
    File transfer status details
    """

    ft_update_msg_max: int
    """
    Maximum file transfer update message size
    """

    DATA_LEN: int = 7
    """
    Expected data length for osdp_FTSTAT payload in bytes
    """

    TITLE: ClassVar[str] = "File Transfer Status"
    """
    Title for this payload type.
    """

    def __post_init__(self):
        """
        Validate OsdpFtstatPayload fields.
        """
        if not (0 <= self.ft_delay <= MAX_16_BIT):
            raise PayloadValidationError("ft_delay must be between 0 and 65535")
        if not (0 <= self.ft_update_msg_max <= MAX_16_BIT):
            raise PayloadValidationError("ft_update_msg_max must be between 0 and 65535")

    def to_bytes(self) -> bytes:
        ft_action = 0
        ft_action |= int(self.ft_ok_to_interleave) << 0
        ft_action |= int(self.ft_leave_secure_channel) << 1
        ft_action |= int(self.ft_separate_poll_response_available) << 2

        ft_delay_lsb = self.ft_delay & 0xFF
        ft_delay_msb = (self.ft_delay >> 8) & 0xFF
        ft_status_detail_lsb = self.ft_status_detail & 0xFF
        ft_status_detail_msb = (self.ft_status_detail >> 8) & 0xFF
        ft_update_msg_max_lsb = self.ft_update_msg_max & 0xFF
        ft_update_msg_max_msb = (self.ft_update_msg_max >> 8) & 0xFF

        return bytes(
            [
                ft_action,
                ft_delay_lsb,
                ft_delay_msb,
                ft_status_detail_lsb,
                ft_status_detail_msb,
                ft_update_msg_max_lsb,
                ft_update_msg_max_msb,
            ]
        )

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpFtstatPayload":
        """
        Process the byte array included in the OsdpFtstatPayload.
        1.  If we have a data length that isn't 7 bytes in size, raise a validation error and exit.
        2.  Set the locale var ft_action to the first byte as that is reflection of FTAction from the osdp spec.
            Determine the specific value of the ft_action based on the value grabbed in the byte array.
            Most occasions will have ft_ok_to_interleave as the TRUE value.
        3.  Determine the file transfer delay based on bytes 1 and 2 in the byte array.
        4.  Determine the file transfer status detail based upon the value of bytes 3 and 4 in the byte array.
        5.  Determine the maximum message size that can be sent to the reader based on bytes 5 and 6 in the byte
            array.

        :return: OsdpFtstatPayload containing the processed byte values of the payload for reporting back
        to the OSDP console.
        """
        if len(ba) != OsdpFtstatPayload.DATA_LEN:
            raise PayloadValidationError("osdp_FTSTAT payload bad length")

        ft_action = ba[0]
        ft_ok_to_interleave = bool((ft_action >> 0) & 0x01)
        ft_leave_secure_channel = bool((ft_action >> 1) & 0x01)
        ft_separate_poll_response_available = bool((ft_action >> 2) & 0x01)

        ft_delay = ba[1] | (ba[2] << 8)
        ft_status_detail = ba[3] | (ba[4] << 8)
        twos_compliment = ctypes.c_int16(ft_status_detail).value

        ft_update_msg_max = ba[5] | (ba[6] << 8)
        return OsdpFtstatPayload(
            tag=ResponseTags.FTSTAT,
            ft_ok_to_interleave=ft_ok_to_interleave,
            ft_leave_secure_channel=ft_leave_secure_channel,
            ft_separate_poll_response_available=ft_separate_poll_response_available,
            ft_delay=ft_delay,
            ft_status_detail=FileTransferStatusDetails(twos_compliment),
            ft_update_msg_max=ft_update_msg_max,
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        fields = {
            "ft_status_detail": {"name": "Status", "transform": "enum"},
        }
        if not format_short:
            fields = {
                **fields,
                "ft_ok_to_interleave": {"name": "Ok To Interleave"},
                "ft_leave_secure_channel": {"name": "Leave Secure Channel"},
                "ft_separate_poll_response_available": {"name": "Separate Poll Available"},
                "ft_delay": {"name": "Delay (ms)"},
                "ft_update_msg_max": {"name": "Max Message Size"},
            }
        return fields


@dataclass
class OsdpXrdPayload(OsdpBasePayload):
    """
    osdp_XRD payload.

    Byte structure (2 + xrw_data_length bytes):
    [0] xrw_mode - Extended read/write mode
    [1] xrd_preply - Extended read protocol reply
    [2...2+xrw_data_length-1] xrw_data - Extended read/write response data
    """

    TITLE: ClassVar[str] = "Extended Read Response"
    """
    Title for this payload type.
    """

    xrw_mode: int
    """
    Extended read/write mode (0-255)
    """
    xrd_preply: int
    """
    Extended read protocol reply (0-255)
    """
    xrw_data: bytes
    """
    Extended read/write response data
    """

    MIN_DATA_LEN: int = 2
    """
    Minimum data length for osdp_XRD payload in bytes
    """

    def __post_init__(self):
        """
        Validate OsdpXrdPayload fields.
        """
        if not (0 <= self.xrw_mode <= MAX_8_BIT):
            raise PayloadValidationError("xrw_mode must be between 0 and 255")
        if not (0 <= self.xrd_preply <= MAX_8_BIT):
            raise PayloadValidationError("xrd_preply must be between 0 and 255")

    def to_bytes(self) -> bytes:
        data = bytearray([self.xrw_mode, self.xrd_preply])
        data.extend(self.xrw_data)
        return bytes(data)

    @classmethod
    def from_bytearray(cls, ba: bytearray) -> "OsdpXrdPayload":
        if len(ba) < OsdpXrdPayload.MIN_DATA_LEN:
            raise PayloadValidationError("osdp_XRD payload too short")

        return OsdpXrdPayload(
            tag=ResponseTags.XRD,
            xrw_mode=ba[0],
            xrd_preply=ba[1],
            xrw_data=bytes(ba[2:]),
        )

    def _get_format_fields(self, format_short: bool = False) -> dict[str, Any]:
        """
        Define format fields for XRD payload.

        :param format_short: If True, return short format fields; if False, return long format fields
        :return: Dict mapping field_name -> config dict
        """
        fields = {
            "xrw_mode": {"name": "Mode"},
            "xrd_preply": {"name": "Reply"},
            "_xrw_data_len": {"name": "Data Len", "compute": lambda p: len(p.xrw_data)},
        }
        return fields
