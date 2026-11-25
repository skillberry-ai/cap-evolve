# Deterministic helpers in the editable surface

Only when the run has `helpers.enabled` and the surface declares executable files (`surface.executable_dirs`,
e.g. `skills/*/scripts` or `tools/`). Not on a prose-only surface.

**Why.** Prose is re-derived by the target on every rollout; a script is the same bytes every trial.

**When to write a helper.** Codify a procedure into a helper once it fails, or is re-implemented by hand with
different outcomes, in **2 or more distinct traces** (distinct tasks, feedback/train traces only, never test).
One trace is not enough. Name them in the hypothesis.

**What a helper is.**
- A small pure function or script: parse, locate, normalise, compute, validate. Parameterised by its inputs,
  stdlib plus packages already in the target environment, deterministic, no network, no subprocess.
- It writes only to a path its caller passes in. It never reads evaluator, gold, split or dataset paths.
- Skill surfaces: `skills/<name>/scripts/*.py` + a `SKILL.md` saying when to call them, loaded from text as
  `skills.<skill>.<script>` (`{skills_root}` = `skills`) in file-name order, no file on disk: a sibling is
  `from .<name> import f` and must sort first. Text files only, no symlink, no `answer*`/`golden*` name.
  Tau: a `tools.py` method decorated `@candidate_helper` (`cap_evolve.helpers`): its crash is the candidate's.
- General procedure only. A task id, an answer literal, a branch on task identity, or a lookup table of answers
  is refused by the lint before any rollout is charged.

**The checks (free, in the pregate, the same for every algorithm).** `helper_surface` (executable
files only in declared dirs, size caps), `helper_lint`, `helper_smoke` (imports as the target loads it, two runs
give identical output, writes only declared outputs, no network, no gold). All three run; a failure leaves the
candidate `proposed` with every finding: fix and propose again. Check first: `python -m
cap_evolve.helper_gate <cand> --parent <its parent> --config guidance/helper_gate/config.json`.

**What a helper crash costs.** A rollout failed by the candidate's own helper scores 0 (`error_kind=candidate`),
it is not missing. A flaky helper is worse than prose.

**Ledger.** One helper per hypothesis keeps its effect attributable. Once promoted, call it, do not
re-implement it. `cap_evolve.helpers.reward_variance`: per-task reward variance.
