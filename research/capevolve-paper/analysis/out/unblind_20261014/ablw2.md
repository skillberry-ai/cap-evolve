# ABLW2: 3 native Claude Code champions on the held-out test-20 (exploratory; designed after the V3 B1 results were seen)

Task set: 20 tasks, 20 families; k = 10 trials per task per champion; seed n = 20; seed-check k = 10; HC-stock-s0-ref = the main-window HC-stock seed-0 champion re-scored in this window. One search seed per arm: no pipeline-level interval, no claim about a component's general importance; raw p only, no family claim, no Holm decision (addenda 6 and 7).

Infrastructure (per_arm_report.json): {'jobs': 1400, 'done': 1400, 'infra_attempts': 0, 'infra_final': 0, 'hangs': 0, 'candidate_errors': 0, 'missing_hang': 0, 'empty_output': 0, 'raw_tool_text_last': 0}

## Window checks

- seed 0.510 (n = 20), seed-check 0.465 (k = 10); seed-check minus seed -0.045 [-0.099, 0.009], p 0.098
- drift (5I, in-window seed, task-demeaned, hour blocks): 0: +0.009 (SE 0.016, n=364); 1: -0.092 (SE 0.051, n=36). Range 0.101, SE of difference 0.054, flag (>2 SE): False.
- HC-stock-s0-ref: mean 0.605; delta over the in-window seed +0.095 [-0.008, 0.198], p 0.0692 (main window: +0.131 over a seed of 0.498; the same artifact, a different time block)

## Per arm

| arm | mean | delta over seed | 95% CI | raw p | difference to HC-stock-s0-ref | 95% CI | raw p |
|---|---|---|---|---|---|---|---|
| NC-1SHOT | 0.550 | +0.040 | [-0.065, 0.145] | 0.437 | -0.055 | [-0.136, 0.026] | 0.172 |
| NC-LOOP | 0.615 | +0.105 | [-0.011, 0.221] | 0.073 | +0.010 | [-0.067, 0.087] | 0.789 |
| NC-SKILLS | 0.585 | +0.075 | [-0.038, 0.188] | 0.180 | -0.020 | [-0.123, 0.083] | 0.688 |

The 'difference to HC-stock-s0-ref' column uses the plain scores (no drift flag).

Count of arms with a positive delta over the seed: 3 of 3; with the CI excluding 0 upward: 0; arms whose delta exceeds HC-stock-s0-ref's: 1; with the difference CI excluding 0: 0.
