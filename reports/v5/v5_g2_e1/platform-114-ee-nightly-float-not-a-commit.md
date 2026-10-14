# platform-114-ee-nightly-float-not-a-commit

<!-- BEGIN:auto -->

**task:** `platform-114-ee-nightly-float-not-a-commit`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.929 |
| v5_b1_e1 (original skill) | val | 5 | 0.962 |

per-trial rewards: [1.000, 0.917, 0.917, 0.810, 1.000]  
min 0.810 · max 1.000 · spread 0.190 · sd 0.070 · errored trials 0  
delta vs v5_b1_e1: -0.033  

**pooling:** Fewer than 5 valid trials in any single run (gateway hangs across repeated attempts). Per explicit instruction, pooled all 14 individually-audited, error-free trials across every attempt on disk for this task (current + .dead-* runs) and randomly sampled 5 (seed=20261014) rather than requiring 5 from one run.

**cost/time:** $0.4735, 130,751.0 tokens, 34.2 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.033 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
