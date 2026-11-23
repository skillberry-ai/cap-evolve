"""agent-optimize scripts must find evaluate/finalize/diagnose/run-optimizer in a flat
(install.sh) skills tree, and still in a source checkout."""
import importlib
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AO = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _flat(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    for comp, name in [("phases", "evaluate"), ("phases", "finalize"), ("phases", "diagnose"),
                       ("optimizers", "run-optimizer"), ("algorithms", "agent-optimize")]:
        shutil.copytree(REPO / "skills" / comp / name, skills / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (skills / "optimizers").mkdir(exist_ok=True)
    shutil.copy(REPO / "skills" / "optimizers" / "registry.yaml", skills / "optimizers")
    return skills


def _load(name, scripts, monkeypatch):
    monkeypatch.syspath_prepend(str(scripts))
    for m in [m for m in sys.modules if m in ("round", "act", "host", "conductor_backend", "pregate")]:
        monkeypatch.delitem(sys.modules, m)
    return importlib.import_module(name)


def test_flat_tree_paths_exist(tmp_path, monkeypatch):
    skills = _flat(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(skills))
    scripts = skills / "agent-optimize" / "scripts"
    from cap_evolve import eval_index, harness
    from cap_evolve.cli import _skills_path

    rnd = _load("round", scripts, monkeypatch)
    act = _load("act", scripts, monkeypatch)
    host = _load("host", scripts, monkeypatch)
    cb = _load("conductor_backend", scripts, monkeypatch)
    for mod in (rnd, act):
        assert mod.SKILLS == skills
        cmd = eval_index.eval_cmd("r", "p", "t", "val", 1, skills_dir=mod.SKILLS)
        assert Path(cmd[1]).is_file() and Path(cmd[1]).is_relative_to(skills)
    assert harness.skills_path("phases", "finalize", act.SKILLS).joinpath("scripts", "run.py").is_file()
    assert harness.skills_path("phases", "diagnose", cb.SKILLS).joinpath("scripts", "run.py").is_file()
    assert cb.RUN_OPTIMIZER.is_file() and host.RUN_OPTIMIZER.is_file() and host.REGISTRY.is_file()
    assert host.SKILLS == skills
    for f in ("conductor.py", "host.py"):
        assert (_skills_path("algorithms", "agent-optimize", skills) / "scripts" / f).is_file()


def test_source_checkout_still_resolves(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_SKILLS_DIR", raising=False)
    from cap_evolve import eval_index, harness
    from cap_evolve.cli import _skills_path

    host = _load("host", AO, monkeypatch)
    assert host.SKILLS == REPO / "skills"
    assert host.RUN_OPTIMIZER == REPO / "skills/optimizers/run-optimizer/scripts/run.py"
    assert host.RUN_OPTIMIZER.is_file() and host.REGISTRY.is_file()
    assert Path(eval_index.eval_cmd("r", "p", "t", "val", 1)[1]).is_file()
    assert harness.skills_path("phases", "diagnose", REPO / "skills").is_dir()
    assert (_skills_path("algorithms", "agent-optimize", REPO / "skills") / "scripts" / "conductor.py").is_file()
