"""split_mode: pooled must take effect in the BASELINE phase on every entry path: ``cap-evolve run`` (whose
run_config event is logged only after the baseline) and a direct call of the baseline script with --spec.
A baseline that silently takes the legacy path evaluates the seed on the whole val split, C included, and
leaves its traces where the proposer can read them."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "benchmarks" / "toy" / "examples" / "calc"
TEMPLATE_SPEC = REPO / "benchmarks" / "_scaffold" / "project" / "capevolve.yaml"
sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    os.environ.pop("CAPEVOLVE_SPLIT_MODE", None)
    yield
    os.environ.clear()
    os.environ.update(old)


def _project(tmp_path):
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")
    text = TEMPLATE_SPEC.read_text(encoding="utf-8").replace(
        "orchestration_mode: deterministic", "orchestration_mode: agent")
    text += "\nsplit_mode: pooled\nfault_attribution: true\nerrored_trial_policy: fail\nbudget_reserve: true\n"
    spec = project / "capevolve.yaml"
    spec.write_text(text, encoding="utf-8")
    return project, spec


def _events(run_dir):
    return [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]


def _leaks(root, ids):
    pats = [re.compile(r"(?<![A-Za-z0-9_])" + re.escape(t) + r"(?![A-Za-z0-9_])") for t in ids]
    bad = []
    for dp, dn, files in os.walk(root, followlinks=True):
        for n in list(dn) + files:
            if any(p.search(n) for p in pats):
                bad.append(os.path.join(dp, n))
        for n in files:
            try:
                t = Path(dp, n).read_text(errors="ignore")
            except OSError:
                continue
            if any(p.search(t) for p in pats):
                bad.append(os.path.join(dp, n))
    return bad


def _assert_pooled(run_dir: Path):
    kinds = [e["kind"] for e in _events(run_dir)]
    assert "pooled_split" in kinds, kinds
    assert kinds.index("pooled_split") < kinds.index("eval_start"), "the partition must precede the first eval"
    from cap_evolve import RunDir
    rd = RunDir.open(run_dir)
    sealed = rd.sealed_dir
    assert sealed is not None and sealed.is_dir() and sealed.name == run_dir.name
    C = rd.read_splits().confirm
    assert C
    on_disk = json.loads((run_dir / "splits.json").read_text())
    assert on_disk["confirm"] == [] and on_disk["train"] == [] and on_disk["val"] == []
    assert not (run_dir / "rollouts" / "confirm").exists()
    assert not (run_dir / "rollouts" / "val").exists() and not (run_dir / "rollouts" / "train").exists()
    assert not _leaks(run_dir, C)
    assert not _leaks(run_dir.parent.parent, C)             # the project: the agent-optimize cwd
    # every spec-driven switch reached the seed baseline (all go through spec_for_run, before run_config)
    ev = _events(run_dir)
    first_eval = next(e for e in ev if e["kind"] == "eval_start")
    assert first_eval.get("fault_attribution") is True
    pol = [e for e in ev if e["kind"] == "errored_trial_policy"]
    assert pol and pol[0]["policy"] == "fail"
    assert rd.reserved_metric_calls() == 0 and rd.spent.metric_calls > 0
    # the seed was measured on F only
    base = json.loads((run_dir / "baseline.json").read_text())
    assert {pt["task_id"] for pt in base["val"]["per_task"]} <= set(rd.read_splits().feedback)


def test_cap_evolve_run_baseline_is_pooled(tmp_path, capsys):
    from cap_evolve import cli
    project, spec = _project(tmp_path)
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                   "--run-ts", "pooled"])
    assert rc == 0
    _assert_pooled(tmp_path / ".capevolve" / "run_pooled")


def test_direct_baseline_script_with_spec_is_pooled(tmp_path):
    project, spec = _project(tmp_path)
    script = REPO / "skills" / "phases" / "baseline" / "scripts" / "run.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--base", str(tmp_path / ".capevolve"), "--project", str(project),
         "--capability", str(tmp_path / "seed_capability"), "--spec", str(spec), "--run-ts", "direct"],
        capture_output=True, text=True, cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(CORE)})
    assert proc.returncode == 0, proc.stderr[-1500:]
    _assert_pooled(tmp_path / ".capevolve" / "run_direct")


def test_a_legacy_spec_is_unchanged(tmp_path):
    project, spec = _project(tmp_path)
    spec.write_text(spec.read_text().replace("split_mode: pooled", "split_mode: legacy"))
    script = REPO / "skills" / "phases" / "baseline" / "scripts" / "run.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--base", str(tmp_path / ".capevolve"), "--project", str(project),
         "--capability", str(tmp_path / "seed_capability"), "--spec", str(spec), "--run-ts", "legacy"],
        capture_output=True, text=True, cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(CORE)})
    assert proc.returncode == 0, proc.stderr[-1500:]
    rd = tmp_path / ".capevolve" / "run_legacy"
    assert "pooled_split" not in [e["kind"] for e in _events(rd)]
    assert not tmp_path.with_name(tmp_path.name + ".sealed").exists()
