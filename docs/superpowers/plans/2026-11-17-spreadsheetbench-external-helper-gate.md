# SpreadsheetBench External Helper Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the helper gate for external optimizers in the SpreadsheetBench adapter, make it skip itself inside a cap-evolve run, and make a broken gate config stop the caller.

**Architecture:** `check.load_adapter` sets `CAPEVOLVE_DRIVER=cap-evolve` before it imports an adapter. The adapter's `_external_gate_config` returns None when it sees that value, so only the loop gate runs inside cap-evolve. `run_target` re-raises `HelperGateConfigError` instead of returning an infra rollout.

**Tech Stack:** Python 3, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-17-spreadsheetbench-external-helper-gate-design.md`

## Global Constraints

- `core/` has zero new runtime dependencies (standard library and sibling modules only).
- The environment variable is named `CAPEVOLVE_DRIVER`. The value for a cap-evolve run is exactly `cap-evolve`. Any other value, including an empty one, means an external caller.
- `load_adapter` sets the variable unconditionally (`os.environ[...] = ...`), not with `setdefault`.
- The parent for the external gate stays the seed. No environment variable carries a parent.
- No core wrapper function is added. The gate code stays in `benchmarks/spreadsheetbench/template/adapter.py`.
- Tests use no network and no LLM call.
- Commit messages end with the trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Prose in code comments, docstrings and docs follows the Simple Engineering English style (short sentences, no idioms).

## Review Focus

Most likely first. Each line has a test in the task named in brackets.

- An external harness sets `CAPEVOLVE_DRIVER=external:gepa`: the gate stays on. [Task 2]
- `CAPEVOLVE_DRIVER=cap-evolve` with a missing or broken `CAPEVOLVE_HELPERS_SPEC`: no raise at `Adapter()`, no gate. [Task 2]
- A `HelperGateConfigError` raised inside `run_target` is not swallowed by the outer `except Exception` of that method. [Task 3]
- The "skipped" line is printed once per process, not once per rollout. [Task 2]
- A `CAPEVOLVE_DRIVER` value that another test left in the process makes the adapter tests pass for the wrong reason. [Task 2]

---

### Task 0: Restack the branch on #964

The current branch `feat/sb-external-helper-gate` was cut from #964's old head, which still contained the three SpreadsheetBench files. #964 now removes them. A later rebase onto `main` would conflict. Build a new branch from #964's current head, put the three files back in one commit, and carry over the design document.

**Files:** none edited by hand.

- [ ] **Step 1: Create the new branch from #964's head**

Run in the worktree `/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/sb-external-helper-gate`:

```bash
git checkout -b feat/spreadsheetbench-external-gate bcarmeli/feat/core-helper-gate
git rev-parse --short HEAD
```

Expected: prints `0a004be09`.

- [ ] **Step 2: Restore the three reviewed files in one commit**

```bash
git checkout e6191a60d -- benchmarks/spreadsheetbench/template/adapter.py \
  benchmarks/spreadsheetbench/template/SEED_V2.md \
  core/tests/test_spreadsheetbench_external_helper_gate.py
