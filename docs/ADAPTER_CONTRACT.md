# The adapter contract

cap-evolve works with *any* target agent, benchmark, and capability because the
agent-specific glue is confined to a small adapter you implement once, in
`.capevolve/project/adapters/adapter.py`. It subclasses `CapabilityAdapter`
(`core/cap_evolve/adapter.py`).

## The three required methods

These three are `@abstractmethod` — `cap-evolve check` refuses to run until all
three are real (no `IMPLEMENT ME` stub):

```python
class Adapter(CapabilityAdapter):
    def tasks(self, split: str) -> list[Task]: ...
    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout: ...
    def score(self, task: Task, rollout: Rollout) -> Score: ...
```

- **`tasks(split)`** — where evaluation data comes from, for `split` in
  `'train' | 'val' | 'test' | 'all'`. Return the same tasks for a given split every
  call (determinism is checked).
- **`run_target(task, ctx, *, seed=0)`** — run the agent *under test* with the
  candidate capability **live as `ctx`**, and capture a `Rollout` (output, trace, tool
  calls, cost). `ctx` is whatever `live()` yields (by default the candidate dir).
  Forward `seed` if the agent is stochastic; set `Rollout.error` on an infra failure
  (never score-penalize infra failures). No scoring here.
- **`score(task, rollout)`** — return a reward in `[0, 1]` plus natural-language
  `feedback`. The feedback is the learning signal (gepa's "Actionable Side
  Information"); describe *why* generally, and **never leak the gold answer**. Must be
  deterministic on a fixed rollout (enforced by the gate).
  You may also return a `metrics` catalog of shown-only secondaries alongside the
  reward — each entry is `{name, value, primary, direction}` with `direction` in
  `higher | lower`. Exactly one entry has `primary: true` and its `value` must equal
  `reward` (the scalar the gate uses); every other entry is display-only and **never
  affects accept/reject**. Secondaries flow through the rollout/results JSON for the
  dashboard. Example (tau2 airline): primary `reward` plus shown-only `db_match`
  (higher) and `cost_usd` (lower). See `examples/tau2_airline/adapters/adapter.py`
  `_shown_metrics()`. Leave `metrics` empty to keep the plain scalar-reward behavior.

## Optional hooks (working defaults provided)

You only override these when the default behavior doesn't fit:

```python
def materialize(self, candidate_dir, edits=None) -> None   # PURE write of {component: text} edits into candidate_dir
def live(self, candidate_dir)                              # @contextmanager: make the candidate live for ONE eval, yield ctx
def apply(self, candidate_dir, edits=None) -> None         # back-compat inject hook (env var / config patch / copy)
def trajectories(self, split, ctx=None) -> Path | None     # the runner's NATIVE trace dir for the last eval (default: None)
```

Two more optional methods are **not** on the base class — the harness probes for them
with `hasattr` (`core/cap_evolve/harness.py`) and uses them when present:

```python
def run_batch(self, tasks, ctx, *, seed=0) -> ...                                  # drive a benchmark's OWN batch runner INSTEAD of run_target (as tau2 does)
def run_trials(self, tasks, ctx, *, n_trials, base_seed) -> {id: [Rollout, ...]}   # batched fast path: ALL trials in ONE run
```

`run_trials` collapses N sequential eval passes into one concurrent run; per-trial
persistence and pass^k / SE are byte-for-byte unchanged, so resume keeps working.

## Why this shape (three abstract, not prior work's three or SkillOpt's five)

Prior agent-optimization work split injection across `runner_adapter` + `inject`;
SkillOpt split the env into build/eval/rollout/reflect/get_task_types. cap-evolve folds
injection into `materialize` + `live`/`apply`, keeps reflection in the `diagnose` skill,
and leaves exactly the orthogonal responsibilities: *get data, run, score* (required),
plus *make-live* and *native traces* (defaulted).

## The gate

```bash
cap-evolve check .capevolve/project   # must print {"ok": true}
```

`cap-evolve check` loads your adapter and refuses until the three abstract methods are
implemented, `tasks` is non-empty and stable, and `score` is deterministic. This is
mandatory before any budget is spent — a half-wired adapter can only produce a
dishonest number.

The gate reads only the **primary** metric (the scalar `reward`). Any shown-only
secondaries a `score()` returns are carried through for display but can never move an
accept/reject decision or the sealed number.

## Everything else is provided

Splits, trials, gating, pass^k, rejected-memory, run-dir state, parent selection, the
sealed test, and the loop mechanics live in `cap_evolve`. Do not reimplement them in the
adapter — calling them is what keeps results comparable and honest. See
[`HONEST_EVAL.md`](HONEST_EVAL.md).
