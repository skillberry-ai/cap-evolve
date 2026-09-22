# cloud-027-azure-pool-database-trap

<!-- BEGIN:auto -->

**task:** `cloud-027-azure-pool-database-trap`  
**category:** cloud  
**tranche:** regression  
**services:** cloud  
**status:** not_optimized  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.000

<!-- END:auto -->

## What this task is about

The task asks to look up an Azure subscription in one specific database of three named options (`pools`, not `aro` or `roadshow`) and report its assignment plus peer subscriptions. The underlying tool's schema doesn't actually reject an invalid database value -- only the instruction's own wording does -- so this measures whether the agent honors a constraint that lives in the contract but not in the environment.

T2 never targeted this task: its seed bundle already scored a perfect 1.0 on our baseline run (`our_baseline`), so there was no headroom to optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat `our_baseline` because no independent optimizer measurement exists -- they are not three separate results.

This task will be evaluated again once a category or global merge (C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' optimizer runs, as a regression check (spec Sec.3).
