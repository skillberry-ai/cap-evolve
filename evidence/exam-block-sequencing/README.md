# Evidence: cap-evolve evolves real code, not just prose

**Claim:** the `skill-package` capability doesn't just reword `SKILL.md` — it can write
an entire working program from scratch when that's the highest-leverage fix, and iterate
on that program's algorithm across accepted candidates.

**Task:** SkillsBench `exam-block-sequencing` (category: mathematics-or-formal-reasoning /
mathematical-optimization). Run: `run_task_exam-block-sequencing_v1_KILLED_ceiling_reached_1.0`
in the `intake_skillbench_c3` worktree (a real `store: git` repo — every accepted iteration
is a commit).

## Reward trajectory

| Candidate | Val reward | Δ | What changed |
|---|---|---|---|
| seed | 0.1 | — | prose only, no script |
| `cand_0001` | 0.9 | +0.8 | **new script created** |
| `cand_0002` (final/best) | 1.0 | +0.1 | script refined |

Status: `KILLED_ceiling` (stopped because val hit 1.0 — no ceiling headroom left).
Source: `results.json` (canonical ledger, this branch's `results/`), row `task:
"exam-block-sequencing"`.

## What the seed actually contained

`seed/` here holds the two `SKILL.md` files from the seed candidate — that's it. No
`scripts/` directory exists anywhere under seed. Verify: `find seed/ -iname '*.py'`
returns nothing.

## Iteration 1 — cand_0001 (val 0.1 → 0.9): a script written from nothing

The optimizer's own log (`history.jsonl`, `candidate_id: cand_0001`):

> "NEW SCRIPT `ordered-window-sequencing-mip/scripts/solve_sequencing.py` — data-driven
> heuristic (feasible front-loaded init → restarted 2-swap simulated annealing +
> steepest descent on the EXACT objective incl. the active-pattern four-slot `z`
> overlap) that writes schedule.csv/metrics.json/formulation.md/report.md and
> round-trip re-verifies. Cluster: 'no output file written'."

`cand_0001/ordered-window-sequencing-mip/scripts/solve_sequencing.py` — **465 lines**,
a genuine heuristic solver (feasible front-loaded initializer, restarted 2-swap
simulated annealing then steepest descent on the exact scheduling objective).
`diffs/seed-to-0001.diff` is the full file as a diff against nothing (`/dev/null`),
i.e. proof it is 100% new content, not an edit of a pre-existing file.

## Iteration 2 — cand_0002 (val 0.9 → 1.0): the algorithm itself improved

The log calls this out explicitly as **script-only**, no prose touched
(`history.jsonl`, `candidate_id: cand_0002`):

> "SCRIPT `ordered-window-sequencing-mip/scripts/solve_sequencing.py`: enlarged the
> local-search neighborhood from 2-swap-only to **2-swap + or-opt(1) relocation** in
> both the SA proposal (50/50) and the steepest-descent polish; added
> `build_feasible` (O(3) front-loading check via the 3 late positions) + `relocate`
> helper... Objective evaluator + output contract + round-trip audit UNCHANGED."

`cand_0002/.../scripts/solve_sequencing.py` grew to **549 lines**. `diffs/0001-to-0002.diff`
shows the real change: two new functions (`build_feasible`, `relocate`) and a widened
search neighborhood, e.g.:

```diff
-def greedy_descent(obj, perm, swap_ok, deadline):
-    """Steepest-descent 2-swap polish on a permutation."""
+def build_feasible(inst):
+    """Return (feasible(perm), late_pos): the front-loading feasibility predicate.
+    ...
```

## Independent confirmation: git history

`git-log.txt` (`git log --stat` on the run's own git store) shows both accept commits,
each touching the script alongside the SKILL.md files:

```
commit 861b0f7e... iter 2: ACCEPT candidate cand_0002 (val 1.000, Δ +0.100)
 .../scripts/solve_sequencing.py                    | 549 +++++++++++++++++++++
 .../__pycache__/solve_sequencing.cpython-312.pyc   | Bin 0 -> 31867 bytes

commit 31f57519... iter 1: ACCEPT candidate cand_0001 (val 0.900, Δ +0.800)
 .../scripts/solve_sequencing.py                    | 465 +++++++++++++++++++++
```

The `__pycache__/solve_sequencing.cpython-312.pyc` on the cand_0002 commit (not carried
into this evidence bundle, since compiled bytecode isn't meaningful evidence on its own —
but its *presence* in the original commit is) is the tell that the script wasn't just
written and left alone: it was actually **imported/executed by a Python interpreter**
as part of scoring that candidate.

## Bottom line

Reward moved in lockstep with the code, not with wording: 0.1 (no script) → 0.9 (new
465-line solver) → 1.0 (549-line solver, richer search neighborhood). No `policy.json`
restricted this run, and the optimizer's own change-log explicitly distinguishes
"script-only" edits from prose edits — this wasn't an accident of a documentation pass
touching a file it didn't need to.
