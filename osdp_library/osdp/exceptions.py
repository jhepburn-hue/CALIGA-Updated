"""Custom exceptions for OSDP protocol operations."""


class OsdpError(Exception):
    """Base exception for OSDP-related errors."""

    pass


class ChecksumVerificationError(OsdpError):
    """Raised when checksum verification fails during message deserialization."""

    pass


class CrcVerificationError(OsdpError):
    """Raised when CRC verification fails during message deserialization."""

    pass


class SecureChannelModeError(OsdpError):
    """Raised if the secure channel mode mismatches the init info for secure channel context"""

    pass


class MacVerificationError(OsdpError):
    """Raised if OSDP secure channel mac verification fails"""

    pass


class PayloadValidationError(OsdpError):
    """Raised if validation of an OSDP data payload fails"""

    pass


class UnknownMessageTypeError(OsdpError):
    """Raised when a message type/tag is not recognized or registered"""

    pass


class BadMessageSequenceError(OsdpError):
    """Raised when there is a sequence mismatch with an incoming message"""

    pass


class IncompleteSetupError(OsdpError):
    """Raised when the setup for a message routine/payload is incomplete to be executed"""

    pass


class RoutineSequenceError(OsdpError):
    """Raised when a routine is active but an incoming payload does not match what is expected"""

    pass


class SecureChannelEstablishmentError(OsdpError):
    """Raised if establishment of secure channel fails"""

    pass


class FileTransferNakError(OsdpError):
    """Raised when a NAK is seen during an OSDP file transfer"""

    error_code: int
    """NAK error code from reply"""

    def __init__(self, message: str, error_code: int):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class FileTransferStatusError(OsdpError):
    """Raised when a file transfer status error is seen"""

    ft_status_detail: int
    """Status detail code received in FTSTAT reply"""

    def __init__(self, message: str, ft_status_detail: int):
        super().__init__(message)
        self.message = message
        self.ft_status_detail = ft_status_detail


class FileTransferNoMoreCommandsError(OsdpError):
    """Raised when an application attempts to get the next command for file transfer, but there are no more valid commands"""
