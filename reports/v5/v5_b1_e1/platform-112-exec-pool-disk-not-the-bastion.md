# platform-112-exec-pool-disk-not-the-bastion

<!-- BEGIN:auto -->

**task:** `platform-112-exec-pool-disk-not-the-bastion`  
**category:** platform  
**task set:** 10-12  
**status:** ok  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.485 |

per-trial rewards: [0.750, 0.750, 0.925, 0.000, 0.000]  
min 0.000 · max 0.925 · spread 0.925 · sd 0.401 · errored trials 0

**cost/time:** $0.2875, 78,844 tokens, 47.2 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: five identical trials spanned 0.000-0.925 (sd 0.401). With n=5 its mean carries a ~95% CI of roughly +/-0.127, so a later arm's change on this task alone is only meaningful well above that. It is one of 92 of 136 v5 tasks (68%) that vary across repeats.

This task came from the **`v5_2026-10-12`** drop (the second 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
