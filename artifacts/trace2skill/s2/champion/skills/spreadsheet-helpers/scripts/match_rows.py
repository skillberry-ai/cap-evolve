import pandas as pd


def match_by_keys(left_df, right_df, left_keys, right_keys=None):
    """Match rows of left_df to rows of right_df by key column(s).

    Args:
        left_df, right_df: pandas DataFrames.
        left_keys: str or list of str — key column name(s) in left_df.
        right_keys: str or list of str — key column name(s) in right_df;
            defaults to left_keys.

    Returns:
        List of (left_index, right_index) pairs, one per left row that has a
        match. Left rows with no match are omitted.

    Raises:
        KeyError: if a key column is missing.
        ValueError: if a key combination appears more than once in either
            frame (matching would be ambiguous).
    """
    if isinstance(left_keys, str):
        left_keys = [left_keys]
    if right_keys is None:
        right_keys = list(left_keys)
    elif isinstance(right_keys, str):
        right_keys = [right_keys]
    if len(left_keys) != len(right_keys):
        raise ValueError("left_keys and right_keys must have the same length")

    for col in left_keys:
        if col not in left_df.columns:
            raise KeyError("left_df missing key column: %r" % col)
    for col in right_keys:
        if col not in right_df.columns:
            raise KeyError("right_df missing key column: %r" % col)

    def _key_tuple(row, cols):
        return tuple(row[c] for c in cols)

    right_map = {}
    for idx, row in right_df.iterrows():
        k = _key_tuple(row, right_keys)
        if k in right_map:
            raise ValueError(
                "Duplicate key %r in right frame; matching is ambiguous" % (k,)
            )
        right_map[k] = idx

    left_seen = {}
    pairs = []
    for idx, row in left_df.iterrows():
        k = _key_tuple(row, left_keys)
        if k in left_seen:
            raise ValueError(
                "Duplicate key %r in left frame; matching is ambiguous" % (k,)
            )
        left_seen[k] = idx
        if k in right_map:
            pairs.append((idx, right_map[k]))
    return pairs
