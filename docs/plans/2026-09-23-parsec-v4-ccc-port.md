# Parsec v4 CCC Port (Doc + Scripts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `v4_t2_e1` (parsec v4's single-task cap-evolve optimization harness) runnable on CCC/LSF instead of only on the author's Mac, by removing its Mac-only code paths, fixing a false-green test defect, documenting the corrected three-layer runtime topology, and adding CCC scripts to bring the stack up/down by hand — without touching the `v4_g2_e1` multi-task scaffold (deferred, separate change) and without changing `v4_t2_e1`'s task semantics (its 21 already-completed task results must stay byte-reproducible).

**Architecture:** Three fixes to `scripts/v4_t2_e1/`'s Python (a new single-source-of-truth `parsec_paths.py` module, a Linux-safe docker-host resolution in `adapter.py`, and a test fix that stops 24 tests from silently skipping on Linux), plus new CCC-side shell scripting (`scripts/ccc/parsec_stack.sh` for bring-up/health-wait/teardown of the 5 host-process MCP simulators + the host `parsec-live` process, and `scripts/ccc/run_ccc_parsec.sh` as a hand-run driver mirroring the existing `run_ccc_experiment.sh` pattern), plus a new documentation section in `CCC_PODMAN_SETUP.md` correcting the false "5-service docker-compose" premise and documenting the real topology, plus a one-time repair of dangling symlinks and a venv rebuild on the two CCC copies of the parsec tree.

**Tech Stack:** Python 3.12 (stdlib `unittest`, no new dependencies), Bash (LSF/CCC scripting, matching the existing `scripts/ccc/*.sh` style), YAML (harness service config, unchanged schema), `uv` (venv rebuild on CCC).

## Global Constraints

