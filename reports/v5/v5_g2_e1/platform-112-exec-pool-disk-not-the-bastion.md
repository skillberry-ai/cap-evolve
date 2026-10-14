# platform-112-exec-pool-disk-not-the-bastion

<!-- BEGIN:auto -->

**task:** `platform-112-exec-pool-disk-not-the-bastion`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** down  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.715 |
| v5_b1_e1 (original skill) | val | 5 | 0.872 |

per-trial rewards: [0.925, 0.575, 0.575, 0.838, 0.662]  
min 0.575 · max 0.925 · spread 0.350 · sd 0.142 · errored trials 0  
delta vs v5_b1_e1: -0.158  

**pooling:** Fewer than 5 valid trials in any single run (gateway hangs across repeated attempts). Per explicit instruction, pooled all 15 individually-audited, error-free trials across every attempt on disk for this task (current + .dead-* runs) and randomly sampled 5 (seed=20261014) rather than requiring 5 from one run.

**cost/time:** $0.4714, 130,367.0 tokens, 29.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved down -0.158** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
