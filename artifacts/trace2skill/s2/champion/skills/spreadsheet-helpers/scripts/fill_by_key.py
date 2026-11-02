"""Key-based cell filling between sheets. Deterministic, offline, general."""
from openpyxl import load_workbook


def fill_by_key(out_path, dest_sheet, key_col, target_col, src_sheet, src_key_col,
                src_value_col, match_mode="exact", start_row=1):
    """Fill dest[target_col] only where dest[key_col] matches src[src_key_col].

    - key_col / target_col: column letters on the destination sheet (e.g. 'A', 'H').
    - src_key_col / src_value_col: column letters on the source sheet (same workbook).
    - match_mode 'exact': string/number equality after str().strip() normalisation.
    - match_mode 'contains': dest key matches if it appears among comma/space-separated
      tokens of the src key cell (for one source row holding several keys).
    - Only cells with a computed match are written; all other cells are left untouched,
    so pre-existing values are preserved. Returns a report dict.
    """
    wb = load_workbook(out_path)
    dest, src = wb[dest_sheet], wb[src_sheet]
    lookup = {}
    for r in range(start_row, src.max_row + 1):
        k = src[f"{src_key_col}{r}"].value
        if k is None:
            continue
        v = src[f"{src_value_col}{r}"].value
        if match_mode == "contains":
            for tok in str(k).replace(",", " ").split():
                lookup.setdefault(tok.strip(), v)
        else:
            lookup[str(k).strip()] = v
    written, unmatched, preserved = 0, [], 0
    for r in range(start_row, dest.max_row + 1):
        k = dest[f"{key_col}{r}"].value
        if k is None:
            continue
        key = str(k).strip()
        if key in lookup:
            dest[f"{target_col}{r}"] = lookup[key]
            written += 1
        else:
            unmatched.append((r, key))
            if dest[f"{target_col}{r}"].value is not None:
                preserved += 1
    wb.save(out_path)
    return {"written": written, "unmatched_keys": unmatched,
            "unmatched_with_existing_value": preserved,
            "lookup_size": len(lookup)}