git commit -m "feat(spreadsheetbench): helper gate for optimizers that call run_target directly"
```

Add the commit trailer from Global Constraints. This commit holds the code as reviewed in #964 (26 tests).

- [ ] **Step 3: Carry over the design document and this plan**

```bash
git cherry-pick b9717d184
git add docs/superpowers/plans/2026-11-17-spreadsheetbench-external-helper-gate.md
git commit -m "docs: plan for the SpreadsheetBench external helper gate"
```

Add the trailer. The plan file is not committed on any branch yet. It stays in the working tree when you switch branches, so `git add` is enough.

- [ ] **Step 4: Check that the 26 existing tests pass on the new base**

Run: `python -m pytest core/tests/test_spreadsheetbench_external_helper_gate.py -q`
Expected: `26 passed`.

---

### Task 1: Core sets `CAPEVOLVE_DRIVER`

**Files:**
- Modify: `core/cap_evolve/check.py` (`load_adapter`, lines 69-92)
- Create: `core/tests/test_adapter_driver_env.py`

**Interfaces:**
- Produces: `cap_evolve.check.DRIVER_ENV: str = "CAPEVOLVE_DRIVER"` and `cap_evolve.check.DRIVER_CAP_EVOLVE: str = "cap-evolve"`. Task 2 imports both.

- [ ] **Step 1: Write the failing tests** in `core/tests/test_adapter_driver_env.py`

The test adapter source records the variable while its module runs:

```python
ADAPTER_SRC = (
    "import os\n"
    "class Adapter:\n"
    "    SEEN = os.environ.get('CAPEVOLVE_DRIVER')\n"
)
```

A fixture `driver_unset(monkeypatch)` makes sure the test leaves no value behind. It calls `monkeypatch.setenv(DRIVER_ENV, "x")` and then `monkeypatch.delenv(DRIVER_ENV)`. The first call makes monkeypatch remember that the variable was unset, so the teardown removes whatever `load_adapter` sets.

- `test_load_adapter_sets_the_driver_before_the_adapter_module_runs`: write the adapter into `<tmp>/p/adapters/adapter.py`, call `load_adapter(project)`, assert `type(adapter).SEEN == "cap-evolve"` and `os.environ[DRIVER_ENV] == "cap-evolve"`.
- `test_load_adapter_replaces_a_value_an_external_harness_set`: set `CAPEVOLVE_DRIVER=external:gepa` first, call `load_adapter`, assert the variable is now `cap-evolve`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest core/tests/test_adapter_driver_env.py -q`
Expected: FAIL with `ImportError: cannot import name 'DRIVER_ENV'`.

- [ ] **Step 3: Implement in `core/cap_evolve/check.py`**

Add the two module constants near the top. In `load_adapter`, set `os.environ[DRIVER_ENV] = DRIVER_CAP_EVOLVE` before `exec_module`. Import `os` at module level if it is not imported yet. Add two sentences to the `load_adapter` docstring: every cap-evolve entry point loads adapters here; an adapter reads the variable to know that cap-evolve, and not an external optimizer, drives the run.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest core/tests/test_adapter_driver_env.py core/tests/test_framework_correctness.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/cap_evolve/check.py core/tests/test_adapter_driver_env.py
git commit -m "feat(core): load_adapter sets CAPEVOLVE_DRIVER=cap-evolve"
```

Add the trailer.

---

### Task 2: The adapter gate skips itself inside a cap-evolve run

**Files:**
- Modify: `benchmarks/spreadsheetbench/template/adapter.py` (`_external_gate_config`, line 1227)
- Modify: `core/tests/test_spreadsheetbench_external_helper_gate.py`

**Interfaces:**
- Consumes: `cap_evolve.check.DRIVER_ENV`, `cap_evolve.check.DRIVER_CAP_EVOLVE` (Task 1). Import them inside the function, as the function already does for `helper_gate`.
- Produces: `_external_gate_config()` returns None whenever `os.environ.get(DRIVER_ENV) == DRIVER_CAP_EVOLVE`. A module global `_EXT_GATE_SKIP_NOTED: bool = False` records that the "skipped" line was printed. `Adapter()`, `live()` and `_external_gate_error` need no change, because they already treat None as "gate off".

- [ ] **Step 1: Write the failing tests** in `core/tests/test_spreadsheetbench_external_helper_gate.py`

First, change the `mod` fixture so no test inherits a value: add `monkeypatch.setenv("CAPEVOLVE_DRIVER", "x")` followed by `monkeypatch.delenv("CAPEVOLVE_DRIVER")` (same reason as in Task 1). Add a new section `# ---- inside a cap-evolve run` with these tests, all using the `on` fixture and `monkeypatch.setenv("CAPEVOLVE_DRIVER", ...)`:

