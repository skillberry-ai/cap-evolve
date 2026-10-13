# platform-033-schema-change-not-the-oom

<!-- BEGIN:auto -->

**task:** `platform-033-schema-change-not-the-oom`  
**category:** platform  
**task set:** 10-10  
**status:** ok  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.829 |

per-trial rewards: [0.893, 0.893, 0.893, 0.893, 0.571]  
min 0.571 · max 0.893 · spread 0.321 · sd 0.129 · errored trials 0

**cost/time:** $1.1606, 359,237 tokens, 15.9 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: five identical trials spanned 0.571-0.893 (sd 0.129). With n=5 its mean carries a ~95% CI of roughly +/-0.127, so a later arm's change on this task alone is only meaningful well above that. It is one of 92 of 136 v5 tasks (68%) that vary across repeats.

This task came from the **`v5_2026-10-10`** drop (the first 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
