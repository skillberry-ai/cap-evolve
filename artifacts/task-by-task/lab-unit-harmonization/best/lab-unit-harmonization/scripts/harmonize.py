#!/usr/bin/env python3
"""
Deterministic clinical lab unit-harmonization pipeline.

Run this script instead of re-implementing the harmonization by hand:

    python3 scripts/harmonize.py <input_csv> <output_csv>

Defaults (task convention) if args are omitted:
    input  = /root/environment/data/ckd_lab_data.csv
    output = /root/ckd_lab_data_harmonized.csv

Pipeline (in order):
  0. Drop patient rows that have ANY missing value in a numeric column.
  1. Parse each raw value to float, handling scientific notation
     (1.5e3 -> 1500), European decimals (12,34 -> 12.34) and whitespace.
  2. Range-based unit detection: if a value is outside the feature's
     expected physiological range, try that feature's candidate
     conversion factors and keep the FIRST converted value that lands
     in range (no factor -> value left unchanged for now).
  3. Clamp any value that is STILL outside [min, max] to the nearest
     boundary. Some records are genuine physiological outliers or have
     no unit that maps into range; the harmonized output must have every
     value inside the expected range, so residuals are clamped, not dropped.
  4. Format every numeric value as X.XX (exactly 2 decimals).

Non-feature/identifier columns (e.g. patient_id) are preserved unchanged.
The factor and range tables below ARE the domain knowledge from
reference/ckd_lab_features.md in machine-readable form; edit them there and
here together if the reference changes. Do not hardcode per-row answers.
"""
import sys
import pandas as pd
import numpy as np

# Expected physiological ranges (min, max) per feature.
RANGES = {
    'Serum_Creatinine': (0.2, 20.0), 'BUN': (5.0, 200.0), 'eGFR': (0.0, 150.0),
    'Cystatin_C': (0.4, 10.0), 'BUN_Creatinine_Ratio': (5.0, 50.0),
    'Sodium': (110.0, 170.0), 'Potassium': (2.0, 8.5), 'Chloride': (70.0, 140.0),
    'Bicarbonate': (5.0, 40.0), 'Anion_Gap': (0.0, 40.0), 'Magnesium': (0.5, 10.0),
    'Serum_Calcium': (5.0, 15.0), 'Ionized_Calcium': (0.8, 2.0), 'Phosphorus': (1.0, 15.0),
    'Intact_PTH': (5.0, 2500.0), 'Vitamin_D_25OH': (4.0, 200.0), 'Vitamin_D_1_25OH': (5.0, 100.0),
    'Alkaline_Phosphatase': (20.0, 2000.0), 'Hemoglobin': (3.0, 20.0), 'Hematocrit': (10.0, 65.0),
    'RBC_Count': (1.5, 7.0), 'WBC_Count': (0.5, 50.0), 'Platelet_Count': (10.0, 1500.0),
    'Serum_Iron': (10.0, 300.0), 'TIBC': (50.0, 600.0), 'Transferrin_Saturation': (0.0, 100.0),
    'Ferritin': (5.0, 5000.0), 'Reticulocyte_Count': (0.1, 10.0), 'Total_Bilirubin': (0.1, 30.0),
    'Direct_Bilirubin': (0.0, 15.0), 'Albumin_Serum': (1.0, 6.5), 'Total_Protein': (3.0, 12.0),
    'Prealbumin': (5.0, 50.0), 'CRP': (0.0, 50.0), 'Total_Cholesterol': (50.0, 500.0),
    'LDL_Cholesterol': (10.0, 300.0), 'HDL_Cholesterol': (10.0, 150.0),
    'Triglycerides': (30.0, 2000.0), 'Non_HDL_Cholesterol': (30.0, 400.0),
    'Glucose': (20.0, 800.0), 'HbA1c': (3.0, 20.0), 'Fructosamine': (150.0, 600.0),
    'Uric_Acid': (1.0, 20.0), 'Urine_Albumin': (0.0, 5000.0), 'Urine_Creatinine': (10.0, 500.0),
    'Albumin_to_Creatinine_Ratio_Urine': (0.0, 5000.0),
    'Protein_to_Creatinine_Ratio_Urine': (0.0, 20000.0), 'Urine_Protein': (0.0, 3000.0),
    'Urine_pH': (4.0, 9.0), 'Urine_Specific_Gravity': (1.0, 1.04),
    'BNP': (0.0, 5000.0), 'NT_proBNP': (0.0, 35000.0), 'Troponin_I': (0.0, 50.0),
    'Troponin_T': (0.0, 10.0), 'Free_T4': (0.2, 6.0), 'Free_T3': (1.0, 10.0),
    'pH_Arterial': (6.8, 7.8), 'pCO2_Arterial': (15.0, 100.0), 'pO2_Arterial': (30.0, 500.0),
    'Lactate': (0.3, 20.0), 'Beta2_Microglobulin': (0.5, 50.0), 'Aluminum': (0.0, 200.0),
}