- `test_inside_a_cap_evolve_run_the_adapter_gate_does_not_run`: driver `cap-evolve`; patch `helper_gate.gate` to a function that fails the test if called; assert `on._external_gate_error(_tree(tmp_path / "c", LEAK)) is None`.
- `test_inside_a_cap_evolve_run_a_broken_spec_does_not_raise`: driver `cap-evolve`; set `CAPEVOLVE_HELPERS_SPEC` to `str(tmp_path / "nope.yaml")`; assert `on.Adapter()` does not raise.
- `test_an_external_driver_value_keeps_the_gate_on`: parametrize the driver value over `"external:gepa"`, `""`, `"CAP-EVOLVE"`; assert `on._external_gate_error(_tree(tmp_path / "c", LEAK))` starts with `"CANDIDATE_HELPER_GATE"`.
- `test_the_skip_is_announced_once_per_process`: driver `cap-evolve`; build `Adapter()`, call `_external_gate_error` three times; `capsys.readouterr().err.count("skipped") == 1`, and the line mentions `CAPEVOLVE_HELPERS_SPEC`.
- `test_no_skip_line_when_no_spec_is_set`: driver `cap-evolve`, `CAPEVOLVE_HELPERS_SPEC` deleted; the error output is empty.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest core/tests/test_spreadsheetbench_external_helper_gate.py -q -k "cap_evolve_run or external_driver or skip"`
Expected: FAIL (the gate still runs, so the first test calls `gate`).

- [ ] **Step 3: Implement in `_external_gate_config`**

Right after `spec_path` is read and before the cache lookup: when the driver value equals `DRIVER_CAP_EVOLVE`, print one line (only when `spec_path` is set, only the first time, tracked with `_EXT_GATE_SKIP_NOTED`) and return None. The line reads: `spreadsheetbench: cap-evolve drives this run, so its loop gate checks the helpers; CAPEVOLVE_HELPERS_SPEC is ignored (helper gate skipped)`. Update the comment block above `_EXT_GATE_LOCK` and the function docstring to say that the external gate is off inside a cap-evolve run.

- [ ] **Step 4: Run the whole adapter gate test file**

Run: `python -m pytest core/tests/test_spreadsheetbench_external_helper_gate.py -q`
Expected: all pass (26 old tests and the new ones).

- [ ] **Step 5: Commit**

```bash
git add benchmarks/spreadsheetbench/template/adapter.py core/tests/test_spreadsheetbench_external_helper_gate.py
git commit -m "feat(spreadsheetbench): the external helper gate skips itself inside a cap-evolve run"
```

Add the trailer.

---

### Task 3: A broken gate config stops the caller

**Files:**
- Modify: `benchmarks/spreadsheetbench/template/adapter.py` (`HelperGateConfigError` docstring, line 1218; `run_target`, lines 1764-1772 and the handler at line 2014)
- Modify: `core/tests/test_spreadsheetbench_external_helper_gate.py`

**Interfaces:**
- Produces: `Adapter.run_target` raises `HelperGateConfigError` when the gate config breaks. A refused candidate still returns `Rollout(error_kind="candidate")`.

- [ ] **Step 1: Replace the test that expects the old behavior**

Rename `test_run_target_reports_a_config_broken_mid_run_as_infra_not_as_a_0` to `test_run_target_raises_when_the_config_breaks_mid_run`. Keep its setup (build the adapter, delete `ids.txt`, patch `_task_template_error`). Replace the assertions with `with pytest.raises(on.HelperGateConfigError, match="ids_file"): adapter.run_target(...)`. Keep the `no_llm` fixture so the test also proves that no LLM call happened. Update the module docstring bullet that says "an infra error (never a 0) in `run_target`".

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest core/tests/test_spreadsheetbench_external_helper_gate.py -q -k raises_when_the_config_breaks`
Expected: FAIL with `DID NOT RAISE`.

- [ ] **Step 3: Implement in `run_target`**

Remove the `try/except HelperGateConfigError` that builds the infra rollout (lines 1764-1769); call `_external_gate_error(ctx)` directly and keep the `if gate_error:` return. The outer `except Exception` (line 2014) would catch the raise and return a rollout without `error_kind`, which `CommonRollout` counts as infra. Add `except HelperGateConfigError: raise` directly above it. The `finally` block must still run. Update the `HelperGateConfigError` docstring: it is raised from `Adapter()`, `live()` and `run_target`, and an external caller that calls `run_target` from a thread pool sees it when it collects the results.

