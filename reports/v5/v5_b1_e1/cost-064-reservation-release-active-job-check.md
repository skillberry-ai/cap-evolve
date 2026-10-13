# cost-064-reservation-release-active-job-check

<!-- BEGIN:auto -->

**task:** `cost-064-reservation-release-active-job-check`  
**category:** cost  
**task set:** 10-10  
**status:** ok  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.400 |

per-trial rewards: [0.620, 0.620, 0.000, 0.760, 0.000]  
min 0.000 · max 0.760 · spread 0.760 · sd 0.331 · errored trials 0

**cost/time:** $0.4032, 119,188 tokens, 49.3 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: five identical trials spanned 0.000-0.760 (sd 0.331). With n=5 its mean carries a ~95% CI of roughly +/-0.127, so a later arm's change on this task alone is only meaningful well above that. It is one of 92 of 136 v5 tasks (68%) that vary across repeats.

This task came from the **`v5_2026-10-10`** drop (the first 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
