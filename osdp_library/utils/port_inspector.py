import os
import sys
from typing import List
from serial.tools import list_ports


class PortInspector:
    def find_and_get_ports(self) -> List[str]:
        if sys.platform.startswith("win"):
            return [port.device for port in list_ports.comports()]

        dev_path = "/dev"
        try:
            dev_contents = os.listdir(dev_path)
            return [
                os.path.join(dev_path, entry)
                for entry in dev_contents
                if "cu.usb" in entry or "tty.usb" in entry or "ttyUSB" in entry
            ]
        except Exception:
            return []