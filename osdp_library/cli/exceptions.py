"""Custom exception classes for OSDP CLI with user-friendly messages."""


class OsdpCliException(Exception):
    """Base exception for OSDP CLI errors with user-friendly messages."""

    pass


class OsdpTimeoutException(OsdpCliException):
    """Timeout waiting for device response."""

    pass


class OsdpConnectionException(OsdpCliException):
    """Connection-related exceptions."""

    pass


class OsdpCommandException(OsdpCliException):
    """Command execution exceptions."""

    pass


class OsdpValidationExceptions(OsdpCliException):
    """Input validation exceptions."""

    pass
