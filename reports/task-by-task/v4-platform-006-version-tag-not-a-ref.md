# platform-006-version-tag-not-a-ref

<!-- BEGIN:auto -->

**task:** `platform-006-version-tag-not-a-ref`  
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

An AAP2 job failed resolving a base image, and its log records the catalog-item version that was running. The task is to compare that version string against the actual base-image tag set in a config file on the default branch -- the trap being to treat the catalog version as a git ref when fetching that file.

T2 never targeted this task: its seed bundle already scored a perfect 1.0 on our baseline run (`our_baseline`), so there was no headroom to optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat `our_baseline` because no independent optimizer measurement exists -- they are not three separate results.

This task will be evaluated again once a category or global merge (C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' optimizer runs, as a regression check (spec Sec.3).
