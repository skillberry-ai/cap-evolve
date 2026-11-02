
import openpyxl

def verify_output(path, sheet_name=None, cell_range=None):
    """Re-open a saved workbook and print/return values in a target range.
    If sheet_name is None, uses the first sheet. If cell_range is None, prints
    a 10x10 sample of the used range."""
    wb = openpyxl.load_workbook(path, data_only=False)
    ws = wb[sheet_name] if sheet_name else wb.worksheets[0]
    if cell_range:
        cells = ws[cell_range]
        if not isinstance(cells, tuple):
            cells = ((cells,),)
        results = []
        for row in cells:
            for c in (row if isinstance(row, tuple) else (row,)):
                print(c.coordinate, repr(c.value), type(c.value).__name__)
                results.append((c.coordinate, c.value, type(c.value).__name__))
        return results
    else:
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 10),
                                max_col=min(ws.max_column, 10)):
            for c in row:
                if c.value is not None:
                    print(c.coordinate, repr(c.value), type(c.value).__name__)
        return None
