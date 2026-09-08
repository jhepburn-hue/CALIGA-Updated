import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .command_payloads import OsdpFiletransferPayload
from .constants import CommandTags, FileFragmentConstants, FileTransferStatusDetails
from .exceptions import (
    FileTransferNakError,
    FileTransferNoMoreCommandsError,
    FileTransferStatusError,
)
from .payload import OsdpBasePayload
from .response_payloads import OsdpFtstatPayload, OsdpNakPayload

DEFAULT_MAX_CHUNK_SIZE: int = 112
"""
Default chunk size, which respects OSDP default max packet size of 128 bytes
minus overhead for header/sc context/encryption/mac etc.
"""


@dataclass
class FileTransferProgress:
    """
    File transfer progress data that is sent as part of a callback on every successful file
    transfer exchange. This allows the consuming application to take action or monitor a
    file transfer.
    """

    status: FileTransferStatusDetails
    """
    Current status of file transfer.
    """

    percent_complete: float
    """
    percentage of file that has been sent.
    """

    bytes_sent: int
    """
    Number of bytes sent so far.
    """

    total_bytes: int
    """
    Total bytes in the transfer.
    """

    ok_to_interleave: bool
    """
    PD has indicated that it is ok to send other message types during a file transfer.
    """

    leave_secure_channel: bool
    """
    PD has indicated that the ACU should leave secure channel for the file transfer.
    """

    separate_poll_response_available: bool
    """
    PD has indicated that there is data waiting for a response to a Poll command
    (i.e. card read, tamper, etc).
    """

    fragment_size: int
    """
    Current fragment size in bytes.
    """


class AcuFileTransferManager:
    """
    Provides full management of long running file transfer sequences, through creation of FT command payloads
    and processing of FTSTAT response payloads.
    """

    chunk_size: int
    """
    Max file chunk size this role can support.
    """

    file_bytes: bytes
    """
    Storage of continuous file bytes prior to it being broken into chunks following the
    first reply from a PD.
    """

    state: FileTransferStatusDetails
    """
    State tracking var to determine command sequence.
    """

    total_bytes: int
    """
    Total file size needed for file transfer OSDP messages.
    """

    bytes_sent: int = 0
    """
    Tracks the bytes sent through the file transfer process, which is required for the
    OSDP messages.
    """

    _on_progress_callback: Callable[[FileTransferProgress], None] | None
    """
    Callback passed during class init to notify implementor of file transfer progress events.
    """

    def __init__(
        self,
        filepath: str,
        chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
        on_progress_callback: Callable[[FileTransferProgress], None] | None = None,
    ):
        """
        Initialize FileTransferManager with file data broken into chunks.

        :param filepath: Path to the file to transfer
        :param chunk_size: starting size of each chunk in bytes. Can be increased by PD from FTSTAT replies.
        :param on_progress_callback: optional callback for the consuming application to be notified of progress.
        """
        self.chunk_size = chunk_size
        self.state = FileTransferStatusDetails.OK
        self.file_bytes = bytes(0)
        self.bytes_sent = 0
        self._on_progress_callback = on_progress_callback

        with Path(filepath).open("rb") as file:
            self.file_bytes = file.read()

        self.total_bytes = len(self.file_bytes)

    def get_next_payload(self) -> OsdpBasePayload:
        """
        Get the next payload in the file transfer sequence. When calling this method, the internal state of the
        file transfer process is advanced.

        :return: OSDP file transfer command payload.
        """
        if self.state == FileTransferStatusDetails.OK or self.state == FileTransferStatusDetails.FILE_PROCESSED:
            # get the chunk
            chunk: bytes = self.file_bytes[: self.chunk_size]

            # drop the chunk bytes from the remaining file bytes
            self.file_bytes = self.file_bytes[len(chunk) :]

            cmd: OsdpFiletransferPayload = OsdpFiletransferPayload(
                tag=CommandTags.FILETRANSFER,
                ft_type=FileFragmentConstants.FILE_TYPE_OPAQUE,
                ft_size_total=self.total_bytes,
                ft_offset=self.bytes_sent,
                ft_fragment_size=len(chunk),
                ft_data=chunk,
            )

            # increment the offset value
            self.bytes_sent += len(chunk)

            return cmd
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
            if self.state >= 1:
                raise FileTransferNoMoreCommandsError(f"File transfer already finished, no more commands. Status: {self.state}")
            else:
                raise FileTransferNoMoreCommandsError(f"File transfer state in error, requires full retry/reset. Status: {self.state}")

    def process_incoming_payload(self, payload: OsdpBasePayload) -> None:
        """
        Process a file transfer response payload received from the PD. This method will advance the internal
        state of the file transfer process or raise an appropriate exception if there was an error.
        """
        if isinstance(payload, OsdpNakPayload):
            # manually set the state to ABORT for NAKs, so that no more commands can be sent.
            self.state = FileTransferStatusDetails.ABORT
            raise FileTransferNakError(
                f"NAK reply received during file transfer. Code: {payload.error_code}",
                payload.error_code,
            )
        elif isinstance(payload, OsdpFtstatPayload):
            # check for errors
            status_detail = payload.ft_status_detail
            if status_detail < 0:
                raise FileTransferStatusError(
                    f"Bad status code during file transfer: Reason: {FileTransferStatusDetails(status_detail).name} Code: {status_detail}",
                    status_detail,
                )

            self.state = status_detail

            if payload.ft_update_msg_max > 0:
                self.chunk_size = payload.ft_update_msg_max

            # notify consuming application with progress.
            if self._on_progress_callback:
                self._on_progress_callback(
                    FileTransferProgress(
                        status=payload.ft_status_detail,
                        percent_complete=round((self.bytes_sent / self.total_bytes) * 100.00, 2),
                        bytes_sent=self.bytes_sent,
                        total_bytes=self.total_bytes,
                        ok_to_interleave=payload.ft_ok_to_interleave,
                        leave_secure_channel=payload.ft_leave_secure_channel,
                        separate_poll_response_available=payload.ft_separate_poll_response_available,
                        fragment_size=self.chunk_size,
                    )
                )

            # sleep for the requested delay before sending the next payload
            time.sleep(payload.ft_delay / 1000.0)
