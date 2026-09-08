# /osdp/data_trafficking/file_transfer_manager.py
"""
Class dedicated to the management of the OSDP file transfer procedure.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from ...utils.interpreter_assistance import UTILITY_ZERO
from ..command_payloads import OsdpFiletransferPayload
from ..constants import CommandTags, FileFragmentConstants, FileTransferStatusDetails
from ..exceptions import FileTransferNakError, FileTransferNoMoreCommandsError, FileTransferStatusError
from ..file_transfer import FileTransferProgress
from ..payload import OsdpBasePayload
from ..response_payloads import OsdpFtstatPayload, OsdpNakPayload


class FileTransferManager:
    """
    File Transfer Manager class implementation.
    """

    total_bytes: int
    """
    Total file size needed for file transfer OSDP messages.
    """

    file_bytes: bytes
    """
    Storage of continuous file bytes prior to it being broken into chunks following the
    first reply from a PD.
    """

    bytes_sent: int = 0
    """
    Tracks the bytes sent through the file transfer process, which is required for the
    OSDP messages.
    """

    state: FileTransferStatusDetails
    """
    State tracking var to determine command sequence.
    """

    def __init__(
        self,
        file_path: str,
        file_transfer_fragment_size: int,
        on_progress_callback: Callable[[FileTransferProgress], None] | None = None,
    ):
        self.__file_path = file_path
        self.__file_transfer_fragment_size = file_transfer_fragment_size
        self._on_progress_callback = on_progress_callback
        self.file_bytes = bytes(0)
        self.total_bytes = len(self.file_bytes)
        self.state = FileTransferStatusDetails.OK

    def read_the_binary_file(self) -> bool:
        """
        Reads the file given from the file path.  Sets the value of the file read to a member variable
        (self.file_bytes) and gets the total count in bytes of the file (self.total_bytes)

        :return: True if the file provided in the path is able to read AND the file has more than
        0 bytes.  False if either of the conditions don't occur.
        """

        read_binary: str = "rb"

        try:
            with Path(self.__file_path).open(read_binary) as file:
                self.file_bytes = file.read()
        except Exception as exception:
            logging.error(f"Exception occurred while reading the file for transfer: {exception}")
            return False

        self.total_bytes = len(self.file_bytes)

        return self.total_bytes > UTILITY_ZERO

    def get_next_payload(self) -> None | OsdpFiletransferPayload:
        """
        Get the next payload in the file transfer sequence. When calling this method, the internal state of the
        file transfer process is advanced.

        :return: OSDP file transfer command payload.
        """

        # If the file transfer status is OK (the last round of data fragments was successfully sent down to the device)
        # OR the file transfer status is fully processed, continue to the incremental fragments of data and return them
        # to the OSDP traffic conductor for processing.
        if self.state == FileTransferStatusDetails.OK or self.state == FileTransferStatusDetails.FILE_PROCESSED:
            # get the fragment of data from the file_bytes list's current beginning.
            fragment: bytes = self.file_bytes[: self.__file_transfer_fragment_size]

            fragment_size: int = len(fragment)

            # Slice off the fragment of data just captured in the fragment variable from the file_bytes list.
            self.file_bytes = self.file_bytes[fragment_size:]

            if fragment_size == 0:
                raise NoAvailableFragmentsException("No more fragments available.")

            # Generate a File transfer payload that will be sent to the device.
            cmd: OsdpFiletransferPayload = OsdpFiletransferPayload(
                tag=CommandTags.FILETRANSFER,
                ft_type=FileFragmentConstants.FILE_TYPE_OPAQUE,
                ft_size_total=self.total_bytes,
                ft_offset=self.bytes_sent,
                ft_fragment_size=fragment_size,
                ft_data=fragment,
            )

            # increment the offset value
            self.bytes_sent += fragment_size

            return cmd

        # When the File transfer is in the process of finishing
        # This section is likely never hit but is provided as a stop gap in the event of unexpected circumstances.
        elif self.state == FileTransferStatusDetails.FINISHING:
            return OsdpFiletransferPayload(
                tag=CommandTags.FILETRANSFER,
                ft_type=FileFragmentConstants.FILE_TYPE_OPAQUE,
                ft_size_total=self.total_bytes,
                ft_offset=self.total_bytes,
                ft_fragment_size=0,
                ft_data=bytes(0),
            )
        else:
            file_transfer_error = FileTransferNoMoreCommandsError(
                f"File transfer state in error, requires full retry/reset. Status: {self.state}"
            )
            logging.error(str(file_transfer_error))
            return None

    def process_incoming_payload(self, payload: OsdpBasePayload | OsdpFtstatPayload | OsdpNakPayload) -> bool:
        """
        Process a file transfer response payload received from the PD. This method will advance the internal
        state of the file transfer process or raise an appropriate exception if there was an error.

        :param payload: Processed payload provided by the message handler.  Under happy path circumstances, this
        will arrive as an OsdpFtstatPayload.  Should an error occur, with the file transfer cycle, this will be
        returned as an OsdpNakPayload.

        :return: flag indicating whether the last OSDP file transfer cycle was successful.

        NOTE:  This method contains the OsdpBasePayload as one of the possible data structures within the payload
        Union.  This is to service where this method's call is originating (OSDP Traffic Conductor method
        __process_file_chunk_sent), which is expected an "osdpBasePayload" from message handler method
        process_incoming_message.
        """

        # Log payload details
        logging.debug(f"File Transfer Payload: {payload}")

        if isinstance(payload, OsdpNakPayload):
            # manually set the state to ABORT for NAKs, so that no more commands can be sent.
            # This is likely to occur if the chunk size is greater than what the reader can consume on a cyclical basis.
            self.state = FileTransferStatusDetails.ABORT_FILE_TRANSFER
            nak_error: FileTransferNakError = FileTransferNakError(
                f"NAK reply received during file transfer. Code: {payload.error_code}",
                payload.error_code,
            )
            logging.error(str(nak_error))
            return False
        elif isinstance(payload, OsdpFtstatPayload):
            # check for errors.  Capture error and return False if an error is detected.
            if payload.ft_status_detail < FileTransferStatusDetails.OK:
                reason = FileTransferStatusDetails(payload.ft_status_detail).name
                code = payload.ft_status_detail
                status_error: FileTransferStatusError = FileTransferStatusError(
                    f"Bad status code during file transfer: Reason: {reason} Code: {code}",
                    payload.ft_status_detail,
                )
                logging.warning(status_error)
                return False

            # Set the state to the currently reported file transfer status detail.
            self.state = payload.ft_status_detail

            if payload.ft_update_msg_max > 0:
                self.__file_transfer_fragment_size = payload.ft_update_msg_max

            # Generate a File Transfer Progress object that is used for analysis of where the
            # file transfer procedure currently stands.
            current_file_transfer_progress: FileTransferProgress = FileTransferProgress(
                status=payload.ft_status_detail,
                percent_complete=round((self.bytes_sent / self.total_bytes) * 100.00, 2),
                bytes_sent=self.bytes_sent,
                total_bytes=self.total_bytes,
                ok_to_interleave=payload.ft_ok_to_interleave,
                leave_secure_channel=payload.ft_leave_secure_channel,
                separate_poll_response_available=payload.ft_separate_poll_response_available,
                fragment_size=self.__file_transfer_fragment_size,
            )

            if self._on_progress_callback:
                self._on_progress_callback(current_file_transfer_progress)

            return True
        else:
            # Unexpected payload type - return False
            return False


class NoAvailableFragmentsException(Exception):
    """Exception for no available fragments."""

    pass


class OutOfFileBytesException(Exception):
    """Exception when no more bytes exist"""

    pass
