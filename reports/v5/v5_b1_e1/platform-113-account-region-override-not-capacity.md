# platform-113-account-region-override-not-capacity

<!-- BEGIN:auto -->

**task:** `platform-113-account-region-override-not-capacity`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 4 | 0.744 |

per-trial rewards: [0.738, 0.750, 0.662, 0.825]  
min 0.662 · max 0.825 · spread 0.163 · sd 0.058 · errored trials 1  

**audit:** 1 trial(s) excluded -- dead trial(s) excluded after per-trial audit: AgentTimeoutError with 0 tool calls (gateway hang before the first LLM response); cap-evolve scored them 0.0 and did not count them as errored.

**cost/time:** $0.3854, 102,172 tokens, 33.7 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 4 identical trials spanned 0.662-0.825 (sd 0.058). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
