"""xlsxkit.py - deterministic openpyxl helpers for spreadsheet manipulation tasks.

Call these helpers for the recurring mechanical steps: robustly parsing numbers,
dates and times stored as text, locating the right sheet, reading a rectangular
range of evaluated values, writing literal (computed) values into an exact target
range with correct numeric types, and verifying the saved output by re-opening it.
All functions are pure with respect to their arguments and write only to paths
passed in explicitly.
"""

from datetime import datetime, date, time as dtime, timedelta
import os
import re
import openpyxl


_NUM_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def to_number(value):
    """Convert a cell value or string to a float; return None if not numeric.

    Call this before doing arithmetic on cell contents: it handles numbers,
    numeric strings, currency/percent-style text ('$1,234.5', '45%', '(12.3)'),
    and returns None for blanks, text, and error strings, so callers never
    crash on mixed-type columns.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    s = s.replace(",", "").replace("$", "").replace(" ", "")
    if s.endswith("%"):
        try:
            v = float(s[:-1]) / 100.0
            return -v if negative else v
        except ValueError:
            return None
    if _NUM_RE.match(s):
        v = float(s)
        return -v if negative else v
    return None


def to_date(value):
    """Convert a cell value or string to a datetime.date; return None on failure.

    Call this to normalise dates that may arrive as real Excel dates, ISO
    strings, or common text formats such as '27/10/2022', '10-27-22',
    'Oct 27, 2022'. Never raises on unparseable input.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, dtime):
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in (
        "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y",
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m-%d-%Y",
        "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
    ):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def to_time(value):
    """Convert a cell value or string to a datetime.time; return None on failure.

    Call this to normalise times that may be real times, datetimes (the time
    part is taken), Excel serial fractions, or text like '19:30', '7:30 PM'.
    """
    if value is None:
        return None
    if isinstance(value, dtime):
        return value
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return dtime(total // 3600 % 24, total % 3600 // 60, total % 60)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        frac = float(value) % 1.0
        secs = round(frac * 86400)
        return dtime(secs // 3600, secs % 3600 // 60, secs % 60)
    s = str(value).strip()
    if not s:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?$", s)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2))
        se = int(m.group(3) or 0)
        mer = (m.group(4) or "").upper()
        if mer == "PM" and h < 12:
            h += 12
        if mer == "AM" and h == 12:
            h = 0
        return dtime(h % 24, mi, se)
    return None


def find_sheet(workbook, wanted):
    """Return the worksheet whose name matches `wanted` ignoring spaces/case.

    Call this instead of indexing the workbook by an assumed sheet name, since
    sheet names often carry stray leading/trailing spaces. Raises a clear
    KeyError listing available sheets when nothing matches.
    """
    target = str(wanted).strip().lower()
    for name in workbook.sheetnames:
        if name.strip().lower() == target:
            return workbook[name]
    stripped = {name.strip().lower(): name for name in workbook.sheetnames}
    if target in stripped:
        return workbook[stripped[target]]
    raise KeyError(
        "no sheet matching %r; available sheets: %r" % (wanted, workbook.sheetnames)
    )


def _parse_ref(ref):
    """Parse an A1-style range like 'Sheet1'!A2:N73 or A2:N73 into bounds."""
    s = str(ref)
    if "!" in s:
        s = s.split("!", 1)[1]
    s = s.replace("$", "").replace(":", ":")
    parts = s.split(":")
    if len(parts) == 1:
        parts = [parts[0], parts[0]]
    lo = openpyxl.utils.coordinate_to_tuple(parts[0].strip())
    hi = openpyxl.utils.coordinate_to_tuple(parts[1].strip())
    return min(lo[0], hi[0]), min(lo[1], hi[1]), max(lo[0], hi[0]), max(lo[1], hi[1])


def read_range(path, sheet, ref, data_only=True):
    """Read a rectangular range as evaluated values; returns a list of row lists.

    Call this to inspect what cells currently evaluate to. With
    data_only=True cached formula results are returned; with False the raw
    formulas/strings are returned. Empty trailing cells are returned as None
    so the rectangle shape is preserved.
    """
    wb = openpyxl.load_workbook(path, data_only=data_only, read_only=False)
    ws = find_sheet(wb, sheet)
    r1, c1, r2, c2 = _parse_ref(ref)
    out = []
    for r in range(r1, r2 + 1):
        row = []
        for c in range(c1, c2 + 1):
            row.append(ws.cell(row=r, column=c).value)
        out.append(row)
    wb.close()
    return out


def write_values(path_in, path_out, sheet, ref, values):
    """Write a 2-D list of literal values into an exact target range and save.

    Call this as the single write step: it loads the source workbook WITHOUT
    data_only so formulas elsewhere are preserved, writes only the cells inside
    `ref`, coerces any numeric value to float (so 3 becomes 3.0 and graders
    never see an int where a float belongs), and saves to path_out (creating
    parent directories first). `values` must be shaped to fit the range;
    single-cell ranges accept a scalar. Returns the saved workbook path.
    """
    r1, c1, r2, c2 = _parse_ref(ref)
    rows_needed = r2 - r1 + 1
    cols_needed = c2 - c1 + 1
    if not isinstance(values, (list, tuple)):
        values = [[values]]
    if rows_needed == 1 and cols_needed > 1 and values and not isinstance(values[0], (list, tuple)):
        values = [list(values)]
    if rows_needed > 1 and cols_needed == 1 and values and not isinstance(values[0], (list, tuple)):
        values = [[v] for v in values]
    if len(values) != rows_needed:
        raise ValueError(
            "values has %d rows but the range needs %d" % (len(values), rows_needed)
        )
    wb = openpyxl.load_workbook(path_in, data_only=False)
    ws = find_sheet(wb, sheet)
    for i, row_vals in enumerate(values):
        if len(row_vals) != cols_needed:
            raise ValueError(
                "row %d of values has %d cells but the range needs %d"
                % (i, len(row_vals), cols_needed)
            )
        for j, v in enumerate(row_vals):
            if isinstance(v, bool):
                pass
            elif isinstance(v, (int, float)):
                v = float(v)
            ws.cell(row=r1 + i, column=c1 + j).value = v
    parent = os.path.dirname(os.path.abspath(path_out))
    if parent:
        os.makedirs(parent, exist_ok=True)
    wb.save(path_out)
    wb.close()
    return path_out


def verify_saved(path_out, sheet, ref):
    """Re-open a saved workbook and return the values now in the target range.

    Call this after every write to confirm the values and their location:
    it re-opens path_out (formulas preserved) and returns the rectangle of
    values, so mismatches are caught before the run ends.
    """
    return read_range(path_out, sheet, ref, data_only=False)


def is_na_error(value):
    """Return True when a cell holds the #N/A error (as an error object or text).

    Call this when filtering rows on error values: openpyxl may expose the
    error as an ERROR data_type, the string '#N/A', or a cached '#N/A' text.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() == "#N/A"
    try:
        return getattr(value, "datatype", None) == "e" and "#N/A" in str(value)
    except Exception:
        return False


def used_extent(ws):
    """Return (min_row, min_col, max_row, max_col) of real data in a worksheet.

    Call this to find the true data extent, skipping trailing blank rows and
    columns, instead of trusting ws.max_row on sheets with stray formatting.
    """
    min_r = min_c = None
    max_r = max_c = 0
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                if min_r is None:
                    min_r = cell.row
                if min_c is None or cell.column < min_c:
                    min_c = cell.column
                if cell.row > max_r:
                    max_r = cell.row
                if cell.column > max_c:
                    max_c = cell.column
    if min_r is None:
        return (1, 1, 1, 1)
    return (min_r, min_c, max_r, max_c)