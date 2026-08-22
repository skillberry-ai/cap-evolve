---
name: diagnose
description: Extract the learning signal from execution traces — the textual analogue of a gradient. Use between evaluation and proposing edits. Reads a candidate's rollouts and traces, separates good signals to keep from bad signals to fix, builds a reflective dataset (per failing task — Inputs, Generated Outputs, Feedback) and clusters the failures by a (failure-site, violated-expectation) signature, ranked by the score each cluster can recover, so the optimizer knows what to change and why.
component: phase
argument-hint: "--run-dir DIR --tag CANDIDATE_ID [--project DIR] [--split train|val] [--cluster root-cause|first-words]"
allowed-tools: Read, Bash
provides: [reflective_dataset]
needs: [scores, traces]
sources: [gepa, skillgrad, trace2skill, evo]
---

# diagnose — failures into actionable side information

A scalar reward says *how much* a candidate failed; it does not say *why*, and "why"
is the only thing an editor can act on. Where RL back-propagates a scalar into
weights, natural-language feedback back-propagates into prompt/tool/skill edits —
and the richer it is, the larger the update extractable from a handful of rollouts.

## What it produces

```json
{
  "split": "val", "tag": "cand_003",
  "reflective_dataset": [
    {"task_id": "t12", "Inputs": "<what the task asked>",
     "Generated Outputs": "<what the agent produced>",
     "Feedback": "<the scorer's diagnosis>",
     "Trajectory": "<path to this task's full trace>"}
  ],
  "clusters": [
    {"signature": "confirm write", "tasks": ["t12", "t19"], "score_lost": 1.6,
     "tag": "BEHAVIORAL", "blast_radius": ["t3", "t7"]}
  ],
  "kept_good": ["t1", "t4"]
}
```

`scripts/run.py` emits everything except `tag` (one of KNOWLEDGE, BEHAVIORAL,
DECISION / PERMISSION, CAPABILITY-GAP) and `blast_radius`, which it leaves `null`
because they need judgement — filling them in is the work below. `kept_good` is the
set the gate's no-regression check protects.

## What counts as a failure

Not only zero-score tasks. Three kinds are real lost score and routinely missed:
**partial credit** (scored e.g. 0.5 because one part of the action was wrong),
**communication / omission** (the action happened but the required information was
never reported or confirmed), and **near-miss** (≈0.7–0.9, one small correct change
from a pass — the cheapest marginal gain per edit, easiest to overlook while staring
at the zeros).

Separate *always-failing* (mean ≈ 0 — a root-cause fix) from *flaky* (0 < mean < 1 —
a consistency fix; find what the passing trials do and make it reliable). The reward
is the honest signal: a per-task `Feedback` line comes from the **last** trial and
can disagree with the graded mean.

## Where the trace comes from

The rollout record supplies the score and the feedback; the **trajectory** supplies
the failure site, and the site is half of the cluster key. The runner owns the trace
format, so never assume one — the location is asked for, not guessed:

- standalone: `adapter.trajectories(split)` returns the directory (any structure,
  any format). `run.py --project DIR` resolves it and attaches the path to each
  entry as `Trajectory`; it never parses it. With no native store the pointer falls
  back to the rollout record's own file, which core wrote.
- inside an optimizer workdir: that directory has already been copied verbatim to
  `./trajectories/`. Read it there. `scripts/` is not copied into
  `./guidance/diagnose/`, so cluster by hand using the procedure below — it is the
  same procedure the script runs.

## Clustering: deriving the signature

A cluster is ONE root cause, identified by a **(failure-site, violated-expectation)**
pair: *where* the trajectory went wrong (the tool, field, or step the trace names)
and *which* expectation was missed. Two failures belong to the same cluster when
both halves agree — however differently the scorer phrased it, and whatever
task-specific values it quoted. Derive the key like this:

1. **Strip the scorer's boilerplate.** Drop the leading token run that *every*
   failure's feedback shares. A scorer that opens each message with "Grading failed
   because the expected outcome was not met" otherwise makes all failures look
   identical.
