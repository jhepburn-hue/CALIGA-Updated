"""Connection management for OSDP devices."""

import logging
import sys
from argparse import Namespace

from serial import Serial
import time

from osdp_library.config.config import config_path, load_config
from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor
from osdp_library.osdp.secure_channel import OsdpSecureChannelContext, ScbkMode

logger = logging.getLogger(__name__)


class ConnectionException(Exception):
    """Raised when a connection cannot be made based on parameters or exceptions from
    lower level libraries are raised.
    """

    pass


class ConnectionManager:
    """
    This class manages an OSDP connection.

    Handles:
    - Config file loading and merging with CLI args
    - Serial port path resolution (cross-platform)
    - Traffic conductor creation
    - Supporting secure channel context
    """

    def __init__(self, args: Namespace):
        """
        Initialize connection manager and create connection.

        :param args: Parsed command-line arguments
        :raises ConnectionException: If connection parameters are invalid or connection fails
        """
        self.args = args
        self._resolve_config()
        self._validate_connection_params()

        # Create connection
        port_path, baud, timeout, address = self._get_connection_params()
        self._serial = self._open_serial_connection(port_path, baud, timeout)
        secure_context = self._create_secure_channel_context()
        # If checksum is unset or False, set to False.
        use_checksum = self.args.use_checksum
        # Checksum and CRC are mutually exclusive.
        use_crc = not use_checksum

        self._conductor = OsdpTrafficConductor(
            serial_interface=self._serial,
            device_address=address,
            secure_channel_context=secure_context,
            use_crc=use_crc,
        )

        # Automatically perform secure channel handshake if secure channel is requested
        if secure_context:
            self._perform_secure_channel_handshake(self._conductor)

    def _resolve_config(self) -> None:
        """
        Load config if specified and merge with CLI args.

        CLI args take precedence over config file values.
        """
        if hasattr(self.args, "config") and self.args.config:
            try:
                cfg = load_config(config_path, self.args.config)
                # CLI args take precedence over config
                for key, value in cfg.items():
                    if not hasattr(self.args, key) or getattr(self.args, key) is None:
                        setattr(self.args, key, value)
            except Exception as e:
                raise ConnectionException(f"Failed to load config '{self.args.config}': {e}") from e

    def _validate_connection_params(self) -> None:
        """
        Validate that we have required connection parameters.

        :raises ConnectionException: If required parameters are missing
        """
        if not hasattr(self.args, "port") or not self.args.port:
            raise ConnectionException("No port specified. Use --port or --config to specify a device.")

    def _get_port_path(self) -> str:
        """
        Get the full port path, handling platform differences.

        :return: Full port path (e.g., /dev/ttyUSB0 on Linux/Mac)
        """
        port = self.args.port
        # On non-Windows, prepend /dev/ if not already present
        if not sys.platform.startswith("win") and not port.startswith("/dev/"):
            port = f"/dev/{port}"
        return port

    def _get_connection_params(self) -> tuple[str, int, float, int]:
        """
        Extract connection parameters from command line with fallbacks.

        :return: Tuple of (port_path, baud, timeout, address)
        """
        port_path = self._get_port_path()
        # Use connection_baud (from top-level -b/--baud) with fallback to baud for backwards compatibility
        baud = getattr(self.args, "connection_baud", None) or getattr(self.args, "baud", 9600) or 9600
        timeout = getattr(self.args, "timeout", 2.0) or 2.0
        # Use connection_address (from top-level -a/--address) with fallback to address for backwards compatibility
        address = getattr(self.args, "connection_address", None) or getattr(self.args, "address", 0) or 0
        return port_path, baud, timeout, address

    def _open_serial_connection(self, port_path: str, baud: int, timeout: float) -> Serial:
        try:
            serial = Serial(
                port_path,
                baudrate=baud,
                timeout=timeout,
                rtscts=False,  
                dsrdtr=False,
            )
            logging.debug(f"Serial opened: port={port_path}, baud={baud}, timeout={timeout}")
            time.sleep(1.0) 
            serial.reset_input_buffer()
            serial.reset_output_buffer()
            return serial
        except Exception as e:
            raise ConnectionException(f"Failed to open {port_path}: {e}") from e

    def _create_secure_channel_context(self) -> OsdpSecureChannelContext | None:
        """
        Create secure channel context if secure channel is requested.

        :return: Secure channel context or None
        :raises ConnectionException: If SCBK is invalid
        """
        if not hasattr(self.args, "secure") or not self.args.secure:
            return None

        scbk = getattr(self.args, "scbk", None)
        if scbk:
            # Parse hex string to bytes
            try:
                scbk_bytes = bytes.fromhex(scbk)
                return OsdpSecureChannelContext(secure_channel_base_key=scbk_bytes, mode=ScbkMode.CUSTOM)
            except ValueError as e:
                raise ConnectionException(f"Invalid SCBK hex string: {scbk}") from e
        else:
            return OsdpSecureChannelContext(secure_channel_base_key=None, mode=ScbkMode.DEFAULT)

    def _perform_secure_channel_handshake(self, conductor: OsdpTrafficConductor) -> None:
        """
        Perform secure channel handshake if secure channel context exists.

        :param conductor: Traffic conductor to perform handshake with
        :raises ConnectionException: If handshake fails
        """
        try:
            logger.debug("Performing automatic secure channel handshake...")
            result = conductor.secure_channel_handshake()
            if result is None:
                raise ConnectionException("Secure channel handshake failed - device did not respond correctly")
        except Exception as e:
            raise ConnectionException(f"Secure channel handshake failed: {e}") from e

    def get_conductor(self) -> OsdpTrafficConductor:
        """
        Return the traffic conductor.

        :return: Configured OsdpTrafficConductor
        """
        return self._conductor

    def close(self) -> None:
        """Close the serial connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()
