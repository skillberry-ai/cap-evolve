"""Verification helpers: re-open a saved workbook, print the answer range,
flag cells modified outside the answer range relative to an input file,
and check that a target range is fully populated."""

import re
from openpyxl import load_workbook


def _parse_range(answer_range):
    """Parse 'Sheet1'!C2:D5000 or Sheet1!C2:D5000 into (sheet, min_col, min_row, max_col, max_row)."""
    m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$", answer_range.strip())
    if not m:
        raise ValueError("Cannot parse range: %r" % answer_range)
    sheet = m.group(1) or m.group(2)
    c1, r1 = m.group(3), int(m.group(4))
    c2 = m.group(5) or c1
    r2 = int(m.group(6)) if m.group(6) else r1

    def col_to_num(col):
        n = 0
        for ch in col:
            n = n * 26 + (ord(ch) - 64)
        return n

    return sheet, col_to_num(c1), r1, col_to_num(c2), r2


def _cells_in_range(ws, min_col, min_row, max_col, max_row, limit=200):
    out = []
    for row in ws.iter_rows(min_row=min_row, max_row=min_row + limit - 1,
                            min_col=min_col, max_col=max_col):
        for cell in row:
            if cell.value is not None:
                out.append((cell.coordinate, cell.value))
    return out


def verify_output(output_path, answer_range, input_path=None):
    """Re-open the saved workbook, print answer-range contents, and report
    cells changed outside the answer range (if input_path given).
    Returns a dict with the findings."""
    sheet_name, c1, r1, c2, r2 = _parse_range(answer_range)
    wb = load_workbook(output_path)
    if sheet_name not in wb.sheetnames:
        print("MISSING SHEET: %r not in %r (sheets: %s)" % (sheet_name, output_path, wb.sheetnames))
        return {"sheet_found": False}
    ws = wb[sheet_name]
    cells = _cells_in_range(ws, c1, r1, c2, r2)
    print("ANSWER RANGE %s: %d non-empty cells (showing up to 200)" % (answer_range, len(cells)))
    for coord, val in cells[:200]:
        print("  %s = %r" % (coord, val))

    findings = {"sheet_found": True, "non_empty": len(cells), "outside_changes": []}

    if input_path is not None:
        wb_in = load_workbook(input_path)
        for name in wb.sheetnames:
            if name not in wb_in.sheetnames:
                findings["outside_changes"].append((name, "sheet", "new sheet added"))
                continue
            ws_new, ws_old = wb[name], wb_in[name]
            for row in ws_new.iter_rows():
                for cell in row:
                    if name == sheet_name and c1 <= cell.column <= c2 and r1 <= cell.row <= r2:
                        continue
                    old = ws_old.cell(row=cell.row, column=cell.column).value
                    if cell.value != old:
                        findings["outside_changes"].append((name, cell.coordinate, "%r -> %r" % (old, cell.value)))
        if findings["outside_changes"]:
            print("WARNING: %d cells changed OUTSIDE the answer range:" % len(findings["outside_changes"]))
            for item in findings["outside_changes"][:50]:
                print("  %s" % (item,))
        else:
            print("OK: no cells modified outside the answer range.")
    return findings


def explore(path, sheet=None, n=10):
    """Print sheet names, dimensions, and the first n rows of a sheet to
    disambiguate instructions against the actual data."""
    wb = load_workbook(path, read_only=True)
    print("SHEETS: %s" % wb.sheetnames)
    names = [sheet] if sheet else wb.sheetnames
    for name in names:
        ws = wb[name]
        print("--- %s: %d rows x %d cols ---" % (name, ws.max_row, ws.max_column))
        for i, row in enumerate(ws.iter_rows(max_row=n, values_only=True)):
            print("  row %d: %s" % (i + 1, row))
    wb.close()


def check_filled(path, sheet, ref):
    """Check every cell in range `ref` of `sheet` holds a non-None value.

    Prints each empty cell and returns True only if all cells are filled.
    """
    ws = load_workbook(path, data_only=False)[sheet]
    empty = []
    for row in ws[ref]:
        for c in row:
            if c.value is None:
                empty.append(c.coordinate)
    if empty:
        print('FAIL: empty cells in %s!%s: %s' % (sheet, ref, ', '.join(empty)))
        return False
    print('OK: all cells in %s!%s are filled' % (sheet, ref))
    return True
