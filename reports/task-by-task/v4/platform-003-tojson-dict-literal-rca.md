# platform-003-tojson-dict-literal-rca

<!-- BEGIN:auto -->

**task:** `platform-003-tojson-dict-literal-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.233 |
| our baseline (v4_t1_e1) | test | 3 | 0.478 |
| seed (val, v4_t2_e1) | val | 5 | 0.563 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.847 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.917 |
| final (test, v4_t2_e1) | test | 5 | 0.763 |

delta vs JB: 0.530 · delta vs our baseline: 0.286

**T2 cost/time:** $27.85, 840,932 tokens, 2.88h (eval $2.28/618,675tok · optimizer $25.56/222,257tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127/report.md`, `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An AAP2 job failed while creating a CNV inventory. The task requires reading the actual failing role code -- in a less obvious repository than the usual content repo -- to explain what's wrong with a value passed through Ansible's `to_json` filter, and to recommend the fix.

## What the optimizer tried

Two iterations, both editing `aap2_agent.md` only (the other 7 files stayed byte-identical to the seed). `cand_0001` added a new "Step 9: Assign Exactly One Root Cause Category" (the taxonomy, an 11-row evidence table, a write contract requiring the literal token even when a read failed), a new "Step 6b: Namespaced Roles Live in Their Own Collection Repo" section mapping an FQCN to the correct `fetch_github_file` argument, and removed the forbidden `agnosticd/agnosticd-v2` owner from two places the prompt itself printed it. `cand_0002` kept all of that and added a discriminator for `application_bug` vs `configuration` (settle it by pointing at the line that sets the value), a mechanical pre-send check that flags any category cell containing a space/hyphen/slash/capital as not a valid taxonomy token, and a rule that a handed-to-you `owner`/`repo` pair travels together and should never be re-resolved via a different `ref`.

## Why the winning candidate won

JOURNAL.md's per-trial reading shows the seed missed `category` in 5/5 trials (the entire early gap); `cand_0001` fixed most of it but left 3/5 trials still missing `category`, for two distinct reasons its own reward-detail breakdown separated out: one trial wrote a paraphrase instead of a taxonomy token, two wrote a valid-but-wrong token (`configuration`) for a value found committed in role source. `cand_0002`'s mechanical token check and application_bug/configuration discriminator addressed both, moving val 0.847 → 0.917 (Δ+0.070) — though the RESULT line marks this move as "unresolved" (below 2×SE of its own measurement).

**Val and test moved in different directions on this task, and the two are not the same number.** The auto block above shows `final (test, v4_t2_e1)` at 0.763, well below `cand_0002`'s val score of 0.917 — `report.md` itself calls this a "Val→test gap: +0.153333 — selection optimism on val; this gap IS the overfitting." Read on its own terms, `report.md`'s held-out test comparison is between the baseline `seed` skills (0.357 ± 0.087) and the optimized skills (0.763 ± 0.114), a test-side improvement of +0.407 — a real gain, but a smaller and noisier one than the val numbers alone would suggest. JOURNAL.md documents two mechanisms consistent with that gap: a mock tool that non-deterministically fabricated file content for an unpinned read on some trials, and a simulator response to a wrong owner/repo pair that is indistinguishable from a genuine tool outage.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). This task's own val→test gap is the largest of the seven in this batch and is explicitly flagged by `report.md` as overfitting, not just noise — treat the val=0.917 number as an optimistic upper bound and the test=0.763 figure in the auto block above as the more trustworthy read of the actual improvement.
