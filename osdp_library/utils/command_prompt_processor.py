# /utils/command_prompt_processor.py
"""
Convenience class that handles input from the console
to supplement service operations.
"""
import os
from typing import List, Any

from .interpreter_assistance import (
    cancel_script_value,
    get_constant_copy,
    UTILITY_ONE,
    UTILITY_ZERO,
)


class CommandPromptProcessor:
    """
    Class that prompts the user for input to pursue and complete
    an OSDP-related operation.
    """

    __DEFAULT_MAX_NUMBER_OF_RETRIES: int = 3
    """
    Default maximum number of retries for selecting from a list of items
    that the prompt processor provides (prompt_for_list_selection).
    """

    @classmethod
    def get_console_input(cls, prompt_message: str):
        """
        Helper method that obtains the value of console input from the user.
        :param prompt_message: The message to be displayed on the console when prompted.

        :return: The input provided by the console.
        """

        return input(f"\n{prompt_message}: ")

    def prompt_for_list_selection(
            self,
            list_selection: List[Any],
            attempts_left: int = __DEFAULT_MAX_NUMBER_OF_RETRIES
    ) -> str:
        """
        Prompt for offering the selection of a list of items.
        1.  If the list_selection parameter is empty, exit the prompt with the cancel_script_value() field.
        2.  If the number of attempts to make a successful attempt falls below 1, exit the prompt with a
        cancel_script_value() field.
        3.  Print out the list of possible selections on the console.
        4.  Prompt the user for input selection.  Results can be:
            A.  A valid selection is made, finish the method and return the value selected in the form of a string.
            B.  A selection outside bounds of the possible options is made.  Throw an error to the console and
            recursively call the method a second time.
            C.  A non-numerical value is provided.  Throw an error to the console and recursively call the method a
            second time.

        :param list_selection: List of items to possibly select from when the prompt is provided.
        :param attempts_left: Number of attempts to provide a successful selection of the prompt.  Default of 3.

        :return:  The value of the item selected in the list in the form of a string OR the cancel_script_value()
        (string value of -1) to indicate that the script will end following the statement return.
        """

        if not list_selection:
            print("AN EMPTY LIST HAS BEEN PROVIDED, EXITING NOW.")
            return cancel_script_value()

        if attempts_left < UTILITY_ONE:
            print("TOO MANY INVALID ATTEMPTS TO MAKE A VALID SELECTION.  EXITING NOW")
            return cancel_script_value()

        item_index: int = 1

        print("--------SELECT ITEM OF INTEREST BY INDEX-------")

        for item in list_selection:
            print(f"{item_index}): {item}")
            item_index += UTILITY_ONE

        # Grab the port selection from the user's input.  If the input is legitimate
        # (matches selection on the possible listing of available ports), then proceed.
        # If the input is outside the range of applicable selections or is not an integer,
        # Provide the attempt to try again by providing the method recursively.
        try:
            item_selection: int = int(input("YOUR SELECTION: "))
            if item_selection >= item_index or item_selection <= UTILITY_ZERO:
                print("BAD SELECTION, PLEASE TRY AGAIN\n")
                return self.prompt_for_list_selection(
                    list_selection,
                    (attempts_left - UTILITY_ONE)
                )
        except ValueError:
            print(f"MUST PROVIDE A NUMERICAL VALUE.  PLEASE TRY AGAIN.\n")
            return self.prompt_for_list_selection(
                list_selection,
                (attempts_left - UTILITY_ONE)
            )

        return str(list_selection[item_selection - UTILITY_ONE])

    def get_secure_channel_selection(self) -> int:
        """
        Helper method that prompts for choosing an OSDP session.  The console user has the choice of selecting
        either a secure channel session (entering "Y", "y") or a plaintext session (entering "N", "n").

        :return: Integer value indicating whether a secure session or plaintext OSDP session is to be used.
        0 for secure channel session
        1 for plaintext session
        -1 is returned if the console entry is unrecognized
        """

        secure_channel_expected: int = get_constant_copy(UTILITY_ZERO)
        plaintext_expected: int = get_constant_copy(UTILITY_ONE)

        prompt_message: str = ("SHOULD THIS BE A SECURE CHANNEL SESSION?\n"
                               "'Y' or 'y' for yes\n"
                               "'N' or 'n' for no\n")

        secure_channel_selection: str = self.get_console_input(prompt_message)

        if secure_channel_selection not in ('Y', 'y', 'N', 'n'):
            print("BAD SELECTION, PLEASE TRY AGAIN")
            return -1

        return secure_channel_expected if secure_channel_selection in ('Y', 'y') else plaintext_expected

    def select_file_for_transfer(self, attempts_left: int = __DEFAULT_MAX_NUMBER_OF_RETRIES) -> str:
        """
        Helper method that prompts the console user to select the desired file for transfer.
        Should no files be found in the file path, then return a cancel script value.

        :param attempts_left: The maximum number of attempts permitted for selecting a valid file of which
        to conduct a transaction against.

        :return: Index result of the console user's selection of a file to upgrade the device to or
        cancel_script_value ("-1") if there are no files detected.
        """

        fw_builds: str = "fw_builds"
        items: List[str]

        try:
            items: List[str] = list(map(lambda filename: f"{fw_builds}/{filename}", os.listdir(fw_builds)))
        except Exception as exception:
            print(f"ERROR OCCURRED WHILE TRYING TO OBTAIN LIST OF AVAILABLE FIRMWARES: {type(exception)}")
            return cancel_script_value()

        if not items:
            print("NO LEGITIMATE FILES FOUND.")
            return cancel_script_value()

        return self.prompt_for_list_selection(items, attempts_left)