- No hardcoded personal paths (`/Users/boazc/...`) in anything that ships — every path must come from an environment variable or be resolved relative to `__file__`.
- `v4_t2_e1`'s per-task semantics (`Adapter.tasks()` returns exactly one task; `TASK_ID` env var required) must not change — that is `v4_g2_e1` work, explicitly out of scope for this change.
- Every existing passing test in `scripts/v4_t2_e1/tests/` must still pass after this change, except the one test (`test_default_matches_adapter_pys_default`) that is being rewritten *because* it currently asserts the defect this change removes.
- New/changed Python files use `from __future__ import annotations` and the existing `sys.path.insert(...)` idiom already used by every file in this package (no `conftest.py`, no package `__init__.py` — matches the codebase's existing test-discovery style).
- New shell scripts follow the existing `scripts/ccc/*.sh` conventions: `set -eo pipefail`, a `usage()` that `sed`s the header comment, a `banner()` helper, override-by-env-var for any path that could plausibly differ per machine.
- Never commit real credentials or machine-specific secrets; the CCC repair task must flag (not silently "fix") the cleartext LiteLLM API key already found in `config.local.yaml`.

---

### Task 1: Shared `parsec_paths.py` module

`adapter.py` and `scaffold_projects.py` each currently hardcode an *independent copy* of the same `PARSEC_V4N` env-var-with-Mac-fallback default (`scaffold_projects.py`'s own comment already flags this: "Two sources of truth for 'which parsec checkout' is how a seed snapshot gets frozen from one tree while the trials that score it run against another"). This task creates the single shared module both will import from, with the Mac fallback removed entirely (CCC has no equivalent personal path to fall back to, and a fallback is exactly the bug being fixed).

**Files:**
- Create: `scripts/v4_t2_e1/common/parsec_paths.py`
- Test: `scripts/v4_t2_e1/tests/test_parsec_paths.py`

**Interfaces:**
- Produces: `parsec_paths.resolve_v4n_or_none() -> Path | None`, `parsec_paths.resolve_v4n() -> Path` (raises `RuntimeError` mentioning `PARSEC_V4N` when unset), `parsec_paths.MCP_PORTS: dict[str, int]` (5 entries: `PLATFORM_MCP_URL=8086, GITHUB_MCP_URL=8087, ICINGA_MCP_URL=8088, COST_MCP_URL=8089, CLOUD_MCP_URL=8090` — identical keys/values to today's `adapter.py` module-level `MCP_PORTS`, just relocated).
- Consumed by: Task 2 (`adapter.py`) and Task 3 (`scaffold_projects.py`).

- [ ] **Step 1: Write the failing tests**

Create `scripts/v4_t2_e1/tests/test_parsec_paths.py`:

```python
# scripts/v4_t2_e1/tests/test_parsec_paths.py
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import parsec_paths  # noqa: E402


class TestResolveV4N(unittest.TestCase):
    def test_or_none_returns_none_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(parsec_paths.resolve_v4n_or_none())

    def test_or_none_returns_path_when_set(self):
        with patch.dict(os.environ, {"PARSEC_V4N": "/tmp/fake-v4n"}, clear=True):
            self.assertEqual(parsec_paths.resolve_v4n_or_none(), Path("/tmp/fake-v4n"))

    def test_or_none_treats_blank_string_as_unset(self):
        with patch.dict(os.environ, {"PARSEC_V4N": "   "}, clear=True):
            self.assertIsNone(parsec_paths.resolve_v4n_or_none())

    def test_resolve_raises_clearly_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                parsec_paths.resolve_v4n()
            self.assertIn("PARSEC_V4N", str(ctx.exception))

    def test_resolve_returns_path_when_set(self):
        with patch.dict(os.environ, {"PARSEC_V4N": "/tmp/fake-v4n"}, clear=True):
            self.assertEqual(parsec_paths.resolve_v4n(), Path("/tmp/fake-v4n"))


class TestMcpPorts(unittest.TestCase):
    def test_has_the_five_expected_entries(self):
        self.assertEqual(
            parsec_paths.MCP_PORTS,
            {
                "PLATFORM_MCP_URL": 8086,
                "GITHUB_MCP_URL": 8087,
                "ICINGA_MCP_URL": 8088,
                "COST_MCP_URL": 8089,
                "CLOUD_MCP_URL": 8090,
            },
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails with an import error**

Run: `python3 scripts/v4_t2_e1/tests/test_parsec_paths.py -v`
Expected: `ModuleNotFoundError: No module named 'parsec_paths'` (the module doesn't exist yet).

- [ ] **Step 3: Write `parsec_paths.py`**

Create `scripts/v4_t2_e1/common/parsec_paths.py`:

```python
#!/usr/bin/env python3
"""Single source of truth for "which parsec v4 checkout" and the shared MCP
port table.

Both were previously hardcoded independently in adapter.py and
scaffold_projects.py — two copies of the same PARSEC_V4N env-var-with-Mac-
fallback default. scaffold_projects.py's own comment already named the
risk: a seed snapshot gets frozen from one tree while the trials that score
it run against another, if the two copies ever drift. This module is the
fix: both files import from here instead of defining their own copy.

There is deliberately NO machine-specific fallback path. A fallback here is
exactly the bug this module replaces (it was a personal Mac path; on CCC
there is no equivalent single "the" checkout to default to) — callers that
need a v4_t2_e1-shaped operation, not just a path, use resolve_v4n() and get
a clear RuntimeError instead of silently resolving to the wrong tree.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Every v4_t2_e1 trial's target: the 5 harness-simulation MCP endpoints,
#: keyed by the env var name adapter.py sets before invoking `harbor run`.
#: Values mirror each service's `server.port` in _run/harness-cfg/*.yaml.
MCP_PORTS: dict[str, int] = {
    "PLATFORM_MCP_URL": 8086,
    "GITHUB_MCP_URL": 8087,
    "ICINGA_MCP_URL": 8088,
    "COST_MCP_URL": 8089,
    "CLOUD_MCP_URL": 8090,
}


def resolve_v4n_or_none() -> Path | None:
    """The parsec v4 checkout root, from $PARSEC_V4N, or None if unset/blank."""
    raw = os.environ.get("PARSEC_V4N", "").strip()
    return Path(raw) if raw else None


def resolve_v4n() -> Path:
    """Like resolve_v4n_or_none(), but raises when PARSEC_V4N is unset."""
    v4n = resolve_v4n_or_none()
    if v4n is None:
        raise RuntimeError(
            "PARSEC_V4N environment variable is required — it must point at "
            "the root of a parsec v4 checkout (e.g. "
            ".../rhdp-parsec/v4_2026-09-16, the directory containing _run/). "
            "Set it before running this script."
        )
    return v4n
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 scripts/v4_t2_e1/tests/test_parsec_paths.py -v`
Expected: `OK` with 6 tests run, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add scripts/v4_t2_e1/common/parsec_paths.py scripts/v4_t2_e1/tests/test_parsec_paths.py
git commit -s -m "$(cat <<'EOF'
feat(v4_t2_e1): add shared parsec_paths module for PARSEC_V4N/MCP_PORTS

adapter.py and scaffold_projects.py each hardcoded an independent copy of
the same PARSEC_V4N-with-Mac-fallback default. This is the single source
of truth both will import from in the next two commits.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Fix `adapter.py` — Linux docker-host resolution, drop the Mac path default, honor caller-set env, fix the false-green tests

`adapter.py`'s `_resolve_docker_host()` unconditionally shells out to `podman machine inspect podman-machine-default`, a Mac/Windows-only concept (rootless podman on Linux has no VM, hence no "podman machine") — this call fails on CCC. Its `V4N` default hardcodes the same Mac path Task 1 just centralized. Its `run_target()` unconditionally overwrites `env["PARSEC_URL"]`/`env["PARSEC_SIM_TRACE"]` even if a caller (e.g. a CCC run using a run-scoped trace path) already set them. Separately, `test_adapter.py` hardcodes its own `REAL_TASKS_DIR` Mac literal, completely decoupled from `PARSEC_V4N` — so its 24 `@unittest.skipUnless(REAL_TASKS_DIR.exists(), ...)`-decorated tests silently skip on CCC even when `PARSEC_V4N` is correctly exported, because the hardcoded literal never existed there. All four fixes touch the same review unit (`adapter.py` + its test file), so they are one task.

**Files:**
- Modify: `scripts/v4_t2_e1/common/adapters/adapter.py:60-95` (imports, `V4N`, `MCP_PORTS`, `_resolve_docker_host`)
- Modify: `scripts/v4_t2_e1/common/adapters/adapter.py:217-246` (`Adapter.__init__`)
- Modify: `scripts/v4_t2_e1/common/adapters/adapter.py:374-378` (`run_target`'s env setup)
- Modify: `scripts/v4_t2_e1/tests/test_adapter.py:29-30` (`REAL_TASKS_DIR`) and every one of its 24 `@unittest.skipUnless` decorator sites
- Test: `scripts/v4_t2_e1/tests/test_adapter.py`

**Interfaces:**
- Consumes: `parsec_paths.resolve_v4n_or_none()`, `parsec_paths.MCP_PORTS` (Task 1).
- Produces: `adapter.V4N: Path | None` (was always a `Path`; now `None` when `PARSEC_V4N` is unset — module import no longer crashes, `Adapter.__init__` now raises the `RuntimeError` instead), `adapter.TASKS_DIR: Path | None`, `adapter.MCP_PORTS` (now literally `parsec_paths.MCP_PORTS`, not a second copy).

- [ ] **Step 1: Write the failing test for the new `_resolve_docker_host()` behavior**

Add to `scripts/v4_t2_e1/tests/test_adapter.py`, in a new `TestResolveDockerHost` class (after `TestAdapterTaskResolution`, before `TestAdapterApply`):

```python
class TestResolveDockerHost(unittest.TestCase):
    def test_prefers_docker_host_env_var_when_set(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "unix:///run/user/1000/podman/podman.sock"}, clear=True):
            self.assertEqual(
                adapter_mod._resolve_docker_host(),
                "unix:///run/user/1000/podman/podman.sock",
            )

    def test_falls_back_to_podman_machine_inspect_when_unset(self):
        fake_stdout = json.dumps([
            {"ConnectionInfo": {"PodmanSocket": {"Path": "/tmp/podman-machine.sock"}}}
        ])
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(
                 adapter_mod.subprocess, "run",
                 return_value=subprocess.CompletedProcess([], 0, stdout=fake_stdout, stderr=""),
             ) as mock_run:
            result = adapter_mod._resolve_docker_host()
            self.assertEqual(result, "unix:///tmp/podman-machine.sock")
            mock_run.assert_called_once()
            self.assertEqual(mock_run.call_args.args[0][:2], ["podman", "machine"])
```

(`json` and `subprocess` are already imported at the top of `test_adapter.py`.)

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/v4_t2_e1/tests/test_adapter.py TestResolveDockerHost -v`
Expected: `test_prefers_docker_host_env_var_when_set` FAILs (current code ignores `$DOCKER_HOST` and calls the real `podman` binary, raising `FileNotFoundError` or a non-zero-exit `CalledProcessError` in a sandboxed test environment with no `podman` on `PATH`).

- [ ] **Step 3: Fix `_resolve_docker_host()`, `V4N`, and `MCP_PORTS` in `adapter.py`**

Replace lines 55-95 of `scripts/v4_t2_e1/common/adapters/adapter.py`:

```python
# This file is reached through a chain of symlinks (project/adapters ->
# v4_t2_e1_common/adapters -> scripts/v4_t2_e1/common/adapters). .resolve()
# fully follows every hop, landing on the real physical path regardless —
# so this always finds the actual repo root, not wherever the caller's
# --project happened to point.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# common/ (this file's parent's parent) holds parsec_paths.py, the single
# source of truth for PARSEC_V4N/MCP_PORTS — see that module's docstring.
_COMMON_DIR = Path(__file__).resolve().parents[1]
if str(_COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMON_DIR))

from capevolve_harbor.results import build_feedback, parse_job_dir  # noqa: E402
from cap_evolve import CapabilityAdapter, Rollout, Score, Task  # noqa: E402
import parsec_paths  # noqa: E402

# May be None if $PARSEC_V4N is unset — deliberately not resolved to a
# machine-specific default (see parsec_paths.py's docstring). Adapter()
# raises a clear RuntimeError at construction time if it is None; nothing
# below the class definition dereferences V4N directly at import time.
V4N = parsec_paths.resolve_v4n_or_none()
TASKS_DIR = V4N / "_run" / "tasks" if V4N else None
JOBS_ROOT = V4N / "_run" / "jobs" / "v4_t2_e1" if V4N else None
TRIAL_TIMEOUT_SEC = 20 * 60

PROMPT_FILES = [
    "orchestrator.md",
    "shared_context.md",
    "aap2_agent.md",
    "babylon_agent.md",
    "cost_agent.md",
    "icinga_agent.md",
    "ocpv_agent.md",
    "security_agent.md",
]

#: Plausibility floor for a candidate's orchestrator.md. The real prompt is
#: ~11.7KB; the corrupted fixture that once reached the live clone (and was
#: then frozen into all 21 seed snapshots) was 21 bytes. Anything under this
#: is truncated or placeholder content, not a prompt worth serving.
MIN_ORCHESTRATOR_BYTES = 500

MCP_PORTS = parsec_paths.MCP_PORTS
```

Replace the `_resolve_docker_host()` function (originally lines 126-133):

```python
def _resolve_docker_host() -> str:
    """The docker/podman socket run_target() sets $DOCKER_HOST to for
    `harbor run`'s own docker-py client.

    Preference order:
      1. $DOCKER_HOST, already set in this process's environment — on CCC,
         setup_podman.sh exports this before any adapter code runs (see
         docs/how-to/ccc/CCC_PODMAN_SETUP.md), so trusting it here means
         this function does nothing platform-specific on Linux at all.
      2. `podman machine inspect podman-machine-default` — Mac/Windows
         only. "podman machine" is the VM rootless podman runs inside on
         those platforms; Linux runs podman natively and has no such
         concept, so this branch is unreachable on CCC and exists only for
         local Mac development.
    """
    existing = os.environ.get("DOCKER_HOST", "").strip()
    if existing:
        return existing
    out = subprocess.run(
        ["podman", "machine", "inspect", "podman-machine-default"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    data = json.loads(out.stdout)
    path = data[0]["ConnectionInfo"]["PodmanSocket"]["Path"]
    return f"unix://{path}"
```

- [ ] **Step 4: Fix `Adapter.__init__` to raise clearly when `V4N` is `None`**

In `Adapter.__init__` (originally lines 218-246), add the check immediately after the existing `TASK_ID` check, before `task_dir = TASKS_DIR / ...`:

```python
    def __init__(self) -> None:
        task_id = os.environ.get("TASK_ID", "").strip()
        if not task_id:
            raise RuntimeError(
                "TASK_ID environment variable is required — this adapter is shared by "
                "all 21 v4_t2_e1 projects via a symlink and has no other way to know "
                "which task it is running. Set it before invoking `cap-evolve run`."
            )
        if V4N is None:
            raise RuntimeError(
                "PARSEC_V4N environment variable is required — see parsec_paths.py. "
                "Set it before invoking `cap-evolve run`."
            )
        task_dir = TASKS_DIR / f"bench-v4-{task_id}"
```

(Everything else in `__init__` is unchanged — `TASKS_DIR` is guaranteed non-`None` by the time it's dereferenced, because this check runs first.)

- [ ] **Step 5: Fix `run_target()` to honor caller-set `PARSEC_URL`/`PARSEC_SIM_TRACE`**

In `run_target()` (originally lines 374-378), change:

```python
        env["PARSEC_URL"] = "http://127.0.0.1:8000"
        env["PARSEC_SIM_TRACE"] = str(V4N / "_run" / "logs" / "parsec-trace" / "trace.jsonl")
        env["DOCKER_HOST"] = docker_host
        for var, port in MCP_PORTS.items():
            env[var] = f"http://localhost:{port}/mcp/sse"
```

to:

```python
        # setdefault, not assignment: a caller (e.g. a CCC run pinning a
        # run-scoped trace path so concurrent lanes don't interleave into one
        # file) may have already set these — overwriting them unconditionally
        # would silently discard that intent.
        env.setdefault("PARSEC_URL", "http://127.0.0.1:8000")
        env.setdefault(
            "PARSEC_SIM_TRACE",
            str(V4N / "_run" / "logs" / "parsec-trace" / "trace.jsonl"),
        )
        env["DOCKER_HOST"] = docker_host
        for var, port in MCP_PORTS.items():
            env[var] = f"http://localhost:{port}/mcp/sse"
```

- [ ] **Step 6: Run the docker-host tests to verify they pass**

Run: `python3 scripts/v4_t2_e1/tests/test_adapter.py TestResolveDockerHost -v`
Expected: `OK` with 2 tests run, 0 failures.

- [ ] **Step 7: Fix the false-green `REAL_TASKS_DIR` in `test_adapter.py`**

Change line 29-30 of `scripts/v4_t2_e1/tests/test_adapter.py`:

```python
REAL_TASKS_DIR = Path("/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/tasks")
KNOWN_TASK_ID = "icinga-011-aap2-job-status-alert"  # one of the 21; real dir on disk
```

to:

```python
# adapter_mod.TASKS_DIR is derived from $PARSEC_V4N via parsec_paths.py (may
# be None if it's unset) — using it here, rather than a second hardcoded
# literal, is the fix for the exact defect this constant used to encode:
# REAL_TASKS_DIR previously named a Mac-only path completely independent of
# $PARSEC_V4N, so these tests silently skipped on any other machine
# regardless of what PARSEC_V4N was set to.
REAL_TASKS_DIR = adapter_mod.TASKS_DIR
_REAL_TASKS_DIR_PRESENT = REAL_TASKS_DIR is not None and REAL_TASKS_DIR.exists()
KNOWN_TASK_ID = "icinga-011-aap2-job-status-alert"  # one of the 21; real dir on disk
```

Then, in the same file, replace every occurrence of:

```python
    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
```

with:

```python
    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
```

This is the same literal string at all 24 sites (lines 45, 78, 108, 179, 191, 202, 210, 220, 236, 247, 269, 314, 366, 427, 498, 536, 562, 620, 625, 637, 647, 693, 698 as of this plan being written) — do a global find-and-replace across the file rather than editing each site individually; confirm the count matches before and after:

```bash
grep -c 'skipUnless(REAL_TASKS_DIR.exists()' scripts/v4_t2_e1/tests/test_adapter.py   # before: 24
# ... after the replace ...
grep -c 'skipUnless(_REAL_TASKS_DIR_PRESENT' scripts/v4_t2_e1/tests/test_adapter.py   # after: 24
grep -c 'REAL_TASKS_DIR.exists()' scripts/v4_t2_e1/tests/test_adapter.py              # after: 0
```

- [ ] **Step 8: Run the full adapter test suite**

Run: `PARSEC_V4N= python3 scripts/v4_t2_e1/tests/test_adapter.py -v 2>&1 | tail -30`
Expected: the 24 previously-Mac-gated tests now report `skipped 'real bench-v4 tasks dir not present (set PARSEC_V4N)'` (still correctly skipped, but now for the *right* reason — `PARSEC_V4N` genuinely unset — not because of a decoupled literal); all non-skipped tests `OK`.

Then, from a machine with the real tree present:

Run: `PARSEC_V4N=/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16 python3 scripts/v4_t2_e1/tests/test_adapter.py -v 2>&1 | tail -40`
Expected: the 24 previously-skipped tests now actually run (no `skipped` lines), ending in `OK`.

- [ ] **Step 9: Commit**

```bash
git add scripts/v4_t2_e1/common/adapters/adapter.py scripts/v4_t2_e1/tests/test_adapter.py
git commit -s -m "$(cat <<'EOF'
fix(v4_t2_e1): make adapter.py Linux-safe, fix false-green skip in tests

- _resolve_docker_host() prefers $DOCKER_HOST (exported by
  setup_podman.sh on CCC) and only falls back to the Mac/Windows-only
  `podman machine inspect` when it's unset.
- V4N/MCP_PORTS now come from the shared parsec_paths module instead of
  a second hardcoded Mac-path default.
- run_target() no longer clobbers a caller-set PARSEC_URL/PARSEC_SIM_TRACE.
- test_adapter.py's REAL_TASKS_DIR now derives from adapter.TASKS_DIR
  (itself driven by $PARSEC_V4N) instead of an independent hardcoded Mac
  literal — the 24 skipUnless-gated tests were silently skipping on every
  non-Mac machine regardless of PARSEC_V4N, a false green.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Fix `scaffold_projects.py` and rewrite the test that asserts the Mac default

`scaffold_projects.py` hardcodes the same `PARSEC_V4N` default Task 1 centralized. Its own test suite includes `test_default_matches_adapter_pys_default`, which currently *asserts that hardcoded Mac path is correct behavior* — that test itself is the defect once the Mac fallback is removed, so it is rewritten (not just skipped) in this task.

**Files:**
- Modify: `scripts/v4_t2_e1/scaffold_projects.py:23-42` (imports, `PARSEC_V4N`, `PROMPTS_DIR`)
- Modify: `scripts/v4_t2_e1/scaffold_projects.py:193-200` (`main()`'s `PROMPTS_DIR` check)
- Modify: `scripts/v4_t2_e1/tests/test_scaffold_projects.py:187-196` (`test_default_matches_adapter_pys_default`)
- Test: `scripts/v4_t2_e1/tests/test_scaffold_projects.py`

**Interfaces:**
- Consumes: `parsec_paths.resolve_v4n_or_none()` (Task 1).
- Produces: `scaffold_projects.PARSEC_V4N: Path | None`, `scaffold_projects.PROMPTS_DIR: Path | None` — both `None` when `$PARSEC_V4N` is unset, used unchanged by every other function in the module (`scaffold_all()`'s `prompts_dir` parameter, `main()`).

- [ ] **Step 1: Write the failing test**

Replace `test_default_matches_adapter_pys_default` (lines 187-196 of `scripts/v4_t2_e1/tests/test_scaffold_projects.py`) with:

```python
    def test_default_is_none_when_env_unset(self):
        """No Mac fallback: unset PARSEC_V4N must resolve to None, not a
        hardcoded personal path. This test used to assert the opposite —
        that the hardcoded Mac path WAS the correct default — which is
        exactly the two-sources-of-truth defect parsec_paths.py replaces."""
        try:
            with patch.dict(os.environ, {}, clear=True):
                reloaded = importlib.reload(scaffold_projects)
                self.assertIsNone(reloaded.PARSEC_V4N)
                self.assertIsNone(reloaded.PROMPTS_DIR)
        finally:
            importlib.reload(scaffold_projects)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/v4_t2_e1/tests/test_scaffold_projects.py TestParsecV4NIsEnvOverridable -v`
Expected: `test_is_none_when_env_unset` FAILs with `AssertionError: PosixPath('/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16') is not None` (current code still has the Mac fallback).

- [ ] **Step 3: Fix `scaffold_projects.py`**

Replace lines 31-42 of `scripts/v4_t2_e1/scaffold_projects.py`:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
CAPEVOLVE_DIR = REPO_ROOT / ".capevolve"
COMMON_ADAPTERS_SRC = Path(__file__).resolve().parent / "common" / "adapters"
COMMON_OPTIMIZER_SRC = Path(__file__).resolve().parent / "common" / "optimizer"

# common/ holds parsec_paths.py, the single source of truth for PARSEC_V4N —
# see that module's docstring for why adapter.py and this file must not each
# keep their own copy of the same default.
_COMMON_DIR = Path(__file__).resolve().parent / "common"
if str(_COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMON_DIR))
import parsec_paths  # noqa: E402

PARSEC_V4N = parsec_paths.resolve_v4n_or_none()
PROMPTS_DIR = (
    PARSEC_V4N / "_run" / "parsec-live" / "config" / "prompts" if PARSEC_V4N else None
)
```

- [ ] **Step 4: Fix `main()`'s prompts-dir check to handle `PROMPTS_DIR is None`**

Change lines 198-200 of `scripts/v4_t2_e1/scaffold_projects.py`:

```python
    if not PROMPTS_DIR.exists():
        print(f"prompts dir not found: {PROMPTS_DIR}", file=sys.stderr)
        return 1
```

to:

```python
    if PROMPTS_DIR is None:
        print(
            "PARSEC_V4N environment variable is required (the parsec v4 "
            "checkout root, e.g. .../rhdp-parsec/v4_2026-09-16) — set it "
            "before scaffolding.",
            file=sys.stderr,
        )
        return 1
    if not PROMPTS_DIR.exists():
        print(f"prompts dir not found: {PROMPTS_DIR}", file=sys.stderr)
        return 1
```

(This check runs before `TestMainChecksItsSources`'s tests ever reach it, because those tests `patch.object(scaffold_projects, "PROMPTS_DIR", self.prompts_dir)` directly with a real `Path` — so this new `None` branch does not change their behavior. `scaffold_all()`'s existing `prompts_dir: Path = PROMPTS_DIR` default parameter is unaffected: every call site in both the tests and `main()` passes `prompts_dir=` explicitly.)

- [ ] **Step 5: Run the full scaffold_projects test suite**

Run: `python3 scripts/v4_t2_e1/tests/test_scaffold_projects.py -v`
Expected: `OK` — all tests pass, including `test_module_reads_the_same_env_var_adapter_py_does` (unaffected — it sets `PARSEC_V4N` explicitly) and the new `test_default_is_none_when_env_unset`.

- [ ] **Step 6: Commit**

```bash
git add scripts/v4_t2_e1/scaffold_projects.py scripts/v4_t2_e1/tests/test_scaffold_projects.py
git commit -s -m "$(cat <<'EOF'
fix(v4_t2_e1): scaffold_projects.py uses shared parsec_paths, drop Mac default

PARSEC_V4N/PROMPTS_DIR now come from parsec_paths.resolve_v4n_or_none()
instead of a second hardcoded Mac-path default (see the adapter.py
commit for the two-sources-of-truth risk this removes). The test that
asserted the old Mac default was correct behavior is rewritten to assert
the new None-when-unset behavior instead.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `CCC_PODMAN_SETUP.md` — corrected topology + parsec-specific section

The existing handoff/design docs describe parsec v4's runtime as a 5-service docker-compose stack. It is not: the 5 MCP simulation services and `parsec-live` are host Python processes (`uvicorn`, one per `_run/harness-cfg/*.yaml` config file, on fixed ports 8086-8090, plus `parsec-live` itself on 8000); the only real container workload is one `harbor run` Harbor task container per trial. This task adds a new, clearly-scoped section to `CCC_PODMAN_SETUP.md` — distinct from the existing BenchFlow §A-§D patches, which apply only to the Harbor container, not to any compose topology — documenting the real topology and the CCC workflow for it.

**Files:**
- Modify: `docs/how-to/ccc/CCC_PODMAN_SETUP.md` — insert a new `## Parsec v4 (v4_t2_e1): host-process harness, not docker-compose` section after the existing `## For BenchFlow-based tooling...` section (which ends at line 543, right before `## Verification: run the smoke` at line 544)
- Modify: `docs/how-to/ccc/CCC_PODMAN_SETUP.md`'s `## Layer index: symptom → fix` table (currently starting at line 591) — add 2 rows
- Modify: `docs/how-to/ccc/CCC_PODMAN_SETUP.md`'s `## What this touches outside the repo` table (currently starting at line 618) — add 1 row

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: the section anchor `## Parsec v4 (v4_t2_e1): host-process harness, not docker-compose`, referenced by Tasks 5 and 6's script header comments.

- [ ] **Step 1: Insert the new section**

Insert immediately before the line `## Verification: run the smoke` in `docs/how-to/ccc/CCC_PODMAN_SETUP.md`:

```markdown
## Parsec v4 (v4_t2_e1): host-process harness, not docker-compose

Earlier handoff/design docs for parsec v4 describe its runtime as a 5-service
`docker-compose` stack. **That premise is false.** The real topology has
three layers, and only the third one is a container at all:

1. **5 MCP simulation services — host Python processes, not containers.**
   Each is a plain `uvicorn` process running the `simulation_harness` module
   against one config file under `<PARSEC_V4N>/_run/harness-cfg/*.yaml`:

   | Service  | Config file                    | Port |
   |----------|---------------------------------|------|
   | platform | `harness-cfg/platform.yaml`     | 8086 |
   | github   | `harness-cfg/github.yaml`       | 8087 |
   | icinga   | `harness-cfg/icinga.yaml`       | 8088 |
   | cost     | `harness-cfg/cost.yaml`         | 8089 |
   | cloud    | `harness-cfg/cloud.yaml`        | 8090 |

   These port numbers are not arbitrary — they are the single source of
   truth in `scripts/v4_t2_e1/common/parsec_paths.py`'s `MCP_PORTS`, and
   every trial's `harbor run` invocation gets them injected as
   `PLATFORM_MCP_URL`/`GITHUB_MCP_URL`/`ICINGA_MCP_URL`/`COST_MCP_URL`/
   `CLOUD_MCP_URL` (see `adapter.py`'s `run_target()`).

2. **`parsec-live` — a second, separate host process, port 8000.** A plain
   `uv run uvicorn src.app:app` invocation from
   `<PARSEC_V4N>/_run/parsec-live/`. This is the live agent process whose
   `config/prompts/*.md` files a candidate's `apply()` overwrites, and whose
   own `MetricsCollector` log (not Harbor's `result.json`, which is always
   null for this agent) is where real cost/token telemetry comes from — see
   `adapter.py`'s module docstring.

3. **The Harbor task container — the only genuine container workload.**
   One `harbor run --config <trial>/harbor_config.json --n-concurrent 1`
   invocation per trial, using the `ParsecAgent` Harbor agent
   (`parsec_harbor_agent:ParsecAgent`) against one task directory under
   `<PARSEC_V4N>/_run/tasks/bench-v4-<task-id>/`. **This is the only layer
   the rest of this document's rootless-podman/docker-shim fixes apply
   to** — layers 1 and 2 are ordinary host processes and need none of it.

Because the task image here is `registry.access.redhat.com/ubi9/ubi:latest`
(not `ubuntu:24.04`), the host-networking fix in §A and the uv-preinstall
fix in §D do not apply to parsec's Harbor container — only the
`storage.conf`/`XDG_RUNTIME_DIR`/dbus-socket/docker-shim layers (the
one-time and per-session setup sections above) do.

### Bringing the stack up on a CCC compute node

```bash
export PARSEC_V4N=/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16
bash scripts/ccc/parsec_stack.sh up
bash scripts/ccc/parsec_stack.sh status   # waits for all 6 ports to accept
```

See `scripts/ccc/parsec_stack.sh --help` for `down`/`status`/`reap`. It is
deliberately a thin wrapper — one `uvicorn` per harness-cfg file, one
`uv run uvicorn` for `parsec-live` — because the reference driver
(`run_full34.py`) already starts these the same way; the script exists so a
CCC job doesn't need an interactive shell per service.

### Known gaps not solved by this change

- **GPFS multi-host collision:** the 6 processes above, plus
  `<PARSEC_V4N>/_run/skills/`, are shared, stateful resources with no
  per-lane isolation. Running two concurrent lanes against the *same*
  `$PARSEC_V4N` tree on two different hosts will corrupt both runs. Until a
  future change adds per-lane checkouts, run exactly one lane per
  `$PARSEC_V4N` tree at a time — matches the "one dedicated host per
  concurrent job" rule in the Batch (LSF) mode section below.
- **`install_seeds.py` hardcodes `localhost` and the fixed ports above** — a
  per-lane port-offsetting scheme is not just unimplemented, it is
  incompatible with this script's current form. Not addressed here.
- **A live LiteLLM API key was found in cleartext** in one CCC copy's
  `_run/parsec-live/config/config.local.yaml` (mode `644`, world/group
  readable). This is a credential exposure independent of anything in this
  section — rotate that key and `chmod 600` the file. Never let this file's
  contents reach a run's `env_snapshot.txt` or any other output that leaves
  the local disk.

```

- [ ] **Step 2: Add rows to the "Layer index: symptom → fix" table**

In the existing table (starts at line 591), add these two rows (matching the table's existing `| Symptom | Fix |` — or however its exact columns read in the live doc — column-for-column):

```markdown
| `podman machine inspect podman-machine-default` fails with "no such machine" | You're running parsec's Harbor-container docker-host resolution on Linux. `adapter.py`'s `_resolve_docker_host()` now prefers `$DOCKER_HOST` (already exported by `setup_podman.sh`) — confirm it's exported in your shell before invoking `cap-evolve run`/`harbor run` directly. |
| A parsec trial scores 0.0 on every task, but the stack "looks" healthy | The 5 MCP services / `parsec-live` are host processes, not containers — `podman ps` won't show them. Use `scripts/ccc/parsec_stack.sh status` (TCP-checks all 6 ports), not `podman ps`, to check parsec's own stack health. |
```

- [ ] **Step 3: Add a row to the "What this touches outside the repo" table**

In the existing table (starts at line 618), add:

```markdown
| `$PARSEC_V4N/_run/logs/`, `$PARSEC_V4N/_run/jobs/v4_t2_e1/` | Per-trial Harbor job output and the parsec-live/trace logs `adapter.py` reads for cost attribution. Grows unboundedly across runs — not cleaned up by anything in this repo. |
```

- [ ] **Step 4: Sanity-check the doc renders and the new anchor is reachable**

Run: `grep -n "^## " docs/how-to/ccc/CCC_PODMAN_SETUP.md`
Expected: the new `## Parsec v4 (v4_t2_e1): host-process harness, not docker-compose` heading appears between `## For BenchFlow-based tooling (SkillsBench, etc.) specifically` and `## Verification: run the smoke`, and every other existing heading is still present and in its original order.

- [ ] **Step 5: Commit**

```bash
git add docs/how-to/ccc/CCC_PODMAN_SETUP.md
git commit -s -m "$(cat <<'EOF'
docs(ccc): document parsec v4's real host-process topology, not compose

Earlier handoff docs described a 5-service docker-compose stack for
parsec v4. It's actually 5 host uvicorn processes (the MCP simulators) +
a 6th host process (parsec-live) + exactly one real container per trial
(the Harbor task). Corrects the premise and documents the CCC bring-up
workflow, referencing scripts/ccc/parsec_stack.sh from the next commit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `scripts/ccc/parsec_stack.sh` — bring-up/health-wait/teardown

The 5 MCP simulators and `parsec-live` are 6 independent host processes today started by hand (per the reference driver's own pattern). This task adds a script to start/stop/health-check all 6 from one CCC job, without changing how any of them are individually configured.

**Files:**
- Create: `scripts/ccc/parsec_stack.sh`

**Interfaces:**
- Consumes: `$PARSEC_V4N` (required — same contract as `parsec_paths.resolve_v4n()`).
- Produces: PID files under `$PARSEC_V4N/_run/logs/pids/{platform,github,icinga,cost,cloud,parsec-live}.pid`, consumed by this same script's `down`/`status`/`reap` subcommands (no other task reads these files in this change).

- [ ] **Step 1: Write the script**

Create `scripts/ccc/parsec_stack.sh`:

```bash
#!/bin/bash
#
# Bring up/down/health-check parsec v4's 6 host-process services: the 5 MCP
# simulation harnesses (platform/github/icinga/cost/cloud) and parsec-live
# itself. See docs/how-to/ccc/CCC_PODMAN_SETUP.md's "Parsec v4 (v4_t2_e1)"
# section for why these are host processes, not containers.
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/ccc/parsec_stack.sh up
#   bash scripts/ccc/parsec_stack.sh status
#   bash scripts/ccc/parsec_stack.sh down
#   bash scripts/ccc/parsec_stack.sh reap     # kill anything holding our ports, even orphans
#
# Exits non-zero if $PARSEC_V4N is unset, or (for `status`) if any port
# isn't accepting connections within the wait budget.

set -eo pipefail

usage() {
  sed -n '2,15p' "$0"
  exit 2
}

CMD="${1:-}"
if [[ -z "$CMD" ]]; then
  usage
fi

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"

PID_DIR="$PARSEC_V4N/_run/logs/pids"
LOG_DIR="$PARSEC_V4N/_run/logs/sims"
mkdir -p "$PID_DIR" "$LOG_DIR"

# name:port:kind — kind "sim" starts via `python -m simulation_harness
# --config <harness-cfg/<name>.yaml>`; kind "live" starts parsec-live's own
# `uv run uvicorn` from its own directory. Order matches
# docs/how-to/ccc/CCC_PODMAN_SETUP.md's table.
SERVICES=(
  "platform:8086:sim"
  "github:8087:sim"
  "icinga:8088:sim"
  "cost:8089:sim"
  "cloud:8090:sim"
  "parsec-live:8000:live"
)

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

port_open() {
  local port="$1"
  (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && exec 3>&- 3<&-
}

start_one() {
  local name="$1" port="$2" kind="$3"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (pid $(cat "$pid_file"))"
    return 0
  fi
  if [[ "$kind" == "sim" ]]; then
    ( cd "$PARSEC_V4N" && \
      nohup python3 -m simulation_harness --config "_run/harness-cfg/$name.yaml" \
        > "$LOG_DIR/$name.log" 2>&1 & echo $! > "$pid_file" )
  else
    ( cd "$PARSEC_V4N/_run/parsec-live" && \
      nohup uv run uvicorn src.app:app --host 0.0.0.0 --port "$port" \
        > "$LOG_DIR/$name.log" 2>&1 & echo $! > "$pid_file" )
  fi
  echo "started $name (pid $(cat "$pid_file"), port $port, log $LOG_DIR/$name.log)"
}

stop_one() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "stopped $name (pid $pid)"
    fi
    rm -f "$pid_file"
  else
    echo "$name: no pid file, nothing to stop"
  fi
}

case "$CMD" in
  up)
    banner "starting parsec v4 stack under $PARSEC_V4N"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port kind <<< "$entry"
      start_one "$name" "$port" "$kind"
    done
    ;;
  down)
    banner "stopping parsec v4 stack"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name _ _ <<< "$entry"
      stop_one "$name"
    done
    ;;
  reap)
    # Belt-and-suspenders teardown: kill whatever is actually listening on
    # our 6 ports, regardless of whether a pid file exists for it (covers
    # an orphan left by a killed-mid-startup job). Never sends a bare kill
    # to a pid we didn't just look up by port.
    banner "reaping anything on parsec v4's 6 ports"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port _ <<< "$entry"
      pid="$(lsof -t -i ":$port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null || true
        echo "reaped $name (port $port, pid $pid)"
      fi
    done
    rm -f "$PID_DIR"/*.pid
    ;;
  status)
    banner "waiting for parsec v4 stack health (max 60s)"
    deadline=$((SECONDS + 60))
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port _ <<< "$entry"
      until port_open "$port"; do
        if (( SECONDS >= deadline )); then
          echo "FATAL: $name (port $port) never opened within 60s" >&2
          exit 1
        fi
        sleep 1
      done
      echo "OK: $name (port $port) is accepting connections"
    done
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    usage
    ;;
esac
```

- [ ] **Step 2: Make it executable and run a shell syntax check**

Run: `chmod +x scripts/ccc/parsec_stack.sh && bash -n scripts/ccc/parsec_stack.sh`
Expected: no output (no syntax error).

- [ ] **Step 3: Smoke-test `status` fails cleanly with nothing running**

Run: `PARSEC_V4N=/tmp/fake-v4n bash scripts/ccc/parsec_stack.sh status`
Expected: exits 1, prints `FATAL: platform (port 8086) never opened within 60s` (or fails fast within a few seconds if nothing is listening — acceptable either way, the assertion is non-zero exit and a named failing service, not the exact timing).

- [ ] **Step 4: Commit**

```bash
git add scripts/ccc/parsec_stack.sh
git commit -s -m "$(cat <<'EOF'
feat(ccc): add parsec_stack.sh for up/down/status/reap of parsec's 6 services

The 5 MCP simulators + parsec-live are host processes (see the
CCC_PODMAN_SETUP.md doc commit) started by hand today. This script gives
a CCC job a single up/down/status/reap entry point for all 6, without
changing how any one of them is individually configured.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `scripts/ccc/run_ccc_parsec.sh` — hand-run driver for one task

`scripts/ccc/run_ccc_experiment.sh` is the existing CCC driver, but its `.env` contract requires `SKILLSBENCH_TASKS_DIR`/`ANTHROPIC_*`, which is wrong for parsec (parsec needs `PARSEC_V4N` plus whatever LLM credentials `config.local.yaml` already carries — not this repo's `.env`). This task adds a sibling script reusing the same phase/banner/output-layout pattern, scoped to running exactly one `v4_t2_e1` task's `cap-evolve run` by hand on one CCC host — the smoke-test target from the original brief.

**Files:**
- Create: `scripts/ccc/run_ccc_parsec.sh`

**Interfaces:**
- Consumes: `scripts/ccc/parsec_stack.sh status` (Task 5), `scripts/ccc/setup_podman.sh` (existing, unchanged), `.capevolve/v4_t2_e1_<task-id>/project/` (existing, produced by `scaffold_projects.py`, Task 3).
- Produces: `results/parsec/<task-id>/<run-id>/{setup.log,cap-evolve.log,env_snapshot.txt,run/}` — same layout convention as `run_ccc_experiment.sh`'s `results/<suite-id>/<run-id>/`.

- [ ] **Step 1: Write the script**

Create `scripts/ccc/run_ccc_parsec.sh`:

```bash
#!/bin/bash
#
# Run one v4_t2_e1 task's cap-evolve project on a CCC compute node, by hand.
# Mirrors run_ccc_experiment.sh's phase structure (podman setup -> stack
# health-wait -> cap-evolve run -> summarize), but for parsec's own stack
# and its own env contract (PARSEC_V4N, not SKILLSBENCH_TASKS_DIR).
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/ccc/run_ccc_parsec.sh --task-id icinga-011-aap2-job-status-alert
#
# Output layout under the project (all under $PROJECT_ROOT/results/parsec/):
#   results/parsec/<task-id>/<run-id>/
#     setup.log            # setup_podman.sh + parsec_stack.sh output
#     cap-evolve.log        # cap-evolve stdout+stderr
#     env_snapshot.txt      # PARSEC_V4N, capevolve.yaml, git commit, hostname
#     run/                  # cap-evolve's run dir (symlinked from .capevolve/run_<run-id>)
#
# Exits non-zero if setup fails, the stack never becomes healthy, or
# cap-evolve returns an error.

set -eo pipefail

TASK_ID=""
RUN_ID=""
MAX_ITERATIONS="0"
DRY_RUN=false

usage() {
  sed -n '2,20p' "$0"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)         TASK_ID="$2"; shift 2 ;;
    --run-id)          RUN_ID="$2"; shift 2 ;;
    --max-iterations)  MAX_ITERATIONS="$2"; shift 2 ;;
    --dry-run)         DRY_RUN=true; shift ;;
    -h|--help)         usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ -z "$TASK_ID" ]]; then
  echo "ERROR: --task-id is required (e.g. --task-id icinga-011-aap2-job-status-alert)" >&2
  usage
fi

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"

if [[ -z "$RUN_ID" ]]; then
  if [[ -n "${LSB_JOBID:-}" ]]; then
    RUN_ID="$LSB_JOBID"
  else
    RUN_ID="local_$(date +%Y%m%d_%H%M%S)"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PROJECT_ROOT:-}" ]]; then
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

PROJECT_DIR=".capevolve/v4_t2_e1_${TASK_ID}/project"
SPEC="$PROJECT_DIR/capevolve.yaml"
if [[ ! -f "$PROJECT_ROOT/$SPEC" ]]; then
  echo "ERROR: $PROJECT_ROOT/$SPEC not found — run scaffold_projects.py first" >&2
  exit 2
fi

OUT_DIR="$PROJECT_ROOT/results/parsec/$TASK_ID/$RUN_ID"
mkdir -p "$OUT_DIR"
SETUP_LOG="$OUT_DIR/setup.log"
RUN_LOG="$OUT_DIR/cap-evolve.log"
ENV_SNAP="$OUT_DIR/env_snapshot.txt"

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

banner "parsec v4 (v4_t2_e1) on CCC: $TASK_ID / $RUN_ID"
{
  echo "Host:          $(hostname)"
  echo "Start:         $(date -Iseconds)"
  echo "PROJECT_ROOT:  $PROJECT_ROOT"
  echo "PARSEC_V4N:    $PARSEC_V4N"
  echo "OUT_DIR:       $OUT_DIR"
  echo "TASK_ID:       $TASK_ID"
  echo "MAX_ITER:      $MAX_ITERATIONS"
  if [[ -n "${LSB_JOBID:-}" ]]; then
    echo "LSF job:       $LSB_JOBID"
  fi
} | tee "$ENV_SNAP"

if [[ "$DRY_RUN" == true ]]; then
  echo "(dry-run: exiting before setup)"
  exit 0
fi

banner "Phase 1: setup_podman.sh"
SETUP_PODMAN="${CCC_SETUP_PODMAN:-$SCRIPT_DIR/setup_podman.sh}"
if [[ ! -r "$SETUP_PODMAN" ]]; then
  echo "FATAL: setup_podman.sh not readable at $SETUP_PODMAN" >&2
  exit 2
fi
# shellcheck disable=SC1090
source "$SETUP_PODMAN" > >(tee "$SETUP_LOG") 2>&1
wait 2>/dev/null || true

banner "Phase 2: parsec stack up + health-wait"
bash "$SCRIPT_DIR/parsec_stack.sh" up | tee -a "$SETUP_LOG"
bash "$SCRIPT_DIR/parsec_stack.sh" status | tee -a "$SETUP_LOG"

{
  echo
  echo "===== $SPEC ====="
  cat "$PROJECT_ROOT/$SPEC"
  echo
  echo "===== git status (worktree) ====="
  ( cd "$PROJECT_ROOT" && git log -1 --format='commit %H%n%s' 2>&1 || echo "(not a git repo)" )
} >> "$ENV_SNAP"

banner "Phase 3: cap-evolve run"
cd "$PROJECT_ROOT"
export TASK_ID
export PARSEC_V4N

CE_RUN_ABS="$PROJECT_ROOT/.capevolve/run_${RUN_ID}"
ln -sfn "$CE_RUN_ABS" "$OUT_DIR/run"
export PYTHONPATH="$PROJECT_DIR/adapters${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "${CE_BIN:-}" ]]; then
  if [[ -x "$PROJECT_ROOT/.venv/bin/cap-evolve" ]]; then
    CE_BIN="$PROJECT_ROOT/.venv/bin/cap-evolve"
  else
    CE_BIN="$(command -v cap-evolve || true)"
  fi
fi
if [[ -z "$CE_BIN" || ! -x "$CE_BIN" ]]; then
  echo "FATAL: cap-evolve CLI not found. Set CE_BIN=/path/to/cap-evolve." >&2
  exit 2
fi

set +e
stdbuf -oL -eL "$CE_BIN" run --spec "$SPEC" --project "$PROJECT_DIR" \
    --run-ts "$RUN_ID" --max-iterations "$MAX_ITERATIONS" 2>&1 | tee "$RUN_LOG"
RC="${PIPESTATUS[0]}"
set -e

banner "Phase 4: done"
echo "End:      $(date -Iseconds)"
echo "Exit:     $RC"
echo "Results:  $OUT_DIR"
exit "$RC"
```

- [ ] **Step 2: Make it executable and run a shell syntax check**

Run: `chmod +x scripts/ccc/run_ccc_parsec.sh && bash -n scripts/ccc/run_ccc_parsec.sh`
Expected: no output.

- [ ] **Step 3: Verify `--task-id` is enforced**

Run: `bash scripts/ccc/run_ccc_parsec.sh`
Expected: exits 2, prints `ERROR: --task-id is required ...` to stderr.

- [ ] **Step 4: Verify `--dry-run` reaches the env snapshot without needing a live stack**

Run: `PARSEC_V4N=/tmp/fake-v4n bash scripts/ccc/run_ccc_parsec.sh --task-id fake-task --dry-run 2>&1 | tail -5`
Expected: fails at the `$PROJECT_ROOT/$SPEC` existence check (`.capevolve/v4_t2_e1_fake-task/project/capevolve.yaml not found`) with exit 2 — confirms argument parsing and path resolution run correctly before the dry-run exit point; this is expected in a repo with no `fake-task` scaffolded, not a script bug.

- [ ] **Step 5: Commit**

```bash
git add scripts/ccc/run_ccc_parsec.sh
git commit -s -m "$(cat <<'EOF'
feat(ccc): add run_ccc_parsec.sh, a hand-run driver for one v4_t2_e1 task

Mirrors run_ccc_experiment.sh's phase structure and results/ layout, but
scoped to parsec's own env contract (PARSEC_V4N) and stack
(parsec_stack.sh up + status) instead of SkillsBench's
(SKILLSBENCH_TASKS_DIR/ANTHROPIC_*). This is the script the "run one task
by hand on one CCC host" smoke test uses.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Repair dangling symlinks and rebuild venvs on both CCC parsec trees

Both CCC copies of the parsec materials (`rhdp-parsec/v4_old` and `rhdp-parsec/v4_2026-09-16`) were copied from the Mac verbatim, including 8 `.claude/skills/*` symlinks per tree pointing at absolute Mac paths (`/Users/boazc/workarea/Python/rhdp-parsec/<tree>/_run/parsec-live/skills/<name>`) and 3 `.venv/bin/python*` symlinks pointing at a macOS-arm64 `uv`-managed Python that does not exist on Linux. This task repairs both, operating directly on the CCC filesystem (not a git-tracked change — these trees are the user's own copied materials, not part of this repo).

**Files:**
- Create: `scripts/ccc/parsec_bootstrap.sh` (repair script, committed to the repo so the repair is repeatable/auditable)
- Operate on (not committed): `/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_old/`, `/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16/`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing consumed by later tasks — this is the operational fix the user asked for alongside the doc/scripts port, run once (with `--check` available for re-verification later).

- [ ] **Step 1: Write `parsec_bootstrap.sh`**

Create `scripts/ccc/parsec_bootstrap.sh`:

```bash
#!/bin/bash
#
# One-time repair for a parsec v4 tree copied from Mac to CCC: re-point the
# 8 .claude/skills/* symlinks at their sibling directory (they currently
# point at an absolute /Users/... path that doesn't exist on this machine),
# and rebuild the parsec-live .venv (its 3 python*/python3.12 symlinks point
# at a macOS-arm64 uv-managed interpreter).
#
# Usage:
#   bash scripts/ccc/parsec_bootstrap.sh --tree /path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/ccc/parsec_bootstrap.sh --tree /path/to/rhdp-parsec/v4_2026-09-16 --check
#
# --check reports what's broken without changing anything (exit 1 if
# anything needs repair, 0 if the tree is already healthy).

set -eo pipefail

TREE=""
CHECK_ONLY=false

usage() {
  sed -n '2,14p' "$0"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tree)   TREE="$2"; shift 2 ;;
    --check)  CHECK_ONLY=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ -z "$TREE" || ! -d "$TREE" ]]; then
  echo "ERROR: --tree must be an existing directory (got: '$TREE')" >&2
  usage
fi
TREE="$(cd "$TREE" && pwd)"

LIVE_DIR="$TREE/_run/parsec-live"
SKILLS_LINK_DIR="$LIVE_DIR/.claude/skills"
SKILLS_REAL_DIR="$LIVE_DIR/skills"
VENV_DIR="$LIVE_DIR/.venv"

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

broken=0

banner "Checking $SKILLS_LINK_DIR"
if [[ -d "$SKILLS_LINK_DIR" ]]; then
  for link in "$SKILLS_LINK_DIR"/*; do
    [[ -L "$link" ]] || continue
    name="$(basename "$link")"
    if [[ ! -e "$link" ]]; then
      echo "BROKEN: $link -> $(readlink "$link")"
      broken=1
      if [[ "$CHECK_ONLY" == false ]]; then
        target="$SKILLS_REAL_DIR/$name"
        if [[ ! -d "$target" ]]; then
          echo "  SKIP: real skill dir missing too: $target" >&2
          continue
        fi
        rel="$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
                 "$target" "$SKILLS_LINK_DIR")"
        rm -f "$link"
        ln -s "$rel" "$link"
        echo "  FIXED: $link -> $rel"
      fi
    fi
  done
else
  echo "(no $SKILLS_LINK_DIR — nothing to check)"
fi

banner "Checking $VENV_DIR"
if [[ -d "$VENV_DIR" ]]; then
  venv_broken=false
  for py in "$VENV_DIR"/bin/python*; do
    [[ -L "$py" ]] || continue
    if [[ ! -e "$py" ]]; then
      echo "BROKEN: $py -> $(readlink "$py")"
      venv_broken=true
      broken=1
    fi
  done
  if [[ "$venv_broken" == true && "$CHECK_ONLY" == false ]]; then
    echo "Rebuilding venv with uv (needs uv + python3.12 on PATH)..."
    rm -rf "$VENV_DIR"
    ( cd "$LIVE_DIR" && uv venv --python 3.12 && uv pip install -e . )
    echo "  FIXED: rebuilt $VENV_DIR"
  fi
else
  echo "(no $VENV_DIR — nothing to check)"
fi

banner "Result"
if [[ "$broken" -eq 0 ]]; then
  echo "OK: $TREE is healthy."
  exit 0
elif [[ "$CHECK_ONLY" == true ]]; then
  echo "NEEDS REPAIR: re-run without --check to fix."
  exit 1
else
  echo "Repaired what could be repaired — re-run with --check to confirm."
  exit 0
fi
```

- [ ] **Step 2: Make it executable and run a shell syntax check**

Run: `chmod +x scripts/ccc/parsec_bootstrap.sh && bash -n scripts/ccc/parsec_bootstrap.sh`
Expected: no output.

- [ ] **Step 3: Confirm the broken state with `--check` on both trees**

Run:
```bash
bash scripts/ccc/parsec_bootstrap.sh --tree /dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16 --check
```
Expected: exit 1, 8 `BROKEN:` lines under the skills check (one per `.claude/skills/*` entry) and 3 under the venv check (`python`, `python3`, `python3.12`), ending `NEEDS REPAIR: re-run without --check to fix.`

Repeat for `v4_old`.

- [ ] **Step 4: Run the repair on `v4_2026-09-16`**

Run: `bash scripts/ccc/parsec_bootstrap.sh --tree /dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16`
Expected: 8 `FIXED:` lines re-pointing each skill symlink at a relative path resolving into `_run/parsec-live/skills/<name>`, then the venv is rebuilt via `uv venv --python 3.12 && uv pip install -e .` inside `_run/parsec-live/`, ending `Repaired what could be repaired — re-run with --check to confirm.`

- [ ] **Step 5: Re-run `--check` to confirm the repair on `v4_2026-09-16`**

Run: `bash scripts/ccc/parsec_bootstrap.sh --tree /dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16 --check`
Expected: exit 0, `OK: ... is healthy.`

- [ ] **Step 6: Repeat Steps 4-5 for `v4_old`**

Run:
```bash
bash scripts/ccc/parsec_bootstrap.sh --tree /dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_old
bash scripts/ccc/parsec_bootstrap.sh --tree /dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_old --check
```
Expected: same repair-then-OK sequence as `v4_2026-09-16`.

- [ ] **Step 7: Spot-check one repaired skill symlink resolves to real content**

Run: `cat /dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16/_run/parsec-live/.claude/skills/icinga-triage/SKILL.md | head -5`
Expected: real file content is printed (not a "No such file or directory" error).

- [ ] **Step 8: Commit the repair script (not the trees themselves — they are outside the repo)**

```bash
git add scripts/ccc/parsec_bootstrap.sh
git commit -s -m "$(cat <<'EOF'
feat(ccc): add parsec_bootstrap.sh to repair Mac->CCC symlink breakage

The copied parsec v4 trees carry 8 .claude/skills/* symlinks pointing at
absolute /Users/... paths and 3 .venv/bin/python* symlinks pointing at a
macOS-arm64 interpreter — both silently broken on CCC. This script
re-points the former at their real sibling directory and rebuilds the
venv with uv. Also ran by hand against both
/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/{v4_old,v4_2026-09-16}
(not committed — those trees are outside this repo).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 9: Surface the cleartext-credential finding to the user**

Not a code change — report it directly: `_run/parsec-live/config/config.local.yaml` in the CCC copy contains a live LiteLLM API key in cleartext at mode `644` (world/group readable). Recommend: rotate that key, then `chmod 600 config/config.local.yaml` on both trees. This plan does not do either automatically (rotating a credential is the user's call, and the file's contents must not be read/echoed by tooling — see the doc section's "Known gaps" note).

---

## Self-Review

**1. Spec coverage:**
- "Doc + scripts port only" scope, three sub-items:
  - New parsec-specific `CCC_PODMAN_SETUP.md` section correcting the compose premise → Task 4. ✓
  - New CCC scripting for bring-up/health-wait/teardown → Task 5 (`parsec_stack.sh`). ✓
  - Concrete code fixes (Mac-only docker-host resolution; hardcoded personal paths; false-green skipping tests) → Tasks 1-3. ✓
- Explicitly NOT in scope: `v4_g2_e1` scaffold — no task touches it, and `Adapter.tasks()`'s single-task semantics are explicitly preserved in Task 2. ✓
- Fix dangling symlinks (8 skills + 3 venv, both trees) → Task 7. ✓
- "Get one task running end-to-end by hand on one CCC host" smoke test → Task 6 (`run_ccc_parsec.sh`) is the vehicle; actually executing it end-to-end is a follow-up action after this plan's tasks land (needs a live CCC allocation), not a task with its own commit — noted in Task 6's docstring and Task 4's doc section.
- Security finding (cleartext LiteLLM key) → surfaced in Task 4's doc "Known gaps" and explicitly flagged (not silently fixed) in Task 7 Step 9. ✓

**2. Placeholder scan:** No `TBD`/`TODO`/"add appropriate handling" strings anywhere above; every step shows the actual file content, not a description of it. The one intentionally-deferred item (multi-lane GPFS isolation, port-offsetting) is called out by name as a documented gap, not left as an implicit placeholder.

**3. Type consistency:** `parsec_paths.resolve_v4n_or_none() -> Path | None` (Task 1) is used identically in Task 2 (`adapter.py`'s `V4N`) and Task 3 (`scaffold_projects.py`'s `PARSEC_V4N`) — both accept `None` and propagate it rather than dereferencing early. `parsec_paths.MCP_PORTS: dict[str, int]` (Task 1) is imported verbatim as `adapter.MCP_PORTS` in Task 2, not redefined. `adapter.TASKS_DIR: Path | None` (Task 2) is consumed by `test_adapter.py`'s `REAL_TASKS_DIR` (Task 2, same task) with an explicit `is not None` guard before `.exists()`, matching the `Path | None` type rather than assuming non-null.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-23-parsec-v4-ccc-port.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
