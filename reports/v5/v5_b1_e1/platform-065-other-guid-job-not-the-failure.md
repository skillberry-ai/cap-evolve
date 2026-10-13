# platform-065-other-guid-job-not-the-failure

<!-- BEGIN:auto -->

**task:** `platform-065-other-guid-job-not-the-failure`  
**category:** platform  
**task set:** 10-10  
**status:** ok  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.804 |

per-trial rewards: [0.720, 0.860, 0.860, 0.860, 0.720]  
min 0.720 · max 0.860 · spread 0.140 · sd 0.069 · errored trials 0

**cost/time:** $0.5473, 165,133 tokens, 7.6 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: five identical trials spanned 0.720-0.860 (sd 0.069). With n=5 its mean carries a ~95% CI of roughly +/-0.127, so a later arm's change on this task alone is only meaningful well above that. It is one of 92 of 136 v5 tasks (68%) that vary across repeats.

This task came from the **`v5_2026-10-10`** drop (the first 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
