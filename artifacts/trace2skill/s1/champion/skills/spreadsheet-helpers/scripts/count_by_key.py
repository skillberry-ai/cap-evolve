import pandas as pd


def group_and_count(df, key_col, value_cols, codes):
    """Count occurrences of each code in value_cols, grouped by key.

    Forward-fills the key column so multi-row records (e.g. a name on the
    first of two rows, second row blank/merged) are fully attributed.

    Args:
        df: DataFrame of the sheet.
        key_col: column label or positional index used as the grouping key.
        value_cols: list of column labels or positional indexes to scan.
        codes: list of code strings to count (e.g. ['P', 'L']).

    Returns:
        DataFrame indexed by key with one column per code containing counts.
    """
    work = df.copy()
    if isinstance(key_col, int):
        keys = work.iloc[:, key_col]
    else:
        keys = work[key_col]
    keys = keys.ffill()
    if isinstance(value_cols[0], int):
        vals = work.iloc[:, list(value_cols)].copy()
    else:
        vals = work[value_cols].copy()
    vals['__key__'] = keys.values
    result = {}
    for code in codes:
        result[code] = vals.set_index('__key__').apply(
            lambda row, c=code: sum(1 for v in row if str(v).strip() == c), axis=1
        ).groupby(level=0).sum()
    out = pd.DataFrame(result)
    out.index.name = str(key_col)
    return out
