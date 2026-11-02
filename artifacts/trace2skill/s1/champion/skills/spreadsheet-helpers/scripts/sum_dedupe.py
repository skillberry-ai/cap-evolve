import pandas as pd


def sum_dedupe(df, key_cols, sum_cols):
    """Return a copy of df with one row per key.

    Each row's sum_cols values are replaced with the group total, then only the
    first occurrence of each key is kept. Original row order and non-summed
    column values (from the first occurrence) are preserved.

    Args:
        df: pandas DataFrame.
        key_cols: str or list of str, column(s) identifying duplicate rows.
        sum_cols: str or list of str, numeric column(s) to total per key.

    Returns:
        DataFrame with duplicates collapsed; one row per key.
    """
    if isinstance(key_cols, str):
        key_cols = [key_cols]
    if isinstance(sum_cols, str):
        sum_cols = [sum_cols]
    out = df.copy()
    for col in sum_cols:
        out[col] = out.groupby(list(key_cols))[col].transform("sum")
    return out.drop_duplicates(subset=list(key_cols), keep="first").reset_index(drop=True)
