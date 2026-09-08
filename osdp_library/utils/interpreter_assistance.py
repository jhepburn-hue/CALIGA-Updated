# /utils/interpreter_assistance.py
"""
Helper file that contains some general functions that assist
with keeping the interpreter in a decent state.
"""
import copy
from typing import Any

UTILITY_ZERO: int = 0
"""
Integer value 0.  Use in place of a magic value WHEREVER applicable.
No more magic values. No No No.
"""

UTILITY_ONE: int = 1
"""
Integer value 1.  Observe above regarding thoughts on magic values.
"""

EMPTY_LIST: list = []
"""
Constant for an empty list.
"""

EMPTY_STRING: str = ""
"""
Constant for an empty string.
"""


def get_constant_copy(const: Any):
    """
    Returns a deep copy of a constant to be consumed by the API business logic.
    :return: An independent copy of the variable passed in.  In other words, the
    referenced variable is completely cloned and an independent instance of the
    variable is generated for the program.
    """
    return copy.deepcopy(const)


def cancel_script_value() -> str:
    return str(get_constant_copy(-UTILITY_ONE))