2. **Reduce to content words.** Drop quoted literals and numbers (task-specific, not
   causal), drop stopwords, and drop outcome-generic words — `failed`, `wrong`,
   `missing`, `expected`, `invalid` name *that* it failed, never *why*. Collapse
   inflections (`confirm` / `confirmed` / `confirmation` are one token).
3. **Read the survivors as the pair.** Identifiers the trace names are the site;
   the remaining verbs are the expectation.
4. **Same cluster iff the keys OVERLAP** — half or more of the smaller key's tokens
   are shared — merged transitively. Overlap rather than equality is what keeps "did
   not confirm the change", "omitted required confirmation step" and "missing
   confirmation before the write" as one cluster instead of three.

Two sanity checks on the result: one cluster per failing task means the signature is
too fine and no generalizing edit is possible; one cluster spanning visibly
different causes means it is too coarse — usually an unstripped preamble (step 1).

## Tag each cluster

The tag says *where the fix belongs*. The lever itself is the selected capability's
business (`./guidance/<cap>/SKILL.md`); the tag tells it which kind of lever to reach
for, and its **blast radius** is the set of currently-passing tasks the fix would
change.

- **KNOWLEDGE** — the agent cannot derive a format, rule, or criterion. Stating it
  in prose is the right lever here. Blast radius: tasks reading the same instruction.
- **BEHAVIORAL** — the agent knows the rule and violates it anyway. Restating it in
  prose will not fix this; the rule has to move somewhere it cannot be skipped — the
  strongest deterministic lever the capability offers. Blast radius: every task
  exercising the same rule or path.
- **DECISION / PERMISSION** — the wrong act-vs-refuse/escalate call on a
  policy-governed class. Fix the exact discriminating **condition**, never the
  class-wide rule: a class-wide change flips behavior for the whole class and
  regresses every task where the original behavior was already correct. Blast radius
  is therefore *every* passing task in that decision class — name them and confirm
  the fix does not flip their action.
- **CAPABILITY-GAP** — no reliable mechanism exists, or the agent narrates a
  multi-step action and then stalls without executing it. Needs the strongest
  STRUCTURAL lever available. Tagged separately so a stall is not mis-filed as
  BEHAVIORAL and "fixed" with a nudge that never works.

## Rank the clusters

A cluster's value is **the score it can recover minus the regression risk to its
blast radius** — which is why the radius is named per cluster and scoped to tasks
concretely (ids, not "the same tool"), so the edit can be made to fire only on the
failing condition. Then:

- rank by cost (`score_lost`), biggest first — but do not let a small cluster whose
  fix is STRUCTURAL sink under task count: a 2-task stall cracked by one new
  mechanism can outweigh a many-task cluster of cosmetic misses;
- note a multi-cause task's **secondary** cause too, so one edit can take the
  primary and the residual together;
- cross-check the run history (LEDGER / prior iterations) and skip any cluster whose
  fix was already tried and rejected — do not re-diagnose a refuted approach.

## Feedback quality

Write each diagnosis **specific** (the wrong call, the skipped step, the misread
field — not "the answer was wrong"), **causal** (the decision that produced it, so
the edit has a target), and **general** (the pattern, not the instance).

Some benchmarks copy ground truth or expected actions into the traces; when present
use them to pinpoint which action, argument, or value was expected — for
*understanding* only. Feedback that quotes the gold answer keeps the level at *what
the right answer is* instead of *what class of mistake was made*, and the optimizer
then memorizes the eval set (`references/concepts.md` has the full consequence).

## How to run

```
python scripts/run.py --run-dir .capevolve/run_XXXX --tag seed \
    --project .capevolve/project --split val
```

Run it on the current best candidate's rollouts each round, then tag, rank, and hand
the clusters to the algorithm's proposal prompt. `--split train` diagnoses train —
the honest learning surface when the gate scores val. `--cluster first-words` is the
old lexical key, kept for comparison only. The same script runs headlessly under
`cap-evolve run` / the `orchestrate` skill, which threads the run dir between phases.

## References

- `references/concepts.md` (~90 lines) — why a scalar reward is not enough, the
  reflective dataset's provenance in GEPA, why clustering beats per-task patching,
  the full consequence of a leaked gold answer, and the optimizer lineage with
  sources. Load it for the *why* behind this procedure or a citation for it; the
  procedure itself is complete above.
