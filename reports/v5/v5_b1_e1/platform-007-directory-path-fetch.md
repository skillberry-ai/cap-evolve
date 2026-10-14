# platform-007-directory-path-fetch

<!-- BEGIN:auto -->

**task:** `platform-007-directory-path-fetch`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.820 |
| v4_t1_e1 (v4's original-skill baseline) | test | 3 | 0.800 |
| JB baseline-v2 (external) | test | 1 | 0.850 |

per-trial rewards: [0.850, 0.850, 0.850, 0.700, 0.850]  
min 0.700 · max 0.850 · spread 0.150 · sd 0.060 · errored trials 0  
delta vs v4_t1_e1: +0.020  

**cost/time:** $0.2226, 65,518 tokens, 5.8 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.700-0.850 (sd 0.060). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** one of v4's original 34 tasks, carried into v5 with its contract unchanged. The two v4 rows above are v4's own original-skill baselines on the same task, so the comparison is like-for-like. Across all 34 such tasks v5 reproduces v4 to -0.002 on average (SE 0.018).