- [ ] **Step 4: Run the whole adapter gate test file**

Run: `python -m pytest core/tests/test_spreadsheetbench_external_helper_gate.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add benchmarks/spreadsheetbench/template/adapter.py core/tests/test_spreadsheetbench_external_helper_gate.py
git commit -m "fix(spreadsheetbench): a broken helper-gate config raises from run_target"
```

Add the trailer.

---

### Task 4: Documentation

**Files:**
- Modify: `benchmarks/spreadsheetbench/template/SEED_V2.md` (the paragraph "The helper gate", about 10 lines)

- [ ] **Step 1: Update the paragraph**

State these facts, one sentence each:
- Inside a cap-evolve run (`CAPEVOLVE_DRIVER=cap-evolve`, set by `check.load_adapter`), only the loop gate runs, and `CAPEVOLVE_HELPERS_SPEC` is ignored with one printed line.
- An external optimizer leaves the variable unset (or sets its own value, for example `external:<name>`) and sets `CAPEVOLVE_HELPERS_SPEC` and `CAPEVOLVE_HELPERS_SEED`.
- The seed is the parent. An external caller cannot pass the parent, because `run_target` has no parameter for it and one process evaluates several candidates at once. The verdict can differ from the core gate's: lint can be less strict (a candidate that re-adds a violation of the seed, which its parent had removed, passes); smoke can be more strict (it imports helpers that earlier candidates added); smoke replays no fixtures.
- A config error raises `HelperGateConfigError` from `Adapter()`, `live()` and `run_target`. It does not become missing data.
- A refused candidate scores 0 on each rollout with no LLM call, and the external caller still pays its own budget for those rollouts.

Remove the old sentence that says a config error is returned as an infra error.

- [ ] **Step 2: Commit**

```bash
git add benchmarks/spreadsheetbench/template/SEED_V2.md
git commit -m "docs(spreadsheetbench): external helper gate, driver variable, parent and error behavior"
```

Add the trailer.

---

### Task 5: Verify, then open the pull request

**Files:** none.

- [ ] **Step 1: Run the checks**

```bash
python -m pytest core/tests/test_spreadsheetbench_external_helper_gate.py core/tests/test_adapter_driver_env.py core/tests/test_helper_gate.py core/tests/test_helper_gate_wiring.py core/tests/test_framework_correctness.py -q
python -m compileall -q core/cap_evolve benchmarks/spreadsheetbench
python skills/_registry/build_manifest.py skills
```

Expected: all tests pass, no compile error, the manifest build prints no error.

- [ ] **Step 2: Run the full unit tier**

Follow the repo `testing` skill (`python -m pytest core/tests -q`, with `litellm` blocked as in CI). Compare the failures with `main`. The four known failures from #964 (`test_live_push_cleanup_is_bounded`, two `test_tau2_airline_eval_cost` tests, `test_a_correction_supersedes_the_earlier_answer`) are not caused by this change.

- [ ] **Step 3: Push the branch**

`git push bcarmeli feat/spreadsheetbench-external-gate`. Ask the user before pushing.

- [ ] **Step 4: Open the pull request after #964 is merged**

This branch contains #964's commits, and a pull request cannot use a branch of the fork as its base. Wait for #964 to merge, then run:

```bash
git fetch origin
git rebase --onto origin/main bcarmeli/feat/core-helper-gate feat/spreadsheetbench-external-gate
```

Run Step 1 again, force-push with `--force-with-lease`, and open the pull request as described by the repo `open-pr` skill, with `review-cycles` after it. The pull request body answers the four review points of #964, each with a link to the code or test that handles it: point 1 (no core wrapper, one user today), point 2 (seed as parent, how the verdict differs), point 3 (no change; the check is deterministic and the dictionaries stay small), point 4 (`CAPEVOLVE_DRIVER`).