# Candidate conversion factors (alt-unit value * factor -> conventional unit).
# Multiple factors are listed for analytes with >1 alternative unit; the first
# factor that brings an out-of-range value inside [min, max] wins.
FACTORS = {
    'Serum_Creatinine': [0.0113], 'BUN': [2.8, 0.357], 'Magnesium': [2.43, 1.215],
    'Serum_Calcium': [4.0, 2.0], 'Ionized_Calcium': [0.25], 'Phosphorus': [3.1],
    'Intact_PTH': [9.43], 'Vitamin_D_25OH': [0.4], 'Vitamin_D_1_25OH': [0.385],
    'Hemoglobin': [0.1, 1.611], 'Serum_Iron': [5.59], 'TIBC': [5.59],
    'Ferritin': [0.445], 'Total_Bilirubin': [0.058], 'Direct_Bilirubin': [0.058],
    'Albumin_Serum': [0.1], 'Total_Protein': [0.1], 'Prealbumin': [0.1, 100.0],
    'CRP': [0.1, 10.0], 'Total_Cholesterol': [38.67], 'LDL_Cholesterol': [38.67],
    'HDL_Cholesterol': [38.67], 'Triglycerides': [88.5], 'Non_HDL_Cholesterol': [38.67],
    'Glucose': [18.02], 'Uric_Acid': [0.0168], 'Urine_Albumin': [0.1, 10.0],
    'Urine_Creatinine': [0.0113, 0.113], 'Albumin_to_Creatinine_Ratio_Urine': [8.84],
    'Protein_to_Creatinine_Ratio_Urine': [8.84], 'Urine_Protein': [0.1],
    'BNP': [3.46], 'NT_proBNP': [8.47], 'Troponin_I': [0.001], 'Troponin_T': [0.001],
    'Free_T4': [0.078], 'Free_T3': [0.651], 'pCO2_Arterial': [7.5], 'pO2_Arterial': [7.5],
    'Lactate': [0.111], 'Aluminum': [26.98],
}

MISSING_TOKENS = {'', 'nan', 'none', 'null', 'na', 'n/a'}


def parse_value(value):
    """Parse a raw cell to float; return np.nan if it is missing/unparseable."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    s = str(value).strip()
    if s.lower() in MISSING_TOKENS:
        return np.nan
    # Scientific notation (e.g. 1.5e3, 3.338e+00)
    if 'e' in s.lower():
        try:
            return float(s)
        except ValueError:
            pass
    # European decimal separator: comma -> dot (this dataset uses ',' as decimal)
    if ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return np.nan


def harmonize_value(value, column):
    """Convert (if out of range) then clamp a single parsed float."""
    if pd.isna(value) or column not in RANGES:
        return value
    lo, hi = RANGES[column]
    if lo <= value <= hi:
        return value
    for factor in FACTORS.get(column, []):
        converted = value * factor
        if lo <= converted <= hi:
            return converted
    # No conversion mapped into range -> clamp residual to nearest boundary.
    return min(max(value, lo), hi)


def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else '/root/environment/data/ckd_lab_data.csv'
    out = sys.argv[2] if len(sys.argv) > 2 else '/root/ckd_lab_data_harmonized.csv'

    df = pd.read_csv(inp, dtype=str)
    feature_cols = [c for c in df.columns if c in RANGES]

    # Step 1: parse every feature cell to float.
    for col in feature_cols:
        df[col] = df[col].apply(parse_value)

    # Step 0: drop rows with ANY missing feature value.
    complete = df[feature_cols].notna().all(axis=1)
    df = df[complete].reset_index(drop=True)

    # Steps 2 + 3: convert out-of-range values, then clamp residuals.
    for col in feature_cols:
        df[col] = df[col].apply(lambda v, c=col: harmonize_value(v, c))

    # Step 4: format to exactly 2 decimals.
    for col in feature_cols:
        df[col] = df[col].apply(lambda v: f"{v:.2f}" if pd.notna(v) else '')

    df.to_csv(out, index=False)
    print(f"Harmonized {len(df)} rows x {df.shape[1]} cols -> {out}")


if __name__ == '__main__':
    main()
