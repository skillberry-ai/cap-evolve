"""Helpers for writing time-only values extracted from datetime cells."""

from datetime import datetime, time


def write_time_only(ws, src_col, dst_col, start_row, end_row,
                    number_format='hh:mm:ss AM/PM'):
    """Copy the time component of datetime cells in src_col into dst_col.

    Writes datetime.time objects as the underlying value (never the full
    datetime) and applies number_format to the destination cells.
    Returns the number of cells written.
    """
    count = 0
    for row in range(start_row, end_row + 1):
        src = ws.cell(row=row, column=src_col).value
        if isinstance(src, datetime):
            value = src.time()
        elif isinstance(src, time):
            value = src
        else:
            continue
        cell = ws.cell(row=row, column=dst_col)
        cell.value = value
        cell.number_format = number_format
        count += 1
    return count


def verify_time_only(ws, dst_col, start_row, end_row):
    """Assert that all non-empty cells in dst_col hold time-only values.

    Raises ValueError if any cell holds a datetime (has a date component)
    or a non-time value. Returns True on success.
    """
    for row in range(start_row, end_row + 1):
        value = ws.cell(row=row, column=dst_col).value
        if value is None:
            continue
        if isinstance(value, datetime):
            raise ValueError(
                f"Row {row}: stored a full datetime {value!r}; "
                "expected a time-only value"
            )
        if not isinstance(value, time):
            raise ValueError(
                f"Row {row}: stored {type(value).__name__} {value!r}; "
                "expected datetime.time"
            )
    return True
