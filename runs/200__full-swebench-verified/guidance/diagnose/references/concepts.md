# Concepts — diagnosis as a textual gradient

> A reward tells you *how much* a candidate failed. An editor can only act on
> *why*. diagnose converts traces into that "why" — the learning signal the
> optimizer edits against. Implementation: `diagnose()` in this skill's
> `scripts/run.py`.

## Why a scalar reward is not enough

Reinforcement learning turns a scalar reward into a parameter update via a
gradient. Prompt/tool/skill optimization has no weights to nudge — the artifact
is text. The substitute for the gradient is **natural-language feedback**: a
diagnosis of what went wrong that an LLM optimizer can read and translate into a
concrete edit. GEPA's central finding is that language is a *richer* learning
signal than a scalar reward — it carries direction and cause, not just
magnitude — which is why reflective evolution can match or beat RL using far
fewer rollouts. diagnose is where that signal is manufactured.

## The reflective dataset

For each failing task, diagnose emits the triple GEPA calls a reflective dataset:

- **Inputs** — what the task asked.
- **Generated Outputs** — what the agent actually produced.
- **Feedback** — the scorer's diagnosis of the failure.
- **Trajectory** — a *path* to the full trace (reasoning, tool calls). A path and
  not parsed content, because the trace format belongs to the runner: the location
  comes from `Adapter.trajectories(split)`, which is documented to return "*any*
  structure, files in *any* format". Anything that parsed it here would bind this
  phase to one runner, which a phase skill may never do.

Giving the optimizer this triple instead of a bare score is the difference
between "you got 0.4" and "on these inputs you called the wrong tool because you
misread field X; here is the trace." Only the latter tells it what to change.

## What makes feedback *actionable*

Three properties, in order of importance:

1. **Specific** — name the concrete failure (wrong tool, skipped step, misread
   field), not "incorrect".
2. **Causal** — point at the decision that produced it, so the edit has a target.
3. **General** — describe the *pattern*, not the single instance, so the fix
   transfers to unseen tasks.

### The no-leak rule (non-negotiable)
Feedback must never quote the gold/target answer. If it does, the optimizer can
"fix" a task by hard-coding the answer into the prompt — it memorizes the eval set
instead of learning the capability. Val climbs, the sealed test number collapses,
and the run's headline becomes a lie. Keep feedback at the level of *what class of
mistake was made*, never *what the right answer is*. This is the same discipline
the scorer must honor at intake.

## Clustering: fix classes, not instances

Listing failures flatly invites the optimizer to patch each one individually —
which overfits to the val set and bloats the artifact. Grouping failures by a
shared signature turns the signal **actionable at scale**: ten tasks failing for
one reason become one generalizing edit. This is the through-line of the
diagnose-then-edit optimizer family:

- **GEPA** — *actionable side information* distilled from trajectories, then
  combined across a Pareto frontier of variants.
- **Trace-analysis optimizers** — parallel analysts read traces and surface
  recurring failure modes.
- **Evolutionary loops** — cluster issues so each generation targets a class of
  defect rather than a single example.

A good round produces a *few* clusters; "one cluster per task" means the signature
is too fine and no generalization is happening.

### Why the signature is an overlap test, not a string match

SKILL.md gives the procedure; this is why it has the shape it does. A signature
built by hashing the leading words of the scorer's feedback fails in both
directions, and both failures are silent:

- **Fragmentation.** One root cause reaches the scorer in many phrasings — "did not
  confirm the change", "omitted required confirmation step", "missing confirmation
  before the write". Under string equality that is three clusters, so the optimizer
  writes three narrow patches for one defect and overfits val three times over.
  Requiring only *overlap* between the content-word keys keeps them together.
- **Collapse.** A scorer whose every message opens with a fixed preamble ("Grading
  failed for this trajectory because the expected outcome was not met: …") makes
  every failure share its first dozen tokens. Under a prefix key the entire signal
  becomes one cluster. Stripping the prefix that *all* failures share removes the
  boilerplate without anyone having to configure a per-benchmark pattern.

Both directions are regression-tested in `scripts/check.py`; the mechanism is
`scripts/cluster.py`.

## Hand-off to the gate

diagnose also emits `kept_good` — the tasks the current candidate already passes.
This is the baseline the gate's **no-regression** check protects: a fix for one
failure cluster must not silently break a passing task. Diagnosis and acceptance
are two halves of one honest loop — diagnose says what to change; the gate refuses
changes that trade a real pass for an aggregate bump.

## Sources
- GEPA: Reflective Prompt Evolution Can Outperform RL (Agrawal et al., 2025) —
  reflective dataset, natural-language feedback as the learning signal, Pareto
  combination of lessons: https://arxiv.org/abs/2507.19457
- DSPy / MIPRO lineage (Opsahl-Ong et al., 2024) — bootstrapped
  instruction/demonstration optimization from execution feedback:
  https://arxiv.org/abs/2406.11695
- τ-bench (Yao et al., 2024) — trajectory-level failures that only trace
  inspection reveals: https://arxiv.org/abs/2406.12045
