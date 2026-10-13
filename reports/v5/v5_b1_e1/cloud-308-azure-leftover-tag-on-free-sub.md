# cloud-308-azure-leftover-tag-on-free-sub

<!-- BEGIN:auto -->

**task:** `cloud-308-azure-leftover-tag-on-free-sub`  
**category:** cloud  
**task set:** 10-12  
**status:** ok  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.093 |

per-trial rewards: [0.117, 0.117, 0.117, 0.117, 0.000]  
min 0.000 · max 0.117 · spread 0.117 · sd 0.047 · errored trials 0

**cost/time:** $1.1410, 363,882 tokens, 40.7 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: five identical trials spanned 0.000-0.117 (sd 0.047). With n=5 its mean carries a ~95% CI of roughly +/-0.127, so a later arm's change on this task alone is only meaningful well above that. It is one of 92 of 136 v5 tasks (68%) that vary across repeats.

This task came from the **`v5_2026-10-12`** drop (the second 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
