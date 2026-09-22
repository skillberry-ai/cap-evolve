# platform-009-catalog-item-no-config

<!-- BEGIN:auto -->

**task:** `platform-009-catalog-item-no-config`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** not_optimized  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.000

<!-- END:auto -->

## What this task is about

A job failed with an undefined variable. Tracing it to the responsible catalog item hits a dead end -- its config file doesn't exist -- and the real explanation, an unmerged pull request, is one hop further still. The task measures whether the agent follows the chain to that actual break instead of stopping short or fabricating a configuration.

T2 never targeted this task: its seed bundle already scored a perfect 1.0 on our baseline run (`our_baseline`), so there was no headroom to optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat `our_baseline` because no independent optimizer measurement exists -- they are not three separate results.

This task will be evaluated again once a category or global merge (C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' optimizer runs, as a regression check (spec Sec.3).
