# platform-034-rate-limit-not-an-outage

<!-- BEGIN:auto -->

**task:** `platform-034-rate-limit-not-an-outage`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.785 |
| v5_b1_e1 (original skill) | val | 5 | 0.786 |

per-trial rewards: [0.769, 0.769, 0.769, 0.847, 0.769]  
min 0.769 · max 0.847 · spread 0.078 · sd 0.031 · errored trials 0  
delta vs v5_b1_e1: -0.001  

**pooling:** Fewer than 5 valid trials in any single run (gateway hangs across repeated attempts). Per explicit instruction, pooled all 19 individually-audited, error-free trials across every attempt on disk for this task (current + .dead-* runs) and randomly sampled 5 (seed=20261014) rather than requiring 5 from one run.

**cost/time:** $0.5212, 139,186.0 tokens, 29.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.001 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
