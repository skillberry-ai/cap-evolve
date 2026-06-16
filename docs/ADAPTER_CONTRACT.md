# The adapter contract

cap-evolve works with *any* target agent, benchmark, and capability because the
agent-specific glue is confined to four methods you implement once, in
`.capevolve/project/adapters/adapter.py`:

```python
class Adapter(CapabilityAdapter):
    def tasks(self, split) -> list[Task]: ...
    def run_target(self, task, candidate_dir, split) -> Rollout: ...
    def score(self, task, rollout) -> Score: ...
    def apply(self, candidate_dir, edits=None) -> None: ...
```

## What each method owns

- **`tasks(split)`** — where evaluation data comes from. Return the same tasks
  for a given split every call (determinism is checked).
- **`run_target(task, candidate_dir, split)`** — run the agent *under test* with
  the candidate capability live, and capture a `Rollout` (output, trace, tool
  calls, cost). No scoring here.
- **`score(task, rollout)`** — return a reward in `[0, 1]` plus natural-language
  `feedback`. The feedback is the learning signal (gepa's "Actionable Side
  Information"); describe *why* generally, never leak the gold answer.
- **`apply(candidate_dir, edits=None)`** — make the capability in `candidate_dir`
  the one the target actually uses (env var, config patch, copy into a skills
  dir). With `edits`, write them first, then make live.

## Why four (and not prior agent-optimization work's three or SkillOpt's five)

prior agent-optimization work split injection across `runner_adapter` + `inject`; SkillOpt split the env
into build/eval/rollout/reflect/get_task_types. We fold injection into
`apply(edits=None)` and keep reflection in the diagnosis skill, leaving exactly
the four orthogonal responsibilities: *get data, run, score, make-live*.

## The gate

`cap-evolve check .capevolve/project` loads your adapter and refuses until all four
methods are implemented (no `IMPLEMENT ME` stubs), `tasks` is non-empty and
stable, and `score` is deterministic. This is mandatory before any budget is
spent — a half-wired adapter can only produce a dishonest number.

## Everything else is provided

Splits, trials, gating, pass^k, rejected-memory, run-dir state, parent selection,
and the loop mechanics live in `cap_evolve`. Do not reimplement them in the
adapter — calling them is what keeps results comparable and honest.
