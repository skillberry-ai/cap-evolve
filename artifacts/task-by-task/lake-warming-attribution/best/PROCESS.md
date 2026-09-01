# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing trials × score recoverable, biggest first)
| rank | cluster | trials | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | `test_trend_result` fails: flaky method choice for the warming-trend slope/p-value | t0, t1, t3, t9 (4/10 fail) | The agent flakily uses **ordinary linear regression** for the trend. On this short (16 pts), gap-year (2020 missing), autocorrelated series linreg gives slope 0.08 / **p 0.0548** — p just ABOVE 0.05, so `assert p<0.05` FAILS. The 6 passing trials used **Sen's slope + Mann-Kendall** (`mk.original_test`) → slope 0.09 / **p 0.0343** → PASS. The oracle uses Mann-Kendall. `trend-analysis/SKILL.md` presented linear regression FIRST as a co-equal method and only softly noted "prefer Sen's slope" in a table, so ~40% of trials picked linreg. | BEHAVIORAL | SCRIPT + BODY |

Note: `test_dominant_factor` passes in every trial (fixed by cand_0001's `attribution.py`); `contribution-analysis`, `meteorology-driver-classification`, `pca-decomposition` were left UNTOUCHED — no failure signature and editing risks regressing the passing half.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (new) | `trend-analysis/scripts/trend_analysis.py` | General trend detector: auto-detects the numeric measurement column (skips year/time columns), runs Sen's slope + Mann-Kendall via pymannkendall, writes `slope,p_value` rounded to 2 dp to `--output`. Nothing task-specific hardcoded (input path, column, output all args; column auto-detected). Reproduces the oracle exactly. | Yes — single-task split; only this task uses `trend-analysis`. Passing trials already use Sen's slope, so the script produces the SAME 0.09/0.03 they already write. |
| 1 | BODY | `trend-analysis/SKILL.md` | Added a "Recommended method for environmental time series: Sen's slope + Mann-Kendall" section at the top (before the Linear Regression section), explaining WHY linreg p is unreliable for short/autocorrelated/uneven series and can land just above 0.05; added a "run the bundled script" block with execute intent ("do NOT reimplement with linear regression"); demoted the Linear Regression section with a caveat. Encodes the general rule, not the task's numbers. | Yes — additive + reordering; the 6 passing trials already do this. Failing trials are pushed onto the passing path. |

## Verify-the-fix (trace it targets → what the new tool/guidance does on those exact inputs)
- `::TestLakeWarmingAttribution::test_trend_result` (asserts `0.07<=slope<=0.11` AND `p<0.05`): ran `trend_analysis.py` on the task's actual `water_temperature.csv` → wrote `slope,p_value` / `0.09,0.03`; re-ran the verifier's exact assertions in Python → PASS. Confirmed the failure mechanism directly: extracted the written `(slope,p)` from all 10 trajectories — the 4 failing trials wrote `0.0805,0.0548` (linreg, p≥0.05) and the 6 passing wrote `0.0879,0.0343` (Mann-Kendall). Independently reproduced both: `stats.linregress` → p=0.0548; `mk.original_test` → p=0.0343.
- Blast radius: `trend-analysis` is used only by this single task (single-task split). `contribution-analysis` / `meteorology-driver-classification` / `pca-decomposition` (the already-passing `test_dominant_factor` half) are untouched. The script matches what passing trials already produce, so no passing trial regresses.

## Process & features used
- Subagents/worktrees: none — a single deterministic root cause; direct diagnosis (extracting written slope/p from every trajectory) + running the script on real inputs was faster and fully verifiable.
- Prior iterations read: cand_0001 (ACCEPTED, fixed dominant_factor). Built on it by leaving its `attribution.py` and body edits fully intact and NOT touching the passing half.
- Verified by RUNNING: executed `trend_analysis.py` on `/root/data/water_temperature.csv`; verified assertions; cross-checked linreg vs Mann-Kendall p-values to confirm the flakiness mechanism.

## Good things to PRESERVE
- cand_0001's `contribution-analysis/scripts/attribution.py` + its category-reporting guidance (fixes `test_dominant_factor`) — untouched, keep.
- `trend-analysis/scripts/trend_analysis.py` + the "use Sen's slope, not linear regression, for environmental series" guidance — the fix for the flaky trend half.

## Deliberately skipped
- Any edit to `contribution-analysis` / `meteorology-driver-classification` / `pca-decomposition` — `test_dominant_factor` passes every trial; editing risks regression with zero upside (no failing signature).
- Reworking the linear-regression section beyond a caveat — removing it entirely is unnecessary and could confuse; demoting + a script pointer is sufficient and lower-risk.
