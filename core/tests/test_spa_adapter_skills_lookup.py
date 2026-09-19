"""The spa adapter must find the SPA intervention library in both project layouts.

Counting parents reaches the repo root only for `<repo>/.capevolve*/project`. Under CI's deeper
layout it resolved to the work dir and every rollout failed to deploy.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ARM = REPO / "examples/skillberry_benchmarks_tau2_airline/spa/adapters"
SKILL_REL = Path("skills/interventions/llm-proxies/spa/scripts")


def _fake_repo(tmp_path, project_rel):
    root = tmp_path / "repo"
    (root / SKILL_REL).mkdir(parents=True)
    shutil.copy(REPO / SKILL_REL / "spa_env.py", root / SKILL_REL / "spa_env.py")
    adapters = root / project_rel / "adapters"
    adapters.mkdir(parents=True)
    for f in ("adapter.py", "gateway.py"):
        shutil.copy(ARM / f, adapters / f)
    return root, adapters


def _load(adapters, monkeypatch, skills_dir=None):
    if skills_dir is None:
        monkeypatch.delenv("CAPEVOLVE_SKILLS_DIR", raising=False)
    else:
        monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(skills_dir))
    monkeypatch.syspath_prepend(str(adapters))
    for name in ("adapter", "gateway", "spa_env"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("adapter", adapters / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["adapter"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _clean_modules():
    yield
    for name in ("adapter", "gateway", "spa_env"):
        sys.modules.pop(name, None)


def test_the_local_layout_still_resolves_without_the_env_var(tmp_path, monkeypatch):
    """What setup.sh builds. Must not regress."""
    root, adapters = _fake_repo(tmp_path, ".capevolve-spa/project")
    mod = _load(adapters, monkeypatch)
    assert Path(mod._spa_env().__file__) == root / SKILL_REL / "spa_env.py"


def test_the_ci_layout_resolves_through_the_env_var(tmp_path, monkeypatch):
    root, adapters = _fake_repo(
        tmp_path, "ci/benchmarks/.work/suite_smoke_skillberry_tau2_spa_proj/.capevolve/project")
    mod = _load(adapters, monkeypatch, skills_dir=root / "skills")
    assert Path(mod._spa_env().__file__) == root / SKILL_REL / "spa_env.py"


def test_the_ci_layout_fails_without_the_env_var(tmp_path, monkeypatch):
    _, adapters = _fake_repo(
        tmp_path, "ci/benchmarks/.work/suite_smoke_skillberry_tau2_spa_proj/.capevolve/project")
    mod = _load(adapters, monkeypatch)
    with pytest.raises(RuntimeError, match="SPA intervention library not found"):
        mod._spa_env()


def test_the_error_names_every_path_tried(tmp_path, monkeypatch):
    _, adapters = _fake_repo(tmp_path, ".capevolve-spa/project")
    shutil.rmtree(adapters.parents[2] / "skills")
    mod = _load(adapters, monkeypatch, skills_dir=tmp_path / "nowhere")
    with pytest.raises(RuntimeError) as e:
        mod._spa_env()
    assert "nowhere" in str(e.value) and str(e.value).count("scripts") == 2
