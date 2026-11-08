"""The blackbox adapter must find the intervention library in both project layouts.

Counting parents reaches the repo root only for `<repo>/.capevolve*/project`. Under CI's deeper
layout it resolved to the work dir and every rollout failed to deploy. The sierra blackbox
adapter walks every parent instead, and CAPEVOLVE_SKILLS_DIR still wins when set.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ARM = REPO / "benchmarks/tau2/examples/sierra_airline/blackbox/adapters"
SKILL_REL = Path("skills/interventions/llm-proxies/blackbox/scripts")


def _fake_repo(tmp_path, project_rel):
    root = tmp_path / "repo"
    (root / SKILL_REL).mkdir(parents=True)
    shutil.copy(REPO / SKILL_REL / "blackbox_env.py", root / SKILL_REL / "blackbox_env.py")
    adapters = root / project_rel / "adapters"
    adapters.mkdir(parents=True)
    for f in ("adapter.py", "tau2_tailoring.py"):
        shutil.copy(ARM / f, adapters / f)
    return root, adapters


def _load(adapters, monkeypatch, skills_dir=None):
    if skills_dir is None:
        monkeypatch.delenv("CAPEVOLVE_SKILLS_DIR", raising=False)
    else:
        monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(skills_dir))
    monkeypatch.syspath_prepend(str(adapters))
    for name in ("adapter", "tau2_tailoring", "blackbox_env"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("adapter", adapters / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["adapter"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _clean_modules():
    yield
    for name in ("adapter", "tau2_tailoring", "blackbox_env"):
        sys.modules.pop(name, None)


def test_the_local_layout_still_resolves_without_the_env_var(tmp_path, monkeypatch):
    """What setup.sh builds. Must not regress."""
    root, adapters = _fake_repo(tmp_path, ".capevolve-blackbox/project")
    mod = _load(adapters, monkeypatch)
    assert Path(mod._blackbox_env().__file__) == root / SKILL_REL / "blackbox_env.py"


def test_the_ci_layout_resolves_through_the_env_var(tmp_path, monkeypatch):
    root, adapters = _fake_repo(
        tmp_path, "ci/benchmarks/.work/suite_smoke_tau2_sierra_blackbox_proj/.capevolve/project")
    mod = _load(adapters, monkeypatch, skills_dir=root / "skills")
    assert Path(mod._blackbox_env().__file__) == root / SKILL_REL / "blackbox_env.py"


def test_the_ci_layout_resolves_even_without_the_env_var(tmp_path, monkeypatch):
    """The sierra adapter walks EVERY parent for skills/, so CI's deeper layout no longer needs
    CAPEVOLVE_SKILLS_DIR to find the library (counting parents is what broke it before)."""
    root, adapters = _fake_repo(
        tmp_path, "ci/benchmarks/.work/suite_smoke_tau2_sierra_blackbox_proj/.capevolve/project")
    mod = _load(adapters, monkeypatch)
    assert Path(mod._blackbox_env().__file__) == root / SKILL_REL / "blackbox_env.py"


def test_no_skills_dir_anywhere_raises_a_named_error(tmp_path, monkeypatch):
    _, adapters = _fake_repo(
        tmp_path, "ci/benchmarks/.work/suite_smoke_tau2_sierra_blackbox_proj/.capevolve/project")
    shutil.rmtree(tmp_path / "repo" / "skills")
    mod = _load(adapters, monkeypatch)
    with pytest.raises(RuntimeError, match="cannot locate skills/interventions/llm-proxies/blackbox/scripts"):
        mod._blackbox_env()


def test_an_explicit_skills_dir_wins_over_the_walk(tmp_path, monkeypatch):
    """CAPEVOLVE_SKILLS_DIR is taken as given: a wrong value fails on import instead of falling
    back to whatever skills/ the walk would find. (The sierra adapter's error does not yet name
    the paths it tried; that is tracked with the adapter-parity work.)"""
    _, adapters = _fake_repo(tmp_path, ".capevolve-blackbox/project")
    mod = _load(adapters, monkeypatch, skills_dir=tmp_path / "nowhere")
    assert mod._blackbox_scripts() == tmp_path / "nowhere" / SKILL_REL.relative_to("skills")
    with pytest.raises(ModuleNotFoundError):
        mod._blackbox_env()
