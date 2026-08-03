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
def runner_model(self) -> str | None                       # the CONSUMING model id, for check's mismatch note (default: None)
```

Three more optional fast paths are **not** on the base class — the harness probes for them
with `hasattr` (`core/cap_evolve/harness.py`) and uses them when present:

```python
def run_batch(self, tasks, ctx, *, seed=0) -> ...                                  # drive a benchmark's OWN batch runner INSTEAD of run_target (as tau2 does)
def run_trials(self, tasks, ctx, *, n_trials, base_seed) -> {id: [Rollout, ...]}   # batched fast path: ALL trials in ONE run
def score_batch(self, tasks, rollouts) -> {id: Score}                             # batched fast path: score a WHOLE trial in ONE call (e.g. one Docker harness invocation, as swebench does)
```

`run_trials` collapses N sequential eval passes into one concurrent run; per-trial
persistence and pass^k / SE are byte-for-byte unchanged, so resume keeps working.
`score_batch` is the scoring-side counterpart: the harness calls it once per trial with
that trial's `{task_id: Rollout}` instead of looping `score()` per task — the point is a
benchmark whose real evaluation cost is in an external harness (e.g. a Docker build per
instance) can batch that harness call and let it parallelize internally. Any task id the
batch omits falls back to a single `score()` call, so a partial implementation can never
silently drop a score.

## Concurrency: `parallel_safe` (optional class attribute)

Only relevant under `cap-evolve run --parallel N`, which evaluates N *sibling* candidates
per round, each in its own hermetic workspace, from N threads of one process. **A
third-party adapter is not required to be reentrant** — omitting the attribute is always
safe, it just costs throughput.

```python
class MyAdapter(CapabilityAdapter):
    parallel_safe = True    # I assert: this adapter may be driven from several threads at once
```

Resolution is **default-deny** for the hook that can be a global inject:

| Adapter | Resolved | Why |
|---|---|---|
| declares `parallel_safe = True` / `False` | as declared | your declaration is authoritative |
| overrides `apply` or `live`, no declaration | **serial** | those hooks are allowed to be a *global* inject — one shared slot two concurrent candidates would clobber |
| overrides neither, no declaration | parallel | uses the pure default `live()`, which only yields the candidate dir |

A downgrade is logged as a `parallel_downgraded` event, so a silent loss of speedup is
never mistaken for a speedup that failed to materialize.

**What `parallel_safe = True` obliges you to.** It asserts that `materialize → live →
run_target → score` for candidate A cannot observe or disturb candidate B: read and write
only `ctx` / the candidate dir, and mutate no process- or host-global state — no module
globals, no shared cache, no `chdir`, no writes to one fixed temp path, no env-var
injection, and **no global RNG**.

The global RNG is the trap worth naming explicitly. `random.seed()` / `random.random()`
and `numpy.random.seed()` / `numpy.random.random()` share one hidden generator across all
threads, so an adapter that seeds it once per batch and then draws per task produces
different per-task rollouts under `--parallel` — and the divergence can be invisible in
the aggregate mean, which is worse than a crash. Seed a local instance:

```python
rng = random.Random(seed)                # not random.seed(seed)
rng = numpy.random.default_rng(seed)     # not numpy.random.seed(seed)
```

That is also what makes a *serial* run reproducible, and it is what every RNG inside
`cap_evolve` itself does.

Note the one gap: an adapter overriding neither `apply` nor `live` is auto-approved as
parallel-safe no matter what other global state it touches. So `parallel_safe` — declared
or inferred — is **your** assertion of reentrancy, not something cap-evolve verified. When
in doubt set `parallel_safe = False` and lose the throughput.

Finally, `--parallel N > 1` **changes the search**: it forks N siblings from one champion
(breadth) rather than one step per accept (depth), so the accept sequence, `best_id` and
the sealed test number differ from a serial run's and can be worse on the same iteration
budget. `N = 1` (the default) is the only mode that reproduces a serial trajectory.

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
