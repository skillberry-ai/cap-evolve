# platform-108-duplicate-guid-concurrent-run

<!-- BEGIN:auto -->

**task:** `platform-108-duplicate-guid-concurrent-run`  
**category:** platform  
**task set:** 10-12  
**status:** ok  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.783 |

per-trial rewards: [0.783, 0.900, 0.783, 0.667, 0.783]  
min 0.667 · max 0.900 · spread 0.233 · sd 0.074 · errored trials 0

**cost/time:** $0.6018, 169,762 tokens, 29.5 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: five identical trials spanned 0.667-0.900 (sd 0.074). With n=5 its mean carries a ~95% CI of roughly +/-0.127, so a later arm's change on this task alone is only meaningful well above that. It is one of 92 of 136 v5 tasks (68%) that vary across repeats.

This task came from the **`v5_2026-10-12`** drop (the second 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
