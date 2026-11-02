"""General, offline, deterministic helpers for exact-coordinate Excel cell I/O."""
import re
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter


def _parse_anchor(anchor):
    a = str(anchor).strip()
    sheet = None
    if '!' in a:
        sheet, a = a.rsplit('!', 1)
        sheet = sheet.strip().strip("'")
    m = re.match(r'^([A-Za-z]+)(\d+)$', a)
    if not m:
        raise ValueError('bad anchor: %r' % anchor)
    return sheet, int(m.group(2)), column_index_from_string(m.group(1).upper())


def open_output(src_path, output_path):
    """Load input workbook for editing; return (wb, wb_values).

    wb keeps formulas/formatting and should be saved to output_path.
    wb_values is a data_only=True copy for reading cached computed values
    (None where Excel never cached a value).
    """
    wb = load_workbook(src_path)
    try:
        wbv = load_workbook(src_path, data_only=True)
    except Exception:
        wbv = None
    return wb, wbv


def _sheet_of(wb, sheet):
    if sheet is None:
        return wb.active
    return wb[sheet]


def as_number(value, default=None):
    """Coerce to int/float when possible; return default otherwise."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip().replace(',', '')
    if s in ('', '-', '–', 'N/A', 'nan', 'None'):
        return default
    try:
        f = float(s)
        return int(f) if f.is_integer() and '.' not in s and 'e' not in s.lower() else f
    except ValueError:
        return default


def write_block(ws, anchor, values):
    """Write a 1D/2D list row-major starting at anchor (e.g. 'G2').

    None entries leave the existing cell untouched. Returns cells written.
    """
    _, r0, c0 = _parse_anchor(anchor)
    if values and not isinstance(values[0], (list, tuple)):
        values = [values]
    n = 0
    for i, row in enumerate(values):
        for j, v in enumerate(row):
            if v is None:
                continue
            ws.cell(row=r0 + i, column=c0 + j).value = v
            n += 1
    return n


def read_region(wb, sheet, anchor, nrows, ncols):
    """Return a 2D list of values for the given region."""
    _, r0, c0 = _parse_anchor(anchor)
    ws = _sheet_of(wb, sheet)
    return [[ws.cell(row=r0 + i, column=c0 + j).value for j in range(ncols)]
            for i in range(nrows)]


def show_region(wb, sheet, anchor, nrows, ncols):
    """Print the region with each cell's Python type (values and types)."""
    _, r0, c0 = _parse_anchor(anchor)
    ws = _sheet_of(wb, sheet)
    for i in range(nrows):
        cells = []
        for j in range(ncols):
            v = ws.cell(row=r0 + i, column=c0 + j).value
            cells.append('%r:%s' % (v, type(v).__name__))
        print('row %d: %s' % (r0 + i, ' | '.join(cells)))


def verify_output(output_path, sheet, anchor, nrows, ncols):
    """Re-open the saved output and print the region with types and coverage."""
    wb = load_workbook(output_path, data_only=True)
    grid = read_region(wb, sheet, anchor, nrows, ncols)
    show_region(wb, sheet, anchor, nrows, ncols)
    filled = sum(1 for row in grid for v in row if v is not None and v != '')
    print('non-empty cells in region: %d of %d' % (filled, nrows * ncols))
    return grid


def diff_region(src_path, output_path, sheet, anchor, nrows, ncols):
    """Print cells in the region that changed vs the original input, and count
    cells left empty (possible missing coverage)."""
    _, r0, c0 = _parse_anchor(anchor)
    a = load_workbook(src_path, data_only=True)
    b = load_workbook(output_path, data_only=True)
    wsa, wsb = _sheet_of(a, sheet), _sheet_of(b, sheet)
    changed = empty = 0
    for i in range(nrows):
        for j in range(ncols):
            va = wsa.cell(row=r0 + i, column=c0 + j).value
            vb = wsb.cell(row=r0 + i, column=c0 + j).value
            if va != vb:
                changed += 1
                print('CHANGED %s%d: %r -> %r' % (
                    get_column_letter(c0 + j), r0 + i, va, vb))
            elif vb is None:
                empty += 1
    print('changed: %d, still-empty-unchanged: %d' % (changed, empty))
