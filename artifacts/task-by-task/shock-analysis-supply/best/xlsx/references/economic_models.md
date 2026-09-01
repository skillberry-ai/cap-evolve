# Multi-source economic & financial models: units and sanity checks

Load this when a spreadsheet task combines data pulled from **multiple external
sources** into one calculation — e.g. a production-function / potential-GDP model,
a national-accounts build, or any model that mixes a capital-stock series, a GDP
series, prices/deflators, and rates. These models fail silently on **units**, not
on formulas: every formula-presence check can pass while the numbers are off by a
round factor. The rules below prevent that.

## 1. Reconcile units BEFORE combining series (the #1 cause of wrong magnitudes)

Independent sources report the *same* economic quantity in *different* currencies
and scales. Common real examples:

- **Capital stock** (e.g. Penn World Table `rnna`) is typically in **millions of a
  reference-year US$** (values in the hundreds of thousands).
- **Real GDP** (e.g. IMF WEO `NGDP_R`) is in the **national currency**, and the
  source's own **"Scale"** field says whether it is in **billions** or millions.
- **Consumption of fixed capital / flows** (e.g. ECB) may be in **raw units** of the
  national currency (values in the billions with no scaling).

**Procedure:**
1. For every series, read the source's own units/scale metadata (WEO has a "Units"
   and "Scale" row; PWT has a metadata sheet). Never assume — confirm.
2. Choose ONE reporting unit for the model (e.g. *millions of local currency*) and
   convert each series into it with an **explicit scale factor inside the linking
   formula**, so the workbook stays dynamic. Examples:
   - GDP reported in **billions** but the model works in **millions** →
     `='WEO_Data'!C10*1000` (do NOT drop the `*1000`).
   - A flow reported in raw currency units divided by a stock reported in
     thousands/millions → scale one of them so the ratio is dimensionless.
3. Keep the source sheet in the source's native unit; apply the scale factor only
   where the series is *linked into* the model. Document the unit in the header.

## 2. A log-linear TFP residual hides a unit mismatch — the OUTPUT still carries GDP's units

In a Cobb-Douglas / Solow setup the TFP term is a **residual**:
`lnZ = lnY − α·lnK`. This residual **absorbs any constant offset** between the
units of K and the units of Y — so `LnK`, `LnY`, `LnZ` all look fine and the HP
filter runs cleanly even if K and Y are in different units.

But potential output is rebuilt as `Ystar = EXP(lnZ_trend)·K^α`, and because lnZ
absorbed the K offset, **Ystar comes back out in the SAME units as GDP (Y), not K.**
Therefore the *reporting unit you chose for GDP in rule 1* is what sets the scale of
every Ystar / potential-GDP number. If GDP was left in billions, Ystar is ~tens;
if GDP is scaled to millions, Ystar is ~tens-of-thousands. Scale GDP to the model's
intended unit **before** computing LnY, or every downstream output is off by that
factor.

## 3. Sanity-check every headline magnitude after recalc (mandatory)

After running `recalc.py`, do NOT stop at "zero errors." Read back the actual
VALUES of each headline output and compare to a rough expectation. A result off by
a clean factor of 10 / 100 / 1000 is almost always a **units error** (rule 1), not
a formula error. Checklist for macro/production models:

- **Capital-output ratio K/Y** (the single most reliable check): compute K/Y over the
  historical rows. It must be a small number — roughly **1–30** for any real economy. A
  ratio in the hundreds or thousands means K and Y are in mismatched scales (GDP left in
  billions, capital in millions). Scale the GDP link by ×1000 and recompute. Do NOT accept
  a K/Y of 3000. The bundled `scripts/check_econ_model.py` computes this for you.
- **GDP level**: within a few × of the source's reported figure for that year.
- **Potential output (Ystar)**: same order of magnitude as actual GDP in the SAME
  reporting unit (potential output tracks actual output, it does not differ by 1000×).
- **Rates** (depreciation, growth, capital share): a small dimensionless number in an
  economically plausible band — a depreciation rate is a *few percent* (roughly
  0.01–0.03), NOT 0.0005 and NOT 5. If a rate lands outside its plausible band, the
  numerator and denominator are in mismatched units (rule 1) — fix the units, do not
  "adjust" the rate with an ad-hoc factor.
- If any headline value fails its expectation, trace back to which linked series was
  not converted to the common unit and fix the scale factor.

## 4. Collecting the source data

- Populate the workbook **incrementally and save often**. Enter each series as soon
  as you have it and re-save; never leave the output file empty while chasing one
  stubborn source. Partial-but-saved beats complete-but-unsaved.
- If a data source returns **HTTP 403 / "Access Denied"** or otherwise blocks
  programmatic requests (`curl`/fetch), do **not** keep retrying the same request.
  Switch to a real browser (e.g. Playwright MCP) to load the page/database and read
  the values, or use the source's documented data API (many statistical agencies
  expose an SDMX/JSON API even when the HTML site blocks scrapers).
