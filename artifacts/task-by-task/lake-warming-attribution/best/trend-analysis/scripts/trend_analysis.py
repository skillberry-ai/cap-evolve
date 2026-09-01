#!/usr/bin/env python3
"""Long-term trend detection for environmental time series.

Uses the non-parametric Sen's slope + Mann-Kendall test (via pymannkendall),
which is the correct default for environmental/climate series: it is robust to
outliers, makes no normality assumption, and does not require evenly spaced
years. Ordinary least-squares linear regression is NOT used for the reported
slope/p-value, because on short or autocorrelated environmental records its
p-value is unstable and can land just above 0.05 for a trend that is in fact
significant.

General usage (nothing task-specific is hardcoded):

    python trend_analysis.py --input <data.csv> [--column <name>] \
        [--output <out.csv>] [--decimals 2]

--column defaults to the single numeric measurement column (any numeric column
whose name is not a year/time index such as "Year"/"year"/"time"/"date").
--output defaults to /root/output/trend_result.csv.

Writes a CSV with columns: slope,p_value  (Sen's slope per time step and the
Mann-Kendall two-sided p-value), each rounded to --decimals places.
"""
import argparse
import os
import sys

import pandas as pd
import pymannkendall as mk


TIME_LIKE = {"year", "years", "time", "date", "datetime", "yr", "index"}


def pick_value_column(df, explicit):
    if explicit:
        if explicit not in df.columns:
            sys.exit(f"column '{explicit}' not found; have {list(df.columns)}")
        return explicit
    numeric = [c for c in df.columns
               if pd.api.types.is_numeric_dtype(df[c]) and c.strip().lower() not in TIME_LIKE]
    if len(numeric) == 1:
        return numeric[0]
    if not numeric:
        sys.exit(f"no numeric measurement column found in {list(df.columns)}")
    # More than one candidate: fall back to the last numeric column and warn.
    sys.stderr.write(
        f"multiple numeric columns {numeric}; using '{numeric[-1]}' "
        f"(pass --column to be explicit)\n")
    return numeric[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="path to the time-series CSV")
    ap.add_argument("--column", default=None, help="measurement column (auto-detected if omitted)")
    ap.add_argument("--output", default="/root/output/trend_result.csv")
    ap.add_argument("--decimals", type=int, default=2)
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    col = pick_value_column(df, args.column)
    values = df[col].dropna().values
    if len(values) < 4:
        sys.exit(f"need at least 4 points, got {len(values)}")

    result = mk.original_test(values)
    slope = round(float(result.slope), args.decimals)
    p_value = round(float(result.p), args.decimals)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write("slope,p_value\n")
        f.write(f"{slope},{p_value}\n")

    print(f"column={col} n={len(values)} slope={slope} p_value={p_value} "
          f"trend={result.trend} -> {args.output}")


if __name__ == "__main__":
    main()
