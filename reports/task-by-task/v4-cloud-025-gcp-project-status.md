# cloud-025-gcp-project-status

<!-- BEGIN:auto -->

**task:** `cloud-025-gcp-project-status`  
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

Someone reports they can't deploy into a GCP project and asks what's going on with it. The task is a single lookup whose finding is a *state* (e.g. `DELETE_REQUESTED`) -- the real work is connecting that state to the reported symptom and explaining that the fix is a new sandbox, not anything inside this project.

T2 never targeted this task: its seed bundle already scored a perfect 1.0 on our baseline run (`our_baseline`), so there was no headroom to optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat `our_baseline` because no independent optimizer measurement exists -- they are not three separate results.

This task will be evaluated again once a category or global merge (C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' optimizer runs, as a regression check (spec Sec.3).
