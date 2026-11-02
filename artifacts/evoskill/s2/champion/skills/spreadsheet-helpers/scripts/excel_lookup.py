"""Excel-VLOOKUP-semantics lookup helper.

Usage:
    from skills.spreadsheet_helpers.excel_lookup import excel_lookup
    values = excel_lookup(src_path, "Lookup", "A", "D", [1111, "1112", 2043])
    # values is a list aligned with `keys`; missing keys yield `default`
    # (which defaults to the string '#N/A').

Reads the lookup sheet once, builds an ordered first-occurrence-wins mapping
(exact-match VLOOKUP semantics: when a key appears multiple times, the FIRST
row wins — NOT the last, unlike `dict[key] = value`), and coerces keys for
matching so int 1111 and str '1111' match (strings are trimmed; numeric-looking
strings compare numerically; other strings compare case-insensitively).

Use this whenever an instruction says VLOOKUP or 'populate column X by matching
IDs from another sheet' — never a hand-rolled dict comprehension, which keeps
the LAST duplicate and silently fails on mixed int/str IDs.
"""


def _norm_key(k):
    """Normalize a key for matching: numeric identity for numbers and numeric
    strings; trimmed, lowercased strings otherwise; None passthrough."""
    if k is None:
        return ("none",)
    if isinstance(k, bool):
        return ("bool", k)
    if isinstance(k, (int, float)):
        return ("num", float(k))
    if isinstance(k, str):
        s = k.strip()
        if s != "":
            try:
                return ("num", float(s))
            except ValueError:
                pass
        return ("str", s.lower())
    return ("other", str(k))


def excel_lookup(src_path, sheet, key_col, value_col, keys, default="#N/A"):
    from openpyxl import load_workbook
    from openpyxl.utils import column_index_from_string
    if isinstance(key_col, str):
        key_col = column_index_from_string(key_col)
    if isinstance(value_col, str):
        value_col = column_index_from_string(value_col)

    wb = load_workbook(src_path, data_only=False, read_only=True)
    if sheet not in wb.sheetnames:
        wb.close()
        raise KeyError(f"sheet {sheet!r} not in {wb.sheetnames}")
    ws = wb[sheet]

    mapping = {}  # normalized key -> value; first occurrence wins
    for row in ws.iter_rows(min_col=min(key_col, value_col),
                            max_col=max(key_col, value_col)):
        k = row[abs(key_col - min(key_col, value_col))].value
        v = row[abs(value_col - min(key_col, value_col))].value
        if k is None or (isinstance(k, str) and k.strip() == ""):
            continue
        nk = _norm_key(k)
        if nk not in mapping:
            mapping[nk] = v
    wb.close()

    return [mapping.get(_norm_key(k), default) for k in keys]
