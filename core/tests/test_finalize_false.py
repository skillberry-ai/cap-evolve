"""Spec key ``finalize: false`` (default true) and the helper surface's seed-unchanged rule."""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402

from cap_evolve import gatecfg, helpers  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "benchmarks" / "toy" / "examples" / "calc"
TEMPLATE_SPEC = REPO / "benchmarks" / "_scaffold" / "project" / "capevolve.yaml"


@pytest.fixture
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _project(tmp_path, extra=""):
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")
    spec = project / "capevolve.yaml"
    spec.write_text(TEMPLATE_SPEC.read_text(encoding="utf-8") + "\n" + extra, encoding="utf-8")
    return project, spec


def _events(run_dir):
    return [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]


def test_finalize_enabled_parses_the_spec_value():
    assert gatecfg.finalize_enabled({}) is True
    assert gatecfg.finalize_enabled({"finalize": True}) is True
    for off in (False, "false", "no", "0", "off"):
        assert gatecfg.finalize_enabled({"finalize": off}) is False
    assert gatecfg.finalize_enabled({"finalize": True}, environ={"CAPEVOLVE_FINALIZE": "0"}) is False


def test_cli_with_finalize_false_ends_after_the_search_with_the_champion_recorded(tmp_path, capsys, _env):
    from cap_evolve import cli
    project, spec = _project(tmp_path, "finalize: false\n")
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                   "--run-ts", "nofinal"])
    assert rc == 0
    run_dir = tmp_path / ".capevolve" / "run_nofinal"
    kinds = [e["kind"] for e in _events(run_dir)]
    assert "step" in kinds, "the search loop still ran"
    skipped = [e for e in _events(run_dir) if e["kind"] == "finalize_skipped"]
    assert skipped and skipped[0]["reason"] == "spec"
    assert not (run_dir / "final.json").exists()
    assert not (run_dir / "rollouts" / "test").exists()                       # no FINAL on test
    assert json.loads((run_dir / "splits.json").read_text())["test_used"] is False
    # no train/val bookend after the search: the only evaluations are the baseline and the candidates
    assert [e for e in _events(run_dir) if e["kind"] == "finalize"] == []
    champ = json.loads((run_dir / "champion.json").read_text())
    assert champ["finalized"] is False and Path(champ["candidate_dir"]).is_dir()


def test_cli_default_still_finalizes(tmp_path, capsys, _env):
    from cap_evolve import cli
    project, spec = _project(tmp_path)
    assert cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                     "--run-ts", "final"]) == 0
    run_dir = tmp_path / ".capevolve" / "run_final"
    assert json.loads((run_dir / "splits.json").read_text())["test_used"] is True
    assert not (run_dir / "champion.json").exists()


def test_conductor_with_finalize_false_records_the_champion_and_scores_nothing(tmp_path):
    spec = {"max_metric_calls": 700, "ao_plateau_n": 40, "finalize": False}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"delay": (1, 3), "salt": 1}, rungs=(8, 16))
    assert cfg.finalize is False
    c = F.run_to_done(w, be, cfg)
    assert not (w.root / "final.json").exists()
    assert any(e[0] == "finalize_skipped" and e[1].get("reason") == "spec" for e in w.events)
    assert c.st["finalized"] is True and c.st["final_skipped"]["finalized"] is False
    assert not any(e[0] == "finalize" for e in w.events)


def test_conductor_default_finalizes(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 700, "ao_plateau_n": 40},
                        world_kw={"delay": (1, 3), "salt": 1}, rungs=(8, 16))
    assert cfg.finalize is True
    F.run_to_done(w, be, cfg)
    assert (w.root / "final.json").exists()


# ---- helper_surface -----------------------------------------------------------------------------

def _cfg():
    return helpers.resolve({"helpers": {"enabled": True}, "surface": {"executable_dirs": ["skills/*/scripts"]}})


def _tree(root: Path, files: dict):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def test_a_seed_file_outside_the_surface_is_not_the_candidates_doing(tmp_path):
    seed = _tree(tmp_path / "seed", {"reference/data_model.py": "X = 1\n", "skills/s/SKILL.md": "s\n"})
    cand = _tree(tmp_path / "cand", {"reference/data_model.py": "X = 1\n", "skills/s/SKILL.md": "s\n",
                                     "skills/s/scripts/h.py": "def f():\n    return 1\n"})
    cfg = _cfg()
    assert any("reference/data_model.py" in p for p in helpers.surface_problems(cand, cfg))     # old behaviour
    assert helpers.surface_problems(cand, cfg, seed) == []


def test_changed_or_new_executables_outside_the_surface_are_still_flagged(tmp_path):
    seed = _tree(tmp_path / "seed", {"reference/data_model.py": "X = 1\n"})
    cand = _tree(tmp_path / "cand", {"reference/data_model.py": "X = 2\n",       # changed
                                     "extra/new.py": "Y = 1\n"})                   # new
    probs = helpers.surface_problems(cand, _cfg(), seed)
    assert any("reference/data_model.py" in p for p in probs) and any("extra/new.py" in p for p in probs)


def test_pregate_helper_surface_uses_the_seed(tmp_path):
    import pregate
    seed = _tree(tmp_path / "seed", {"reference/data_model.py": "X = 1\n"})
    cand = _tree(tmp_path / "cand", {"reference/data_model.py": "X = 1\n"})
    checks = pregate.helper_checks(cand, None, {**_cfg(), "lint": False, "smoke": False}, seed=seed)
    surf = next(c for c in checks if c["name"] == "helper_surface")
    assert surf["ok"] is True
    checks = pregate.helper_checks(cand, None, {**_cfg(), "lint": False, "smoke": False})
    assert next(c for c in checks if c["name"] == "helper_surface")["ok"] is False
