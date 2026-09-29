"""Unit tests for the outside-in tau2 tailoring — OFFLINE, no tau2 import required.

These cover the pure logic and the shapes the wrappers depend on. The seam contract itself
(does `llm_args` still reach litellm? is `run_simulation` still wrappable?) needs the real
benchmark and lives in test_tau2_seam_contract.py, behind the `seam_contract` marker.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "examples" / "tau2_airline" / "blackbox" / "adapters" / "tau2_tailoring.py"


def _tailoring():
    """Import the module WITHOUT importing tau2 (it imports tau2 lazily, inside functions)."""
    if str(MOD.parent) not in sys.path:
        sys.path.insert(0, str(MOD.parent))
    spec = importlib.util.spec_from_file_location("_tau2_tailoring_probe", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _tailoring()


# --- import-time behaviour (the check gate imports this module) --------------------------

def test_import_is_offline_and_registers_nothing():
    """`cap-evolve check` imports the adapter and its siblings unconditionally, so an import
    that dialled a service or mutated tau2's registry would hang or corrupt the gate."""
    src = MOD.read_text(encoding="utf-8")
    top = [l for l in src.split("\n")
           if l and not l[0].isspace() and not l.startswith(("#", '"', "'", ")", "]", "}"))]
    for line in top:
        assert not line.startswith("registry."), f"registration at import time: {line}"
    assert "import tau2" not in "\n".join(top), "tau2 must be imported lazily, inside functions"
    assert T._INSTALLED is False


# --- the context header: the highest-consequence pure function ---------------------------

def test_flatten_keys_produces_dash_separated_headers():
    out = T.flatten_keys({"skillberry-context": {"env_id": "e1", "task_id": "9"}})
    assert out == {"skillberry-context-env_id": "e1", "skillberry-context-task_id": "9"}


def test_flatten_keys_drops_none_but_keeps_falsy_values():
    out = T.flatten_keys({"a": {"keep": 0, "drop": None}})
    assert out == {"a-keep": "0"}


def test_context_headers_carry_env_id_task_id_and_plugin():
    h = T.context_headers("env-7", "9")
    assert h["skillberry-context-env_id"] == "env-7"
    assert h["skillberry-context-task_id"] == "9"
    assert h["skillberry-context-plugin"] == "tau2"


def test_context_headers_without_a_task_still_carry_env_id():
    """env_id is what routes a store tool to this rollout; task_id is only attribution."""
    h = T.context_headers("env-7", None)
    assert h["skillberry-context-env_id"] == "env-7"
    assert "skillberry-context-task_id" not in h


# --- service URLs are overridable, and share the primitives' env var --------------------

def test_res_url_uses_the_same_env_var_as_the_frozen_primitives(monkeypatch):
    """The skill's tools read SPA_REMOTE_ENV_URL. If this module read a different name the two
    could point at different services and the mismatch would be invisible."""
    monkeypatch.setenv("SPA_REMOTE_ENV_URL", "http://res.invalid:9/")
    assert T.res_url() == "http://res.invalid:9"


def test_spa_url_is_overridable_and_defaults(monkeypatch):
    monkeypatch.delenv("SPA_AGENT_URL", raising=False)
    assert T.spa_url() == T.DEFAULT_SPA_URL
    monkeypatch.setenv("SPA_AGENT_URL", "http://spa.invalid:1/")
    assert T.spa_url() == "http://spa.invalid:1"


# --- merge mechanics --------------------------------------------------------------------

class _Msg:
    """Minimal stand-in for a tau2 message: _renumber only touches timestamp + turn_idx."""

    def __init__(self, ts, tag):
        self.timestamp, self.tag, self.turn_idx = ts, tag, None


def test_renumber_sorts_by_timestamp_and_reassigns_turn_idx():
    """tau2's own get_trajectory contract. A merged message with a stale turn_idx makes the
    persisted trace disagree with itself."""
    out = T._renumber([_Msg("3", "c"), _Msg("1", "a"), _Msg("2", "b")])
    assert [m.tag for m in out] == ["a", "b", "c"]
    assert [m.turn_idx for m in out] == [0, 1, 2]


def test_renumber_does_not_mutate_its_input():
    src = [_Msg("2", "b"), _Msg("1", "a")]
    T._renumber(src)
    assert [m.tag for m in src] == ["b", "a"] and src[0].turn_idx is None


# --- the wrappers: idempotence and the double-binding trap -------------------------------

def test_the_wrapper_marker_is_what_makes_install_idempotent():
    """Every cap-evolve phase is a separate process that loads the adapter again, and a wrapper
    applied twice would merge each trajectory twice."""
    assert T._MARK


def test_the_simulation_wrapper_targets_both_bindings():
    """tau2.runner.batch imports run_simulation BY NAME at module load. Patching only
    tau2.runner.simulation leaves the batch path — the one every run uses — unwrapped, and the
    symptom is a silently unmerged trace."""
    src = MOD.read_text(encoding="utf-8")
    assert "tau2.runner.simulation" in src
    assert "tau2.runner.batch" in src


def test_finish_rollout_is_a_no_op_without_a_session():
    """A rollout whose remote env never started must degrade, not raise — an exception inside a
    simulation costs three full re-runs."""
    class _Agent:
        skillberry_env_id = ""

    class _Orch:
        agent = _Agent()

    class _Sim:
        messages = ["untouched"]

    sim = _Sim()
    T._finish_rollout(_Orch(), sim)
    assert sim.messages == ["untouched"]


# --- the arm's registered names ---------------------------------------------------------

def test_the_arm_registers_its_own_domain_and_agent_names():
    """A separate domain name is what lets a run dir say WHICH arm produced a number."""
    assert T.DOMAIN == "airline_skillberry" and T.DOMAIN != T.RES_DOMAIN
    assert T.AGENT_NAME == "llm_agent_skillberry"
    assert T.RES_DOMAIN == "airline", "the remote environment is plain vanilla tau2"


def test_the_sentinel_matches_the_gateway_module():
    """Two spellings of the sentinel would route the agent straight upstream and silently
    measure the unoptimized capability."""
    if str(MOD.parent) not in sys.path:
        sys.path.insert(0, str(MOD.parent))
    import gateway

    assert T.SENTINEL_MODEL == gateway.SPA_AGENT_MODEL


def test_seam_errors_name_the_seam_the_version_and_the_consequence():
    e = T._seam_error("some.seam", "it moved", "reward collapses")
    msg = str(e)
    assert "some.seam" in msg and "it moved" in msg and "reward collapses" in msg
    assert "YOUR responsibility" in msg
    assert isinstance(e, T.SeamError)
