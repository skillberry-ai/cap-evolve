# platform-019-anarchysubject-state

<!-- BEGIN:auto -->

**task:** `platform-019-anarchysubject-state`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** not_optimized  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.150 |
| our baseline (v4_t1_e1) | test | 3 | 1.000 |

delta vs JB: 0.850 · delta vs our baseline: 0.000

<!-- END:auto -->

## What this task is about

A user's Babylon provision never came up. The task is a two-hop lookup: find the AnarchySubject for the given GUID and cluster, report its current vs. desired state, then look up its governor's component definition on the same cluster for the expected instance count and cloud provider.

T2 never targeted this task: its seed bundle already scored a perfect 1.0 on our baseline run (`our_baseline`), so there was no headroom to optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat `our_baseline` because no independent optimizer measurement exists -- they are not three separate results.

This task will be evaluated again once a category or global merge (C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' optimizer runs, as a regression check (spec Sec.3).
