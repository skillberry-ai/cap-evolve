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


def _render_briefing(host, tmp_path):
    run, proj = tmp_path / "run", tmp_path / "proj"
    run.mkdir(), proj.mkdir()
    return host._briefing(run_dir=run, project=proj, spec={}, skills=host.SKILLS, rounds=1,
                          workdir=tmp_path, context={})


def _briefing_paths(text, host):
    import re
    a = re.search(r'^A="([^"]+)"', text, re.M).group(1)
    s = re.search(r'^S="([^"]+)"', text, re.M).group(1)
    names = set(re.findall(r"`\$A/([\w.]+\.py)`", text))
    return Path(a), Path(s), names


def test_flat_briefing_paths_exist(tmp_path, monkeypatch):
    skills = _flat(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(skills))
    host = _load("host", skills / "agent-optimize" / "scripts", monkeypatch)
    a, s, names = _briefing_paths(_render_briefing(host, tmp_path), host)
    assert s.is_dir() and a.is_dir() and a.is_relative_to(skills)
    assert {"spend.py", "gate_check.py", "commit.py", "measure.py"} <= names
    for n in names:
        assert (a / n).is_file(), n
    # "Read this first" must name a file that exists in the flat install too.
    legacy = skills / "agent-optimize" / "references" / "legacy" / "legacy-SKILL.md"
    legacy.parent.mkdir(exist_ok=True)
    shutil.copy(REPO / "docs/archive/agent-optimize-legacy/legacy-SKILL.md", legacy)
    host = _load("host", skills / "agent-optimize" / "scripts", monkeypatch)
    (tmp_path / "run").rmdir(), (tmp_path / "proj").rmdir()
    text = _render_briefing(host, tmp_path)
    assert str(legacy) in text and host.LEGACY_DOC == legacy


def test_install_sh_ships_legacy_doc(tmp_path, monkeypatch):
    import subprocess
    src = tmp_path / "src"
    shutil.copytree(REPO, src, ignore=shutil.ignore_patterns(
        ".git", ".symcc", ".scratch", "node_modules", "__pycache__", "dashboard", "benchmarks", ".venv"))
    dest = tmp_path / "inst"
    r = subprocess.run(["bash", str(src / "install.sh"), "--dest", str(dest)],
                       capture_output=True, text=True, cwd=src)
    assert (dest / "agent-optimize" / "references" / "legacy" / "legacy-SKILL.md").is_file(), r.stdout + r.stderr
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(dest))
    host = _load("host", dest / "agent-optimize" / "scripts", monkeypatch)
    assert host.LEGACY_DOC == dest / "agent-optimize" / "references" / "legacy" / "legacy-SKILL.md"
    import re
    doc = host.LEGACY_DOC
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", doc.read_text()):
        if "://" in target or target.startswith("mailto:"):
            continue
        assert (doc.parent / target).exists(), target


def test_source_checkout_briefing_paths_exist(tmp_path, monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_SKILLS_DIR", raising=False)
    host = _load("host", AO, monkeypatch)
    a, _, names = _briefing_paths(_render_briefing(host, tmp_path), host)
    assert a == AO and all((a / n).is_file() for n in names)


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


def test_installed_docs_script_paths_resolve(tmp_path, monkeypatch):
    """Every "$VAR/..." script in the installed SKILL.md and legacy-SKILL.md exists once the
    briefing's variables are substituted; no $S/phases|algorithms|optimizers left."""
    import re
    import subprocess
    src = tmp_path / "src"
    shutil.copytree(REPO, src, ignore=shutil.ignore_patterns(
        ".git", ".symcc", ".scratch", "node_modules", "__pycache__", "dashboard", "benchmarks", ".venv"))
    dest = tmp_path / "inst"
    r = subprocess.run(["bash", str(src / "install.sh"), "--dest", str(dest)],
                       capture_output=True, text=True, cwd=src)
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(dest))
    host = _load("host", dest / "agent-optimize" / "scripts", monkeypatch)
    text = _render_briefing(host, tmp_path)
    env = dict(re.findall(r'^([A-Z]+)="([^"]*)"', text, re.M))
    docs = [dest / "agent-optimize" / "SKILL.md",
            dest / "agent-optimize" / "references" / "legacy" / "legacy-SKILL.md"]
    for doc in docs:
        assert doc.is_file(), r.stdout + r.stderr
        body = doc.read_text()
        assert not re.search(r'\$S/(phases|algorithms|optimizers)', body), doc
        assert not re.search(r'^\s*A=', body, re.M), doc
        found = re.findall(r'"\$([A-Z]+)/([\w./-]+\.py)"', body)
        assert found, doc
        for var, rel in found:
            assert var in env, (doc, var)
            assert (Path(env[var]) / rel).is_file(), (doc, var, rel)
