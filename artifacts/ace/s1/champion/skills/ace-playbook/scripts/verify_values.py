
import openpyxl
from openpyxl.utils import range_boundaries


def verify_values(output_path, sheet_name, cell_range, original_path=None, original_sheet=None):
    """Re-open the saved output with data_only=True and return (coord, value) for
    the target range. If original_path is given, also diff every cell of the sheet
    against the original's computed values and report cells that became empty or
    changed outside the target range (collateral damage from re-saving formulas)."""
    wb = openpyxl.load_workbook(output_path, data_only=True)
    ws = wb[sheet_name]
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    target = []
    empty_in_target = []
    for row in ws.iter_rows(min_row=min_row, max_row=max_row,
                            min_col=min_col, max_col=max_col):
        for c in row:
            target.append((c.coordinate, c.value))
            if c.value is None:
                empty_in_target.append(c.coordinate)
    print('TARGET RANGE VALUES:')
    for coord, v in target:
        print(coord, repr(v))
    print('EMPTY CELLS IN TARGET:', empty_in_target or 'none')
    issues = []
    if original_path:
        owb = openpyxl.load_workbook(original_path, data_only=True)
        ows = owb[original_sheet or sheet_name]
        max_r = max(ws.max_row, ows.max_row)
        max_c = max(ws.max_column, ows.max_column)
        for r in range(1, max_r + 1):
            for col in range(1, max_c + 1):
                ov = ows.cell(row=r, column=col).value
                nv = ws.cell(row=r, column=col).value
                coord = ws.cell(row=r, column=col).coordinate
                in_target = (min_row <= r <= max_row and min_col <= col <= max_col)
                if not in_target and ov != nv:
                    issues.append((coord, 'was', repr(ov), 'now', repr(nv)))
    if issues:
        print('COLLATERAL CHANGES OUTSIDE TARGET:')
        for i in issues:
            print(i)
    else:
        print('No collateral changes outside target.' if original_path else '')
    return {'target': target, 'empty_in_target': empty_in_target, 'issues': issues}
