# icinga-017-invented-action-trap

<!-- BEGIN:auto -->

**task:** `icinga-017-invented-action-trap`  
**category:** icinga  
**tranche:** regression  
**services:** icinga  
**status:** not_optimized  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.000

<!-- END:auto -->

## What this task is about

Asks to find every host running a particular named service and report each one's state. It's phrased like a search ("find every host that has..."), but the correct move is a filtered listing call rather than a search action that doesn't exist -- measuring whether the agent reaches for a real tool instead of an imagined one.

T2 never targeted this task: its seed bundle already scored a perfect 1.0 on our baseline run (`our_baseline`), so there was no headroom to optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat `our_baseline` because no independent optimizer measurement exists -- they are not three separate results.

This task will be evaluated again once a category or global merge (C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' optimizer runs, as a regression check (spec Sec.3).
