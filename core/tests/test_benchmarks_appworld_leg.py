"""The `appworld` leg of the benchmark CI: ci_setup.sh provisions it, run_suite.sh scaffolds it.

No AppWorld install and no model call. ``run_suite.sh appworld`` is driven for real: a stub
stands in for ``$PY``. Python heredocs and scripts run on the real interpreter, but every
``-m cap_evolve.cli`` call (``check``, ``run``) is only recorded, so nothing reaches a model and
the generated project, spec and secrets file can be inspected as the runner would see them.
"""

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"
EX = REPO / "examples" / "appworld"
WORKFLOW = REPO / ".github" / "workflows" / "integration-tests.yml"

STUB = """#!/usr/bin/env bash
# Stand-in for $PY. Python heredocs and scripts run on the real interpreter; the cap-evolve CLI
# does not: each call is recorded and fails, so nothing reaches a model.
if [ "$1" = "-m" ] && [ "$2" = "cap_evolve.cli" ]; then
  echo "$*" >> "$CALLS"
  exit 97
fi
case "$1" in */metrics.py) exit 1 ;; esac
exec "$REAL_PY" "$@"
"""


def _run_suite(tmp_path: Path, **env_extra) -> tuple[subprocess.CompletedProcess, Path]:
    stub = tmp_path / "py"
    stub.write_text(STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    aw_eval = tmp_path / "aw_eval"
    (aw_eval / "reference").mkdir(parents=True)
    (aw_eval / "lint_cache.json").write_text("{}")
    out = tmp_path / "out"
    env = {
        "PATH": os.environ["PATH"], "HOME": str(tmp_path), "CALLS": str(tmp_path / "calls"),
        "REAL_PY": sys.executable, "CAPEVOLVE_PY": str(stub), "TIER": "integration",
        "AW_EVAL": str(aw_eval), "AGENT_MODEL": "gpt-oss-120b-a100", "OPTIMIZER_MODEL": "claude-opus-4-8",
        "IBM_RITS_API_BASE": "http://lite-rits.invalid:4000", "IBM_RITS_API_KEY": "rits-secret-key",
        "IBM_ETE_INT_API_BASE": "http://ete.invalid", "IBM_ETE_INT_API_KEY": "ete-secret-key",
        "ITERATIONS": "1", "NUM_TRIALS": "1",
        **env_extra,
    }
    proc = subprocess.run(["bash", str(LIB / "run_suite.sh"), "appworld", str(out)], cwd=str(REPO),
                          env=env, capture_output=True, text=True, timeout=120)
    return proc, REPO / "ci" / "benchmarks" / ".work" / "suite_integration_appworld_proj"


@pytest.fixture
def suite(tmp_path):
    proc, work = _run_suite(tmp_path)
    yield proc, work, tmp_path
    import shutil
    shutil.rmtree(work, ignore_errors=True)


def test_tier_is_the_examples_itest_task():
    tasks = json.loads((REPO / "ci/benchmarks/appworld/integration/tasks.json").read_text())
    split = json.loads((EX / "itest_split.json").read_text())
    assert [t["id"] for t in tasks] == split["val"] == ["82e2fac_1"]


def test_run_suite_reaches_check_with_the_examples_project(suite):
    proc, work, tmp = suite
    calls = (tmp / "calls").read_text().splitlines()
    assert [c.split()[2] for c in calls] == ["check", "run"], proc.stderr[-2000:]
    assert calls[1] == ("-m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml "
                        "--project .capevolve/project --run-ts suite --max-iterations 1")
    proj = work / ".capevolve" / "project"
    for f in ("adapters/adapter.py", "adapters/aw_agent.py", "adapters/lints.py",
              "seed_capability/policy/instructions.txt", "optimizer/INSTRUCTIONS.md"):
        assert (proj / f).is_file(), f
    assert (proj / "adapters/adapter.py").read_bytes() == (EX / "adapters/adapter.py").read_bytes()


def test_spec_matches_the_example(suite):
    proc, work, tmp = suite
    spec = (work / ".capevolve/project/capevolve.yaml").read_text()
    for line in ("capabilities:       [system-prompt, tools]", "actions: [edit]",
                 "capability_sources: [reference/api_index.md, reference/react_agent_notes.md]",
                 f'runner_repo_path: "{tmp}/aw_eval/reference"', "orchestration_mode: deterministic",
                 "memory_skill: md-files", "protected_paths: [default]", "optimizer_skill:    claude-code",
                 "optimizer_model:    claude-opus-4-8", "target_model:       rits/openai/gpt-oss-120b-a100",
                 "max_iterations:     1", "num_trials:         1"):
        assert line in spec, line
    instr = work / ".capevolve/project/optimizer/INSTRUCTIONS.md"
    assert f'optimizer_instructions_file: "{instr}"' in spec
    text = instr.read_text()
    assert "{AW_" not in text and f"AW_LINT_CACHE={tmp}/aw_eval/lint_cache.json" in text


def test_agent_key_is_in_a_private_file_not_the_spec(suite):
    proc, work, tmp = suite
    secrets = work / "aw_secrets.env"
    assert secrets.read_text() == "AW_AGENT_KEY=rits-secret-key\n"
    assert oct(secrets.stat().st_mode & 0o777) == "0o600"
    for f in (work / ".capevolve/project").rglob("*"):
        if f.is_file():
            assert "rits-secret-key" not in f.read_text(errors="ignore"), f
    settings = json.loads((work / ".capevolve/project/sandbox/optimizer-sandbox.json").read_text())
    assert str(secrets) in settings["sandbox"]["filesystem"]["denyRead"]
    assert f"{tmp}/aw_eval/root_opt" in settings["sandbox"]["filesystem"]["denyRead"]


def test_missing_lint_cache_fails_loudly(tmp_path):
    stub_dir = tmp_path
    proc, work = _run_suite(stub_dir, AW_EVAL=str(tmp_path / "empty"))
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    assert proc.returncode != 0
    assert "lint_cache.json missing" in proc.stdout + proc.stderr
    assert not (tmp_path / "calls").exists()


def test_ci_setup_provisions_appworld_like_the_readme():
    src = (LIB / "ci_setup.sh").read_text()
    block = src[src.index("  appworld)\n    # examples/appworld/README.md"):src.index("  tau2)\n")]
    for needle in ("42b5bcf", "git lfs pull", "appworld-extra-headers.patch", "fastapi==0.135.0",
                   "starlette>=0.48", "pydantic>=2.12,<2.13", "appworld\" install --repo", "src/appworld/apps/admin",
                   "download data --root", "make_roots.py", "make_reference.py", "check_injection.py"):
        assert needle in block, needle
    assert re.search(r'^  appworld\)\s+VENV="\$CACHE/appworld/venv-aw" ;;$', src, re.M)
    assert '[ "$BENCH" = appworld ] && VENV_PY_VERSION=3.11' in src
    assert 'echo "AW_EVAL=$AW_EVAL"' in src


def test_integration_workflow_offers_appworld():
    wf = WORKFLOW.read_text()
    assert "options: [tau2, tau2_sierra, tau2_sierra_blackbox, appworld]" in wf
    assert "examples/appworld/scripts/assert_itest.py \"$run_dir\"" in wf
    assert "(github.event.inputs.bench || 'tau2') == 'appworld' && 'gpt-oss-120b-a100'" in wf


def test_agent_model_routes_through_the_gateway_with_a_bearer_key():
    src = (LIB / "run_suite.sh").read_text()
    block = src[src.index("  appworld)\n"):src.index("  tau2_sierra|tau2_sierra_blackbox)\n")]
    assert 'AW_MODEL_NAME="litellm_proxy/$AGENT_MODEL_WIRE"' in block
    assert 'AW_MODEL_URL="$AGENT_API_BASE"' in block
    assert "AW_KEY_HEADER=bearer" in block
