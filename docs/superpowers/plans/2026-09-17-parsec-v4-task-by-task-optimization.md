# parsec v4 task-by-task optimization (v4_t2_e1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build every missing piece needed to run cap-evolve's first real
optimization pass over parsec v4: a harbor adapter that injects candidate
prompts into the live `parsec-live` clone, 21 per-task cap-evolve projects
(one per sub-1.0 task from `v4_t1_e1`), and a single-task runner that drives
them one at a time as independent, monitored OS processes.

**Architecture:** Single lane, strictly sequential — one shared `parsec-live`
+ 5-service harness stack, never more than one task's `cap-evolve run` active
at a time. Each of the 21 per-task projects shares one adapter and one
optimizer-instructions file (symlinked from a `common/` project, itself
symlinked from the tracked source under `scripts/v4_t2_e1/common/`) and
starts from the same seed capability (a snapshot of `config/prompts/*.md`);
only the task being optimized differs (`train = val = test = {task}`, pinned
via `split_ids.json`, per the real precedent at
`parsec-intake_v1/.capevolve/project/experiments/seed-recheck/split_ids.json`).
The runner (`scripts/v4_t2_e1/run_one_task.py`) launches exactly **one**
`cap-evolve run` as a foreground child process, waits for it to exit, records
the outcome, and exits — it never loops over tasks itself. Re-invoking it
repeatedly (by hand, or via a trivial external `while` loop / launchd job) is
what advances through all 21 tasks; a VPN drop, sleep, or crash kills at most
the one task in flight, and the next invocation picks up exactly where the
crashed one left off.

