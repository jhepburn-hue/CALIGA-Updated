# /osdp/data_trafficking/osdp_traffic_conductor.py
"""
Special object used specifically for transporting traffic between the host machine and
the peripheral device.
"""

import logging
from collections.abc import Callable

from serial import Serial

from ..command_payloads import (
    OsdpBuzPayload,
    OsdpCapPayload,
    OsdpComsetPayload,
    OsdpIdReportRequestPayload,
    OsdpLedPayload,
    OsdpLedRecord,
    OsdpLstatPayload,
    OsdpMfgMobilePayload,
    OsdpMfgPayload,
    OsdpPollPayload,
)
from ..constants import (
    MAXIMUM_SERIAL_NUMBER,
    BleTxPower,
    CommandTags,
    FileTransferStatusDetails,
    LEDCodes,
    LEDPermControlCodes,
    LEDTempControlCodes,
    ManufacturingTags,
    ResponseTags,
)
from ..exceptions import IncompleteSetupError
from ..file_transfer import FileTransferProgress
from ..message import OsdpMessage
from ..message_handler import OsdpMessageHandler
from ..response_payloads import (
    OsdpAckPayload,
    OsdpComPayload,
    OsdpFtstatPayload,
    OsdpKeypadPayload,
    OsdpLstatrPayload,
    OsdpMFGExtendedReaderInfoPayload,
    OsdpMFGHostGetDeviceDescriptionPayload,
    OsdpNakPayload,
    OsdpPdcapPayload,
    OsdpPdidPayload,
    OsdpRawPayload,
    OsdpRstatrPayload,
)
from ..sc_payloads import (
    OsdpCcryptPayload,
    OsdpChlngPayload,
    OsdpRmaciPayload,
    OsdpScryptPayload,
)
from ..secure_channel import OsdpSecureChannelContext, ScbkMode, SecureChannelState
from ..utils import AES_BLOCK_SIZE
from .file_transfer_manager import FileTransferManager, NoAvailableFragmentsException, OutOfFileBytesException

DEFAULT_FILE_TRANSFER_FRAGMENT_SIZE: int = 1024

COMMAND_TAGS_TO_PAYLOAD_TYPE: dict = {
    CommandTags.ID: OsdpIdReportRequestPayload,
    CommandTags.CAP: OsdpCapPayload,
    CommandTags.LSTAT: OsdpLstatPayload,
    CommandTags.BUZ: OsdpBuzPayload,
}

"""
Specified in OSDP 2.2-2 section 5.7.
"The transmitting device shall drive the line to a marking state for a minimum time pause
equivalent of one UTF-8 character before starting to send the first character of a message (this
can be achieved by sending a character with all bits set to '1')"
"""
SERIAL_LINE_MARK_BYTE = b"\xff"


