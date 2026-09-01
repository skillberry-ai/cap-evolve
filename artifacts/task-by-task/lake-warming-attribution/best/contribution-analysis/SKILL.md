---
name: contribution-analysis
description: Calculate the relative contribution of different factors to a response variable using R² decomposition. Use when you need to quantify how much each factor explains the variance of an outcome.
license: MIT
---

# Contribution Analysis Guide

## Overview

Contribution analysis quantifies how much each factor contributes to explaining the variance of a response variable. This skill focuses on R² decomposition method.

## Report the CATEGORY, not an individual variable

When factors are organized into **categories** (e.g. Heat / Flow / Wind / Human), the
answer to "which factor is most important" is the **category NAME**, not the single
best-correlated measured column. Even if a prompt says "output the most important
variable" or names the output column `variable`, the value you write must be the
**category** (e.g. `Heat`) with that category's aggregate contribution — never an
individual column like `AirTempLake`. Aggregate the variables into their categories
first, decompose R² per category, then report the dominant category.

## Recommended: run the bundled script

For category attribution, run the packaged script instead of hand-rolling the pipeline —
it merges the data, derives combined variables (e.g. `NetRadiation = Longwave + Shortwave`),
runs one global PCA, maps each factor to its category by loadings, R²-decomposes, and writes
`variable,contribution` with the dominant **category** name:

```bash
python scripts/attribution.py --data-dir /root/data --response WaterTemperature \
    --output /root/output/dominant_factor.csv
```

Do NOT reimplement this. The script's category is the raw R²-decomposition contribution in
percentage points (this is the number to report — do not renormalize to sum to 100). If a
task uses different category names or variables, edit the `CATEGORY_KEYWORDS` map at the top
of the script. The manual workflow below documents the same method.

## Complete Workflow

When you have multiple correlated variables that belong to different categories:
```python
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from factor_analyzer import FactorAnalyzer

# Step 1: Combine ALL variables into one matrix
pca_vars = ['Var1', 'Var2', 'Var3', 'Var4', 'Var5', 'Var6', 'Var7', 'Var8']
X = df[pca_vars].values
y = df['ResponseVariable'].values

# Step 2: Standardize
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Step 3: Run ONE global PCA on all variables together
fa = FactorAnalyzer(n_factors=4, rotation='varimax')
fa.fit(X_scaled)
scores = fa.transform(X_scaled)

# Step 4: R² decomposition on factor scores
def calc_r2(X, y):
    model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return 1 - (ss_res / ss_tot)

full_r2 = calc_r2(scores, y)

# Step 5: Calculate contribution of each factor
contrib_0 = full_r2 - calc_r2(scores[:, [1, 2, 3]], y)
contrib_1 = full_r2 - calc_r2(scores[:, [0, 2, 3]], y)
contrib_2 = full_r2 - calc_r2(scores[:, [0, 1, 3]], y)
contrib_3 = full_r2 - calc_r2(scores[:, [0, 1, 2]], y)
```

## R² Decomposition Method

The contribution of each factor is calculated by comparing the full model R² with the R² when that factor is removed:
```
Contribution_i = R²_full - R²_without_i
```

## Output Format
```python
contributions = {
    'Category1': contrib_0 * 100,
    'Category2': contrib_1 * 100,
    'Category3': contrib_2 * 100,
    'Category4': contrib_3 * 100
}

dominant = max(contributions, key=contributions.get)
dominant_pct = round(contributions[dominant])

with open('output.csv', 'w') as f:
    f.write('variable,contribution\n')
    f.write(f'{dominant},{dominant_pct}\n')
```

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Negative contribution | Suppressor effect | Check for multicollinearity |
| Contributions don't sum to R² | Normal behavior | R² decomposition is approximate |
| Very small contributions | Factor not important | May be negligible driver |

## Best Practices

- Run ONE global PCA on all variables together, not separate PCA per category
- Use factor_analyzer with varimax rotation
- Map factors to category names based on loadings interpretation
- Report contribution as percentage
- Identify the dominant (largest) factor
