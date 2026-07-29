# Concepts — the hard gate before budget

> implement-and-check verifies the measurement apparatus before any measurement
> is trusted. A green check is the only honest entry into the optimization loop.
> Implementation: `cap_evolve.check.run_check` + each skill's `scripts/check.py`.

## The adapter is the contract

cap-evolve measures everything through **3 required methods** the user implements
(plus defaulted hooks). The check verifies each required one is real:

| method                             | contract                                            | failure if stubbed                |
|------------------------------------|-----------------------------------------------------|-----------------------------------|
| `tasks(split)`                     | non-empty, stable across calls                      | mean over nothing; unstable split |
| `run_target(task, ctx, *, seed=0)` | runs the agent, captures output + trace into Rollout| no behavior to score              |
| `score(task, rollout)`             | reward ∈ [0,1] + general feedback, deterministic    | every candidate scores the same   |

Beyond those three, `materialize(candidate_dir, edits=None)`, `live(candidate_dir)`,
`apply(candidate_dir, edits=None)`, `trajectories(split, ctx=None)` and `runner_model()`
are **defaulted hooks** — they are defined on the base class with working defaults (the
last two `return None`) and are called unconditionally, so override them only when the
default does not fit. Separately, `run_batch` / `run_trials` / `score_batch` are **not** on
the base class at all; the harness feature-detects them with `hasattr` and uses them only
when an adapter defines them.

If any required method is a stub, the optimization still *runs* — it just produces a number
that measures nothing. The whole point of a pre-budget gate is to make that
failure loud and early instead of silent and expensive.

## Why each check exists

- **No stubs.** A `NotImplementedError` or empty body returns nothing; downstream
  the reward is vacuous. The check refuses to call a method that was never filled.
- **`tasks` non-empty and stable.** The split is computed from the task list. If
  `tasks()` is empty, there is nothing to average; if it shuffles between calls,
  the split is not reproducible and train/val/test stop being disjoint across
  reruns.
- **`materialize()` probed.** An edit that cannot be materialized onto a capability
  copy cannot be evaluated — the loop would propose into the void. The check calls it
  against a temp copy; because `materialize` is pure, the host is never mutated. This is a
  **probe, not an assertion**: a raise is reported as a note and does NOT fail the check
  (`check.py:166-167`), because a real adapter may legitimately need its full environment.

## Scorer determinism vs target stochasticity — a crucial distinction

These are *not* the same thing, and the check only forbids one:

- **Target (agent) stochasticity is expected and legitimate.** A sampling LLM
  agent gives different rollouts each run. That variance is *measured*, not
  banned — it is exactly what multi-trial evaluation, combined standard error,
  and pass^k exist to quantify.
- **Scorer nondeterminism is a bug.** If `score(task, rollout)` returns different
  rewards for the *same* rollout, the "reward" includes noise that originates in
  the measuring instrument, not in the agent. The optimizer cannot learn against
  a ruler that changes length. The check scores a fixed rollout twice and requires
  agreement.

A scorer that calls an LLM judge can still be deterministic enough: fix the
judge's decoding (temperature 0) or average enough judge samples that the per-call
variance is negligible, and treat any residual as part of the (measured) trial
variance rather than smuggling it into a single score.

## Validation gate before budget — the discipline

Self-improving systems that skip a wiring check tend to "improve" against broken
measurements and report gains that vanish on inspection. The fix, common to
skill-/agent-optimization frameworks, is a non-negotiable validation gate: prove
the contract holds, *then* spend. implement-and-check is that gate for cap-evolve —
the analog of running a test suite green before trusting a benchmark built on top
of it. The no-gold-leak rule from intake also belongs here in spirit: a scorer can
pass the determinism check and still corrupt the run if its feedback hands the
optimizer the answer, so verify feedback stays at the level of *why it failed*,
never *what the answer was*.

## Sources
- GEPA: Reflective Prompt Evolution (Agrawal et al., 2025) — the loop is only as
  honest as the feedback/score it runs on: https://arxiv.org/abs/2507.19457
- SWE-bench (Jimenez et al., 2024) — execution-based, deterministic scoring as the
  precondition for a meaningful benchmark: https://arxiv.org/abs/2310.06770
- τ-bench (Yao et al., 2024) — separating agent stochasticity (measured via
  trials) from measurement error: https://arxiv.org/abs/2406.12045