**Tech Stack:** Python 3 standard library + `unittest` (no pytest, no new
third-party deps — matches `core/cap_evolve`'s own zero-dependency policy),
`uv` (manages the globally-installed `cap-evolve` and `harbor` tool venvs),
`harbor` CLI (already installed, `v0.20.0`), `cap-evolve` CLI (installed via
`uv tool`, but — see Task 1 — **currently stale**, built from a different
worktree's `core/`; Task 1 fixes this before anything else runs).

**Spec:** `docs/superpowers/specs/2026-09-17-parsec-v4-task-by-task-optimization-design.md`

**Deviations from the spec, found while verifying every file path and CLI
flag against the real, current code (flagged here per the writing-plans
No-Placeholders rule — these are corrections, not reinterpretations):**

1. **The spec's own per-task layout has a run-directory collision bug.**
   `cap-evolve run --project <P>` creates its `run_<timestamp>/` directory
   under `<P>`'s **parent**, not under `<P>` itself
   (`core/cap_evolve/cli.py`: `workdir = proj_abs.parent.parent`; `base =
   proj_abs.parent` relative to `workdir`; `RunDir.latest()` in
   `core/cap_evolve/rundir.py` globs `base.glob("run_*")`). The spec's layout
   (`.capevolve/v4_t2_e1/project_<task-id>/`) puts all 21 projects' parent at
   the same shared `v4_t2_e1/` directory, so all 21 tasks' `run_*` dirs would
   land in that one shared directory and `--resume`'s `RunDir.latest()` could
   resolve to the wrong task's run. **Fix:** nest one level deeper —
   `.capevolve/v4_t2_e1_<task-id>/project/` — so each task's project has a
   *unique* parent directory and its `run_*` dirs never collide with another
   task's. See Task 2.
2. **The installed `cap-evolve` tool is stale and missing `stop_at_reward`
   entirely** (confirmed by running it: 911-line installed `cli.py`, 0 matches
   for `stop_at_reward`, vs. this worktree's 1762-line `cli.py`; its
   `direct_url.json` shows it was built from `parsec-intake_v1/core`, not this
   worktree). This is exactly the risk the spec's Run Parameters section
   flagged as a pre-flight to check — checking it here found it **failing**.
   Task 1 fixes it (`uv tool install --force <this worktree's core/>`) before
   any other task runs. **This changes a machine-global `uv tool`, shared by
   every worktree on this machine** — call this out to the user before
   running it, not just in this doc.
3. **The adapter and optimizer-instructions source live under `scripts/`, not
   under `.capevolve/`.** `.capevolve*/` is gitignored
   (`parsec-intake_v4/.gitignore:19`), so anything placed only under
   `.capevolve/` — as the spec's `common/` diagram shows — would never be
   committed, losing real engineering work to `.gitignore`. **Fix:** the
   authored source lives at `scripts/v4_t2_e1/common/{adapters,optimizer}/`
   (tracked in git); `.capevolve/v4_t2_e1_common/{adapters,optimizer}` are
   symlinks *into* that tracked source, and each task's `project/{adapters,
   optimizer}` are symlinks to *those* symlinks. Editing the tracked source
   takes effect immediately, with nothing to re-copy.
4. **Single lane, not 2** — per the user's explicit redirect after seeing the
   2-lane plan ("assume I want only a single lane... I will then run these in
   parallel on the CCC, but for this run assume it will just take more time").
   This plan does not build the second lane, the port-offset stack variant, or
   the job-pool dispatcher the spec's *Execution mechanics* section describes.
   CCC itself remains fully deferred, per the spec's own "Not CCC" section —
   this plan adds no CCC-facing plumbing.
5. **The 21-task dispatch is a single-task runner invoked once per task, not
   a loop over all 21** — per the user's explicit correction to this plan
   while it was being written: *"I prefer running the tasks as a stand-alone
   processes/script. Not in a loop within a script. Each time run a single
   harbor task, let it perform and finish. Monitor it and once done launch the
   following one. This will allow a more robust execution e.g. against VPN
   errors and computer shutdown or going to sleep."* Task 5 builds exactly
   this: one process, one task, run to completion, exit — repetition is an
   external concern (documented, not scripted as an internal loop).
6. **`split_ids.json` is required, not optional** — the design doc's
   `train = val = test = {task}` scope is degenerate for ratio-based
   splitting (there is exactly one task; a 0.5/0.25/0.25 split of one item is
   meaningless). The real mechanism for this — confirmed against
   `skills/phases/baseline/scripts/run.py`'s `--split-ids` handling and a real
   example at `parsec-intake_v1/.capevolve/project/experiments/seed-recheck/split_ids.json`
   — is a pinned `split_ids.json` of the shape `{"train": [id], "val": [id],
   "test": [id]}`, referenced from `capevolve.yaml` via `split_ids_file:
   split_ids.json`. Task 2 writes one per task.

## Global Constraints

- `num_trials: 5`, `max_iterations: 3`, `stop_at_reward: 1.0` in every
  per-task `capevolve.yaml` (all three are genuine `capevolve.yaml` keys read
  by `core/cap_evolve/cli.py`'s `_cmd_run` via `spec.get(...)`).
- `optimizer_model: claude-opus-5` (optimizer) and `target_model:
  claude-sonnet-4-6` (the model parsec-live actually runs — confirmed live in
  `_run/parsec-live/config/config.local.yaml`'s `anthropic.model`, replacing
  v1's stale `claude-sonnet-4-20250514`), per the standing model-assignment
  convention (Opus 5 optimizer / Sonnet 5 evaluator).
- `train = val = test = {task}` for every project, via a pinned
  `split_ids.json` (see deviation 6 above) — no held-out test split this
  phase.
- No cross-task regression checking; no merge of the 21 resulting mutations
  (both deferred to `v4_t3_e1`).
- Single lane, strictly sequential — never more than one `cap-evolve run` (and
  therefore never more than one `harbor run` against the shared 5-service
  harness + `parsec-live` stack) active at a time.
- Candidate injection = overwrite `config/prompts/*.md` in the **live**
  `parsec-live` clone; the running uvicorn process picks it up on its next
  request via its mtime-cache — no restart (`_run/parsec-live/src/agent/system_prompt.py`).
- The live `parsec-live` + 5-service harness stack is never stopped, started,
  or reconfigured by anything in this plan — every script only reads from it,
  writes candidate prompt files into it, or health-checks it. (`start-sims-v4.sh`
  / `start-parsec.sh` are out of scope — the stack is assumed already running,
  exactly as `run_full34.py` assumes today.)
- The LiteLLM API key (`_run/parsec-live/config/config.local.yaml`'s
  `anthropic.litellm_api_key`) is never hardcoded in any script, generated
  config file, log, or commit message. It is never read or referenced by any
  script in this plan at all — parsec-live reads it itself from its own
  config file; nothing here needs it.
- `parsec-intake_v4/.gitignore:19` (`.capevolve*/`) means everything under
  `.capevolve/` is untracked, always. All *authored* source (the adapter, the
  optimizer instructions, the scaffolding/runner/pre-flight scripts and their
  tests) lives under the tracked `scripts/v4_t2_e1/` instead, and is copied
  into place there only via symlinks resolved at run time (see deviation 3).
- Every script in this plan uses only the Python 3 standard library — no new
  `pip`/`uv` dependencies.
- `.capevolve/v4_t2_e1_<task-id>/project/` is the per-task project root passed
  as `--project` to `cap-evolve run` (see deviation 1); `TASK_ID` is a
  required environment variable the shared adapter reads to know which task
  it is running (there is no other way for one shared, symlinked
  `adapters/adapter.py` to know which of the 21 projects invoked it — checked
  against `core/cap_evolve/check.py`'s `load_adapter()`, which imports
  `Adapter()` with zero constructor arguments).

---

### Task 1: Pre-flight — sync the installed `cap-evolve` tool with this worktree

The globally-installed `cap-evolve` CLI (`~/.local/bin/cap-evolve`, a `uv
tool`) is currently built from `parsec-intake_v1`'s `core/`, not this
worktree's. Confirmed by direct inspection: its installed `cli.py` is 911
lines with zero occurrences of `stop_at_reward`, versus this worktree's
1762-line `cli.py`; its `direct_url.json` reads `"url":
"file:///Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v1/core"`.
Every later task in this plan depends on `--stop-at-reward` working. This
task builds a script that detects the staleness and, once you've run the fix
command it prints, verifies the fix took.

**Files:**
- Create: `scripts/v4_t2_e1/preflight_check.py`
- Test: `scripts/v4_t2_e1/tests/test_preflight_check.py`

**Interfaces:**
- Produces: `installed_cli_supports_stop_at_reward() -> bool`,
  `REMEDY_CMD: str` (the exact `uv tool install --force ...` command, computed
  from this file's own resolved repo root), `main() -> int` — Task 5's runner
  imports and calls `installed_cli_supports_stop_at_reward()` once before
  launching any task, refusing to start if it returns `False`.

- [ ] **Step 1: Write the failing test**

```python
# scripts/v4_t2_e1/tests/test_preflight_check.py
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_check  # noqa: E402


class TestPreflightCheck(unittest.TestCase):
    def test_supports_flag_when_help_mentions_it(self):
        completed = subprocess.CompletedProcess(
            args=["cap-evolve", "run", "--help"], returncode=0,
            stdout="usage: cap-evolve run [-h] ... --stop-at-reward STOP_AT_REWARD ...",
            stderr="",
        )
        with patch("subprocess.run", return_value=completed):
            self.assertTrue(preflight_check.installed_cli_supports_stop_at_reward())

    def test_does_not_support_flag_when_help_omits_it(self):
        completed = subprocess.CompletedProcess(
            args=["cap-evolve", "run", "--help"], returncode=0,
            stdout="usage: cap-evolve run [-h] --project PROJECT --spec SPEC",
            stderr="",
        )
        with patch("subprocess.run", return_value=completed):
            self.assertFalse(preflight_check.installed_cli_supports_stop_at_reward())

    def test_remedy_cmd_points_at_this_worktrees_core(self):
        self.assertIn("uv tool install", preflight_check.REMEDY_CMD)
        self.assertIn("--force", preflight_check.REMEDY_CMD)
        self.assertTrue(preflight_check.REMEDY_CMD.rstrip().endswith("core"))

    def test_main_returns_0_when_supported(self):
        with patch.object(preflight_check, "installed_cli_supports_stop_at_reward",
                           return_value=True):
            self.assertEqual(preflight_check.main(), 0)

    def test_main_returns_1_when_not_supported(self):
        with patch.object(preflight_check, "installed_cli_supports_stop_at_reward",
                           return_value=False):
            self.assertEqual(preflight_check.main(), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/v4_t2_e1/tests/test_preflight_check.py -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'preflight_check'`
(the file doesn't exist yet).

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Pre-flight: confirm the globally-installed `cap-evolve` tool matches this
worktree's core/ (specifically, that it supports --stop-at-reward, added by
PR #415 / commit d1275b32a). v4_t2_e1's per-task runner refuses to start a
run until this passes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
REMEDY_CMD = f"uv tool install --force {CORE_DIR}"


def installed_cli_supports_stop_at_reward() -> bool:
    try:
        result = subprocess.run(
            ["cap-evolve", "run", "--help"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"could not run `cap-evolve run --help`: {exc}", file=sys.stderr)
        return False
    return "--stop-at-reward" in result.stdout


def main() -> int:
    if installed_cli_supports_stop_at_reward():
        print("OK: installed cap-evolve supports --stop-at-reward.")
        return 0
    print(
        "STALE: the installed `cap-evolve` tool does not support --stop-at-reward.\n"
        "It is likely built from a different worktree's core/ (this has happened before —\n"
        "check its direct_url.json under the uv tool venv's dist-info).\n"
        f"Fix by reinstalling it from THIS worktree's core/:\n\n"
        f"    {REMEDY_CMD}\n\n"
        "Note: this is a machine-global `uv tool`, shared by every cap-evolve worktree on\n"
        "this machine — confirm with whoever else might be running it before doing this.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/v4_t2_e1/tests/test_preflight_check.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Run the script for real against the current environment**

Run: `python3 scripts/v4_t2_e1/preflight_check.py; echo "exit=$?"`
Expected right now: prints `STALE: ...` and the remedy command, `exit=1` —
this has been confirmed true as of this plan being written.

- [ ] **Step 6: Tell the user, then run the remedy command**

Before running it, tell the user explicitly that this replaces a
machine-global `uv tool` shared by every worktree (v1, v2, v4, ...) on this
machine, then run:

```bash
uv tool install --force /Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/core
```

- [ ] **Step 7: Re-run the pre-flight script to confirm the fix took**

Run: `python3 scripts/v4_t2_e1/preflight_check.py; echo "exit=$?"`
Expected: prints `OK: installed cap-evolve supports --stop-at-reward.`,
`exit=0`.

- [ ] **Step 8: Commit**

```bash
git add scripts/v4_t2_e1/preflight_check.py scripts/v4_t2_e1/tests/test_preflight_check.py
git commit -m "$(cat <<'EOF'
feat(v4_t2_e1): pre-flight check for a stale installed cap-evolve tool

The globally-installed cap-evolve uv tool was built from parsec-intake_v1's
core/, missing --stop-at-reward entirely. v4_t2_e1's runs depend on it.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Per-task project scaffolding

Builds the 21 per-task cap-evolve projects plus the shared `common/` symlink
targets, using the corrected nested layout from deviation 1 above.

**Files:**
- Create: `scripts/v4_t2_e1/scaffold_projects.py`
- Test: `scripts/v4_t2_e1/tests/test_scaffold_projects.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `TASK_IDS: list[str]` (21 ids, fixed order — Task 5's runner
  imports this for its default task-ordering), `PROMPT_FILES: list[str]` (the
  8 prompt filenames), `render_capevolve_yaml(task_id: str) -> str`,
  `render_split_ids(task_id: str) -> str`, `scaffold_all(capevolve_dir: Path,
  *, prompts_dir: Path, task_ids: list[str], common_adapters_src: Path,
  common_optimizer_src: Path) -> list[Path]` (returns every path it created or
  verified, for the test and for a human `--dry-run` reader).

- [ ] **Step 1: Write the failing test**

```python
# scripts/v4_t2_e1/tests/test_scaffold_projects.py
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scaffold_projects  # noqa: E402


class TestScaffoldProjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.capevolve_dir = Path(self.tmp.name) / ".capevolve"
        # A fake prompts_dir standing in for _run/parsec-live/config/prompts/ —
        # real 8-file fixture, not the actual live prompts (keeps the test
        # hermetic and fast).
        self.prompts_dir = Path(self.tmp.name) / "fake_prompts"
        self.prompts_dir.mkdir(parents=True)
        for name in scaffold_projects.PROMPT_FILES:
            (self.prompts_dir / name).write_text(f"# seed content for {name}\n")
        # Fake common/ source, standing in for scripts/v4_t2_e1/common/.
        self.common_adapters_src = Path(self.tmp.name) / "common_src" / "adapters"
        self.common_optimizer_src = Path(self.tmp.name) / "common_src" / "optimizer"
        self.common_adapters_src.mkdir(parents=True)
        self.common_optimizer_src.mkdir(parents=True)
        (self.common_adapters_src / "adapter.py").write_text("# fake adapter\n")
        (self.common_optimizer_src / "INSTRUCTIONS.md").write_text("# fake instructions\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_one_project_per_task_with_all_seed_files(self):
        task_ids = ["task-a", "task-b"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        for tid in task_ids:
            proj = self.capevolve_dir / f"v4_t2_e1_{tid}" / "project"
            for name in scaffold_projects.PROMPT_FILES:
                self.assertTrue((proj / "seed_capability" / name).exists(),
                                 f"missing {name} for {tid}")
            self.assertTrue((proj / "capevolve.yaml").exists())
            self.assertTrue((proj / "split_ids.json").exists())

    def test_project_adapters_symlink_resolves_to_common_source(self):
        task_ids = ["task-a"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        resolved = (proj / "adapters").resolve()
        self.assertEqual(resolved, self.common_adapters_src.resolve())
        self.assertTrue((proj / "adapters" / "adapter.py").exists())

    def test_run_dir_parent_is_unique_per_task(self):
        # The whole point of the nested layout: two tasks' projects must not
        # share a parent directory (that parent is where cap-evolve run puts
        # run_*/ — see deviation 1 in the plan header).
        task_ids = ["task-a", "task-b"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj_a = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        proj_b = self.capevolve_dir / "v4_t2_e1_task-b" / "project"
        self.assertNotEqual(proj_a.resolve().parent, proj_b.resolve().parent)

    def test_split_ids_json_pins_train_val_test_to_the_one_task(self):
        import json
        task_ids = ["task-a"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        data = json.loads((proj / "split_ids.json").read_text())
        self.assertEqual(data, {"train": ["task-a"], "val": ["task-a"], "test": ["task-a"]})

    def test_capevolve_yaml_has_required_keys(self):
        import yaml_lite  # local helper defined below, avoids a PyYAML dependency
        task_ids = ["task-a"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        text = (proj / "capevolve.yaml").read_text()
        for key in ("optimizer_skill", "optimizer_model", "algorithm_skill",
                    "target_model", "capabilities", "num_trials", "max_iterations",
                    "stall", "max_usd", "max_optimizer_usd", "stop_at_reward",
                    "split_ids_file"):
            self.assertIn(key, text, f"missing key {key!r} in capevolve.yaml")

    def test_scaffold_is_idempotent(self):
        task_ids = ["task-a"]
        first = scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        second = scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        self.assertEqual(sorted(first), sorted(second))


if __name__ == "__main__":
    unittest.main()
```

This test imports a tiny `yaml_lite` helper — since the plan has no PyYAML
dependency, write it as a 4-line substring-presence checker rather than a
real parser:

```python
# scripts/v4_t2_e1/tests/yaml_lite.py
"""Just enough to assert a key is present in a hand-written YAML file in
tests, without adding a PyYAML dependency this plan otherwise has no use
for."""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/v4_t2_e1/tests/test_scaffold_projects.py -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'scaffold_projects'`.

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Scaffold the 21 per-task cap-evolve projects for v4_t2_e1.

Layout (see the plan's deviation 1 for why it's nested one level deeper than
the original design doc):

    .capevolve/
      v4_t2_e1_common/
        adapters  -> ../../scripts/v4_t2_e1/common/adapters   (symlink)
        optimizer -> ../../scripts/v4_t2_e1/common/optimizer  (symlink)
      v4_t2_e1_<task-id>/
        project/
          seed_capability/*.md   (8 files, real copies — a frozen snapshot)
          capevolve.yaml
          split_ids.json
          adapters  -> ../../v4_t2_e1_common/adapters   (symlink)
          optimizer -> ../../v4_t2_e1_common/optimizer  (symlink)

Each task's project/ is its own unique directory, so cap-evolve run's
run_<timestamp>/ (created under project/'s PARENT) never collides with
another task's.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPEVOLVE_DIR = REPO_ROOT / ".capevolve"
COMMON_ADAPTERS_SRC = Path(__file__).resolve().parent / "common" / "adapters"
COMMON_OPTIMIZER_SRC = Path(__file__).resolve().parent / "common" / "optimizer"

PARSEC_V4N = Path("/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16")
PROMPTS_DIR = PARSEC_V4N / "_run" / "parsec-live" / "config" / "prompts"

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

TASK_IDS = [
    "cloud-024-guid-to-account",
    "cloud-026-gpu-abuse-triage",
    "cost-029-no-cost-rows-for-guid",
    "cost-030-threshold-not-an-anomaly",
    "icinga-010-stuck-anarchysubjects",
    "icinga-011-aap2-job-status-alert",
    "icinga-013-acknowledged-not-an-issue",
    "icinga-014-check-script-path-moved",
    "platform-001-ee-entrypoint-rca",
    "platform-002-collection-not-found-rca",
    "platform-003-tojson-dict-literal-rca",
    "platform-004-events-then-config",
    "platform-005-wrong-owner-trap",
    "platform-007-directory-path-fetch",
    "platform-008-log-does-not-say",
    "platform-022-job-on-no-controller",
    "platform-023-splunk-guid-no-events",
    "platform-031-helm-url-not-a-timeout",
    "platform-032-shared-secret-not-a-registry-outage",
    "platform-033-schema-change-not-the-oom",
    "platform-034-rate-limit-not-an-outage",
]


def render_capevolve_yaml(task_id: str) -> str:
    return f"""\
# v4_t2_e1 — single-task optimization project for {task_id}.
# See docs/superpowers/plans/2026-09-17-parsec-v4-task-by-task-optimization.md
optimizer_skill: claude-code
optimizer_model: claude-opus-5
algorithm_skill: hill-climb
target_model: claude-sonnet-4-6
capabilities: [system-prompt]
split_ids_file: split_ids.json
num_trials: 5
max_iterations: 3
stall: 2
max_usd: 50.0
max_optimizer_usd: 20.0
stop_at_reward: 1.0
"""


def render_split_ids(task_id: str) -> str:
    return (
        "{\n"
        f'  "train": ["{task_id}"],\n'
        f'  "val":   ["{task_id}"],\n'
        f'  "test":  ["{task_id}"]\n'
        "}\n"
    )


def _ensure_symlink(link: Path, target: Path) -> Path:
    """Create ``link`` -> relative(``target``) if missing; verify it if present."""
    link.parent.mkdir(parents=True, exist_ok=True)
    rel_target = Path(
        __import__("os").path.relpath(target, start=link.parent)
    )
    if link.is_symlink() or link.exists():
        if link.resolve() != target.resolve():
            raise RuntimeError(
                f"{link} already exists and does not point at {target} "
                f"(points at {link.resolve()})"
            )
        return link
    link.symlink_to(rel_target, target_is_directory=True)
    return link


def scaffold_all(
    capevolve_dir: Path,
    *,
    prompts_dir: Path = PROMPTS_DIR,
    task_ids: list[str] | None = None,
    common_adapters_src: Path = COMMON_ADAPTERS_SRC,
    common_optimizer_src: Path = COMMON_OPTIMIZER_SRC,
) -> list[Path]:
    task_ids = list(task_ids) if task_ids is not None else list(TASK_IDS)
    created: list[Path] = []

    common_dir = capevolve_dir / "v4_t2_e1_common"
    created.append(_ensure_symlink(common_dir / "adapters", common_adapters_src))
    created.append(_ensure_symlink(common_dir / "optimizer", common_optimizer_src))

    for task_id in task_ids:
        proj = capevolve_dir / f"v4_t2_e1_{task_id}" / "project"
        seed_dir = proj / "seed_capability"
        seed_dir.mkdir(parents=True, exist_ok=True)
        for name in PROMPT_FILES:
            src = prompts_dir / name
            dst = seed_dir / name
            shutil.copyfile(src, dst)
            created.append(dst)

        yaml_path = proj / "capevolve.yaml"
        yaml_path.write_text(render_capevolve_yaml(task_id), encoding="utf-8")
        created.append(yaml_path)

        split_path = proj / "split_ids.json"
        split_path.write_text(render_split_ids(task_id), encoding="utf-8")
        created.append(split_path)

        created.append(_ensure_symlink(proj / "adapters", common_dir / "adapters"))
        created.append(_ensure_symlink(proj / "optimizer", common_dir / "optimizer"))

    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="print what would be created, write nothing")
    parser.add_argument("--only", action="append", default=None,
                         help="scaffold only this task id (repeatable)")
    args = parser.parse_args()

    task_ids = args.only if args.only else TASK_IDS
    unknown = [t for t in task_ids if t not in TASK_IDS]
    if unknown:
        print(f"unknown task id(s): {unknown}", file=sys.stderr)
        return 1

    if args.dry_run:
        for task_id in task_ids:
            print(f"would scaffold {CAPEVOLVE_DIR / f'v4_t2_e1_{task_id}' / 'project'}")
        return 0

    if not PROMPTS_DIR.exists():
        print(f"prompts dir not found: {PROMPTS_DIR}", file=sys.stderr)
        return 1

    paths = scaffold_all(CAPEVOLVE_DIR, task_ids=task_ids)
    print(f"scaffolded {len(task_ids)} task project(s), {len(paths)} paths touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/v4_t2_e1/tests/test_scaffold_projects.py -v`
Expected: all 7 tests PASS. (The `yaml_lite` import in the test file is a
placeholder module reference — replace it inline with a plain substring
`assertIn` against the raw YAML text, as written in
`test_capevolve_yaml_has_required_keys` above; delete the unused import.)

- [ ] **Step 5: Dry-run against the real prompts dir**

Run: `python3 scripts/v4_t2_e1/scaffold_projects.py --dry-run`
Expected: 21 lines, one per task, each naming a
`.capevolve/v4_t2_e1_<task-id>/project` path under this worktree.

- [ ] **Step 6: Scaffold for real**

Run: `python3 scripts/v4_t2_e1/scaffold_projects.py`
Expected: `scaffolded 21 task project(s), <N> paths touched.` — this will
partially fail at this point in the plan, because
`scripts/v4_t2_e1/common/{adapters,optimizer}` (Tasks 3 and 4) don't exist
yet, so `_ensure_symlink` for the common dir will raise. **Re-run this step
after Task 4** instead of expecting it to fully succeed here; running it now
is only to catch scaffolding bugs unrelated to the missing common/ source
(seed file copies, yaml/json rendering).

- [ ] **Step 7: Commit**

```bash
git add scripts/v4_t2_e1/scaffold_projects.py scripts/v4_t2_e1/tests/test_scaffold_projects.py
git commit -m "$(cat <<'EOF'
feat(v4_t2_e1): scaffold the 21 per-task cap-evolve projects

Nested layout (.capevolve/v4_t2_e1_<task-id>/project/) gives each task a
unique run-dir parent, avoiding the run_*/ collision the original design
doc's flatter layout would have hit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Harbor adapter

The shared adapter every one of the 21 projects' `project/adapters ->` symlink
chain resolves to. Reads which task it's running from the `TASK_ID`
environment variable (set by Task 5's runner immediately before each
`cap-evolve run` invocation), runs that one Harbor trial (replicating
`run_full34.py`'s subprocess/env pattern exactly), and delivers candidates by
overwriting `config/prompts/*.md` in the live `parsec-live` clone.

**Files:**
- Create: `scripts/v4_t2_e1/common/adapters/adapter.py`
- Test: `scripts/v4_t2_e1/tests/test_adapter.py`

**Interfaces:**
- Consumes: `capevolve_harbor.results.parse_job_dir(job_dir) ->
  dict[str, list[TrialResult]]` and `capevolve_harbor.results.TrialResult`
  (fields: `task_id`, `reward`, `error`, `feedback` among others — the real,
  already-installed `capevolve_harbor` package). `from cap_evolve import
  CapabilityAdapter, Rollout, Score, Task` (the installed `cap_evolve`
  package this adapter runs inside of, once Task 1's pre-flight fix is
  applied).
- Produces: `class Adapter(CapabilityAdapter)` — the name `load_adapter()`
  requires (`core/cap_evolve/check.py`).

- [ ] **Step 1: Write the failing test**

```python
# scripts/v4_t2_e1/tests/test_adapter.py
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common" / "adapters"))

import adapter as adapter_mod  # noqa: E402


REAL_TASKS_DIR = Path("/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/tasks")
KNOWN_TASK_ID = "icinga-011-aap2-job-status-alert"  # one of the 21; real dir on disk


class TestAdapterTaskResolution(unittest.TestCase):
    def test_raises_clearly_when_task_id_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                adapter_mod.Adapter()
            self.assertIn("TASK_ID", str(ctx.exception))

    def test_raises_clearly_when_task_dir_missing(self):
        with patch.dict(os.environ, {"TASK_ID": "not-a-real-task-xyz"}, clear=True):
            with self.assertRaises(FileNotFoundError):
                adapter_mod.Adapter()

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_tasks_returns_the_one_pinned_task(self):
        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            tasks = a.tasks("val")
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].id, KNOWN_TASK_ID)
            task_dir = Path(tasks[0].metadata["task_dir"])
            self.assertTrue(task_dir.exists())
            self.assertEqual(task_dir.name, f"bench-v4-{KNOWN_TASK_ID}")
            # split argument is ignored on purpose — train == val == test == this task
            self.assertEqual(a.tasks("train"), tasks)
            self.assertEqual(a.tasks("test"), tasks)


class TestAdapterApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.live_prompts_dir = Path(self.tmp.name) / "live_prompts"
        self.live_prompts_dir.mkdir()
        for name in adapter_mod.PROMPT_FILES:
            (self.live_prompts_dir / name).write_text(f"seed {name}\n")
        self.env_patch = patch.dict(
            os.environ,
            {"TASK_ID": KNOWN_TASK_ID, "PARSEC_LIVE_PROMPTS_DIR": str(self.live_prompts_dir)},
            clear=True,
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.tmp.cleanup()

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_apply_copies_candidate_files_into_live_prompts_dir(self):
        a = adapter_mod.Adapter()
        with tempfile.TemporaryDirectory() as cand_dir_s:
            cand_dir = Path(cand_dir_s)
            (cand_dir / "orchestrator.md").write_text("MUTATED orchestrator\n")
            a.apply(cand_dir)
            self.assertEqual(
                (self.live_prompts_dir / "orchestrator.md").read_text(),
                "MUTATED orchestrator\n",
            )
            # a file the candidate didn't touch is left alone
            self.assertEqual(
                (self.live_prompts_dir / "shared_context.md").read_text(),
                "seed shared_context.md\n",
            )


class TestAdapterScore(unittest.TestCase):
    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_score_is_zero_on_rollout_error(self):
        from cap_evolve import Rollout
        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            task = a.tasks("val")[0]
            rollout = Rollout(task_id=task.id, error="timeout after 1200s")
            score = a.score(task, rollout)
            self.assertEqual(score.reward, 0.0)
            self.assertIn("timeout", score.feedback)

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_score_reads_reward_from_trial_result(self):
        from cap_evolve import Rollout
        from capevolve_harbor.results import TrialResult
        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            task = a.tasks("val")[0]
            tr = TrialResult(task_id=task.id, reward=0.83)
            rollout = Rollout(task_id=task.id, metadata={"trial_result": tr.__dict__})
            score = a.score(task, rollout)
            self.assertEqual(score.reward, 0.83)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/v4_t2_e1/tests/test_adapter.py -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'adapter'`
(the file doesn't exist yet). Some tests will `SKIP` if
`/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/tasks` is not
present on the machine running the test — that's expected on a machine
without the rhdp-parsec checkout; the import-time and TASK_ID-validation
tests still run everywhere.

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Harbor adapter for v4_t2_e1 — single-task, system-prompt-only cap-evolve
optimization of parsec v4.

Shared by all 21 per-task projects via a symlink chain
(project/adapters -> .capevolve/v4_t2_e1_common/adapters -> this file's own
directory). Since load_adapter() (core/cap_evolve/check.py) instantiates
Adapter() with zero constructor arguments, this adapter reads a required
TASK_ID environment variable — set by scripts/v4_t2_e1/run_one_task.py
immediately before each `cap-evolve run` invocation — to know which of the
21 tasks it is running.

Candidate delivery: system_prompt.py's get_agent_prompt() re-reads
config/prompts/*.md from disk on every request, keyed by mtime (see the
design doc) — so apply() just overwrites those files in the live
parsec-live clone. No process restart, no Harbor injection flag needed.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# This file is reached through a chain of symlinks (project/adapters ->
# v4_t2_e1_common/adapters -> scripts/v4_t2_e1/common/adapters). .resolve()
# fully follows every hop, landing on the real physical path regardless —
# so this always finds the actual repo root, not wherever the caller's
# --project happened to point.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from capevolve_harbor.results import parse_job_dir  # noqa: E402
from cap_evolve import CapabilityAdapter, Rollout, Score, Task  # noqa: E402

V4N = Path(os.environ.get("PARSEC_V4N", "/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16"))
TASKS_DIR = V4N / "_run" / "tasks"
JOBS_ROOT = V4N / "_run" / "jobs" / "v4_t2_e1"
LIVE_PROMPTS_DIR = Path(
    os.environ.get("PARSEC_LIVE_PROMPTS_DIR", str(V4N / "_run" / "parsec-live" / "config" / "prompts"))
)
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

MCP_PORTS = {
    "PLATFORM_MCP_URL": 8086,
    "GITHUB_MCP_URL": 8087,
    "ICINGA_MCP_URL": 8088,
    "COST_MCP_URL": 8089,
    "CLOUD_MCP_URL": 8090,
}


def _resolve_docker_host() -> str:
    out = subprocess.run(
        ["podman", "machine", "inspect", "podman-machine-default"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    data = json.loads(out.stdout)
    path = data[0]["ConnectionInfo"]["PodmanSocket"]["Path"]
    return f"unix://{path}"


class Adapter(CapabilityAdapter):
    def __init__(self) -> None:
        task_id = os.environ.get("TASK_ID", "").strip()
        if not task_id:
            raise RuntimeError(
                "TASK_ID environment variable is required — this adapter is shared by "
                "all 21 v4_t2_e1 projects via a symlink and has no other way to know "
                "which task it is running. Set it before invoking `cap-evolve run`."
            )
        task_dir = TASKS_DIR / f"bench-v4-{task_id}"
        if not task_dir.exists():
            raise FileNotFoundError(f"no such bench-v4 task directory: {task_dir}")
        self.task_id = task_id
        self.task_dir = task_dir

    # ------------------------------------------------------------------
    # tasks() ignores the split argument: train == val == test == the one
    # task pinned via split_ids.json (see Task 2's capevolve.yaml).
    # ------------------------------------------------------------------
    def tasks(self, split: str) -> list[Task]:
        return [Task(id=self.task_id, metadata={"task_dir": str(self.task_dir)})]

    # ------------------------------------------------------------------
    # Candidate delivery: overwrite whichever *.md files the candidate
    # snapshot contains. The framework always hands apply() a FULL
    # directory snapshot (harness.py's run_dir.snapshot("seed", seed_dir)
    # copies the whole seed_capability tree as the run's first candidate),
    # so there is no partial-edit case to special-case here.
    # ------------------------------------------------------------------
    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        for name in PROMPT_FILES:
            src = Path(candidate_dir) / name
            if src.exists():
                (LIVE_PROMPTS_DIR / name).write_text(
                    src.read_text(encoding="utf-8"), encoding="utf-8"
                )

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        task_dir = task.metadata["task_dir"]
        trial_dir = JOBS_ROOT / self.task_id / f"seed-{seed}" / str(int(time.time() * 1000))
        trial_dir.mkdir(parents=True, exist_ok=True)

        try:
            docker_host = _resolve_docker_host()
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, KeyError, IndexError) as exc:
            return Rollout(task_id=task.id, error=f"could not resolve docker host: {exc}")

        cfg_path = trial_dir / "harbor_config.json"
        cfg = {
            "jobs_dir": str(trial_dir),
            "agents": [{"name": "parsec_harbor_agent:ParsecAgent"}],
            "tasks": [{"path": task_dir}],
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        env = dict(os.environ)
        env["PYTHONPATH"] = "."
        env["PARSEC_URL"] = "http://127.0.0.1:8000"
        env["PARSEC_SIM_TRACE"] = str(V4N / "_run" / "logs" / "parsec-trace" / "trace.jsonl")
        env["DOCKER_HOST"] = docker_host
        for var, port in MCP_PORTS.items():
            env[var] = f"http://localhost:{port}/mcp/sse"

        log_path = trial_dir / "harbor_run.log"
        try:
            with open(log_path, "w", encoding="utf-8") as logf:
                proc = subprocess.run(
                    ["harbor", "run", "--config", str(cfg_path), "--n-concurrent", "1"],
                    cwd=str(V4N), env=env, stdout=logf, stderr=subprocess.STDOUT,
                    timeout=TRIAL_TIMEOUT_SEC,
                )
        except subprocess.TimeoutExpired:
            return Rollout(task_id=task.id, error=f"harbor run timed out after {TRIAL_TIMEOUT_SEC}s",
                           metadata={"trial_dir": str(trial_dir)})

        if proc.returncode != 0:
            return Rollout(task_id=task.id, error=f"harbor run exited {proc.returncode}",
                           metadata={"trial_dir": str(trial_dir)})

        results = parse_job_dir(trial_dir)
        if not results:
            return Rollout(task_id=task.id, error="harbor produced no parseable result",
                           metadata={"trial_dir": str(trial_dir)})
        trial_result = next(iter(results.values()))[0]

        return Rollout(
            task_id=task.id,
            output=trial_result.feedback,
            metadata={"trial_dir": str(trial_dir), "trial_result": trial_result.__dict__},
        )

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
            return Score(task_id=task.id, reward=0.0, feedback=rollout.error, n=1)
        tr = (rollout.metadata or {}).get("trial_result") or {}
        reward = float(tr.get("reward") or 0.0)
        feedback = str(tr.get("feedback") or "")
        return Score(task_id=task.id, reward=reward, feedback=feedback, n=1)

    def trajectories(self, split: str, ctx=None) -> Path | None:
        candidates = sorted(glob.glob(str(JOBS_ROOT / self.task_id / "**" / "agent"), recursive=True))
        return Path(candidates[-1]) if candidates else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/v4_t2_e1/tests/test_adapter.py -v`
Expected: all tests PASS (or SKIP for the real-tasks-dir-dependent ones, if
run on a machine without the `rhdp-parsec` checkout).

- [ ] **Step 5: Commit**

```bash
git add scripts/v4_t2_e1/common/adapters/adapter.py scripts/v4_t2_e1/tests/test_adapter.py
git commit -m "$(cat <<'EOF'
feat(v4_t2_e1): harbor adapter for single-task system-prompt optimization

Reads TASK_ID from the environment (shared/symlinked across all 21
per-task projects), replicates run_full34.py's harbor invocation for one
task/seed, and delivers candidates by overwriting the live parsec-live
clone's config/prompts/*.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Optimizer INSTRUCTIONS.md

The optimizer-facing instructions template, adapted from
`parsec-intake_v1/.capevolve/project/optimizer/INSTRUCTIONS.md` for a
prompt-only (no tools/code editing), single-task scope.

**Files:**
- Create: `scripts/v4_t2_e1/common/optimizer/INSTRUCTIONS.md`

**Interfaces:**
- Consumes: nothing (a template file, not code).
- Produces: the file `core/cap_evolve/specfile.py`'s
  `resolve_instructions_file()` finds by its documented default,
  `optimizer/INSTRUCTIONS.md` — resolved project-relative, i.e. via the
  `project/optimizer` symlink chain Task 2 built. No
  `optimizer_instructions_file:` key is needed in `capevolve.yaml` because
  this filename **is** the default.

Placeholder tokens used by `run-optimizer`/hill-climb to fill this template
per-iteration (the same live set v1's INSTRUCTIONS.md uses):
`{{TARGET_READER}}`, `{{FOCUS_SUMMARY}}`, `{{EMPTY_SEED}}`, `{{FAILURES}}`,
`{{PASSING}}`, `{{CAP_BRIEF}}`, `{{ALGO_BRIEF}}`, `{{BENCH_REPO}}`,
`{{PARALLEL_NOTE}}`.

- [ ] **Step 1: Write the file**

```markdown
# Optimizing parsec v4's system prompts for one task

You are optimizing {{TARGET_READER}}. {{FOCUS_SUMMARY}}

{{EMPTY_SEED}}

## What you can edit

The capability is **`system-prompt`** — plain-text edits to the 8 files under
this project's candidate directory:

- `orchestrator.md` — routes every request to one of 6 domain agents below.
- `shared_context.md` — prepended to every domain agent's prompt (not the
  orchestrator's).
- `aap2_agent.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
  `ocpv_agent.md`, `security_agent.md` — one per domain.

There is **no tools/code layer** in this phase — you cannot add, remove, or
edit any Python tool. Every lever available to you is a change to what these
files *say*. If a failure looks like it needs a new tool or a code-level
guard, the honest fix within this phase's scope is a prose rule that gets the
agent to use its *existing* tools correctly (a missing capability that
genuinely requires new code is a real finding — write it into your
handover notes as an escalation, not something to fake with prose).

## The task you're optimizing for

This project's `train`, `val`, and `test` splits are all the *same single
task* (see `split_ids.json`) — there is no cross-task generalization question
this round. Every rollout you see is a different trial of that one task.
Your only question: **what does this one task's transcript show the agent
getting wrong, and which of the 8 files is the right place to fix it?**

Cross-reference the task's `task.toml` `services=[...]` against
`orchestrator.md`'s own routing text to find your task's actual prompt
footprint — almost always `orchestrator.md` + `shared_context.md` + one
domain file, occasionally two for cross-domain tasks.

## Choose the lever by failure type

- **Missing knowledge** (the agent didn't know a fact/convention it needed) →
  add a concrete prose rule to the file that should have carried it. Prefer
  the most specific file that's actually read for this task's domain over
  `shared_context.md` — only put a rule in `shared_context.md` if it is
  genuinely domain-general.
- **Wrong routing** (orchestrator sent the request to the wrong domain agent,
  or didn't route a cross-domain request to both) → tighten
  `orchestrator.md`'s routing rule with a *discriminating* condition (what
  distinguishes this case from the ones already routed correctly) — never
  a blanket "always route X to Y" that would misroute a case you haven't
  seen.
- **Right domain, wrong action** (agent reached the right sub-agent but chose
  the wrong tool call, wrong parameters, or stopped too early) → add a
  worked example or an explicit decision rule to that domain agent's file,
  anchored to the specific ambiguity that tripped it up.
- **Overcautious or overconfident** (agent asked for confirmation it didn't
  need, or asserted something it hadn't verified) → narrow the relevant
  rule with an explicit condition for *when* caution/confidence is
  warranted — never loosen a rule globally to fix one instance.

## Non-overfitting (read this before every edit)

Never hardcode this task's specific GUID, hostname, ticket number, or any
other instance-specific value into a prompt file. A rule that only works
because it names *this exact case* is not a fix — score gains for the
wrong reason don't survive a re-run with a different seed, let alone a
different task. Every rule you add must describe a *pattern* the next
similar case would also match.

## Verify the fix

Before finalizing a candidate: re-read the specific rollout(s) that failed
and check your edited text actually would have changed the agent's behavior
at the exact point it went wrong — not just that it's *plausible* it might
help. If it wouldn't have changed anything at that point, it isn't a fix,
even if it reads like good advice.

## Handover

At the end of your work on this candidate, write:

- `PROCESS.md` — what you tried, in the order you tried it, and why. A
  future reader (human or another optimizer run) should be able to follow
  your reasoning without re-deriving it from the diff alone.
- `JOURNAL.md` — append-only. One entry per iteration: what changed, what
  you expected it to fix, whether it did. Never rewrite a past entry —
  append a correction instead if you were wrong.

## Context for this run

{{BENCH_REPO}}

{{PARALLEL_NOTE}}

---

**Failing rollouts (what to fix):**

{{FAILURES}}

**Passing rollouts (what NOT to break):**

{{PASSING}}

**Capability brief:**

{{CAP_BRIEF}}

**Algorithm brief:**

{{ALGO_BRIEF}}
```

- [ ] **Step 2: Verify the placeholder set matches what hill-climb actually fills**

Run: `grep -o '{{[A-Z_]*}}' scripts/v4_t2_e1/common/optimizer/INSTRUCTIONS.md | sort -u`
Expected output (9 lines): `{{ALGO_BRIEF}}`, `{{BENCH_REPO}}`,
`{{CAP_BRIEF}}`, `{{EMPTY_SEED}}`, `{{FAILURES}}`, `{{FOCUS_SUMMARY}}`,
`{{PARALLEL_NOTE}}`, `{{PASSING}}`, `{{TARGET_READER}}` — cross-check this
list against `parsec-intake_v1/.capevolve/project/optimizer/INSTRUCTIONS.md`'s
own placeholder set (`grep -o '{{[A-Z_]*}}' <that file> | sort -u`); the two
lists must be identical, since these tokens are filled by the shared
hill-climb/run-optimizer machinery, not anything project-specific.

- [ ] **Step 3: Re-run Task 2's scaffolding now that common/ exists**

Run: `python3 scripts/v4_t2_e1/scaffold_projects.py`
Expected: `scaffolded 21 task project(s), <N> paths touched.` with no errors
this time — every `project/optimizer/INSTRUCTIONS.md` symlink chain now
resolves to this real file.

- [ ] **Step 4: Commit**

```bash
git add scripts/v4_t2_e1/common/optimizer/INSTRUCTIONS.md
git commit -m "$(cat <<'EOF'
feat(v4_t2_e1): optimizer INSTRUCTIONS.md for single-task prompt-only edits

Adapted from parsec-intake_v1's INSTRUCTIONS.md: drops every tools/code
lever (this phase's capability is system-prompt only) and reframes the
per-task/multi-cluster ranking language for a single pinned task.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Single-task runner

The standalone process the user asked for: one invocation runs exactly one
task's `cap-evolve run` to completion (or failure) as a foreground child
process, then exits — no internal loop over the 21 tasks. Repetition across
tasks is an external concern (a `while` loop on the command line, a cron
entry, a launchd job — documented below, not built into this script).

**Files:**
- Create: `scripts/v4_t2_e1/run_one_task.py`
- Test: `scripts/v4_t2_e1/tests/test_run_one_task.py`

**Interfaces:**
- Consumes: `scaffold_projects.TASK_IDS` (Task 2, for default ordering),
  `preflight_check.installed_cli_supports_stop_at_reward()` (Task 1).
- Produces: `resolve_next_task_id(capevolve_dir: Path, task_ids: list[str]) ->
  str | None` (the next task with no `run_*/final.json` yet, in `task_ids`
  order, or `None` if all 21 are done), `run_task(task_id: str, *,
  capevolve_dir: Path = CAPEVOLVE_DIR, repo_root: Path = REPO_ROOT) -> int`
  (the child's exit code), `main() -> int`.

- [ ] **Step 1: Write the failing test**

```python
# scripts/v4_t2_e1/tests/test_run_one_task.py
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_one_task  # noqa: E402


class TestResolveNextTaskId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.capevolve_dir = Path(self.tmp.name) / ".capevolve"
        self.capevolve_dir.mkdir()
        self.task_ids = ["task-a", "task-b", "task-c"]

    def tearDown(self):
        self.tmp.cleanup()

    def _mark_done(self, task_id: str, run_ts: str = "20260101_000000") -> None:
        run_dir = self.capevolve_dir / f"v4_t2_e1_{task_id}" / f"run_{run_ts}"
        run_dir.mkdir(parents=True)
        (run_dir / "final.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    def test_returns_first_task_when_none_done(self):
        self.assertEqual(
            run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids),
            "task-a",
        )

    def test_skips_tasks_with_a_final_json(self):
        self._mark_done("task-a")
        self.assertEqual(
            run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids),
            "task-b",
        )

    def test_returns_none_when_all_done(self):
        for t in self.task_ids:
            self._mark_done(t)
        self.assertIsNone(run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids))

    def test_a_run_dir_without_final_json_does_not_count_as_done(self):
        stuck = self.capevolve_dir / "v4_t2_e1_task-a" / "run_20260101_000000"
        stuck.mkdir(parents=True)  # crashed mid-run: no final.json written
        self.assertEqual(
            run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids),
            "task-a",
        )


class TestRunTask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)
        self.capevolve_dir = self.repo_root / ".capevolve"
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        proj.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_invokes_cap_evolve_with_expected_project_and_task_id_env(self):
        captured = {}

        def fake_run(cmd, env=None, cwd=None):
            captured["cmd"] = cmd
            captured["env"] = env
            captured["cwd"] = cwd

            class _Result:
                returncode = 0

            return _Result()

        with patch("subprocess.run", side_effect=fake_run):
            code = run_one_task.run_task(
                "task-a", capevolve_dir=self.capevolve_dir, repo_root=self.repo_root
            )
        self.assertEqual(code, 0)
        self.assertIn("cap-evolve", captured["cmd"])
        self.assertIn("run", captured["cmd"])
        self.assertIn(str(self.capevolve_dir / "v4_t2_e1_task-a" / "project"), captured["cmd"])
        self.assertEqual(captured["env"]["TASK_ID"], "task-a")
        self.assertEqual(captured["cwd"], str(self.repo_root))

    def test_propagates_nonzero_exit_code(self):
        def fake_run(cmd, env=None, cwd=None):
            class _Result:
                returncode = 17

            return _Result()

        with patch("subprocess.run", side_effect=fake_run):
            code = run_one_task.run_task(
                "task-a", capevolve_dir=self.capevolve_dir, repo_root=self.repo_root
            )
        self.assertEqual(code, 17)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/v4_t2_e1/tests/test_run_one_task.py -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'run_one_task'`.

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Run exactly ONE v4_t2_e1 task's cap-evolve optimization to completion, as
a single foreground child process, then exit.

Deliberately NOT a loop over all 21 tasks: each invocation launches one
`cap-evolve run`, waits for it, records the outcome, and stops. This is what
makes a VPN drop, a sleep, or a crash cost at most the one task in flight —
the next invocation (run by hand, or from a trivial external loop) picks up
exactly where this one left off, via resolve_next_task_id().

Usage:
    python3 scripts/v4_t2_e1/run_one_task.py               # next pending task
    python3 scripts/v4_t2_e1/run_one_task.py --task-id X   # a specific task
    python3 scripts/v4_t2_e1/run_one_task.py --follow      # + --follow to cap-evolve run

External repetition (run from the repo root):
    while python3 scripts/v4_t2_e1/run_one_task.py; do :; done

Or, to survive the terminal closing / the machine sleeping less easily:
    caffeinate -i python3 -c '
    import subprocess, sys
    while True:
        rc = subprocess.call(["python3", "scripts/v4_t2_e1/run_one_task.py"])
        if rc != 0:
            sys.exit(rc)
    '
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPEVOLVE_DIR = REPO_ROOT / ".capevolve"
PROGRESS_LOG = CAPEVOLVE_DIR / "v4_t2_e1_progress.log"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preflight_check  # noqa: E402
from scaffold_projects import TASK_IDS  # noqa: E402


def _log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    CAPEVOLVE_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def resolve_next_task_id(capevolve_dir: Path, task_ids: list[str]) -> str | None:
    for task_id in task_ids:
        task_root = capevolve_dir / f"v4_t2_e1_{task_id}"
        if not task_root.exists():
            return task_id
        done = any((run_dir / "final.json").exists() for run_dir in task_root.glob("run_*"))
        if not done:
            return task_id
    return None


def run_task(task_id: str, *, capevolve_dir: Path = CAPEVOLVE_DIR,
             repo_root: Path = REPO_ROOT, follow: bool = False) -> int:
    project = capevolve_dir / f"v4_t2_e1_{task_id}" / "project"
    cmd = ["cap-evolve", "run", "--project", str(project), "--dashboard", "off"]
    if follow:
        cmd.append("--follow")

    import os
    env = dict(os.environ)
    env["TASK_ID"] = task_id

    _log(f"starting {task_id}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env, cwd=str(repo_root))
    _log(f"finished {task_id}: exit={proc.returncode}")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default=None,
                         help="run this specific task id instead of the next pending one")
    parser.add_argument("--follow", action="store_true",
                         help="pass --follow through to `cap-evolve run`")
    args = parser.parse_args()

    if not preflight_check.installed_cli_supports_stop_at_reward():
        _log("ABORT: installed cap-evolve tool is stale — see preflight_check.py output")
        preflight_check.main()
        return 2

    task_id = args.task_id or resolve_next_task_id(CAPEVOLVE_DIR, TASK_IDS)
    if task_id is None:
        _log("ALL_DONE: every v4_t2_e1 task has a final.json")
        return 0
    if task_id not in TASK_IDS:
        _log(f"ABORT: unknown task id {task_id!r}")
        return 2

    return run_task(task_id, follow=args.follow)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/v4_t2_e1/tests/test_run_one_task.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/v4_t2_e1/run_one_task.py scripts/v4_t2_e1/tests/test_run_one_task.py
git commit -m "$(cat <<'EOF'
feat(v4_t2_e1): single-task runner, one standalone process per task

Deliberately not a loop over the 21 tasks: one invocation runs one task's
cap-evolve run to completion and exits, so a VPN drop / sleep / crash costs
at most the task in flight. Re-invoking (by hand or via a trivial external
while-loop) advances to the next pending task.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: End-to-end smoke test

Run the real pipeline against one real task with a reduced budget, and
verify candidate injection actually changes what `parsec-live` serves.

**Files:**
- Modify: none (this is a manual verification task; no new source files).
- Create (scratch, not committed): a temporary budget override is passed on
  the command line, not written into the shared `capevolve.yaml`, so no file
  needs to be reverted afterward.

**Interfaces:**
- Consumes: the real `.capevolve/v4_t2_e1_<task-id>/project/` (Task 2), the
  real adapter (Task 3). Step 3 below invokes `cap-evolve run` directly
  (the same command `run_one_task.run_task()` from Task 5 builds), with two
  extra CLI overrides (`--max-iterations 1 --n-trials 1`) that `run_task()`
  itself has no parameter for — those overrides are for this smoke test
  only, not a gap in Task 5.
- Produces: nothing new — this task's deliverable is a verified, working
  end-to-end run.

- [ ] **Step 1: Confirm the shared stack is up**

Run:
```bash
curl -sf http://127.0.0.1:8000/docs >/dev/null && echo "parsec-live: up"
for p in 8086 8087 8088 8089 8090; do curl -sf "http://127.0.0.1:$p/healthz" >/dev/null && echo "harness $p: up"; done
```
Expected: `parsec-live: up` plus 5 `harness <port>: up` lines. If any are
missing, start the stack the same way `run_full34.py` assumes it's already
started (this plan does not build or touch the startup scripts — see Global
Constraints).

- [ ] **Step 2: Pick one real task and note its current baseline reward**

Choose `icinga-011-aap2-job-status-alert` (already used as the fixture in
Task 3's tests, so its task dir is confirmed to exist). Check its
`v4_t1_e1` baseline from `rhdp-parsec/v4_2026-09-16/_run/jobs/full34/progress.csv`
(should show a 3-trial average below 1.0, since it's one of the 21).

- [ ] **Step 3: Run it with a reduced budget, in the foreground, with `--follow`**

Run:
```bash
cd /Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4
TASK_ID=icinga-011-aap2-job-status-alert cap-evolve run \
  --project .capevolve/v4_t2_e1_icinga-011-aap2-job-status-alert/project \
  --max-iterations 1 --n-trials 1 --dashboard off --follow
```
(This overrides the yaml's `max_iterations: 3`/`num_trials: 5` for the smoke
test only — CLI flags win over the spec, per `_cmd_run`'s `spec.get(...)`
calls only supplying *defaults* for flags argparse doesn't already have from
the command line.)

Expected: the run reaches the algorithm phase (baseline eval, then one
hill-climb iteration) without a Python traceback. Watch the follower output
for the baseline eval starting a `harbor run` — confirms the adapter's
`run_target()` actually launched.

- [ ] **Step 4: Verify a `final.json` was produced**

Run: `find .capevolve/v4_t2_e1_icinga-011-aap2-job-status-alert -name final.json`
Expected: one path, under
`.capevolve/v4_t2_e1_icinga-011-aap2-job-status-alert/run_<timestamp>/final.json`
— confirms the run-dir landed at the corrected nested location (deviation 1),
not colliding with any other task.

- [ ] **Step 5: Verify candidate injection actually changed the served prompt**

While the run is between iterations (or immediately after, before another
process overwrites it), run:
```bash
diff \
  /Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/parsec-live/config/prompts/orchestrator.md \
  .capevolve/v4_t2_e1_icinga-011-aap2-job-status-alert/project/seed_capability/orchestrator.md
```
Expected: if the optimizer proposed and accepted any change touching
`orchestrator.md`, this `diff` is non-empty — the live file differs from the
frozen seed snapshot, proving `apply()` really overwrote the live clone (not
just some other copy). If the optimizer made no accepted change to this
particular file this run, repeat the check against whichever file its
journal says it edited (`run_<timestamp>/candidates/<id>/` holds the
accepted candidate's own copy for comparison).

- [ ] **Step 6: Revert the live clone back to the seed**

Run:
```bash
cd /Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/parsec-live
git checkout -- config/prompts/
```
Expected: `git status` in that clone shows `config/prompts/` clean again —
per the design doc, this clone is git-clean on these files outside of an
active candidate, so this is always safe.

- [ ] **Step 7: Report the smoke-test result**

No commit for this task (nothing new is added to git — Steps 1-6 only
exercise already-committed code against the real stack). Summarize for the
user: did the run complete, was `final.json` valid, did injection provably
change the live file, and what reward the one smoke-test iteration reached
versus the task's `v4_t1_e1` baseline.
