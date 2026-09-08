import os
from pathlib import Path
import time
import serial
import serial.tools.list_ports

from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import (
    OsdpTrafficConductor,
)


class OsdpFlasher:
    """Flasher utility for transmitting firmware and profile binaries over OSDP serial/RS-485 connections.

    Attributes:
        default_port (str | None): Default serial port path or name.
    """

    def __init__(self, default_port: str = None):
        """Initializes OsdpFlasher with optional default serial port setting.

        Args:
            default_port (str, optional): The default serial port device path.
              Defaults to None.
        """
        self.default_port = default_port or os.getenv("OSDP_SERIAL_PORT")

    @staticmethod
    def get_available_ports() -> list[dict]:
        """Lists connected serial/RS-485 ports on Mac and Windows platforms.

        Returns:
            list[dict]: A list of port dictionaries containing device paths and descriptions.
        """
        ports = serial.tools.list_ports.comports()
        return [
            {
                "device": p.device,  # e.g. '/dev/cu.usbserial-10' or 'COM3'
                "description": p.description,  # e.g. 'FT232R USB UART'
            }
            for p in ports
        ]

    def _flash_file(
        self, file_bytes: bytes, filename: str, port: str = None
    ) -> dict:
        """Transmits binary data to a reader over OSDP, stepping baud rate up and down.

        Args:
            file_bytes (bytes): Raw binary payload data.
            filename (str): Name of file to save temporarily.
            port (str, optional): Target serial port path. Defaults to None.

        Returns:
            dict: Operation status dictionary with success status and message or error.
        """
        target_port = port or self.default_port
        if not target_port:
            return {"success": False, "error": "No serial port selected."}

        temp_file = Path(f"/tmp/{filename}")
        try:
            temp_file.write_bytes(file_bytes)

            # Step 1: Connect at standard 9600 baud rate
            with serial.Serial(target_port, baudrate=9600, timeout=1) as ser:
                conductor = OsdpTrafficConductor(
                    serial_interface=ser, device_address=0
                )

                # Step 2: Request reader switch to 115200 baud
                print(
                    "[OSDP Flasher] Requesting reader baud rate switch to"
                    " 115200..."
                )
                conductor.conduct_comset_transaction(
                    address=0, baud_rate=115200
                )
                time.sleep(0.2)

            # Step 3: Re-open serial port at 115200 baud and stream the file
            with serial.Serial(
                target_port, baudrate=115200, timeout=1
            ) as ser_fast:
                conductor_fast = OsdpTrafficConductor(
                    serial_interface=ser_fast, device_address=0
                )
                print(
                    f"[OSDP Flasher] Transferring {filename} at 115200 baud..."
                )
                ack = conductor_fast.conduct_file_transfer(str(temp_file))

            # Step 4: Re-open at 115200 baud to switch reader back to 9600 baud
            with serial.Serial(
                target_port, baudrate=115200, timeout=1
            ) as ser_reset:
                conductor_reset = OsdpTrafficConductor(
                    serial_interface=ser_reset, device_address=0
                )
                print(
                    "[OSDP Flasher] Resetting reader baud rate back to 9600..."
                )
                conductor_reset.conduct_comset_transaction(
                    address=0, baud_rate=9600
                )
                time.sleep(0.2)

            temp_file.unlink(missing_ok=True)

            if ack:
                return {
                    "success": True,
                    "message": (
                        f"Successfully flashed {filename} over OSDP"
                        f" ({target_port})."
                    ),
                }
            return {
                "success": False,
                "error": "OSDP transfer failed or reader aborted connection.",
            }

        except Exception as e:
            temp_file.unlink(missing_ok=True)
            return {
                "success": False,
                "error": f"RS-485 Transfer Error: {str(e)}",
            }

    def flash_profile(
        self, bin_bytes: bytes, filename: str, port: str = None
    ) -> dict:
        """Flashes a Profile BIN configuration file.

        Args:
            bin_bytes (bytes): Profile binary payload bytes.
            filename (str): Name of profile binary file.
            port (str, optional): Target serial port path. Defaults to None.

        Returns:
            dict: Flashing status response dictionary.
        """
        return self._flash_file(bin_bytes, filename, port)

    def flash_firmware(
        self, dck_bytes: bytes, filename: str, port: str = None
    ) -> dict:
        """Flashes a Firmware DCK file.

        Args:
            dck_bytes (bytes): Firmware DCK binary bytes.
            filename (str): Name of firmware DCK file.
            port (str, optional): Target serial port path. Defaults to None.

        Returns:
            dict: Flashing status response dictionary.
        """
        return self._flash_file(dck_bytes, filename, port)