"""Deterministic INDEX/MATCH-style cross-table fill.

Builds a (row_label, col_label) -> value map from a source block and writes it
into a target block, writing `blank_value` (default 0, matching INDEX/MATCH
semantics for empty source cells) wherever the source cell is empty or the
pair is missing. Returns (cells_written, blanks_written).
"""


def crossfill(ws, src_header_row, src_label_col, src_first_row, src_last_row,
              src_first_col, src_last_col, tgt_header_row, tgt_label_col,
              tgt_first_row, tgt_last_row, tgt_first_col, tgt_last_col,
              blank_value=0):
    lookup = {}
    for r in range(src_first_row, src_last_row + 1):
        label = ws.cell(row=r, column=src_label_col).value
        if label is None:
            continue
        for c in range(src_first_col, src_last_col + 1):
            header = ws.cell(row=src_header_row, column=c).value
            if header is None:
                continue
            lookup[(str(label).strip(), str(header).strip())] = ws.cell(row=r, column=c).value
    written = blanks = 0
    for r in range(tgt_first_row, tgt_last_row + 1):
        label = ws.cell(row=r, column=tgt_label_col).value
        for c in range(tgt_first_col, tgt_last_col + 1):
            header = ws.cell(row=tgt_header_row, column=c).value
            val = lookup.get((str(label).strip(), str(header).strip())) if (label is not None and header is not None) else None
            if val is None:
                val = blank_value
                blanks += 1
            ws.cell(row=r, column=c, value=val)
            written += 1
    return written, blanks


