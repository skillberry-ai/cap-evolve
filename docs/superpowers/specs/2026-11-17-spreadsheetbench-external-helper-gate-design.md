# SpreadsheetBench external helper gate: design

Date: 2026-11-17. Follows the review of #964 (eranra, [comment](https://github.com/skillberry-ai/cap-evolve/pull/964#issuecomment-6819381064)).

## Intent

#964 runs the helper gate (`cap_evolve.helper_gate`) inside every cap-evolve algorithm. External optimizers
(the #895 competitors) do not run a cap-evolve loop. They call the SpreadsheetBench adapter's `run_target`
directly, through `recipes/common/rollout.py` (`CommonRollout`) in
[skillberry-runs/spreadsheetbench](https://github.com/skillberry-runs/spreadsheetbench/blob/main/recipes/common/rollout.py)
(it was on cap-evolve's `spreadsheet-history` branch). This PR keeps the gate for those callers in the SpreadsheetBench adapter, and answers the four review points on #964.

## Goals

- An external optimizer that sets `CAPEVOLVE_HELPERS_SPEC` gets the same three checks as the core gate
  (surface, lint, smoke), from the same code (`helper_gate.gate`).
- Inside a cap-evolve run, only the loop gate runs. The adapter gate never runs a second time.
- A broken gate config stops an external optimizer. It never turns into missing data.

## Non-goals

- A core wrapper for other benchmarks. Only the SpreadsheetBench adapter loads helper code today.
- Gating inside `CommonRollout` (option D below). That code is not on `main`.
- Re-running the published #895 results.

## Approaches

| Option | What | Decision |
|---|---|---|
| A | A core function, called from each adapter's `run_target` | Not chosen: one user today, and a new core API |
| B | Keep the gate in the SpreadsheetBench adapter and fix the review points there | **Chosen** |
| C | No gate for external optimizers; document it | Not chosen: external optimizers could ship helpers that cheat |
| D | Gate in `CommonRollout.evaluate` (once per candidate, real parent) | Not chosen: future external callers may call `run_target` directly |

How the adapter knows it runs inside a cap-evolve loop:

| Option | What | Decision |
|---|---|---|
| 1 | Check the candidate path for a cap-evolve run-directory layout | Not chosen: breaks without a sign if the layout changes |
| 2 | Core sets an environment variable when it loads an adapter | **Chosen**: an explicit signal, also useful for other code that must know who drives the run |
| 3 | Documentation only | Not chosen: nothing enforces it |

## Design

### Core: the driver variable

- `cap_evolve.check.load_adapter` sets `CAPEVOLVE_DRIVER=cap-evolve` in `os.environ` before it imports the
  adapter module. All cap-evolve entry points load adapters through this function (20 call sites: the CLI, the
  phase scripts, every algorithm script). Subprocesses that a cap-evolve process starts inherit the value.
- External optimizers import the adapter directly, so for them the variable is unset. An external harness may
  set its own value (for example `external:gepa`). The adapter treats every value except `cap-evolve` as
  external.
- The value is set unconditionally, not with `setdefault`: a process that loaded the adapter through cap-evolve
  is a cap-evolve process.

### Adapter: changes to the external gate

- **Skip inside a cap-evolve run.** When `CAPEVOLVE_DRIVER=cap-evolve`, `_external_gate_config` returns None,
  so `Adapter()`, `live()` and `run_target` do no external-gate work. If `CAPEVOLVE_HELPERS_SPEC` is also set,
  the adapter prints one line, once per process: the loop gate checks candidates, so the adapter gate is skipped.
  This answers review point 4.
- **Config error during a run raises.** `run_target` raises `HelperGateConfigError` instead of returning
  `error_kind=infra`. `CommonRollout` retries an infra error 3 times, returns the budget and marks the task as
  missing, so the run continued with less data. A raise stops the evaluation (`ThreadPoolExecutor.map` re-raises).
  Inside a cap-evolve run the gate is skipped, so this raise reaches only external callers.
- **The parent stays the seed.** An external caller has no way to pass the parent: `run_target(task, ctx, seed)`
  has no parameter for it, and an environment variable holds one value for a process that evaluates several
  candidates at once. The adapter docs and `SEED_V2.md` state how the verdict can differ from the core gate's:
  - lint can be less strict (a candidate that re-adds a seed violation its parent removed passes);
  - smoke can be more strict (it imports helpers added by earlier candidates);
  - smoke replays no fixtures (external callers give no rollout traces).
  This answers review point 2.
- **No change for global state.** Each process checks a candidate once. The result is the same in every
  process, because the check is deterministic. The dictionaries hold one small entry per distinct candidate.
  The PR body explains this. This answers review point 3.
- **No core wrapper.** The PR body says why (one user today). This answers review point 1.

## Tests

- Core: `load_adapter` sets `CAPEVOLVE_DRIVER=cap-evolve` before the adapter module runs (the test adapter
  records the value at import time).
- Adapter, with `CAPEVOLVE_DRIVER=cap-evolve` and `CAPEVOLVE_HELPERS_SPEC` set:
  - a cheating candidate is not refused by the adapter, and no gate runs;
  - `Adapter()` does not raise on a broken gate config;
  - the "skipped" line is printed once.
- Adapter, external: a config error during a run raises from `run_target` (replaces the test that expected
  `error_kind=infra`).
- Adapter, external: a value other than `cap-evolve` (for example `external:gepa`) keeps the gate on.
- The existing 26 adapter tests still pass.

## Constraints

- `load_adapter` changes `os.environ` for the whole process. In pytest, a test that loads an adapter leaves
  `CAPEVOLVE_DRIVER` set for later tests. The adapter tests must remove it with `monkeypatch.delenv` (an
  autouse fixture), or they would skip the gate and pass for the wrong reason.
- The core change is in this PR, not in #964: it is two lines, and the adapter gate is its first user.
- This PR depends on #964 (`helper_gate`). It is opened as a draft against `main` and rebased after #964 is
  merged.

## Left to the builder

- Where the core variable is documented (the `load_adapter` docstring at least).
- The exact wording of the "skipped" line and of the doc paragraphs.
