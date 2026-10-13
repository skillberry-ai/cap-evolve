# platform-068-deprecation-warning-not-the-fatal

<!-- BEGIN:auto -->

**task:** `platform-068-deprecation-warning-not-the-fatal`  
**category:** platform  
**task set:** 10-10  
**status:** ok  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.944 |

per-trial rewards: [0.860, 1.000, 1.000, 1.000, 0.860]  
min 0.860 · max 1.000 · spread 0.140 · sd 0.069 · errored trials 0

**cost/time:** $1.2747, 399,297 tokens, 9.5 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: five identical trials spanned 0.860-1.000 (sd 0.069). With n=5 its mean carries a ~95% CI of roughly +/-0.127, so a later arm's change on this task alone is only meaningful well above that. It is one of 92 of 136 v5 tasks (68%) that vary across repeats.

This task came from the **`v5_2026-10-10`** drop (the first 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
