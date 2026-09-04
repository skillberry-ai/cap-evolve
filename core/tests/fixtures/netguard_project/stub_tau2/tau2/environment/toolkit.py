"""Minimal stand-in for tau2's ``ToolKitBase``/``is_tool``/``ToolType`` — just enough
surface for ``AirlineTools.update_reservation_flights`` to import and run. NOT a real
tau2 install; see core/tests/test_microcase.py for why a stub is used here instead of
the real package (~heavy external install, unavailable offline).
"""

from enum import Enum


class ToolType(Enum):
    READ = "read"
    WRITE = "write"
    GENERIC = "generic"


def is_tool(_tool_type):
    def deco(fn):
        return fn
    return deco


class ToolKitBase:
    def __init__(self, db) -> None:
        self.db = db
