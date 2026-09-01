#!/usr/bin/env python3
"""Category attribution via global PCA + R^2 decomposition.

Answers: "which CATEGORY of drivers contributes most to a response variable,
and by what percentage?" The reported factor is the CATEGORY NAME
(e.g. Heat / Flow / Wind / Human) -- NOT an individual measured column.

Method (generalizes; no factor index or answer hardcoded):
  1. Merge every CSV in --data-dir on their shared key column (e.g. Year).
  2. Optionally derive combined variables (NetRadiation = Longwave + Shortwave).
  3. Classify each numeric predictor column into a category by keyword.
  4. Standardize predictors, run ONE global PCA (varimax), n_factors = #categories.
  5. Map each factor to the category whose variables load most on it (by summed |loading|).
  6. Contribution_cat = R2_full - R2_without_that_factor (summed if >1 factor maps to a cat).
  7. Report the dominant category and its contribution as a percentage (rounded).

Usage:
  python attribution.py --data-dir /root/data --response WaterTemperature \
      --output /root/output/dominant_factor.csv

Edit CATEGORY_KEYWORDS below if a task uses different category names/variables.
"""
import argparse, glob, os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from factor_analyzer import FactorAnalyzer

# Keyword -> category. Substring match on column name (case-insensitive).
CATEGORY_KEYWORDS = {
    "Heat":  ["temp", "radiation", "shortwave", "longwave", "humid", "cloud", "heat"],
    "Flow":  ["precip", "inflow", "outflow", "streamflow", "evap", "runoff", "flow", "discharge"],
    "Wind":  ["wind", "gust", "pressure"],
    "Human": ["developed", "agricultur", "impervious", "population", "industrial", "landuse", "urban"],
}

def classify(col):
    c = col.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in c for k in kws):
            return cat
    return None

def calc_r2(X, y):
    m = LinearRegression().fit(X, y)
    p = m.predict(X)
    return 1 - np.sum((y - p) ** 2) / np.sum((y - np.mean(y)) ** 2)

def load_merged(data_dir):
    frames = [pd.read_csv(f) for f in sorted(glob.glob(os.path.join(data_dir, "*.csv")))]
    if not frames:
        sys.exit(f"No CSVs found in {data_dir}")
    # find a key column common to all frames (e.g. Year)
    common = set(frames[0].columns)
    for f in frames[1:]:
        common &= set(f.columns)
    key = next((c for c in frames[0].columns if c in common), None)
    df = frames[0]
    for f in frames[1:]:
        df = df.merge(f, on=key) if key else pd.concat([df, f], axis=1)
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--response", required=True, help="response/outcome column name")
    ap.add_argument("--output", default=None, help="write dominant_factor.csv here")
    args = ap.parse_args()

    df = load_merged(args.data_dir)
    # derive NetRadiation when both components exist
    if "NetRadiation" not in df.columns and {"Longwave", "Shortwave"} <= set(df.columns):
        df["NetRadiation"] = df["Longwave"] + df["Shortwave"]

    y = df[args.response].astype(float).values
    # predictors: numeric cols that classify into a category (skip raw Long/Shortwave
    # once NetRadiation exists, and skip the response + non-numeric keys)
    skip = {args.response}
    if "NetRadiation" in df.columns:
        skip |= {"Longwave", "Shortwave"}
    var2cat, pca_vars = {}, []
    for col in df.columns:
        if col in skip:
            continue
        if not np.issubdtype(df[col].dtype, np.number):
            continue
        cat = classify(col)
        if cat:
            var2cat[col] = cat
            pca_vars.append(col)

    cats = sorted(set(var2cat.values()))
    if not pca_vars:
        sys.exit("No predictor columns matched any category keyword.")

    X = StandardScaler().fit_transform(df[pca_vars].values)
    n_factors = len(cats)
    fa = FactorAnalyzer(n_factors=n_factors, rotation="varimax")
    fa.fit(X)
    scores = fa.transform(X)
    L = fa.loadings_

    # map each factor -> category with the largest summed |loading|
    factor_cat = {}
    for f in range(n_factors):
        load = {}
        for vi, v in enumerate(pca_vars):
            c = var2cat[v]
            load[c] = load.get(c, 0.0) + abs(L[vi, f])
        factor_cat[f] = max(load, key=load.get)

    full = calc_r2(scores, y)
    contrib = {c: 0.0 for c in cats}
    for f in range(n_factors):
        keep = [j for j in range(n_factors) if j != f]
        contrib[factor_cat[f]] += (full - calc_r2(scores[:, keep], y)) * 100

    dominant = max(contrib, key=contrib.get)
    dom_pct = round(contrib[dominant])

    print("Category contributions (percentage points of R^2):")
    for c in sorted(contrib, key=contrib.get, reverse=True):
        print(f"  {c}: {contrib[c]:.1f}")
    print(f"\nDominant category: {dominant} ({dom_pct}%)")

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as fh:
            fh.write("variable,contribution\n")
            fh.write(f"{dominant},{dom_pct}\n")
        print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
