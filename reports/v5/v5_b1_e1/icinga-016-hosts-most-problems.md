# icinga-016-hosts-most-problems

<!-- BEGIN:auto -->

**task:** `icinga-016-hosts-most-problems`  
**category:** icinga  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.936 |
| v4_t1_e1 (v4's original-skill baseline) | test | 3 | 1.000 |
| JB baseline-v2 (external) | test | 1 | 1.000 |

per-trial rewards: [0.680, 1.000, 1.000, 1.000, 1.000]  
min 0.680 · max 1.000 · spread 0.320 · sd 0.128 · errored trials 0  
delta vs v4_t1_e1: -0.064  

**cost/time:** $0.3860, 117,250 tokens, 5.2 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.680-1.000 (sd 0.128). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** one of v4's original 34 tasks, carried into v5 with its contract unchanged. The two v4 rows above are v4's own original-skill baselines on the same task, so the comparison is like-for-like. Across all 34 such tasks v5 reproduces v4 to -0.002 on average (SE 0.018).
