# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | No output files written | exam-block-sequencing (5 of 7 completed trials; t2,t5,t6,t7,t8) | Agent commits the entire 1500s budget to an EXACT MIP (PySCIPOpt `.optimize()`) for a 24×24 permutation with a 24⁴ overlap term (~492k binaries per the passing trace). The solve never finishes, so `/root/output/schedule.csv` is never written. ALL 3 verifier tests then fail on `AssertionError: Missing schedule file`. | BEHAVIORAL / CAPABILITY-GAP | SCRIPT (bundled heuristic solver) + BODY (tractability triage + write-outputs-early) |

Note on the task label: the run summary called this task "flaky / infrastructure timeout" because the LAST trial (t9) happened to be a 2400s bench timeout. That is misleading — only 3/10 trials were infra timeouts (t0,t1,t9); 6/10 were REAL verifier failures and 1/10 passed (t4). The real, optimizable defect is the "no output written" cluster above, confirmed from the per-trial `verifier/test-stdout.txt` in `bench_jobs/`.

Diagnosis evidence:
- Passing trial t4: explicitly reasoned "exact linearization ~492k binaries, impractical; solve via heuristic which the task permits" → ran SA + 2-swap local search → obj 3993 ≤ allowed 4085 → wrote all outputs → PASSED (0 `.optimize()` calls).
- Failing trials t2/t7: 16 PySCIPOpt mentions, `.optimize()` called, 24 "time limit" mentions in t7 → stuck in solver, never wrote `schedule.csv`.
- Every trial (incl. the pass) burned the full 1500s agent budget (`timing.json`), so the differentiator is "did outputs get written", not solve time.
- Oracle itself used `heuristic_direct_permutation_search` (oracle_metrics.json), objective 3966, `max_relative_gap` 0.03 → allowed objective ≈ 4085.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (new) | `ordered-window-sequencing-mip/scripts/solve_sequencing.py` | Data-driven heuristic solver: reads `instance.json` + `pair_counts.csv` + `triplet_counts.csv`, builds a feasible front-loaded permutation, runs restarted feasibility-preserving 2-swap simulated-annealing + steepest-descent on the EXACT objective (ordered tuples; active-pattern four-slot `z` overlap), writes schedule.csv/metrics.json/formulation.md/report.md, and round-trip re-verifies. No hardcoded answer — all weights/masks/large/early rules come from `instance.json`, so it works on any instance of this family (held-out seeds). | Yes — the ONLY passing trial (t4) already used a heuristic; this makes that winning behavior deterministic and always-writes-output. |
| 1 | BODY (additive) | `ordered-window-sequencing-mip/SKILL.md` | Added "Bundled solver — run it" section: run `scripts/solve_sequencing.py` with a `--time-limit` instead of hand-rolling; if building your own model, write feasible outputs first then improve. | Yes — additive; steers toward the behavior t4 already did. |
| 1 | BODY (additive) | `mip-solver-and-solution-audit/SKILL.md` | Added "Tractability triage and guaranteed outputs": estimate exact-model size first; if intractable and heuristics permitted, go heuristic immediately; write feasible outputs EARLY; always pass a solver time limit < agent budget. | Yes — additive; does not delete the existing solver-preference guidance, only adds a triage/early-output rule. |

## Verify-the-fix (trace it targets → what the change does on those exact inputs)
- Targets `test_solution_is_feasible` / `test_objective_value_is_reported_correctly` / `test_verifier_objective_is_no_worse_than_oracle`, all failing with `Missing schedule file: /root/output/schedule.csv` in t2/t5/t6/t7/t8. Ran `scripts/solve_sequencing.py --data <task data> --out <out> --time-limit 240` on the REAL instance, then executed the REAL verifier `pytest verifier/test_outputs.py`: **3 passed** (objective 3999 ≤ allowed 4085). My `evaluate_perm`/`evaluate` matches the verifier's `evaluate_schedule` byte-for-byte (objective + all 6 components + feasibility) on the produced schedule.
- Robustness: 240s default budget gives ~48 restarts (best-of-N). At 120s (24 restarts) seeds 1/7/42/99 → 3968/4052/4065/4027, all ≤ 4085; 240s adds margin. Budget 240s ≪ 1500s agent budget, so outputs are always written well before the wall.

## Process & features used
- Subagents / worktrees: serial — single task, single tight cluster; the leverage was one verified script, not fan-out. Used background bash tasks + Monitor to run 120–240s solves without blocking.
- Prior iterations read: none exist (seed baseline only; LEDGER/JOURNAL empty).

## Good things to PRESERVE
- `ordered-window-sequencing-mip/scripts/solve_sequencing.py` and both body pointers. The exact objective evaluator (ordered tuples + active-pattern `z` overlap) is verified against the benchmark verifier — do not "simplify" the `z` term into all-triples-in-a-4-span.
- Keep the default `--time-limit` (240s) well under the agent budget; do not raise it near 1500s.

## Deliberately skipped
- Objective-modeling/z-term prose clusters: NOT the failure here (failures were "no file", not "wrong z"). The script encodes the correct z, so no separate prose edit needed.
- The 3 infra-timeout trials (t0,t1,t9): genuine bench noise, not skill-fixable.
