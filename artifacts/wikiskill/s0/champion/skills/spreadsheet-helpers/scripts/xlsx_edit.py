"""Deterministic openpyxl helpers: in-place editing, range parsing, verification, diffing."""
import re
import openpyxl


def parse_ref(ref):
    """Parse a ref like "'Total'!O5:Z12", "'Main!'A2:M70", "Sheet1!A1" or "A1:B2".
    Returns (sheet_name_or_None, min_row, min_col, max_row, max_col)."""
    ref = str(ref).strip()
    sheet = None
    if '!' in ref:
        sheet_part, ref = ref.split('!', 1)
        sheet = sheet_part.strip().strip("'").strip()
        sheet = sheet.rstrip("'") if sheet.endswith("'") else sheet
    ref = ref.strip().replace('$', '')
    if ':' in ref:
        a, b = ref.split(':', 1)
    else:
        a = b = ref
        if '!' in a:
            sheet, a = a.split('!', 1)
    from openpyxl.utils import range_boundaries
    min_col, min_row, max_col, max_row = range_boundaries('%s:%s' % (a, b))
    return sheet, min_row, min_col, max_row, max_col


def _as_wb(path_or_wb):
    if isinstance(path_or_wb, str):
        return openpyxl.load_workbook(path_or_wb)
    return path_or_wb


def open_inplace(input_path, output_path):
    """Load the ORIGINAL workbook (formulas + formatting intact), save a copy to
    output_path, and return the workbook for in-place cell edits."""
    wb = openpyxl.load_workbook(input_path)
    wb.save(output_path)
    return wb


def read_range(path_or_wb, sheet, ref):
    """Return the current values of the range as a 2-D list [row][col]."""
    wb = _as_wb(path_or_wb)
    ws = wb[sheet]
    _, min_row, min_col, max_row, max_col = parse_ref(ref if '!' not in str(ref) else str(ref).split('!', 1)[1])
    return [[ws.cell(row=r, column=c).value for c in range(min_col, max_col + 1)]
            for r in range(min_row, max_row + 1)]


def write_cells(ws, ref, values, start_row=None, start_col=None):
    """Write a 2-D (or 1-D) list of values into the range beginning at its top-left.
    None entries are skipped so partial fills never erase existing content."""
    _, min_row, min_col, _, _ = parse_ref(ref if '!' not in str(ref) else str(ref).split('!', 1)[1])
    if start_row is not None:
        min_row = start_row
    if start_col is not None:
        min_col = start_col
    if values and not isinstance(values[0], (list, tuple)):
        values = [values]
    for i, row_vals in enumerate(values):
        for j, v in enumerate(row_vals):
            if v is None:
                continue
            ws.cell(row=min_row + i, column=min_col + j).value = v


def _cells_of(ws, min_row, min_col, max_row, max_col):
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            yield ws.cell(row=r, column=c)


def verify_range(path, sheet, ref, expected):
    """Re-open the saved file and per-cell compare answer range against expected.
    Prints each mismatch with coordinates. Returns True if all match."""
    wb = openpyxl.load_workbook(path)
    ws = wb[sheet]
    _, min_row, min_col, max_row, max_col = parse_ref(ref if '!' not in str(ref) else str(ref).split('!', 1)[1])
    if expected and not isinstance(expected[0], (list, tuple)):
        expected = [expected]
    ok = True
    for i, row_vals in enumerate(expected):
        for j, exp in enumerate(row_vals):
            r, c = min_row + i, min_col + j
            if r > max_row or c > max_col:
                continue
            got = ws.cell(row=r, column=c).value
            if got != exp or type(got) is not type(exp):
                ok = False
                print('MISMATCH %s%d: got %r (%s), expected %r (%s)'
                      % (openpyxl.utils.get_column_letter(c), r, got, type(got).__name__, exp, type(exp).__name__))
    print('verify_range: %s' % ('ALL MATCH' if ok else 'MISMATCHES FOUND'))
    return ok


def _same(a, b):
    if a == b and type(a) is type(b):
        return True
    try:
        return float(a) == float(b) and isinstance(a, (int, float)) and isinstance(b, (int, float))
    except (TypeError, ValueError):
        return False


def diff_report(input_path, output_path, answer_ref=None, max_print=50):
    """Report every cell that differs between input and output. Cells outside
    answer_ref are flagged OUT-OF-RANGE (collateral damage); in-range value/type
    changes are listed so you can confirm each was intentional."""
    wb_in = openpyxl.load_workbook(input_path)
    wb_out = openpyxl.load_workbook(output_path)
    ans_sheet = ans_box = None
    if answer_ref:
        ans_sheet, r1, c1, r2, c2 = parse_ref(answer_ref)
        ans_box = (r1, c1, r2, c2)
    diffs = []
    for name in wb_in.sheetnames:
        ws_in, ws_out = wb_in[name], wb_out[name]
        max_r = max(ws_in.max_row, ws_out.max_row)
        max_c = max(ws_in.max_column, ws_out.max_column)
        for r in range(1, max_r + 1):
            for c in range(1, max_c + 1):
                a = ws_in.cell(row=r, column=c).value
                b = ws_out.cell(row=r, column=c).value
                if _same(a, b):
                    continue
                coord = '%s!%s%d' % (name, openpyxl.utils.get_column_letter(c), r)
                if ans_sheet is not None and name == ans_sheet and ans_box[0] <= r <= ans_box[2] and ans_box[1] <= c <= ans_box[3]:
                    tag = 'IN-RANGE'
                else:
                    tag = 'OUT-OF-RANGE'
                if a is not None and b is not None and type(a) is not type(b):
                    tag += '/TYPE-CHANGE'
                diffs.append((coord, tag, a, b))
    for coord, tag, a, b in diffs[:max_print]:
        print('%s %s: input=%r output=%r' % (tag, coord, a, b))
    if len(diffs) > max_print:
        print('... and %d more diffs' % (len(diffs) - max_print))
    print('diff_report: %d cell(s) differ (%d OUT-OF-RANGE)'
          % (len(diffs), sum(1 for d in diffs if d[1].startswith('OUT'))))
    return diffs
