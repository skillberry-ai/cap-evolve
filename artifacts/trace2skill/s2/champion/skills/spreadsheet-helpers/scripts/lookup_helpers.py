"""Helpers for VLOOKUP-style lookups and post-save verification.

General, offline, deterministic. No task-specific logic.
"""


def vlookup_map(lookup_df, key_col, value_col):
    """Build a dict mapping key -> value from a lookup table.

    Mimics VLOOKUP semantics: NaN/None keys are dropped and can never
    match, and the first occurrence of a duplicate key wins.
    """
    mapping = {}
    for k, v in zip(lookup_df[key_col], lookup_df[value_col]):
        if k is None:
            continue
        try:
            if k != k:  # NaN check that works for floats
                continue
        except TypeError:
            pass
        if k not in mapping:
            mapping[k] = v
    return mapping


def apply_vlookup(main_df, key_col, lookup_df, value_col, target_col):
    """Apply VLOOKUP semantics to main_df, writing results to target_col.

    Rows whose key is missing/NaN, or whose key is not found in the
    lookup table, get NaN in target_col (a real VLOOKUP would leave
    these blank / #N/A). Never merges on NaN keys.
    """
    mapping = vlookup_map(lookup_df, key_col, value_col)
    values = []
    for k in main_df[key_col]:
        if k is None:
            values.append(float("nan"))
            continue
        try:
            if k != k:
                values.append(float("nan"))
                continue
        except TypeError:
            pass
        values.append(mapping.get(k, float("nan")))
    main_df[target_col] = values
    return main_df


def check_saved(path, checks):
    """Re-open a saved workbook/csv and run verification checks.

    checks: list of (name, callable) where callable receives the loaded
    DataFrame (csv) or dict of DataFrames (excel) and returns True/False.
    Prints PASS/FAIL per check and returns overall bool.
    """
    import pandas as pd

    if str(path).lower().endswith(('.xlsx', '.xls', '.xlsm')):
        data = pd.read_excel(path, sheet_name=None)
    else:
        data = pd.read_csv(path)
    ok = True
    for name, fn in checks:
        passed = bool(fn(data))
        print(('PASS' if passed else 'FAIL'), '-', name)
        ok = ok and passed
    print('OVERALL:', 'PASS' if ok else 'FAIL')
    return ok
