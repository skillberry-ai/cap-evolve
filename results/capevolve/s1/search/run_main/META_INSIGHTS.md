# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

## cand_0001
- 5 parallel read-only diagnosis subagents (10 tasks each) + serial edit merge worked well: full coverage of 49 failing tasks in ~4 minutes, no context overflow. Reuse this shape.
- The optimizer environment lacks openpyxl/network: verify helper scripts against a minimal in-memory openpyxl shim written to a temp dir inside the workdir (deleted before stopping), or keep helpers self-contained (own range parser in range_utils.py).
- The scorer feedback summary in INSTRUCTIONS.md truncates; always compute per-task mean rewards from trajectories/*.json directly — the listed "(a)/(b)" groups understate the failing set (49 actual vs 30+19 listed, consistent).

## Iteration cand_0002
- A single python pass over all 360 traces (classification by fmt-fail counts / duplicate-message counts / feedback text) gave full-cluster coverage in one step — cheaper and more precise than the 5-subagent fan-out used in iteration 1. Prefer this first, then read 3-4 representative traces.
- When a prior candidate scores exactly 0.000 with fixed={}, suspect MECHANICAL failure (lint/smoke/placeholder), not behavior — redesign for lint-safety before re-attempting the same behavioral fixes.

## Iteration cand_0004
- cand_0001 and cand_0002 both scored EXACTLY 0.000 with byte-identical broke/unresolved sets despite different prompt content — that pattern means no rollouts ran (mechanical kill at lint/smoke/validation), not a behavioral regression. Treat "val=0.000 + fixed={}" as a mechanical-failure signature and redesign for lint-safety rather than re-reasoning about behavior.
- New mechanical-safety checklist shipped with cand_0004: (1) no braces outside the known {skills_root} placeholder in ANY agent-visible text that may be format-substituted (prompt.md AND SKILL.md — the priors only format-simulated prompt.md); (2) scripts must import + self_check green in BOTH layouts (flat skills.<pkg>.<script> and scripts subpackage) without openpyxl; (3) leave task_template.md untouched unless a cluster demands it, to shrink the kill surface.
- If cand_0004 also zeroes, the next iteration should BISECT surfaces (prompt-only first) instead of diagnosing behavior — one iteration spent isolating the killer beats three more blind rejections.

## Iteration cand_0005
- Strategy: after 3 mechanical deaths (0.000, zero rollouts), switched from combined prompt+scripts batches to a MINIMAL-SURFACE BISECT (prose-only, no fences/scripts/braces). This is the right move whenever repeated candidates die with the all-tasks-broke signature: shrink the changed surface to isolate the killer before spending more eval budget (LEDGER rows 1,2,4 vs 3).
- Budget awareness forced the choice: 1800/2160 rollouts used ≈ one eval left — a candidate that might die mechanically has negative expected value regardless of its behavioral merit.
- Next iteration must read the cand_0005 RESULT as a measurement of the KILLER, not just of the behavioral rules: ACCEPT ⇒ fences-or-scripts was the killer, scripts can return; 0.000 ⇒ prompt.md editing itself is fatal.
