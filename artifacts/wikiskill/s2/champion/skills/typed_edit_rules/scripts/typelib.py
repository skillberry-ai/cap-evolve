"""Type-coercion and minimal-edit helpers matching the scorer's typed comparison."""
import re
from openpyxl.utils import column_index_from_string


def astype_like(value, refs):
    """Coerce a numeric value to match the Python type of reference cells.

    refs: one value or a list of values taken from the ORIGINAL output column
    (or the column it is derived from). If any ref is a float and value is a
    whole number, return float(value); if all refs are ints, return int(value).
    Non-numeric values are returned unchanged; NaN refs are ignored.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if isinstance(value, float) and value != value:  # NaN
        return value
    if not isinstance(refs, (list, tuple)):
        refs = [refs]
    nums = [r for r in refs
            if isinstance(r, (int, float)) and not isinstance(r, bool)]
    if not nums:
        return value
    if any(isinstance(r, float) for r in nums):
        return float(value)
    return int(value)


def changed_cells(ws, orig_values, anchor, values):
    """Yield (row_offset, col_offset, new_value) only where the intended value
    differs from the ORIGINAL cell value, so you write a minimal edit set.

    ws: the openpyxl worksheet being edited. orig_values: 2D list of ORIGINAL
    values (e.g. from iolib.read_region on the values view) with the same
    shape as values. anchor: e.g. 'F2'. values: 2D list of intended values;
    None means "leave untouched".
    """
    m = re.match(r'^([A-Za-z]+)(\d+)$', str(anchor).strip())
    if not m:
        raise ValueError('bad anchor: %r' % anchor)
    c0 = column_index_from_string(m.group(1).upper())
    del ws, c0  # math is done by the caller via row/col offsets
    for i, row in enumerate(values):
        for j, v in enumerate(row):
            if v is None:
                continue
            old = None
            if i < len(orig_values) and j < len(orig_values[i]):
                old = orig_values[i][j]
            if v != old:
                yield i, j, v
