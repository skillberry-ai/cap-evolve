# cloud-024-guid-to-account

<!-- BEGIN:auto -->

**task:** `cloud-024-guid-to-account`  
**category:** cloud  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** yes  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.200 |
| v4_t1_e1 (v4's original-skill baseline) | test | 3 | 0.200 |
| JB baseline-v2 (external) | test | 1 | 0.200 |

per-trial rewards: [0.200, 0.200, 0.200, 0.200, 0.200]  
min 0.200 · max 0.200 · spread 0.000 · sd 0.000 · errored trials 0  
delta vs v4_t1_e1: -0.000  

**cost/time:** $0.0906, 28,853 tokens, 13.8 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

All five trials returned the identical reward, so this task's score carries no run-to-run noise -- unusual here: only 60 of 136 v5 tasks are deterministic.

**Lineage:** one of v4's original 34 tasks, carried into v5 with its contract unchanged. The two v4 rows above are v4's own original-skill baselines on the same task, so the comparison is like-for-like. Across all 34 such tasks v5 reproduces v4 to -0.002 on average (SE 0.018).
