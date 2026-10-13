# platform-033-schema-change-not-the-oom

<!-- BEGIN:auto -->

**task:** `platform-033-schema-change-not-the-oom`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.829 |
| v4_t1_e1 (v4's original-skill baseline) | test | 3 | 0.929 |
| JB baseline-v2 (external) | test | 1 | 1.000 |

per-trial rewards: [0.893, 0.893, 0.893, 0.893, 0.571]  
min 0.571 · max 0.893 · spread 0.321 · sd 0.129 · errored trials 0  
delta vs v4_t1_e1: -0.100  

**cost/time:** $1.1606, 359,237 tokens, 15.9 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.571-0.893 (sd 0.129). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** one of v4's original 34 tasks, carried into v5 with its contract unchanged. The two v4 rows above are v4's own original-skill baselines on the same task, so the comparison is like-for-like. Across all 34 such tasks v5 reproduces v4 to -0.002 on average (SE 0.018).
