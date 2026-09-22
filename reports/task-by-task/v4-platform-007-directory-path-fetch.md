# platform-007-directory-path-fetch

<!-- BEGIN:auto -->

**task:** `platform-007-directory-path-fetch`  
**category:** platform  
**tranche:** regression  
**services:** github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-007-directory-path-fetch/run_20260920_185422` (n_runs: 2)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.850 |
| our baseline (v4_t1_e1) | test | 3 | 0.800 |
| seed (val, v4_t2_e1) | val | 5 | 0.470 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.150 · delta vs our baseline: 0.200

**T2 cost/time:** $7.38, 351,046 tokens, 0.79h (eval $0.91/267,653tok · optimizer $6.48/83,393tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-007-directory-path-fetch/run_20260920_185422/report.md`, `.capevolve/v4_t2_e1_platform-007-directory-path-fetch/run_20260920_185422/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

Single iteration (`cand_0001`) touching `aap2_agent.md` (plus a matching fix to `babylon_agent.md`) after finding the prompt taught a forbidden move in three places while banning it abstractly in only one: it rewrote Critical Rule 3 to name the two concrete prohibited moves (never pass a directory path to `fetch_github_file`; never guess a file path from naming convention), corrected two tool descriptions that falsely told the agent `fetch_github_file` reads directories, added a new "Finding a File in a GitHub Repo" section with a 3-branch selector (catalog lookup → `lookup_catalog_item`; a complete path from a tool result → `fetch_github_file` verbatim; anything else, including a directory → `search_github_repo` first), and deleted a worked example that had demonstrated the forbidden directory fetch. This is a rerun (`run_20260920_185422`); the first attempt (`run_20260920_121011`) genuinely underperformed — both of its candidates were framework-synthesized "empty handover" placeholders (no prompt-edit rationale was recorded) and both were rejected, leaving the seed as champion at val 0.630 and test 0.475, well below this run's result.

## Why the winning candidate won

JOURNAL.md's own count of 15 historical runs found the seed made a forbidden directory fetch as its first move in every one of them, zeroing the `tool_calls` component (weight 0.3) every time — the prompt taught the trap concretely (in three places) while forbidding it only in the abstract. The new selector and corrected tool descriptions removed the affordance, moving val 0.470 → 1.0 (Δ+0.530) and fixing the task per the RESULT line. On the held-out test split, `report.md` records the baseline `seed` skills at 0.510 ± 0.126 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.490.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md flags a large uncracked residual on the `answer` component (weight 0.7) that this edit could not reach: across 25 historical runs the GitHub simulator served the authored fixture content in only 9, substitute LLM-generated content in 6, and a tool-unavailable error in 10 — meaning 64% of runs cap the answer-weighted score for reasons no prompt edit can fix, an escalation the optimizer filed rather than tried to paper over.
