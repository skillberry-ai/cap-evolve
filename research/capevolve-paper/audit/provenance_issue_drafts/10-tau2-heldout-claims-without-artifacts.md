# tau2 airline held-out claims lack artifacts and reuse the same 20 test tasks

## Problem
30.0 -> 47.5 (30/20), 0.460 -> 0.545 (agent-optimize, 20 x 10), Qwen 17.0 -> 24.0 and 12.0 -> 27.0 are quoted as held-out results with no per-task artifact. The runner for 30.0 -> 47.5 is Claude in RESULTS.md and the draft but gpt-oss-120b in TAU2_SUMMARY.

## Evidence
No run dir for the official 30/20 split in `examples/tau2_airline` (only `run_full` 50=50=50 and `run_agentopt*` 26/12/12); RESULTS.md: "committed separately... until it lands". The 20 official test ids (2,6,8,13,16,18,19,22,24,25,26,29,30,31,32,35,37,44,45,48) were sealed-scored in TAU2_SUMMARY rows 2, 3, 4, 9 (0.475, 0.550, 0.400, 0.545) and 2 Qwen runs; 15 of 20 were train/val in the 26/12/12 runs. Run 4 re-measured run 3's candidate and got 0.467 -> 0.400 (negative). Qwen baselines on the same model/split are 17.0 and 12.0.

## Impact
Cannot audit; no untouched airline task remains; "surface comparison" confounded by unequal baselines on 20 tasks.

## Correction
Quarantine these numbers. If kept, label as unaudited, repeatedly-sealed.

## Acceptance
Artifacts landed (per-task, with commit), or numbers removed; new tau2 evidence uses an untouched task set and a matched 2x2 surface design.