class OsdpTrafficConductor:
    """
    OSDP traffic conductor class.  Transports data in the form of bytes between the upstream machine
    (imitates an ACU) and the downstream peripheral device.
    """

    def __init__(
        self,
        serial_interface: Serial,
        device_address: int = 0,
        secure_channel_context: OsdpSecureChannelContext | None = None,
        use_crc: bool = True,
    ):
        self.__serial_interface = serial_interface
        self.__device_address = device_address
        self.use_crc = use_crc
        self.__message_handler = self.setup_osdp_message_handler(secure_channel_context)
        self._register_response_payloads()

    def setup_osdp_message_handler(self, secure_channel_context: OsdpSecureChannelContext | None) -> OsdpMessageHandler:
        """
        Helper method that establishes and returns the osdp message handler to be secure or plain text depending on
        whether the secure_channel_context is properly populated.

        :param secure_channel_context: The configuration consumed by the OSDP message handler to make the
        OSDP session secure.  If this field is empty, a plain text OSDP session is generated.

        :return: An OSDP message handler object that has either a secure or plaintext session depending on
        the value of the secure_channel_context parameter.
        """

        # If a secure channel context is not provided by the caller, we use the default.

        message_handler: OsdpMessageHandler
        if not secure_channel_context:
            message_handler = OsdpMessageHandler(
                OsdpSecureChannelContext(None, mode=ScbkMode.DEFAULT),
                self._handle_sequence_reset,
                # Checksum and CRC error handling are mutually exclusive.
                use_crc=self.use_crc,
            )
        else:
            message_handler = OsdpMessageHandler(secure_channel_context, self._handle_sequence_reset)

        return message_handler

    @classmethod
    def _handle_sequence_reset(cls) -> None:
        """
        Helper method that spits out a logging warning.  Used primarily for setup of the OSDP message handler.
        """
        logging.warning("sequence reset detected")

    def _receive_osdp_packet(self) -> bytes:
        """
        This function gets a "complete" OSDP packet by leveraging the determined
        length in the packet. It times out if the start of message is not received.
        It also fails if the packet contains an invalid lenghth. This algorithm does not
        follow OSDP in timing or method, so it will be changed with the following ticket
        # TODO: https://wavelynx.atlassian.net/browse/AUT-49
        """
        # Implement a checksum and timeout option in accordance with OSDP standard 2.2-2
        received_bytes = bytearray()

        #breakpoint()
        while True:
            b = self.__serial_interface.read(1)
            if not b:
                raise (TimeoutError("Timeout waiting for SOM (OSDP Start of Message)"))
            if b[0] == 0x53:
                received_bytes.append(0x53)
                break

        hdr = self.__serial_interface.read(3)
        if len(hdr) < 3:
            raise TimeoutError("Timeout reading header")
        received_bytes.extend(hdr)
        # The OSDP header is composed of PD (peripheral device) address,
        # Least significant, and most significant byte of the packet length
        # (named LEN_LSB and LEN_MSB in SIA_OSDP-2.2-2 respectively)
        # Only the LEN_LSB and LEN_MSB are used here.
        _, len_lsb, len_msb = hdr

        # Calculate the packet length value using byte arithmetic.
        # For example if len_lsb = 0x43 and len_msb = 0x2A
        # Left shift len_msb by 8 bits (one byte): 0x2A << 8 = 0x2A00
        # Then OR that new value with len_lsb: 0x2A00 | 0x43 = 0x2A43
        # An addition operation is mathematically equivalent in this context
        # after the left shift; 0x2A00 + 0x43 == 0x2A00 | 0x43
        total_length = (len_msb << 8) | len_lsb

        # Since 4 bytes have already been read, (SOM, ADDR, LEN_LSB, LEN_MSB)
        # read only the remaining bytes as determined by the received length.
        already_read_byte_count = 4
        to_read = total_length - already_read_byte_count
        if total_length < already_read_byte_count:
            raise ValueError("Invalid packet, no Message Control Information")

        while to_read:
            chunk = self.__serial_interface.read(to_read)
            if not chunk:
                raise TimeoutError(f"Timeout waiting for {to_read} more bytes")
                return bytearray()
            received_bytes.extend(chunk)
            to_read -= len(chunk)

        return bytes(received_bytes)

    def _register_response_payloads(self) -> None:
        """
        Register all supported response payload classes.
        """
        self.__message_handler.register_payload_class(ResponseTags.ACK, OsdpAckPayload)
        self.__message_handler.register_payload_class(ResponseTags.NAK, OsdpNakPayload)
        self.__message_handler.register_payload_class(ResponseTags.PDID, OsdpPdidPayload)
        self.__message_handler.register_payload_class(ResponseTags.PDCAP, OsdpPdcapPayload)
        self.__message_handler.register_payload_class(ResponseTags.RSTATR, OsdpRstatrPayload)
        self.__message_handler.register_payload_class(ResponseTags.LSTATR, OsdpLstatrPayload)
        self.__message_handler.register_payload_class(ResponseTags.RAW, OsdpRawPayload)
        self.__message_handler.register_payload_class(ResponseTags.KEYPAD, OsdpKeypadPayload)
        self.__message_handler.mfg_reply_class(
            ResponseTags.EXT_READER_ID,
            OsdpMFGExtendedReaderInfoPayload,
            ManufacturingTags.WL_MANUFACTURING_CODE_EXTENDED_ID,
        )
        self.__message_handler.mfg_reply_class(
            ResponseTags.EXT_READER_ID,
            OsdpMFGHostGetDeviceDescriptionPayload,
            ManufacturingTags.WL_MANUFACTURING_CODE_GET_DEVICE_DESCRIPTION,
        )
        self.__message_handler.mfg_reply_class(
            ResponseTags.MFGREP,
            OsdpMfgMobilePayload,
            ManufacturingTags.MOBILE,
        )

        self.__message_handler.register_payload_class(ResponseTags.CCRYPT, OsdpCcryptPayload)
        self.__message_handler.register_payload_class(ResponseTags.RMAC_I, OsdpRmaciPayload)

        self.__message_handler.register_payload_class(ResponseTags.FTSTAT, OsdpFtstatPayload)

        self.__message_handler.register_payload_class(ResponseTags.COM, OsdpComPayload)

    ####################################################################################################################

    def _handle_rmaci_response(self, rmaci_payload: OsdpRmaciPayload) -> None:
        """
        Handle RMAC_I response to complete secure channel establishment.

        :param rmaci_payload: RMAC_I payload from PD
        """
        if not self.__message_handler.secure_channel_context:
            logging.error("No secure channel context available for RMAC_I processing")
            return

        sscrypt: bytes = self.__message_handler.secure_channel_context.calc_server_cryptogram()
        expected_rmaci: bytes = self.__message_handler.secure_channel_context.calc_rmaci(sscrypt)

        if expected_rmaci != rmaci_payload.mac_i:
            logging.error(f"RMAC_I mismatch: expected {expected_rmaci}, got {rmaci_payload.mac_i}")
            return

        # Store the RMAC_I as the initial RMAC for ACU (for generating command MACs per OSDP spec)
        self.__message_handler.secure_channel_context.rmac = rmaci_payload.mac_i

        # ACU's CMAC starts at zero (for PD to use when generating reply MACs)
        self.__message_handler.secure_channel_context.cmac = bytes(AES_BLOCK_SIZE)

        # Transition to active state to complete handshake
        self.__message_handler.secure_channel_context.state = SecureChannelState.ACTIVE

        # Don't reset sequence - let it continue normally after secure channel establishment

        # Verify the secure channel is now active
        if not self.__message_handler.secure_channel_context.state.is_active():
            logging.warning("Secure channel not active after RMAC_I processing")

    def _handle_ccrypt_response(self, ccrypt_payload: OsdpCcryptPayload) -> None:
        """
        Handle CCRYPT response to continue secure channel establishment.

        :param ccrypt_payload: CCRYPT payload from PD
        """
        if not self.__message_handler.secure_channel_context:
            logging.error("No secure channel context available for CCRYPT processing")
            return

        # Store RNDB from PD
        self.__message_handler.secure_channel_context.rndb = ccrypt_payload.random_number

        # Derive session keys using RNDA and RNDB
        self.__message_handler.secure_channel_context.derive_session_keys()

        # Validate client cryptogram to verify PD authenticity
        expected_ccrypt = self.__message_handler.secure_channel_context.calc_client_cryptogram()
        if expected_ccrypt != ccrypt_payload.client_cryptogram:
            logging.error("Client cryptogram validation failed - PD authentication error")
            return

        # Verify the secure channel is now pending
        if not self.__message_handler.secure_channel_context.state.is_pending():
            logging.warning("Unexpected secure channel state after CCRYPT processing")

    def process_response(self, raw_bytes: bytearray) -> OsdpMessage | None:
        """
        Process incoming response from peripheral device.

        :param raw_bytes: Raw response bytes from device
        :return: OsdpMessage with parsed payload, or None on error
        """
        try:
            message = self.__message_handler.process_incoming_message(raw_bytes)

            # Handle special payloads that need additional processing
            if isinstance(message.payload, OsdpCcryptPayload):
                self._handle_ccrypt_response(message.payload)
            elif isinstance(message.payload, OsdpRmaciPayload):
                self._handle_rmaci_response(message.payload)
            return message
        except Exception as e:
            # Log empty message errors at DEBUG level (expected in error test cases)
            # Check both direct ValueError and PayloadValidationError that wraps it
            error_str = str(e)
            if "Cannot parse empty osdp message" in error_str or (
                isinstance(e, ValueError) and "Cannot parse empty osdp message" in error_str
            ):
                logging.debug(f"Failed to parse empty response:\n{e}")
            else:
                logging.error(f"Error processing response:\n{e}")
                logging.error(f"Raw bytes: {raw_bytes.hex()}")

            return None

    def __get_extended_reader_info_payload(self) -> bytearray:
        """
        Helper method that constructs the manufacturing data value for getting extended reader information.

        :return: Byte array consumed by the APEX reader for returning extended reader information.
        """

        vendor_code_bytes: bytes = ManufacturingTags.VENDOR_CODE.to_bytes(3, "big")

        extended_reader_data_list: list[int] = [
            ManufacturingTags.WL_FORMAT,
            ManufacturingTags.WL_MANUFACTURING_CODE_EXTENDED_ID,
            ManufacturingTags.APEX_EXTENDED_ID_GET_LENGTH,
        ]

        data_list_to_bytes: bytearray = bytearray(extended_reader_data_list)

        extended_info_payload: OsdpMfgPayload = OsdpMfgPayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code_bytes,
            data=bytes(data_list_to_bytes),
        )

        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=extended_info_payload,
        )

    def __get_device_description_payload(self) -> bytearray:
        """
        Helper method that constructs the manufacturing data value for getting device description.

        :return: Byte array consumed by the APEX reader for returning device description information.
        """

        vendor_code_bytes: bytes = ManufacturingTags.VENDOR_CODE.to_bytes(3, "big")

        extended_reader_data_list: list[int] = [
            ManufacturingTags.WL_FORMAT,
            ManufacturingTags.WL_MANUFACTURING_CODE_GET_DEVICE_DESCRIPTION,
            ManufacturingTags.APEX_EXTENDED_ID_GET_LENGTH,
        ]

        data_list_to_bytes: bytearray = bytearray(extended_reader_data_list)

        extended_info_payload: OsdpMfgPayload = OsdpMfgPayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code_bytes,
            data=bytes(data_list_to_bytes),
        )

        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=extended_info_payload,
        )

    def __create_extended_set_manufacturing_data_payload(
        self, serial_number: str, ble_enable: int = 0x01, hf_enable: int = 0x01, lf_enable: int = 0x01
    ) -> bytearray:
        """
        Helper method that constructs the manufacturing data value for setting the serial number.

        :return: Byte array consumed by the APEX reader for the manufacturing command to set serial number.
        """
        # Serial number can be at maximum a 16 digit (8 byte) hex string.
        # Validate this using Python's integer constructor at base 16 (hex).
        hexadecimal_ordinal = 16
        try:
            serial_number_numeric = int(serial_number, hexadecimal_ordinal)
        except ValueError as e:
            raise ValueError(f"Requested serial number {serial_number} is not valid hexadecimal.") from e
        if serial_number_numeric > MAXIMUM_SERIAL_NUMBER or serial_number_numeric < 0:
            raise ValueError(f"Requested serial number {serial_number} is outside of serial number range.")

        # Fit the serial number into an 8 byte array by padding zeroes
        length_of_eight_bytes = 16
        num_zeroes_to_fill = length_of_eight_bytes - len(serial_number)
        zero_bytes = "0" * num_zeroes_to_fill
        padded_serial_number = zero_bytes + serial_number

        vendor_code_bytes: bytes = ManufacturingTags.VENDOR_CODE.to_bytes(3, "big")

        extended_reader_data_list: list[int] = [
            ManufacturingTags.WL_FORMAT,
            ManufacturingTags.WL_MANUFACTURING_CODE_EXTENDED_ID,
            ManufacturingTags.APEX_EXTENDED_ID_SET_LENGTH,
        ]

        header: bytearray = bytearray(extended_reader_data_list)
        serial_number_data = bytearray.fromhex(padded_serial_number)
        settings_enabled_data: bytearray = bytearray([ble_enable, hf_enable, lf_enable])

        wavelynx_mfg_set_data = header + serial_number_data + settings_enabled_data

        extended_info_payload: OsdpMfgPayload = OsdpMfgPayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code_bytes,
            data=bytes(wavelynx_mfg_set_data),
        )

        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=extended_info_payload,
        )

    def get_challenge_command(self) -> bytearray:
        """
        Generate challenge command for secure channel establishment.
        1. In the member message handler object, generate an 8 byte random number (gen_rnda()).
        2. Generate the OsdpChlngPayload which will be used to begin the procedure of establishing a
        secure channel between the device and the upstream "controller."
        3. Return the result of the attempt to create the outgoing message.

        :return: Raw bytes for CHLNG command (SCS11)
        """
        if not self.__message_handler.secure_channel_context:
            raise IncompleteSetupError("Secure channel context required to generate challenge")

        # Generate RNDA
        self.__message_handler.secure_channel_context.rnda = self.__message_handler.secure_channel_context.gen_rnda()
        self.__message_handler.secure_channel_context.gen_state()

        payload = OsdpChlngPayload(tag=CommandTags.CHLNG, rnd=self.__message_handler.secure_channel_context.rnda)
        return self.__message_handler.create_outgoing_message(self.__device_address, payload)

    def get_scrypt_command(self) -> bytearray:
        """
        Generate SCRYPT command for secure channel establishment.

        :return: Raw bytes for SCRYPT command (SCS13)
        """
        if not self.__message_handler.secure_channel_context:
            raise IncompleteSetupError("Secure channel context required to generate SCRYPT")

        # Calculate server cryptogram
        scrypt = self.__message_handler.secure_channel_context.calc_server_cryptogram()

        payload = OsdpScryptPayload(
            tag=CommandTags.SCRYPT,
            server_cryptogram=scrypt,
        )
        return self.__message_handler.create_outgoing_message(self.__device_address, payload)

    def conduct_get_extended_id_transaction(self) -> OsdpMessage | None:
        """
        Persona function for conducting the osdp_MFG transaction for getting extended device identification.
        Organizes the bytes needed to conduct the payload transaction via the member __get_extended_reader_info_payload.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :return: OsdpMessage with parsed payload, or None on failure.
        """

        test_extended_reader_payload: bytearray = self.__get_extended_reader_info_payload()
        full_command_spec: bytes = SERIAL_LINE_MARK_BYTE + bytes(test_extended_reader_payload)

        self.__serial_interface.write(full_command_spec)
        rsp: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(rsp))

    def conduct_set_extended_id_transaction(
        self, serial_number: str, ble_enable: int = 0x01, hf_enable: int = 0x01, lf_enable: int = 0x01
    ) -> OsdpMessage | None:
        """
        Conducts the osdp_MFG transaction for setting extended device identification.

        :param serial_number: Serial number to set
        :param ble_enable: BLE enable flag
        :param hf_enable: HF enable flag
        :param lf_enable: LF enable flag

        :return: OsdpMessage with parsed payload, or None on failure.
        """
        wavelynx_mfg_payload: bytearray = self.__create_extended_set_manufacturing_data_payload(
            serial_number, ble_enable, hf_enable, lf_enable
        )
        command_bytes: bytes = SERIAL_LINE_MARK_BYTE + bytes(wavelynx_mfg_payload)
        self.__serial_interface.write(command_bytes)
        rsp: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(rsp))

    def conduct_host_get_device_description_transaction(self) -> OsdpMessage | None:
        """
        Persona function for conducting the osdp_MFG transaction for getting extended device identification.
        Organizes the bytes needed to conduct the payload transaction via the member __get_extended_reader_info_payload.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :return: The processed result of the osdp_MFG transaction for extended reader info
        that has taken place against the device.  A successful transaction will yield an
        OsdpMFGExtendedReaderInfoPayload object while a failure will yield None.
        """
        test_extended_reader_payload: bytearray = self.__get_device_description_payload()
        full_command_spec: bytes = SERIAL_LINE_MARK_BYTE + bytes(test_extended_reader_payload)

        self.__serial_interface.write(full_command_spec)
        rsp: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(rsp))

    def __get_poll_command(self) -> bytearray:
        """
        Create a POLL command message.

        :return: Raw bytes for POLL command
        """
        payload = OsdpPollPayload(tag=CommandTags.POLL)
        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=payload,
        )

    def conduct_polling_transaction(self) -> OsdpMessage | None:
        """
        Persona function for conducting the osdp_POLL transaction against a device.
        Organizes the bytes needed to conduct the payload transaction via the member get_poll_command.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :return: OsdpMessage with parsed payload, or None on failure.
        """
        # Regular polling
        cmd: bytearray = self.__get_poll_command()

        # Padding added for full compatibility across devices (ethos, apex, etc.)
        # Apex in particular is expecting padding added at the front of the command.  Otherwise, the
        # command will fail.
        full_command_spec: bytes = SERIAL_LINE_MARK_BYTE + bytes(cmd)  # Pure OSDP packet starting directly with 0x53
    
        self.__serial_interface.write(bytes(full_command_spec))
        rsp: bytes = self._receive_osdp_packet()

        result = self.process_response(bytearray(rsp))
        return result

    def __get_led_command(self, color: LEDCodes) -> bytearray:
        """
        Create an LED command message for permanent color.

        :param color: LED color to set permanently
        :return: Raw bytes for LED command
        """
        led_record = OsdpLedRecord(
            reader_number=0,
            led_number=0,
            temp_control_code=LEDTempControlCodes.LED_TEMP_NOOP,
            temp_on_time=0,
            temp_off_time=0,
            temp_on_color=LEDCodes.LED_BLACK,
            temp_off_color=LEDCodes.LED_BLACK,
            temp_timer=0,
            perm_control_code=LEDPermControlCodes.LED_PERM_ENABLE,
            perm_on_time=255,  # Always on (255 * 100ms)
            perm_off_time=0,  # Never off
            perm_on_color=color,
            perm_off_color=LEDCodes.LED_BLACK,
        )
        payload = OsdpLedPayload(tag=CommandTags.LED, records=[led_record])
        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=payload,
        )

    def conduct_set_led_transaction(self, desired_led_color: LEDCodes) -> OsdpMessage | None:
        """
        Persona function for conducting the osdp_LED transaction against a device.
        Organizes the bytes needed to conduct the payload transaction via the member get_led_command.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        NOTE:  An edge case has been presented at this stage to present an intentionally poor byte array
        to confirm that the device will not receive the OSDP command but will still be able to gracefully proceed
        even after being handed a bad value.

        :param desired_led_color: Enumerated numerical of the color which to map and color the device LED's.

        :return: OsdpMessage with parsed payload, or None on failure.
        """
        led_cmd: bytearray
        if desired_led_color != LEDCodes.BAD_LED:
            led_cmd: bytearray = self.__get_led_command(desired_led_color)
        else:
            led_cmd = bytearray(b"S\x00\x16\x00\x04i\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xff\x00\x00\x93\xef")
            logging.debug(f"Writing BAD_LED command bytes to serial: bytes={bytes(led_cmd).hex()}")
        self.__serial_interface.write(bytes(led_cmd))
        led_rsp: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(led_rsp))

    def __get_mfg_buzzer(self, tone_code: int) -> bytearray:
        """
        Helper method that constructs the manufacturing data value for turning the APEX buzzer either on
        or off.

        :param tone_code: Flag that indicates whether the buzzer should be on, off,
        or should only beep on card reads.

        :return: Byte array consumed by the APEX reader for turning the buzzer on or off.
        """

        vendor_code_bytes: bytes = ManufacturingTags.VENDOR_CODE.to_bytes(3, "big")
        buzzer_data_list: list[int] = [
            ManufacturingTags.WL_FORMAT,
            ManufacturingTags.WL_MANUFACTURING_CODE_SET_BUZZER,
            ManufacturingTags.APEX_BUZZER_LENGTH,
            tone_code,
        ]
        data_list_to_bytes: bytearray = bytearray(buzzer_data_list)
        mfg_buzzer_on: OsdpMfgPayload = OsdpMfgPayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code_bytes,
            data=bytes(data_list_to_bytes),
            MIN_DATA_LEN=7,
        )
        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=mfg_buzzer_on,
        )

    def conduct_mfg_flip_buzzer(self, tone_code: int) -> OsdpMessage | None:
        """
        Persona function for conducting the WaveLynx manufacturing command for turning the buzzer on, off, or
        only beeping upon card reads.
        Organizes the bytes needed to conduct the payload transaction via the member __get_mfg_buzzer command.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :param: tone_code: Enumerated value that indicates the action of the buzzer:
        Note: These values are specific to Wavelynx, not OSDP.
        off: 0x00
        on: 0x01
        buzz on reads only: 0x02

        :return: OsdpMessage with parsed payload, or None on failure.
        """
        buzzer_bytes: bytearray = self.__get_mfg_buzzer(tone_code)
        full_command_spec: bytes = SERIAL_LINE_MARK_BYTE + bytes(buzzer_bytes)
        self.__serial_interface.write(full_command_spec)
        buzzer_response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(buzzer_response))

    def __get_ble_command(
        self,
        advertising_name: str,
        tx_power: BleTxPower,
        advertising_interval_min: int,
        advertising_interval_max: int,
    ) -> bytearray:
        vendor_code_bytes: bytes = ManufacturingTags.VENDOR_CODE.to_bytes(3, "big")
        name_ascii_bytes: bytes = advertising_name.encode("ascii")
        # Length of command excluding name is 5 bytes
        # Find length of name and add 5 to get full cmd length
        ble_cmd_length_no_name = 0x05
        ble_cmd_length_name = len(name_ascii_bytes)
        ble_cmd_length = ble_cmd_length_no_name + ble_cmd_length_name
        ble_data_bytearray = bytearray(
            [
                ManufacturingTags.WL_FORMAT,
                ManufacturingTags.WL_MANUFACTURING_CODE_SET_BLE,
                ble_cmd_length,
            ]
        )

        # Fill name_ascii_bytes as LSB in the first 4 bytes (pad or truncate as needed)
        adv_name = name_ascii_bytes[:ble_cmd_length_name].rjust(ble_cmd_length_name, b"\x00")
        ble_data_bytearray.extend(adv_name)
        ble_data_bytearray.append(int(tx_power))
        ble_data_bytearray.extend(advertising_interval_min.to_bytes(2, byteorder="big"))
        ble_data_bytearray.extend(advertising_interval_max.to_bytes(2, byteorder="big"))
        mfg_ble: OsdpMfgPayload = OsdpMfgPayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code_bytes,
            data=bytes(ble_data_bytearray),
            MIN_DATA_LEN=7,
        )
        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=mfg_ble,
        )

    def conduct_mfg_set_ble(
        self,
        advertising_name: str,
        tx_power: BleTxPower,
        advertising_interval_min: int,
        advertising_interval_max: int,
    ) -> OsdpMessage | None:
        ble_command: bytearray = self.__get_ble_command(advertising_name, tx_power, advertising_interval_min, advertising_interval_max)
        ble_command[0:0] = SERIAL_LINE_MARK_BYTE
        self.__serial_interface.write(ble_command)
        ble_response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(ble_response))

    def __create_set_mobile_command(
        self,
        key_rolling: bool,
        mypass_cred: bool,
        ble_cred: bool,
        keyset_one: bool,
        keyset_two: bool,
    ) -> bytearray:
        """
        Helper method that constructs the manufacturing data value for setting mobile settings.

        :param key_rolling: Key rolling setting (True or False)
        :param mypass_cred: MyPass credential setting (True or False)
        :param ble_cred: BLE credential setting (True or False)
        :param keyset_one: Keyset 1 setting (True or False)
        :param keyset_two: Keyset 2 setting (True or False)

        :return: Byte array consumed by the APEX reader for setting mobile settings.
        """
        vendor_code_bytes: bytes = ManufacturingTags.VENDOR_CODE.to_bytes(3, "big")
        mobile_payload: OsdpMfgMobilePayload = OsdpMfgMobilePayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code_bytes,
            length=ManufacturingTags.MOBILE_COMMAND_LENGTH,
            key_rolling=key_rolling,
            mypass_cred=mypass_cred,
            ble_cred=ble_cred,
            keyset_one=keyset_one,
            keyset_two=keyset_two,
        )

        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=mobile_payload,
        )

    def __create_get_mobile_command(
        self,
    ) -> bytearray:
        """
        Helper method that constructs the manufacturing data value for getting mobile settings.

        :return: Byte array consumed by the APEX reader for getting mobile settings.
        """
        vendor_code_bytes: bytes = ManufacturingTags.VENDOR_CODE.to_bytes(3, "big")

        mobile_payload: OsdpMfgMobilePayload = OsdpMfgMobilePayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code_bytes,
            length=0,
        )

        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=mobile_payload,
        )

    def conduct_mfg_set_mobile(
        self,
        key_rolling: bool,
        mypass_cred: bool,
        ble_cred: bool,
        keyset_one: bool,
        keyset_two: bool,
    ) -> OsdpMessage | None:
        """
        Conducts the osdp_MFG transaction for setting mobile settings.
        Organizes the bytes needed to conduct the payload transaction via the member __create_set_mobile_command command.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        Note: On Apex, Only 0x01 (keyset 1 active) or 0x03 (keysets 1 and 2 active) are allowed. Otherwise reader will return a NACK.

        :param key_rolling: Key rolling setting
        :param mypass_cred: MyPass credential setting
        :param ble_cred: BLE credential setting
        :param keyset_one: Keyset 1 setting
        :param keyset_two: Keyset 2 setting

        :return: OsdpMessage with parsed payload, or None on failure.
        """
        mobile_command: bytearray = self.__create_set_mobile_command(key_rolling, mypass_cred, ble_cred, keyset_one, keyset_two)
        mobile_command[0:0] = SERIAL_LINE_MARK_BYTE
        self.__serial_interface.write(mobile_command)
        mobile_response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(mobile_response))

    def conduct_mfg_get_mobile(self) -> OsdpMessage | None:
        """
        Conducts the osdp_MFG transaction for getting mobile settings.
        Organizes the bytes needed to conduct the payload transaction via the member __create_get_mobile_command command.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :return: OsdpMessage with parsed payload, or None on failure.
        """
        mobile_command: bytearray = self.__create_get_mobile_command()
        mobile_command[0:0] = SERIAL_LINE_MARK_BYTE
        self.__serial_interface.write(mobile_command)
        mobile_response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(mobile_response))

    def conduct_mfg_raw_transaction(
        self,
        vendor_code: bytes,
        data: bytearray,
    ) -> OsdpMessage | None:
        """
        Conduct a raw MFG command transaction with arbitrary vendor code and data.

        :param vendor_code: 3-byte vendor code (e.g., WaveLynx is 0x002357)
        :param data: Raw data bytes to send in the MFG command
        :return: OsdpMessage with parsed payload, or None on failure.
        """
        mfg_payload = OsdpMfgPayload(
            tag=CommandTags.MFG,
            vendor_code=vendor_code,
            data=bytes(data),
        )
        mfg_bytes = self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=mfg_payload,
        )
        full_command_spec: bytes = SERIAL_LINE_MARK_BYTE + bytes(mfg_bytes)
        self.__serial_interface.write(full_command_spec)
        response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(response))

    def __get_buz_command(self, reader_number: int, tone_code: int, on_time: int, off_time: int, count: int) -> bytearray:
        buz_command_payload = OsdpBuzPayload(
            tag=CommandTags.BUZ,
            reader_number=reader_number,
            tone_code=tone_code,
            on_time=on_time,
            off_time=off_time,
            count=count,
        )
        return self.__message_handler.create_outgoing_message(address=self.__device_address, payload=buz_command_payload)

    def conduct_buz_transaction(self, reader_number: int, tone_code: int, on_time: int, off_time: int, count: int) -> OsdpMessage | None:
        buz_command: bytearray = self.__get_buz_command(reader_number, tone_code, on_time, off_time, count)
        buz_command[0:0] = SERIAL_LINE_MARK_BYTE
        self.__serial_interface.write(buz_command)
        buz_response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(buz_response))

    def __get_cap_command(self) -> bytearray:
        cap_command_payload = OsdpCapPayload(tag=CommandTags.CAP)
        return self.__message_handler.create_outgoing_message(address=self.__device_address, payload=cap_command_payload)

    def conduct_cap_transaction(self) -> OsdpMessage | None:
        cap_command: bytearray = self.__get_cap_command()
        cap_command[0:0] = SERIAL_LINE_MARK_BYTE
        self.__serial_interface.write(cap_command)
        cap_response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(cap_response))

    def conduct_command_transaction(self, command_tag: CommandTags) -> OsdpMessage | None:
        command_payload_type = COMMAND_TAGS_TO_PAYLOAD_TYPE[command_tag]
        command_payload_object = command_payload_type(tag=command_tag)
        command_bytes = self.__message_handler.create_outgoing_message(address=self.__device_address, payload=command_payload_object)
        # Use interpolation to insert the marking byte at the beginning of the message.
        command_bytes[0:0] = SERIAL_LINE_MARK_BYTE
        #breakpoint()
        self.__serial_interface.write(command_bytes)
        response: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(response))

    def __get_comset_command(self, address: int, baud_rate: int) -> bytearray:
        """
        Create a COMSET command message.

        :param address: Device address to set (0-127)
        :param baud_rate: Baud rate to set (9600, 19200, 38400, 115200, 230400, 460800)
        :return: Raw bytes for COMSET command
        """
        # Convert baud rate to 4-byte little-endian
        baud_rate_bytes = baud_rate.to_bytes(4, byteorder="little")

        payload = OsdpComsetPayload(tag=CommandTags.COMSET, address=address, baud_rate=baud_rate_bytes)
        return self.__message_handler.create_outgoing_message(
            address=self.__device_address,
            payload=payload,
        )

    def conduct_comset_transaction(self, address: int, baud_rate: int) -> OsdpMessage | None:
        """
        Persona function for conducting the osdp_COMSET transaction against a device.
        Organizes the bytes needed to conduct the payload transaction via the member __get_comset_command.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :param address: Device address to set (0-127)
        :param baud_rate: Baud rate to set (9600, 19200, 38400, 115200, 230400, 460800)

        :return: OsdpMessage with parsed payload, or None on failure.
        """
        comset_cmd: bytearray = self.__get_comset_command(address, baud_rate)

        # Padding added for full compatibility across devices (ethos, apex, etc.)
        # Apex in particular is expecting padding added at the front of the command.  Otherwise, the
        # command will fail.
        full_command_spec: bytes = SERIAL_LINE_MARK_BYTE + comset_cmd

        self.__serial_interface.write(full_command_spec)
        rsp: bytes = self._receive_osdp_packet()
        return self.process_response(bytearray(rsp))

    def __complete_osdp_challenge(self) -> OsdpCcryptPayload | None:
        """
        Persona function for conducting the osdp_CHLNG transaction against a device.
        Organizes the bytes needed to conduct the payload transaction via the member get_challenge_command.
        This is the first step in establishing a secure channel session between a control panel and a device.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :return: The processed result of the osdp_CHLNG transaction that has taken place against the device.  A
        successful transaction will yield an OsdpCcryptPayload object while a failure will yield None.
        """
        challenge_msg: bytearray = self.get_challenge_command()
        self.__serial_interface.write(challenge_msg)
        challenge_rsp: bytes = self._receive_osdp_packet()
        result = self.process_response(bytearray(challenge_rsp))
        return result.payload if result and isinstance(result.payload, OsdpCcryptPayload) else None

    def __conduct_scrypt_transaction(self) -> OsdpRmaciPayload | None:
        """
        Persona function for conducting the osdp_SCRYPT transaction against a device.
        Organizes the bytes needed to conduct the payload transaction via the member get_scrypt_command.
        This is the second step in establishing a secure channel session between a control panel and a device.
        Sends the message downward to the device and then processes the response accordingly utilizing
        the member process_response method.

        :return: The processed result of the osdp_SCRYPT transaction that has taken place against the device.  A
        successful transaction will yield an OsdpRmaciPayload object while a failure will yield None.
        """
        crypto_message = self.get_scrypt_command()
        self.__serial_interface.write(crypto_message)
        crypto_rsp = self._receive_osdp_packet()
        result = self.process_response(bytearray(crypto_rsp))
        return result.payload if result and isinstance(result.payload, OsdpRmaciPayload) else None

    def secure_channel_handshake(self) -> None | OsdpRmaciPayload:
        """
        Method for activating an OSDP secure channel.
        Conducts the operations of osdp_CHLNG and osdp_SCRYPT in sequence to complete
        the protocol needed for engaging a secure channel.

        :return: Result of the attempt to establish an OSDP secure channel session between the "controller" and the
        device.  A successful secure channel session yields a
        """
        completed_item: None | OsdpRmaciPayload = None
        processed_challenge_rsp: None | OsdpCcryptPayload = self.__complete_osdp_challenge()

        if None is not processed_challenge_rsp:
            completed_item = self.__conduct_scrypt_transaction()

        if not self.__message_handler.secure_channel_context or not self.__message_handler.secure_channel_context.state.is_active():
            logging.warning("FAILED TO ESTABLISH SECURE CHANNEL")
            return None
        else:
            logging.info("Secure channel handshake successful")
            return completed_item

    # File transfer-specific operations
    # ------------------------------------------------------------------------------------------------------------------

    def __is_device_healthy_for_file_transfer(self) -> bool:
        """
        Quick inspector flow which verifies that:
        1.  The reader's information is available (osdp_ID)
        2.  The reader can be reached via polling (osdp_POLL)

        :return: Result of attempting to reach the reader via osdp_ID and osdp_POLL.
        """

        # We send a pdid request and poll command before file transfer just to make sure the device is
        # online and responding.
        if None is self.conduct_command_transaction(CommandTags.ID):
            logging.warning("FAILED TO SUCCESSFULLY GET THE DEVICE IDENTIFICATION:")
            return False

        if None is self.conduct_polling_transaction():
            logging.warning("FAILED TO SUCCESSFULLY POLL THE DEVICE TO CONFIRM FILE TRANSFER ELIGIBILITY")
            return False

        return True

    def __process_file_chunk_sent(self, ft_manager: FileTransferManager) -> bool:
        """
        Convenience method that conducts send and receive of a chunk of file data.
        1.  Get the next payload of data to send.
        2.  Create the outgoing OSDP message using the message handler.
        3.  Send the command with the message down to the device.
        4.  Get the response back.
        5.  Process the response.
        6.  Return the result of the message response processing.

        return: If the procedure is successful, an osdp_FSTAT payload response is acquired and the procedure
        can gracefully move to the next chunk of data.  Otherwise, return None to indicate that the procedure failed.

        :return: Result of the file data chunk processing.
        """

        try:
            cmd_payload = ft_manager.get_next_payload()
        except NoAvailableFragmentsException as e:
            logging.error(f"Detected fragment exception {e}")
            return False
        if cmd_payload is None:
            return False

        ft_cmd: bytearray = self.__message_handler.create_outgoing_message(self.__device_address, cmd_payload)
        full_packet: bytes = SERIAL_LINE_MARK_BYTE + bytes(ft_cmd)
        self.__serial_interface.write(full_packet)

        rsp: bytes = self._receive_osdp_packet()
        message: OsdpMessage = self.__message_handler.process_incoming_message(bytearray(rsp))

        if message.payload is None:
            return False
        return ft_manager.process_incoming_payload(message.payload)

    def conduct_file_transfer(
        self,
        file_path: str,
        file_fragment_size: int = DEFAULT_FILE_TRANSFER_FRAGMENT_SIZE,
        on_progress_callback: Callable[[FileTransferProgress], None] | None = None,
    ) -> None | OsdpAckPayload:
        """
        Perform the OSDP file transfer.  Steps involved:
        1.  Check the device health to make sure that it is ready for a file transfer
        (__is_device_healthy_for_file_transfer).
        2.  Read the binary file via the path provided to the file transfer manager class (read_the_binary_file).
        3.  While the file manager still recognizes that there are data chunks to be sent (ft.manager.state >= 0
            OK = 0
            FILE_PROCESSED = 1
            REBOOTING = 2
            FINISHING = 3
        ), continue to send and process data chunks.

        4.  Complete the procedure and send an osdp_ACK back to the console to indicate a successful completion.

        :return:  OSDP Ack payload to indicate a full successful file transfer.  None to indicate that the
        procedure failed somewhere down the line.
        """
        ft_manager: FileTransferManager = FileTransferManager(
            file_path,
            file_fragment_size,
            on_progress_callback=on_progress_callback,
        )

        if not self.__is_device_healthy_for_file_transfer():
            return None

        if not ft_manager.read_the_binary_file():
            return None

        # While the file transfer manager's state is in the process of transferring AND is not
        # in the process of rebooting (file transfer process finished), continue on with the file transfer
        # procedure.
        while ft_manager.state >= FileTransferStatusDetails.OK and ft_manager.state != FileTransferStatusDetails.REBOOTING:
            # Make the attempt to transfer a chunk of data down to the reader.  If the attempt fails without
            # causing a noticeable exception, exit here with a return value of none.
            try:
                if ft_manager.bytes_sent >= ft_manager.total_bytes:
                    raise OutOfFileBytesException("No more bytes available but finished state not received from reader.")
                if not self.__process_file_chunk_sent(ft_manager):
                    logging.error("Failed to process file data chunk.")
                    return None

            except Exception as e:
                # The reader may stop communicating any time after sending the FINISHING or REBOOTING status
                # While it is "supposed" to send a REBOOTING status as a final reply, we need to handle
                # both states if it stops communicating.
                if ft_manager.state != FileTransferStatusDetails.FINISHING or ft_manager.state != FileTransferStatusDetails.REBOOTING:
                    logging.error(f"Error transferring file: {e}")
                return None

        # Return an OSDP Ack Payload indicating that the file transfer process has successfully completed
        # end-2-end.
        return OsdpAckPayload(ResponseTags.ACK)
