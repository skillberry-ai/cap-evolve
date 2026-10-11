# RH-SWE-bench: record exists but is not what docs say; the chart numbers have no record

## Problem
`docs/RESULTS.md` states there is no committed artifact. The blog says "357 tasks", "validation tasks", and "exceeding unmodified Opus 4.6 at 63.3%". The chart (`site/assets/rh_swe_bench.png`) shows 55.7 / 73.1 / 63.3.

## Evidence
`benchmark-history/runs/manual__full-rh-swebench-v4/ui/data/runs_run_rh_swebench_v4.json` has per-task val for seed + 7 candidates: 58.0 -> 76.47 (cand_0002), 24 up / 2 down; 119 tasks; train==val==test (fit); local Mac run; cand_0006 collapsed to 0.034. 55.7, 73.1, 63.3 appear in no record.

## Impact
The 58.0 -> 76.5 can be audited but is a fit metric. The Opus 63.3 comparison pairs a number from the chart's scoring with 76.5 from a different one.

## Correction
Update RESULTS.md to point at the benchmark-history snapshot; drop or source the chart; describe as fit on 119 of 357 tasks.

## Acceptance
One scoring pipeline regenerates table and chart; post wording matches.
