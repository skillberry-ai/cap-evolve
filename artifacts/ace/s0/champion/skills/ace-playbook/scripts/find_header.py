from openpyxl.utils import get_column_letter

def locate_header(ws, text):
    """Scan the used range for a cell whose string value, stripped, equals text.
    Returns (row, col) of the first match, or None."""
    target = str(text).strip()
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 50)):
        for cell in row:
            if cell.value is not None and str(cell.value).strip() == target:
                return (cell.row, cell.column)
    return None

def print_sheet_preview(ws, max_rows=8, max_cols=None):
    """Print a raw preview of cell values for debugging layout."""
    max_cols = max_cols or ws.max_column
    for r in range(1, min(ws.max_row, max_rows) + 1):
        vals = []
        for c in range(1, max_cols + 1):
            v = ws.cell(row=r, column=c).value
            vals.append(repr(v))
        print(r, vals)
