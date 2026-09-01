# Macro-accounting shock / impact analysis workbooks

Load this when a task asks you to estimate an **investment or spending shock** to
an economy using the **macro accounting (demand-side) framework** and to deliver
an Excel workbook — typically referencing IMF **WEO** GDP data, a national
statistics **supply-use table (SUT)**, and a **National-Accounts (NA)** impact
table with several scenarios.

## Build the structure with the bundled scaffolder — do not hand-build it

These workbooks are graded on **sheet names, cell layout, and formula wiring**,
not on prose. Hand-building them repeatedly reorders columns, hardcodes projected
values, or drops a required sheet. Run the scaffolder instead, then paste the data
you collected into the blank cells:

```bash
python scripts/build_shock_model.py --out <target.xlsx> \
    --investment <USD amount from task> --fx <local/USD rate from task> \
    --multiplier <baseline demand multiplier> \
    --scenario2-multiplier <e.g. 1.0> --scenario3-import-share <e.g. 0.5>
```

If the target file already exists (a provided template), it is loaded and its
existing sheets (e.g. `NA` with its year rows and assumption labels) are preserved
and filled in place; missing sheets are added. All numeric parameters come from the
task statement — the script contains **no answer data**, only structure.

## Required sheets and layout conventions

The scaffolder produces these; if you build any part by hand, match them exactly.

- **`WEO_Data`** — one row per year, `A`=Year, `B`=Real GDP (constant prices),
  `C`=Real GDP growth %, `D`=GDP deflator index, `E`=deflator YoY change %.
  Historical rows: leave `B/C/D` blank and paste the IMF WEO actuals; `E` is a
  formula `=(D{r}/D{r-1}-1)*100`. **Projected years are FORMULAS, never numbers**:
  `B{r}==B{r-1}*(1+C{r}/100)` (Real GDP), growth held at the last actual year,
  deflator extended by the recent-4-year average change as a fixed anchor.
- **`SUT Calc`** — `C`/`D` link the SUPPLY sheet's import & resources columns,
  `E` links the USE sheet's construction column, `F=C/D` (product import share),
  `G=F*E`; **`C46`** = estimated import content share `=SUM(G...)/E{total}`.
- **`SUPPLY (38-38)-2024`** and **`USE (38-38)-2024`** — paste the Geostat supply
  and use tables here, keeping these exact sheet names so `SUT Calc` links resolve.
- **`NA`** — `B`=Year, `C`=Real GDP (linked from `WEO_Data`), `D`=Project
  Allocation % (**bell shape**, e.g. 0.05/0.10/0.15/0.20/0.20/0.15/0.10/0.05 over
  8 years), `E`=Project Investment, `F`=Imports, `G`=I−M, `H`=×multiplier,
  `I`=% of GDP, `J`=baseline growth. Assumptions block: `D30`=total investment
  (`=investment*fx`), `D31`=import content share (`='SUT Calc'!C46`),
  `D32`=demand multiplier, `D33`=Project allocation. Scenarios 2 and 3 replicate
  the table below with their own assumption blocks (override the multiplier / import
  share respectively).

## After scaffolding

1. Paste the collected IMF-WEO actuals and Geostat SUPPLY/USE tables into the blank
   cells (do not move or reorder existing rows/columns).
2. Run `python recalc.py <target.xlsx>` to evaluate every formula and confirm zero
   errors. Keep formulas in the file — do not replace them with computed constants.
