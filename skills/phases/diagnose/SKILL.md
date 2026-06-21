---
name: diagnose
description: Extract the learning signal from execution traces — the textual analogue of a gradient. Use between evaluation and proposing edits. Reads a candidate's val rollouts, separates good signals to keep from bad signals to fix, builds a reflective dataset (per failing task — Inputs, Generated Outputs, Feedback) and groups failures into clusters by shared signature, so the optimizer knows what to change and why.
component: phase
argument-hint: "--run-dir DIR --tag CANDIDATE_ID"
allowed-tools: Read, Bash
provides: [reflective_dataset]
needs: [scores, traces]
sources: [gepa, skillgrad, trace2skill, evo]
---

# diagnose — failures into actionable side information

A scalar reward says *how much* a candidate failed; it does not say *why*, and
"why" is the only thing an editor can act on. diagnose converts raw traces into
the signal the optimizer edits against — the **textual analogue of a gradient**.
In reinforcement learning a scalar reward back-propagates into weight updates;
here, natural-language feedback back-propagates into prompt/tool/skill edits. The
richer that feedback, the larger the update you can extract from a handful of
rollouts.

## Inputs / outputs (manifest tokens)
- **needs:** `scores`, `traces` — the per-task rewards and rollouts from
  `evaluate` (with the scorer's textual feedback).
- **provides:** `reflective_dataset` — the structured "what to change and why"
  that the algorithm injects into the optimizer's proposal prompt.

## What it produces
- **reflective_dataset:** for each *failing* task, `{Inputs, Generated Outputs,
  Feedback}` — GEPA's reflective-dataset shape. This triple lets the optimizer see
  the task, what the agent actually did, and the diagnosis, instead of a bare
  score.
- **clusters:** ALL failing trajectories grouped by shared root cause, so the
  optimizer can fix a whole *class* of failure with one principled edit rather
  than patching tasks one at a time (and overfitting to each). "Failing" here is
  not only zero-score tasks — explicitly include **partial-credit** failures (a
  task that scored e.g. 0.5 because a write got the wrong arguments) and
  **communication / omission** failures (the agent did the action but failed to
  report or confirm the required information). These are real lost score and are
  routinely missed when only total failures are clustered. Each cluster is
  **ranked by cost** — how many tasks (and how much aggregate score) it accounts
  for — so the biggest lever is addressed first. And each cluster is tagged
  KNOWLEDGE (the agent doesn't know a format/rule/criterion → fix in the prompt)
  or BEHAVIORAL/execution (the agent knows but skips/fumbles the action, e.g.
  stalls before a write → fix in code/tools), so the optimizer knows *where* the
  fix belongs, not just what it is.
- **kept_good:** tasks already passing — the set the gate's no-regression check
  must protect, so a fix for one cluster does not silently break a passing task.

## The signal the optimizer iterates on (analyze → ideate → edit)
The reflective dataset feeds a fixed three-step shape the algorithm encodes into
the per-iteration optimizer INSTRUCTIONS — the optimizer must **analyze before it
edits**, never patch blindly:
1. **Analyze the trajectories DEEPLY first.** Read the traces closely (not a
   skim) alongside the current capability, and name (a) the MAIN RECURRING root-cause
   *clusters* — the rules and workflows the agent botches, the steps it skips, the
   tools it mis-uses or repeats N times. Cluster **ALL** failing trajectories by
   shared root cause, not only the zero-score ones: include **partial-credit**
   failures (wrong arguments to a write, a missed required action) and
   **communication / omission** failures (the action was done but the required
   info was never reported/confirmed) — these lose real score and are easy to
   overlook. **Rank the clusters by how much they cost** (tasks affected ×
   score lost), biggest first, with evidence. For each cluster, label it
   **KNOWLEDGE** (the agent lacks a format/rule/criterion → fix in the prompt) or
   **BEHAVIORAL/execution** (the agent knows but skips or fumbles the action — the
   classic stall before a write, an un-issued call → fix in code/tools): more
   prose will not fix a behavioral cluster the model already "knew" and skipped.
   Then name (b) the GOOD behaviors that occur only *sometimes* (tasks whose mean
   reward is between 0 and 1 pass on some trials and fail on others); identify what
   the good runs do so it can be made CONSISTENT. (Always-failing tasks, mean ≈ 0,
   are a root-cause fix; flaky tasks are a consistency/reinforcement fix — a
   different edit. The per-task `Feedback` line is from the *last* trial and can
   disagree with a graded mean; the reward is the honest signal.) If your coding agent
   supports parallel sub-agents, fan them out — one per failure cluster or per
   candidate-edit hypothesis — to analyze concurrently, then synthesize; it makes
   each costly iteration deeper and faster.
   **Use ground-truth / eval signals when the traces provide them.** Some benchmarks
   copy ground-truth / expected actions / a reward breakdown into the trajectories;
   when PRESENT, use them to pinpoint exactly what went wrong — which action,
   argument, or value was expected vs what the agent did. You will NOT always have
   this: if you do, use it; if not, infer from the traces + feedback. CRITICAL:
   ground truth is for UNDERSTANDING the failure class only — the resulting EDIT must
   still be a GENERAL rule, never a copied gold value (see the no-leak rule).
2. **Then ideate a DRASTIC, generalizing edit.** Each iteration is costly
   (optimize + full eval is long), so aim for a big root-cause improvement, not a
   tiny tweak: propose the single best targeted edit (or tight set) that addresses
   the biggest cluster from (a) and reinforces (b) — concrete, generalizing across
   the class, never a one-off patch to one task. When the capability is the agent's
   own tools, PREFER writing a new code-bearing tool over a docstring tweak — a
   deterministic tool can't be forgotten the way a prompt rule can: wrap a primitive
   to enforce a general rule (then remove the raw primitive), or collapse a recurring
   multi-step workflow into one looped tool. Write a real body, not `...`.
3. **Then edit and stop.** Apply it; the harness re-scores. Be economical — no
   narration, no exploring unrelated files, do exactly what's needed and finish.

## Turning traces into an actionable signal (the real work)
A good diagnosis is **specific, causal, and general**:
- **Specific:** name the concrete failure (the wrong tool call, the missing step,
  the misread field), not "the answer was wrong".
- **Causal:** point at the decision that caused it, so the edit has a target.
- **General:** describe the *pattern*, not the instance. Feedback that quotes the
  gold answer turns the optimizer into a memorizer of the eval set and corrupts
  the held-out number — keep it at the level of "what class of mistake", never
  "here is the solution".

Clustering is what makes the signal *actionable* at scale: ten tasks failing for
one reason should drive one edit, not ten. A flat list of failures invites
one-off patches that raise val by overfitting; a clustered list invites a single
generalizing change. This mirrors the lineage of "diagnose-then-edit" optimizers
(GEPA's actionable side information; trace-analysis approaches that run parallel
analysts; issue-clustering in evolutionary loops).

## Dual-mode
This phase runs two ways from the **same** SKILL.md: standalone as the slash command `/cap-evolve:diagnose` (the `argument-hint` shows its run.py args), and orchestrator-callable — `cap-evolve run` / the `orchestrate` skill invokes the same `scripts/run.py` headlessly and threads the run dir between phases.

## How to run
```
python scripts/run.py --run-dir .capevolve/run_XXXX --tag seed
```
Run it on the current best's val rollouts each round; feed `reflective_dataset` +
`clusters` into the algorithm's proposal prompt, and hand `kept_good` to the gate.

## What good vs bad looks like
- **Good:** failures grouped into a few clear clusters; feedback names the cause
  and the pattern; the biggest cluster is addressed first; gold answers never
  appear in feedback.
- **Bad:** one cluster per task (no generalization); feedback that just restates
  the reward; the gold answer leaked into feedback (the optimizer memorizes the
  eval); `kept_good` ignored so fixes regress passing tasks.

## References
- `references/concepts.md` — the reflective dataset, feedback as a textual
  gradient, why clustering beats per-task patching, the no-leak rule, and the
  optimizer lineage, with sources.
