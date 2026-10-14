# platform-111-recycled-sandbox-swallowed-teardown

<!-- BEGIN:auto -->

**task:** `platform-111-recycled-sandbox-swallowed-teardown`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.835 |
| v5_b1_e1 (original skill) | val | 5 | 0.811 |

per-trial rewards: [0.765, 0.853, 0.853, 0.853, 0.853]  
min 0.765 · max 0.853 · spread 0.087 · sd 0.035 · errored trials 0  
delta vs v5_b1_e1: +0.024  

**pooling:** Fewer than 5 valid trials in any single run (gateway hangs across repeated attempts). Per explicit instruction, pooled all 12 individually-audited, error-free trials across every attempt on disk for this task (current + .dead-* runs) and randomly sampled 5 (seed=20261014) rather than requiring 5 from one run.

**cost/time:** $0.6508, 182,739.0 tokens, 35.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.024 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
