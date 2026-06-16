# Concepts — intake and the inputs contract

> intake turns "make this agent better at X" into a runnable project. The hard
> part is not scaffolding files; it is refusing to proceed on a fabricated input.
> This note explains the contract `inputs/INPUTS.md` encodes and why it is shaped
> that way.

## The adapter is the whole interface

Everything cap-evolve measures flows through four methods the user implements in
`.capevolve/project/adapters/adapter.py`. intake's job is to make sure each one
*can* be implemented from real inputs:

| method        | question it answers                              | NEEDED input behind it |
|---------------|--------------------------------------------------|------------------------|
| `tasks(split)`| what problems do we evaluate on?                 | tasks dataset          |
| `run_target(task, capability)` | how do we run the agent under test? | target agent / runner |
| `score(task, rollout)` | how does a rollout become a reward in [0,1] + feedback? | scorer |
| `apply(capability, edit)` | how is a proposed edit materialized?      | capability artifact    |

If any of these cannot be filled from a real input, the optimization cannot
produce a meaningful number. That is why those four inputs are NEEDED, not
RECOMMENDED.

## NEEDED vs RECOMMENDED — and why the split exists

**NEEDED** = the run is meaningless without it, and there is no honest default.
The correct action when one is missing is to **ask the user** — quoting the
expected path, the command that produces it, and the alternatives — then wait.

**RECOMMENDED** = a defensible default exists. You may proceed on the default,
but you must **log the choice in `PROJECT.md`** so its honesty cost is visible.

This is the central anti-pattern guard. "Auto-optimize my agent" tools fail when
they treat a missing input as a gap to backfill: they synthesize a plausible
dataset or a lenient scorer, run green, and report a number that measures
nothing. Encoding inputs as a contract makes the only legitimate
proceed-without-input path an *explicit, recorded default* — never silent
fabrication. The model has good judgment; the contract exists so that judgment is
applied to *which question to ask*, not to *what to invent*.

### Feedback must not leak the gold

A subtle NEEDED-input rule: the scorer's textual `feedback` is what `diagnose`
turns into the learning signal. It must describe *why* a rollout failed without
quoting the gold answer. A scorer that echoes the target answer into feedback
turns the optimizer into a memorizer of the eval set — the agent "improves" on
val/test by being told the answers, and the held-out number becomes a lie. Keep
feedback general (what was wrong, what class of error), never the solution.

## Splits, trials, and budget (RECOMMENDED, but consequential)

- **Splits** — `train` / `val` / `test`. The default is a seeded ratio split
  (0.5 / 0.25 / 0.25). You may pin an official benchmark split via
  `split_ids_file`. You may also set all three equal to fit the whole set with
  **no holdout** — but then there is no honest test number, and the report must
  flag it as a *fit* metric. **train** is what the optimizer edits against;
  **val** is what the gate accepts on; **test** is sealed and scored once at
  finalize. This train/val/test discipline is the same one that keeps supervised
  ML honest — the test set must never inform a decision made during search.

- **num_trials** — trials per task. Default 1, but stochastic agents need ≥3–4:
  a single trial hides variance, so the significance gate cannot tell a real gain
  from noise, and multi-trial reliability metrics (pass^k / pass@k) are
  undefined. tau-bench introduced pass^k precisely because single-run success
  overstates how dependable an agent is.

- **budget** — `max_iterations`, `stall` (stop after N consecutive rejects),
  `max_metric_calls`, `max_usd`. A budget too small to plausibly find a gain is
  itself a misconfiguration worth flagging at intake.

## Sources
- τ-bench (Yao, Shinn, Razavi, Narasimhan, 2024) — pass^k as a *reliability*
  metric; why single-run success overstates dependability:
  https://arxiv.org/abs/2406.12045
- Koehn, "Statistical Significance Tests for Machine Translation Evaluation"
  (EMNLP 2004) — bootstrap resampling for deciding whether a score difference is
  real, the statistical backbone of the gate: https://aclanthology.org/W04-3250/
- GEPA: Reflective Prompt Evolution (Agrawal et al., 2025) — natural-language
  feedback as the learning signal the scorer must produce honestly:
  https://arxiv.org/abs/2507.19457
- Hastie, Tibshirani, Friedman, *The Elements of Statistical Learning* — the
  train/validation/test protocol and why the test set must stay sealed:
  https://hastie.su.domains/ElemStatLearn/
