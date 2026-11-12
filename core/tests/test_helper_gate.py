"""The shared helper gate (``cap_evolve.helper_gate``): one rule set for every path that proposes candidates.

The checks themselves (``surface_problems``, ``lint_candidate``, ``run_smoke``) have their own tests. This file tests
the gate around them: when it is on, which checks it runs and against what, how a config problem is reported, and
that the agent-optimize pregate and conductor give the same verdict as the gate itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

from cap_evolve import helper_gate, helpers  # noqa: E402

LEAK = 'ID = "105-24"\n'
BROKEN = "import nonexistent_module_xyz\n"
CLEAN = "def f(x):\n    return x\n"


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    monkeypatch.delenv("CAPEVOLVE_HELPER_GATE", raising=False)


def _cfg(**helpers_tbl):
    return helpers.resolve({"helpers": {"enabled": True, "task_ids": ["105-24"], "smoke_timeout": 30,
                                        **helpers_tbl}})


def _tree(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def _cand(root: Path, script: str | None, name="h.py") -> Path:
    files = {"skills/s/SKILL.md": "s\n"}
    if script is not None:
        files[f"skills/s/scripts/{name}"] = script
    return _tree(root, files)


def _failed(res) -> list[str]:
    return [c["name"] for c in res["checks"] if not c["ok"]]


# ---- on by default, off only explicitly --------------------------------------------------------

def test_the_gate_is_on_whenever_helpers_are_on():
    assert helper_gate.active(_cfg()) is True
    assert helper_gate.off_reason(_cfg()) is None


def test_the_gate_is_off_when_helpers_are_off():
    assert helper_gate.active(helpers.resolve({})) is False
    assert helper_gate.off_reason(helpers.resolve({})) is None      # nothing to warn about: no helpers at all


def test_helpers_gate_false_turns_it_off_and_says_so():
    cfg = _cfg(gate=False)
    assert helper_gate.active(cfg) is False
    assert helper_gate.off_reason(cfg) == "helpers.gate: false"


def test_the_env_switch_turns_it_off_and_wins_over_the_spec(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HELPER_GATE", "0")
    assert helper_gate.active(_cfg()) is False
    assert helper_gate.off_reason(_cfg()) == "CAPEVOLVE_HELPER_GATE=0"
    monkeypatch.setenv("CAPEVOLVE_HELPER_GATE", "1")
    assert helper_gate.active(_cfg(gate=False)) is True


def test_a_bad_env_value_is_a_config_error(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HELPER_GATE", "maybe")
    with pytest.raises(helper_gate.GateConfigError):
        helper_gate.active(_cfg())


def test_the_spec_key_is_known_to_resolve():
    # `gate` must be a recognised helpers key: resolve() refuses unknown keys as typos
    assert helpers.resolve({"helpers": {"enabled": True, "gate": False}})["gate"] is False


def test_an_inactive_gate_runs_nothing(tmp_path):
    res = helper_gate.gate(_cand(tmp_path, LEAK), _cfg(gate=False))
    assert res == {"ok": True, "checks": [], "failure": ""}


# ---- what it checks ----------------------------------------------------------------------------

def test_a_clean_helper_passes_all_three_checks(tmp_path):
    res = helper_gate.gate(_cand(tmp_path, CLEAN), _cfg())
    assert res["ok"] and [c["name"] for c in res["checks"]] == list(helper_gate.CHECKS)


def test_a_task_id_literal_is_refused_by_the_lint(tmp_path):
    res = helper_gate.gate(_cand(tmp_path, LEAK), _cfg())
    assert not res["ok"] and "helper_lint" in _failed(res) and "[helper_lint]" in res["failure"]


def test_a_helper_that_does_not_import_is_refused_by_the_smoke(tmp_path):
    res = helper_gate.gate(_cand(tmp_path, BROKEN), _cfg())
    assert not res["ok"] and _failed(res) == ["helper_smoke"]


def test_all_three_checks_run_even_when_one_fails(tmp_path):
    # every path reports every finding, not only the first one
    res = helper_gate.gate(_cand(tmp_path, LEAK), _cfg())
    assert [c["name"] for c in res["checks"]] == list(helper_gate.CHECKS)


def test_lint_and_smoke_can_be_turned_off_but_the_surface_check_cannot(tmp_path):
    res = helper_gate.gate(_cand(tmp_path, LEAK), _cfg(lint=False, smoke=False))
    assert [c["name"] for c in res["checks"]] == ["helper_surface"] and res["ok"]


def test_an_executable_outside_the_declared_surface_is_refused(tmp_path):
    cand = _tree(tmp_path / "c", {"skills/s/SKILL.md": "s\n", "elsewhere/x.py": CLEAN})
    res = helper_gate.gate(cand, _cfg(lint=False, smoke=False))
    assert _failed(res) == ["helper_surface"]


def test_a_file_the_parent_already_had_is_not_blamed_on_the_candidate(tmp_path):
    # lint and smoke compare against the PARENT: an unchanged helper is not this edit's doing
    parent = _cand(tmp_path / "parent", LEAK)
    cand = _cand(tmp_path / "cand", LEAK)
    assert helper_gate.gate(cand, _cfg(), parent=parent)["ok"]
    assert not helper_gate.gate(cand, _cfg())["ok"]


def test_a_file_the_seed_already_had_is_not_a_surface_violation(tmp_path):
    seed = _tree(tmp_path / "seed", {"reference/data_model.py": "X = 1\n"})
    cand = _tree(tmp_path / "cand", {"reference/data_model.py": "X = 1\n"})
    cfg = _cfg(lint=False, smoke=False)
    assert helper_gate.gate(cand, cfg, seed=seed)["ok"]
    assert not helper_gate.gate(cand, cfg)["ok"]


# ---- a gate that cannot run stops the run --------------------------------------------------------

def test_an_unreadable_ids_file_is_a_config_error_not_a_candidate_failure(tmp_path):
    cfg = _cfg(ids_file=str(tmp_path / "missing_ids.txt"))
    with pytest.raises(helper_gate.GateConfigError, match="ids_file"):
        helper_gate.check_config(cfg)
    with pytest.raises(helper_gate.GateConfigError):
        helper_gate.gate(_cand(tmp_path / "c", CLEAN), cfg)


def test_a_declared_fixtures_file_that_is_missing_is_a_config_error(tmp_path):
    with pytest.raises(helper_gate.GateConfigError, match="fixtures"):
        helper_gate.check_config(_cfg(fixtures=str(tmp_path / "nope.jsonl")))


def test_a_missing_seed_dir_is_a_config_error(tmp_path):
    with pytest.raises(helper_gate.GateConfigError, match="seed"):
        helper_gate.check_config(_cfg(), seed=tmp_path / "no_seed")


def test_an_inactive_gate_never_raises_for_its_config(tmp_path):
    helper_gate.check_config(_cfg(gate=False, ids_file=str(tmp_path / "missing")), seed=tmp_path / "nope")


def test_a_readable_ids_file_is_used_by_the_lint(tmp_path):
    ids = tmp_path / "ids.txt"
    ids.write_text("99-9\n")
    res = helper_gate.gate(_cand(tmp_path / "c", 'X = "99-9"\n'), _cfg(ids_file=str(ids), task_ids=[]))
    assert "helper_lint" in _failed(res)


# ---- the same verdict on every path --------------------------------------------------------------

@pytest.mark.parametrize("script,expected", [(CLEAN, None), (LEAK, "helper_lint"), (BROKEN, "helper_smoke")])
def test_the_pregate_the_conductor_and_the_gate_agree(tmp_path, script, expected):
    import conductor_backend
    import pregate
    spec = {"helpers": {"enabled": True, "task_ids": ["105-24"], "smoke_timeout": 30}}
    cfg = helpers.resolve(spec)
    cand = _cand(tmp_path / "c", script)
    seed = _cand(tmp_path / "seed", None)

    via_gate = helper_gate.gate(cand, cfg, seed=seed)
    via_pregate = pregate.helper_checks(cand, None, cfg, seed=seed)
    via_conductor = conductor_backend.helper_refusal(spec, cand, None, seed=seed)

    first_failed = next((c["name"] for c in via_gate["checks"] if not c["ok"]), None)
    assert first_failed == expected
    assert [(c["name"], c["ok"]) for c in via_pregate] == [(c["name"], c["ok"]) for c in via_gate["checks"]]
    assert (via_conductor[0] if via_conductor else None) == expected
