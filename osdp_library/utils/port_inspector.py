# /utils/port_inspector.py
"""
Helper object that inspects whether ports attached to the machine are currently in use.
This object acts as somewhat of a gatekeeper for the entry flow of the application.
"""
import os
import sys
from typing import List

from serial.tools import list_ports


class PortInspector:
    """
    Port Inspector class.  Responsible for gathering ports in use on the system and reporting them
    out to the console.
    """

    def find_and_get_ports(self) -> List[str]:
        """
        Find all available ports that are currently in applicable use.  Upon ports discovery,
        return the listed ports for further processing.

        :return: List of available ports currently utilizing a USB connection to the machine.
        """

        # Search for matching ports if you are unfortunate enough to be working on
        # a windows operating system.
        platform_win: str = "win"

        # Search for matching ports that have an active USB connection on a Linux/Unix machine.
        port_match: str = "tty"

        # Search specifically within the /dev directory of the root of the Linux/Unix machine.
        dev_path: str = "/dev"

        if sys.platform.startswith(platform_win):
            # Return list of port device names, like 'COM3'
            return [port.device for port in list_ports.comports()]

        # Get all contents of the /dev directory.
        dev_directory_contents: List[str] = os.listdir(dev_path)

        # Return ONLY the items that contain the port_match ("tty.usb") equivalent.
        return [usb_port for usb_port in dev_directory_contents if port_match in usb_port]
