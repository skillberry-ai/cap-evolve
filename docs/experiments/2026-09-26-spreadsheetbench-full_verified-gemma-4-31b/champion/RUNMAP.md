# RUNMAP — every prior iteration's working dir (read these before proposing)

For each prior iteration, its artifacts are copied into `./prior_iterations/<candidate>/`:
- `PROCESS.md` — what that iteration did (ranked issues, changes, verify-the-fix, process)
- `diff.patch` — the EXACT capability edit it made vs its parent

The live run dir (read-only) is at `/vol/home/skillberry/.cache/capevolve-gh-runner/_work/cap-evolve/cap-evolve/ci/benchmarks/.work/suite_full_verified_spreadsheetbench_proj/.capevolve/run_suite` if you need `rollouts/<split>/` traces or the git log.

| iter | candidate | parent | outcome | val | ./prior_iterations/<id>/ |
| --- | --- | --- | --- | --- | --- |
| 1 | r1_contract | seed | ACCEPT | 0.775 | PROCESS.md + diff.patch |
| 2 | r2_numeric | r1_contract | reject | 0.846 | PROCESS.md + diff.patch |
| 3 | r3_decide | r1_contract | ACCEPT | 0.887 | PROCESS.md + diff.patch |
| 4 | r4_silent | r3_decide | reject | 0.842 | PROCESS.md + diff.patch |
| 5 | r5_verdict | r3_decide | reject | 0.800 | PROCESS.md + diff.patch |
| 6 | r6_scope | r3_decide | reject | 0.769 | PROCESS.md + diff.patch |
| 7 | r7_path | r3_decide | reject | 0.846 | PROCESS.md + diff.patch |
| 8 | r8_cut | r3_decide | reject | 0.875 | PROCESS.md + diff.patch |

Before proposing, read the PROCESS.md + diff.patch of the prior iterations that targeted the SAME cluster you are about to work on — so you BUILD ON them rather than repeat a rejected or already-tried edit. Cross-reference LEDGER.md for which of them the gate accepted vs rejected, and JOURNAL.md for the lessons.
