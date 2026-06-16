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
- **clusters:** failing tasks grouped by a shared feedback signature, so the
  optimizer can fix a whole *class* of failure with one principled edit rather
  than patching tasks one at a time (and overfitting to each).
- **kept_good:** tasks already passing — the set the gate's no-regression check
  must protect, so a fix for one cluster does not silently break a passing task.

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
