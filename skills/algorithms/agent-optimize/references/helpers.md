# Deterministic helpers in the editable surface

Only when the run has `helpers.enabled` and the surface declares executable files (`surface.executable_dirs`,
for example `skills/*/scripts` or the `tools/` dir). On a prose-only surface this file does not apply.

**Why.** Prose is re-derived by the target on every rollout; a script is the same bytes every trial.

**When to write a helper.** Codify a procedure into a helper once it fails, or is re-implemented by hand with
different outcomes, in **2 or more distinct traces** (distinct tasks, feedback/train traces only, never test).
One trace is not enough. Name the traces in the hypothesis.

**What a helper is.**
- A small pure function or script: parse, locate, normalise, compute, validate. Parameterised by its inputs,
  stdlib plus packages already in the target environment, deterministic, no network, no subprocess.
- It writes only to a path its caller passes in. It never reads evaluator, gold, split or dataset paths.
- Skill surfaces: `skills/<name>/scripts/*.py` plus a `SKILL.md` that says when to call it. The target gets them preloaded as
  `skills.<skill>.<script>` (token `{skills_root}` = `skills`). Tau surfaces: a method in `tools.py`, decorated
  `@candidate_helper` (from `cap_evolve.helpers`) so a crash in it is attributed to the candidate.
- General procedure only. A task id, an answer literal, a branch on task identity, or a lookup table of answers
  is rejected by the lint before any rollout is charged.

**The checks (free, in the pregate; the same helper gate every algorithm runs).** `helper_surface` (executable
files only in declared dirs, size caps), `helper_lint`, and `helper_smoke` (the helper imports, two runs give
identical output, it writes only its declared outputs, no network, no gold). All three run; a failure leaves the
candidate `proposed` with every finding; fix it and propose again.

**What a helper crash costs.** A rollout that fails because the candidate's own helper raised is scored 0
(`error_kind=candidate`), not treated as missing. A flaky helper is worse than prose.

**Ledger.** One helper per hypothesis keeps its effect attributable. Once promoted, call it instead of
re-implementing it. `cap_evolve.helpers.reward_variance` reports per-task reward variance across trials.
