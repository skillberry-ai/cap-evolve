# PROCESS — what I did this iteration (explainability; REQUIRED)

Candidate: cand_0002 (parent: cand_0001, the current champion, val=0.900).

## Decision: SHIP NO CAPABILITY EDITS THIS ITERATION (no real failing cluster exists)

Only val task: syzkaller-ppdev-syzlang. This iteration's `./trajectories/` are the 10
seed trials of the champion cand_0001:

| trial | reward | verifier result |
| --- | --- | --- |
| t0 | 0.0 | **NO rollout** — `error: bench eval run timed out after 2400s`; `output=None`, `trace=None`, `tool_calls=0`. Feedback: *"Rollout did not complete for an infrastructure reason … Uncontrollable noise, not a skill defect; do not optimize against it."* |
| t1–t9 (9 trials) | 1.0 each | **7/7 pytest tests passed** (`test_files_exist_and_have_includes`, `test_compilation_and_const_validation`, `test_fd_ppdev_resource_and_open`, `test_all_ioctls_with_correct_signatures`, `test_structs_and_flags_defined`, `test_ioctl_and_mode_constant_values`, `test_build_syzkaller`). |

Mean reward = 0.90 = 9×1.0 / 10, with the single 0.0 being the infra timeout. The 0.90
is a **ceiling imposed by infra variance, not by any skill defect.**

## Ranked issue list (clusters by leverage)
| rank | cluster | tasks(trials) | root cause | tag | action |
| --- | --- | --- | --- | --- | --- |
| — | (none) | — | No verifier assertion fails in any completed trial. The 3 clusters that failed under the seed (hex `.const` values; spurious `arg const[0]` on `_IO` ioctls; budget exhaustion) were ALL fixed by cand_0001 and no longer appear. | — | none |
| n/a | infra timeout | t0 | Whole-eval 2400s wall-clock timeout; no agent output captured at all. Dominated by environment/build contention on shared hardware, not by anything the skill text controls. | INFRA-NOISE | **excluded by explicit instruction** |

There is **no cluster that passes the REAL test** (a failing verifier assertion tied to a
skill defect in this iteration's traces). Therefore there is nothing to fix.

## Why I did not ship speculative edits
Every candidate edit was evaluated against the THREE TESTS and dropped:
- **REAL** — fails. No completed trial has a failing assertion. The one failure (t0) is
  an infra timeout the instructions explicitly say not to optimize against, and it carries
  ZERO agent output, so there is no behavior to diagnose or correct.
- **SAFE** — any edit to `syz-extract-constants`, `syzlang-ioctl-basics`, or
  `syzkaller-build-loop` has a wide blast radius: those three skills are what the 9 passing
  trials rely on to score 7/7. A rewrite risks pushing a currently-passing trial onto a
  worse path — the exact way a good iteration gets sunk.
- **VERIFIED** — impossible: there is no failing assertion to tie a fix to.

Options I explicitly considered and rejected:
- *"Efficiency" edits to reduce timeout risk* (e.g. tell the agent to skip `make all` since
  the verifier builds too, or trim exploration further). Rejected: (a) the instruction bars
  optimizing against the infra timeout; (b) t0 produced no output, so the timeout was not
  the agent being slow — it was the eval environment; (c) telling the agent not to build
  would remove its own compile-check of the descriptions and could ship non-compiling
  syzlang → `test_build_syzkaller` / `test_compilation_and_const_validation` regress. Not safe.
- *A task-specific gen-ppdev script.* Overfitting — forbidden by the NON-OVERFITTING rule;
  cand_0001's PROCESS already recorded this as deliberately skipped.

## Verify-the-fix
N/A — no fixes shipped. Verification performed instead:
- Confirmed t0 is a content-free infra timeout (`rollout.output=None`, `trace=None`,
  `error="bench eval run timed out after 2400s"`) in both `./trajectories/` and the live
  `rollouts/val/`.
- Confirmed t1–t9 each report `summary.passed=7, failed=0`.
- Re-ran the bundled `syz-extract-constants/scripts/ioctl.py` on the ppdev ioctls to confirm
  it is still correct: `IO p 0x8b → 28811`, `IOW p 0x80 4 → 1074032768`,
  `IOR p 0x98 4 → 2147774616` (matches the oracle). No latent bug found.
- Read all three SKILL.md bodies + the script; found no incorrect or misleading guidance
  that the agents merely worked around.

## Process & features used
- Serial diagnosis (single val task, 10 traces). Parallel subagents/worktrees would add
  overhead with no benefit for a single already-solved task.
- Read STEP-0 files, LEDGER, JOURNAL, RUNMAP, all three skills + script, and both the
  `./trajectories/` and live `rollouts/val/` copies of the traces.

## Good things to PRESERVE (do not let a future iteration undo these)
- `syz-extract-constants/scripts/ioctl.py` + the "decimal not hex" body rule (fixed cluster 1/3).
- The no-arg `_IO` ioctl pattern in `syzlang-ioctl-basics` (fixed cluster 2).
- The write-files-early efficiency note in `syzkaller-build-loop`.
These three are why every completed trial now scores 7/7. Do not rewrite them.

## Deliberately skipped
- Everything. The task class is solved by the champion; the residual 0.10 gap is a
  documented, excluded infrastructure timeout. Adding edits would be speculative padding
  that risks regressing the 9 passing trials against the significance gate.

## Note to next iteration
If the re-score of this task still sits at ~0.90, inspect whether the non-passing trial is
AGAIN a content-free `timed out after 2400s` / `output=None` case. If so, it remains infra
noise — do NOT manufacture skill edits against it. Only act if a completed trial produces a
real failing verifier assertion.
