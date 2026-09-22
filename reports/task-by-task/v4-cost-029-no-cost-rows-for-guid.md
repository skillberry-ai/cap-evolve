# cost-029-no-cost-rows-for-guid

<!-- BEGIN:auto -->

**task:** `cost-029-no-cost-rows-for-guid`  
**category:** cost  
**tranche:** regression  
**services:** cost  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_cost-029-no-cost-rows-for-guid/run_20260919_161308` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.800 |
| our baseline (v4_t1_e1) | test | 3 | 0.800 |
| seed (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.200 · delta vs our baseline: 0.200

**T2 cost/time:** $26.12, 1,045,237 tokens, 2.35h (eval $2.69/827,852tok · optimizer $23.42/217,385tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_cost-029-no-cost-rows-for-guid/run_20260919_161308/report.md`, `.capevolve/v4_t2_e1_cost-029-no-cost-rows-for-guid/run_20260919_161308/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Finance asks what a specific sandbox cost us in Azure for a given month. The task is that no cost rows exist for that subscription in that period, and the correct answer says so explicitly, with a plausible explanation, rather than reporting a fabricated `$0`.

## What the optimizer tried

Two candidates, both editing `cost_agent.md` and `shared_context.md` (the task's only prompt footprint, per `classify_fast()` skipping the orchestrator for single-domain cost queries). `cand_0001` diagnosed that all 5 seed trials filtered `query_azure_costs` to one subscription, got back an empty result (`total_cost: 0`), and reported that as a measured $0 spend rather than an absence of data — and added a new "Empty Cost Results" section distinguishing a measured zero from an absent row. It was rejected (Δ +0.000) because 4 of 5 trials still failed on citing a sibling subscription's honest total with padded cents ("$310.00"), which matches the forbidden `invented-figure` check as a bare substring. `cand_0002` kept the absence/measured-zero distinction and added a "write the number the way the source recorded it" rule banning cents-padding on whole-dollar values, plus tightened the contract to state the gap without characterizing it.

## Why the winning candidate won

JOURNAL.md mechanically verified the cause of `cand_0001`'s failure by running the task's real `verify.py` against its own trial answers: changing only "$310.00" to "$310" flipped every one of `cand_0001`'s failing answers from 0.800 to 1.000. `cand_0002`'s cents-padding rule fixes exactly that, plus resolves two other independently-failing checks (the fabricated-zero and the "characterizing the absence" phrasing), taking val 0.800 (seed) → 0.800 (`cand_0001`, rejected) → 1.000 (`cand_0002`, accepted; test also 1.0).

## Caveats

n=5 val trials; single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md also flags this as a structural limit of a prompt-only fix: the verifier's forbidden-substring check is not negation-aware, so a fully robust guarantee would need a code-level answer lint rather than prose — recorded as an escalation, not shipped in this run.
