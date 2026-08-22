---
name: implement-and-check
description: Runs the hard gate that has to pass before any optimization budget is spent. Use right after intake. Walks the agent through implementing the 3 required adapter methods plus any defaulted hooks that need overriding (and any selected skill's abstract methods), then runs `cap-evolve check` on the project plus each involved skill's check.py, listing exactly what is still stubbed or non-deterministic and what to do about each kind of failure.
component: phase
argument-hint: "--project .capevolve/project --skill-check PATH"
allowed-tools: Read, Write, Edit, Bash
provides: [checked]
needs: [project]
sources: [skillopt]
---

# implement-and-check — make the contract real

Optimizing against a half-wired adapter produces a number that means nothing: a stub
scorer gives every candidate the same reward, an empty `tasks()` averages over nothing,
a non-deterministic scorer makes the gate chase measurement noise. This phase proves the
measurement apparatus works *before* budget is spent. It is cheaper to fail here than
after a full run.

## Steps

1. **Implement the 3 required adapter methods** in
   `.capevolve/project/adapters/adapter.py`. These are the `@abstractmethod`s
   (`core/cap_evolve/adapter.py:77-106`) — the gate refuses to run until all three are real:
   - `tasks(split)` → `list[Task]` for `'train'|'val'|'test'|'all'`; non-empty, same list
     every call.
   - `run_target(task, ctx, *, seed=0)` → `Rollout`. Run the agent under test with the
     candidate live as `ctx`; capture output + trace + tool calls + cost. Do not score
     here. Forward `seed` if the runner is stochastic; set `Rollout.error` on an infra
     failure so the engine treats it as noise, not as a low score.
   - `score(task, rollout)` → `Score`: reward in `[0,1]` + general feedback (it becomes
     the diagnosis signal, so never leak the gold answer).

   Override a **defaulted hook** only when its default does not fit:
   `materialize(candidate_dir, edits=None)` (pure write of `{component: text}`),
   `live(candidate_dir)` (context manager yielding `ctx`),
   `apply(candidate_dir, edits=None)` (back-compat inject),
   `trajectories(split, ctx=None)` and `runner_model()` (both default `None`).
   Three **optional fast paths** are not on the base class at all — the harness
   feature-detects them with `hasattr` and uses them only if you define them:
   `run_batch(tasks, ctx, *, seed)` (drive a benchmark's own batch runner *instead of*
   `run_target`), `run_trials(tasks, ctx, *, n_trials, base_seed)` (all trials in one
   concurrent run), `score_batch(tasks, rollouts)` (score a whole trial in one external
   harness call). `docs/ADAPTER_CONTRACT.md` is the full contract, including the
   shown-only `metrics` catalog `score()` may return.

   Note `capability_sources` is **not** an adapter method — it is a `capevolve.yaml` key
   (the data-model/types files copied into the optimizer's context), owned by intake.

2. **Implement any selected skill's `scripts/abstract.py`** (most are concrete and need
   nothing).

3. **Run the gate:**
   ```
   python scripts/run.py --project .capevolve/project \
       --skill-check <skills>/capabilities/<cap>/scripts/check.py
   ```
   Exit 0 = green. The JSON has three fields with three different meanings — see the
   table below before you react to it.

4. **Pipeline-wiring self-test (automatic once the check is green).** A green adapter is
   necessary but not sufficient — the optimizer also needs its *context* wired. `run.py`
   then runs `pipeline_selftest.py` (zero API cost): the optimizer-prompt template named
   by `capevolve.yaml::optimizer_instructions_file` exists, still carries its `{{...}}`
   placeholders, and renders through the real harness renderer with none left over; and
   whether the adapter defines `trajectories()` or inherits the base default (both valid,
   both reported). The template checks are **skipped with a note** for an algorithm that
   never reads the template — only `hill-climb` is passed `--instructions-file`
   (`cli.py:869-876`). `--no-pipeline-selftest` skips it; it also runs standalone.

   A full one-iteration mock run is deliberately not attempted: it would need a baseline,
   a frozen split and a run dir that do not exist yet at gate time, and building them is
   benchmark-specific. This exercises the same workdir-building and prompt-rendering paths.

## When it is red — what to do, per failure kind

`CheckReport` has three fields (`core/cap_evolve/check.py:30-38`) and only `problems`
affects `ok`. Treating a note as a failure is how an agent gets stuck in a loop.

| report field / message | what it means | do this |
|---|---|---|
| `stubs: ["<name>"]` | that method still raises the `IMPLEMENT ME` marker | write the method in `adapters/adapter.py`; nothing later was even probed (`check.py:102-107`) |
| `"could not load adapter: ..."` | import/instantiation failed — often an unimplemented `@abstractmethod` (`TypeError`) or a bad sibling import | fix the import or define all three abstract methods; the adapter's own dir is on `sys.path`, so sibling helpers import plainly |
| `"tasks('val') raised: ..."` | the data path is wrong | point `tasks()` at real data; check the `split` argument is being honored |
| `"tasks('val') returned an empty list"` | the split has no tasks | usually a filter or path that matched nothing — print the list before returning |
| `"tasks('val') is not stable across calls"` | ids differ between two calls | remove `set`/`dict` iteration order and any per-call shuffle; sort explicitly |
| `"scorer is non-deterministic: X vs Y"` | `score()` returned two rewards for one rollout | remove the RNG, or pin an LLM judge's decoding (temperature 0) and cache nothing that hides the variance |
| `"score(...) raised on a probe rollout"` | the scorer cannot survive an unfamiliar output | make `score()` total — an unparseable output is reward 0 with feedback, not an exception |
| `notes: [...]` | informational, incl. the `materialize()` probe raise and the consuming-model tier mismatch | read; do **not** treat as failure |
| skill `check.py` red | that capability/algorithm skill's own contract is unmet | run its `check.py` directly; its JSON names the assertion |

Re-run until green. Green is the entry condition for `baseline`.

## What the gate does and does not guarantee

Determinism is genuinely executed, not asserted: `check.py:133-142` scores one fixed
rollout twice and reports a problem when the rewards differ. Do not read more into green
than that. Measured on this checkout (issue #358):

- **`run_target` is never called** on the default path, so a `pass`-body runner goes
  green and fails later, after the split is frozen.
- The scorer probe uses a **synthetic** rollout (`output="__probe_output__"`), so a
  scorer that short-circuits on unrecognizable output — every LLM-judge scorer — is not
  really tested. Both `score()` calls happen on one in-process instance, so a memoized
  scorer is unfalsifiable here.
- `materialize()` is a **probe, not an assertion**: a raise is a note and does not fail
  the check (`check.py:166-167`), because a real adapter may need its full environment.
  Green means "callable or explained", not "edit path verified".
- Both entry paths fail closed, so a red check never freezes a split: `cap-evolve run`
  returns 1 before creating a run dir (`cli.py:721-726`), and the **standalone**
  `/cap-evolve:baseline` re-runs the core check itself and exits non-zero before the run
  dir exists (`baseline/scripts/run.py`). What is *not* a runtime precondition is the
  `provides: checked` token — it declares ordering only, so a phase that skips baseline
  gets no gate from the DAG.

If your scorer calls a judge, say so in `PROJECT.md` along with how its decoding is
pinned — the gate cannot see it. The one failure mode nothing here can catch: feedback
that leaks the gold answer passes every wiring check and still corrupts diagnosis.

## Dual-mode

Standalone as `/cap-evolve:implement-and-check`; orchestrator-callable — but uniquely for
this phase, `cap-evolve run` does **not** invoke `scripts/run.py`. It calls the core check
inline and shells straight to `baseline`, so `--skill-check` and the pipeline self-test run
in standalone mode only. Run this phase yourself before either `cap-evolve run` or
`/cap-evolve:baseline` if you want them: both of those re-run the *core* check, but
neither runs `--skill-check` or the pipeline self-test.

## References
- `references/concepts.md` — why each check exists, the
  scorer-determinism-vs-target-stochasticity distinction (load this when deciding whether
  your scorer's variance is a bug or a measurement), and the sources.
