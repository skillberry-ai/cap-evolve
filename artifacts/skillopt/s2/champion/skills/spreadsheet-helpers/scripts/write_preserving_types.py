"""Write a DataFrame (or list of rows) to a sheet while preserving per-cell types.

Avoids the pandas to_excel failure where integer-like values in columns with
blanks are coerced to floats (66 -> 66.0). Whole-number floats become ints,
NaN/None become truly empty cells, everything else is written as-is.
"""


def write_df_preserving_types(writer_path, df, sheet_name, start_row=1, start_col=1, header=True):
    """Append/overwrite `sheet_name` in the workbook at writer_path with df's values.

    Creates the workbook or sheet if missing; preserves other sheets. Writes
    whole-number floats as ints and NaN/None as empty cells. Returns the worksheet.
    """
    import math
    import pandas as pd
    from openpyxl import load_workbook
    import os

    os.makedirs(os.path.dirname(writer_path) or '.', exist_ok=True)
    if os.path.exists(writer_path):
        wb = load_workbook(writer_path)
    else:
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)

    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)

    def norm(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v

    r = start_row
    if header:
        for j, col in enumerate(df.columns):
            ws.cell(row=r, column=start_col + j, value=str(col))
        r += 1
    for _, row in df.iterrows():
        for j, v in enumerate(row):
            ws.cell(row=r, column=start_col + j, value=norm(v))
        r += 1
    wb.save(writer_path)
    return ws

