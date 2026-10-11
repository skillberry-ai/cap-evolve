# GLM 5.3 SWE-bench Verified (85.9 / 96.4%) is unsupported; the nearest record has gold-patch access and an upstream-lookup skill

## Problem
The post reports 85.9% held-out and 96.4% (482/500). No artifact yields either. PRs #673 and #699 (open, unmerged) report 0.976 val, 0.959 test.

## Evidence
PR #673 `examples/swebench_glm/run_full`: split 250/125/125 seed 0; test 117/122 scored (3 errored, same tasks both arms) = 0.959; baseline 106/122 = 0.869; `final.json` has `recovered: true` (events show finalize wrote test 0.0 placeholders, then a recovered record ~84 h later, "assembled from rollouts"); one trial; best of 10 candidates; `INSIGHTS.md` says `/tmp/swebench_rows.json` held gold + test patches and F2P/P2P for all 500 tasks and gold patches were used for diagnosis; `cand_0005/prompt.md` tells the agent to find the upstream fix and "port the commit exactly". PR #699 record run_id 202 has `url: github.com/yyualvin/cap-evolve`, no sha.

## Impact
Even 95.9 is not an uncontaminated generalisation number; 85.9 and 482/500 are unsupported (482/500 would include train/val tasks diagnosed with gold patches).

## Correction
Remove from any results table until reproduced; request exact run, denominator and leakage controls.

## Acceptance
Network-isolated rerun, >=3 trials, official harness, recorded commit, no gold or upstream access; denominator and error handling stated.
