"""An installed (flat) skills tree must work: cap_evolve copied outside the repo, skills
laid out the way install.sh does (``<dir>/<name>``, no capabilities/ or phases/ folders)."""

import importlib
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class _Run:
    def __init__(self):
        self.events = []

    def log_event(self, *a, **k):
        self.events.append((a, k))


def test_flat_install_layout_is_found(tmp_path, monkeypatch):
    # Deep enough that the package's source-checkout fallback (parents[2]/"skills") is NOT
    # the folder CAPEVOLVE_SKILLS_DIR points to, so the env var is really what is tested.
    site = tmp_path / "a" / "b" / "site"
    shutil.copytree(REPO / "core" / "cap_evolve", site / "cap_evolve",
                    ignore=shutil.ignore_patterns("__pycache__"))
    skills = tmp_path / "skills"
    skills.mkdir()
    for comp, name in [("capabilities", "system-prompt"), ("phases", "diagnose"),
                       ("optimizers", "run-optimizer"), ("memory", "wiki")]:
        shutil.copytree(REPO / "skills" / comp / name, skills / name)
    (skills / "optimizers").mkdir(exist_ok=True)
    shutil.copy(REPO / "skills" / "optimizers" / "registry.yaml", skills / "optimizers")
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(skills))
    monkeypatch.syspath_prepend(str(site))
    for m in [m for m in sys.modules if m == "cap_evolve" or m.startswith("cap_evolve.")]:
        monkeypatch.delitem(sys.modules, m)
    harness = importlib.import_module("cap_evolve.harness")
    try:
        assert Path(harness.__file__).resolve().is_relative_to(site.resolve())

        dest = tmp_path / "work"
        dest.mkdir()
        harness.stage_capability_guidance(_Run(), dest, capabilities=["system-prompt"])
        assert (dest / "guidance" / "system-prompt").is_dir()
        assert (dest / "guidance" / "diagnose").is_dir()

        mod, why = harness._load_capability_abstract("system-prompt", "t")
        assert mod is not None and why is None

        ref = harness._skill_dir("optimizers", "run-optimizer") / "references" / "claude-code.md"
        assert ref.is_file()

        assert harness._optimizer_parallel("claude-code") is True
        wd = tmp_path / "wd"
        wd.mkdir()
        harness._inject_native_skills(_Run(), wd, ["system-prompt"], tmp_path,
                                      "claude-code")
        assert (wd / ".claude" / "skills" / "system-prompt").is_dir()
        assert (wd / ".claude" / "skills" / "diagnose").is_dir()

        harness._inject_memory_skill_guidance(_Run(), dest, "wiki")
        assert (dest / "guidance" / "memory-wiki" / "SKILL.md").is_file()
    finally:
        for m in [m for m in sys.modules if m == "cap_evolve" or m.startswith("cap_evolve.")]:
            sys.modules.pop(m, None)
