import os
import time
from pathlib import Path
import serial
import serial.tools.list_ports

# Import lower-level OSDP primitives
from osdp_library.osdp.command_payloads import OsdpFiletransferPayload
from osdp_library.osdp.constants import CommandTags, FileTransferStatusDetails
from osdp_library.osdp.data_trafficking.osdp_traffic_conductor import OsdpTrafficConductor
from osdp_library.osdp.response_payloads import OsdpFtstatPayload, OsdpNakPayload

SUPPORTED_BAUD_RATES = [9600, 19200, 38400, 57600, 115200]

class OsdpFlasher:
    """Manages OSDP hardware serial connections, reader discovery, and file transfers."""

    def __init__(self, port: str = None, target_address: int = 0):
        self.port = port or os.getenv("OSDP_SERIAL_PORT")
        self.address = target_address
        self.active_baud = 9600
        self.serial_conn: serial.Serial | None = None
        self.conductor: OsdpTrafficConductor | None = None

    @staticmethod
    def get_available_ports() -> list[dict]:
        """Scans the local host machine for active serial COM/TTY hardware ports."""
        valid_ports = []
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                device_path = p.device
                if not any(x in device_path for x in ["Bluetooth", "debug-console", "H300", "incoming"]):
                    valid_ports.append({
                        "device": p.device,
                        "description": p.description or p.device,
                    })
        except Exception as e:
            print(f"[OsdpFlasher] Port scan error: {e}")
        return valid_ports

    def discover_reader_baud(self) -> int | None:
        """Iterates through supported baud rates and addresses (0-3) until a reader responds."""
        for baud in SUPPORTED_BAUD_RATES:
            for addr in range(0, 4):
                try:
                    temp_serial = serial.Serial(self.port, baudrate=baud, timeout=0.3)
                    temp_conductor = OsdpTrafficConductor(temp_serial, device_address=addr)
                    rsp = temp_conductor.conduct_polling_transaction()
                    temp_serial.close()
                    if rsp is not None:
                        print(f"[OSDP Discovery] Found reader on {self.port} at {baud} baud (Addr: {addr}).")
                        self.address = addr
                        return baud
                except Exception:
                    continue
        return None

    def connect(self) -> bool:
        """Discovers reader settings and opens an active serial connection."""
        discovered_baud = self.discover_reader_baud()
        if not discovered_baud:
            raise Exception(f"No responding OSDP reader found on port {self.port}.")

        self.active_baud = discovered_baud
        self.serial_conn = serial.Serial(
            self.port,
            baudrate=self.active_baud,
            timeout=2.0,
            write_timeout=2.0
        )
        self.conductor = OsdpTrafficConductor(
            self.serial_conn,
            device_address=self.address
        )
        return True

    def flash_binary_file(self, file_path: Path | str, progress_callback=None, ft_type: int = 1) -> bool:
        """Transmits a binary file over OSDP using file transfer payloads.
        Steps baud rate up to 115200 for fast transfer and steps back down to 9600.
        """
        if not self.conductor or not self.serial_conn:
            raise Exception("OsdpFlasher is not connected.")

        with Path(file_path).open("rb") as f:
            file_bytes = f.read()

        total_bytes = len(file_bytes)
        bytes_sent = 0
        chunk_size = 112  # Standard initial fragment size for OSDP over serial
        state = FileTransferStatusDetails.OK

        # STEP 1: Step baud rate up to 115200 if connected at a lower rate
        if self.active_baud != 115200:
            print("[OSDP Flasher] Stepping baud rate up to 115200 for fast transfer...")
            self.conductor.conduct_comset_transaction(address=self.address, baud_rate=115200)
            time.sleep(0.25)
            
            # Re-open serial port at 115200 baud
            self.serial_conn.close()
            self.serial_conn.baudrate = 115200
            self.serial_conn.open()
            self.active_baud = 115200

        try:
            # STEP 2: Transmit file chunks at 115200 baud
            while state >= 0 and state != FileTransferStatusDetails.REBOOTING:
                if bytes_sent < total_bytes:
                    chunk = file_bytes[bytes_sent : bytes_sent + chunk_size]
                    payload = OsdpFiletransferPayload(
                        tag=CommandTags.FILETRANSFER,
                        ft_type=ft_type,
                        ft_size_total=total_bytes,
                        ft_offset=bytes_sent,
                        ft_fragment_size=len(chunk),
                        ft_data=chunk
                    )
                else:
                    payload = OsdpFiletransferPayload(
                        tag=CommandTags.FILETRANSFER,
                        ft_type=ft_type,
                        ft_size_total=total_bytes,
                        ft_offset=total_bytes,
                        ft_fragment_size=0,
                        ft_data=b""
                    )

                handler = self.conductor._OsdpTrafficConductor__message_handler
                cmd_bytes = handler.create_outgoing_message(self.address, payload)

                full_packet = b"\xff" + bytes(cmd_bytes)
                self.serial_conn.write(full_packet)

                rsp_bytes = self.conductor._receive_osdp_packet()
                msg = handler.process_incoming_message(bytearray(rsp_bytes))

                if not msg or not msg.payload or isinstance(msg.payload, OsdpNakPayload):
                    return False

                if isinstance(msg.payload, OsdpFtstatPayload):
                    ftstat = msg.payload
                    state = ftstat.ft_status_detail

                    if bytes_sent < total_bytes:
                        bytes_sent += len(chunk)

                    if ftstat.ft_update_msg_max > 0:
                        chunk_size = ftstat.ft_update_msg_max

                    if progress_callback:
                        pct = min(100.0, round((bytes_sent / total_bytes) * 100.0, 2))
                        progress_callback(pct)

                    if ftstat.ft_delay > 0:
                        time.sleep(ftstat.ft_delay / 1000.0)

            transfer_success = (
                state == FileTransferStatusDetails.REBOOTING or 
                state == FileTransferStatusDetails.FINISHING or 
                state == FileTransferStatusDetails.FILE_PROCESSED
            )

        finally:
            # STEP 3: Reset reader baud rate back to 9600
            print("[OSDP Flasher] Resetting reader baud rate back to 9600...")
            try:
                self.conductor.conduct_comset_transaction(address=self.address, baud_rate=9600)
                time.sleep(0.25)
                self.serial_conn.close()
                self.serial_conn.baudrate = 9600
                self.serial_conn.open()
                self.active_baud = 9600
            except Exception as e:
                print(f"[OSDP Flasher] Reader baud reset notice: {e}")

        return transfer_success

    def flash_profile(self, bin_bytes: bytes, filename: str, port: str = None) -> dict:
        """Wrapper for profile flashing."""
        temp_file = Path(f"/tmp/{filename}")
        try:
            temp_file.write_bytes(bin_bytes)
            self.port = port or self.port
            self.connect()
            success = self.flash_binary_file(temp_file, ft_type=2)
            temp_file.unlink(missing_ok=True)
            return {"success": success}
        except Exception as e:
            temp_file.unlink(missing_ok=True)
            return {"success": False, "error": str(e)}

    def flash_firmware(self, dck_bytes: bytes, filename: str, port: str = None) -> dict:
        """Wrapper for firmware flashing."""
        temp_file = Path(f"/tmp/{filename}")
        try:
            temp_file.write_bytes(dck_bytes)
            self.port = port or self.port
            self.connect()
            success = self.flash_binary_file(temp_file, ft_type=1)
            temp_file.unlink(missing_ok=True)
            return {"success": success}
        except Exception as e:
            temp_file.unlink(missing_ok=True)
            return {"success": False, "error": str(e)}