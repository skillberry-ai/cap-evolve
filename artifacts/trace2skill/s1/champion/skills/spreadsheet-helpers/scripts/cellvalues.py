"""General helpers for reading computed cell values and writing results
without destroying formulas. Offline, deterministic, task-agnostic."""

import openpyxl


def load_values(path):
    """Load workbook with data_only=True: formula cells expose cached
    computed values instead of formula strings. Use this view for any
    numeric aggregation or lookup over possibly-formula cells."""
    return openpyxl.load_workbook(path, data_only=True)


def load_for_writing(path):
    """Load workbook normally (formulas preserved). NEVER save a workbook
    that was loaded with data_only=True - its formulas would be lost.
    Write results into this view, then save it."""
    return openpyxl.load_workbook(path)


def cell_value(ws, row, col):
    """Get a cell's value from a values-loaded worksheet, tolerating
    cells that hold formula strings (returns None for them)."""
    v = ws.cell(row=row, column=col).value
    if isinstance(v, str) and v.startswith("="):
        return None
    return v


def find_row(ws, col, key, start_row=1):
    """Find first row in column col whose value matches key, comparing
    string representations (robust to int vs str, e.g. 2012 vs '2012').
    Returns row number or None."""
    target = str(key)
    for r in range(start_row, ws.max_row + 1):
        if str(ws.cell(row=r, column=col).value) == target:
            return r
    return None
