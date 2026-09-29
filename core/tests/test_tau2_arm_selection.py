"""ONE arm per adapter: the direct and proxy adapters must not leak into each other.

`examples/tau2_airline/adapters/` is the DIRECT arm; `examples/tau2_airline/blackbox/adapters/`
is the proxy arm. Each ships a self-contained adapter, per the convention the adapter docstring
states — an adapter is ONE file copied into a project's adapters/, so a shared import would break
that. The cost of duplication is DRIFT, so these tests pin the boundary in both directions:
the direct adapter must contain no proxy machinery, and the proxy adapter must contain no
policy-editing machinery.

Offline: nothing here needs a network. The proxy adapter's deploy path is exercised with a stub
tau2_tailoring so the adapter's own logic is tested independently of the tailoring's behaviour.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EX = REPO / "examples" / "tau2_airline"
DIRECT = EX / "adapters" / "adapter.py"
PROXY = EX / "blackbox" / "adapters" / "adapter.py"


def _load(path: Path, name: str):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def stub_tailoring(monkeypatch):
    """A fake `tau2_tailoring` recording whether the adapter reached it."""
    calls = []
    stub = types.ModuleType("tau2_tailoring")
    stub.verify = lambda: (calls.append("verify"), {"notes": ["stub"]})[1]
    stub.install = lambda: calls.append("install")
    monkeypatch.setitem(sys.modules, "tau2_tailoring", stub)
    return calls


def _candidate(tmp_path: Path, *, store_skill: bool) -> Path:
    cand = tmp_path / "cand"
    if store_skill:
        (cand / "my_skill").mkdir(parents=True)
        (cand / "my_skill" / "SKILL.md").write_text("", encoding="utf-8")
        (cand / "primitive_tools").mkdir(parents=True)
        (cand / "primitive_tools" / "functions.py").write_text("", encoding="utf-8")
    else:
        (cand / "policy").mkdir(parents=True)
        (cand / "policy" / "policy.md").write_text("be helpful", encoding="utf-8")
    return cand


# --- both files exist, and each is self-contained ---------------------------------------

def test_each_arm_ships_its_own_adapter_and_gateway():
    for base in (EX / "adapters", EX / "blackbox" / "adapters"):
        for name in ("adapter.py", "gateway.py"):
            assert (base / name).exists(), f"missing {base / name}"
    # Only the proxy arm ships the tailoring module.
    assert (EX / "blackbox" / "adapters" / "tau2_tailoring.py").exists()
    assert not (EX / "adapters" / "tau2_tailoring.py").exists()


def test_the_direct_adapter_contains_no_proxy_machinery():
    """The leak that matters most: a direct project must not carry, import, or mention the
    delivery path it does not use — a direct project does not even ship that module, so an
    import would raise at gate time."""
    src = DIRECT.read_text(encoding="utf-8")
    for token in ("tau2_tailoring", "airline_skillberry", "skillberry-local",
                  "blackbox_env", "my_skill", "SPA_MODEL_NAME"):
        assert token not in src, f"direct adapter mentions {token!r}"


def test_the_proxy_adapter_contains_no_policy_machinery():
    """The mirror image: the policy is the benchmark's exam and is not part of this capability,
    so the proxy adapter must not read or install a candidate policy."""
    src = PROXY.read_text(encoding="utf-8")
    for token in ("_read_candidate_policy", "_build_candidate_tools", "_original_env_ctor"):
        assert token not in src, f"proxy adapter still carries {token!r}"


def test_the_proxy_adapter_is_single_arm():
    """No arm switching left: the strip replaced the accessors with constants."""
    src = PROXY.read_text(encoding="utf-8")
    for token in ("self._blackbox", "BLACKBOX_DOMAIN", "def _domain(", "def _agent("):
        assert token not in src, f"proxy adapter still branches on the arm: {token!r}"


# --- the proxy adapter's shape guard ----------------------------------------------------

def test_the_guard_accepts_a_store_skill_and_rejects_a_policy_tree(tmp_path):
    P = _load(PROXY, "_arm_guard")
    assert P._is_store_skill(_candidate(tmp_path, store_skill=True))
    assert not P._is_store_skill(_candidate(tmp_path / "d", store_skill=False))


def test_the_committed_proxy_seed_is_a_store_skill():
    P = _load(PROXY, "_arm_guard_seed")
    assert P._is_store_skill(EX / "blackbox" / "seed_capability")
    # ...and the direct seed is NOT, so a mix-up cannot pass the guard silently.
    assert not P._is_store_skill(EX / "seed_capability")


def test_a_direct_shaped_candidate_is_a_deploy_error_not_an_adaptation(tmp_path, stub_tailoring):
    """This adapter has exactly ONE delivery path. Quietly running a direct-shaped candidate
    would record the wrong delivery as the requested one."""
    P = _load(PROXY, "_arm_wrong_shape")
    a = P.Adapter()
    a.apply(_candidate(tmp_path, store_skill=False))
    assert a._deploy_error and "SKILL.md" in a._deploy_error
    assert "install" not in stub_tailoring, "nothing should be installed for a bad candidate"


def test_a_skill_without_the_frozen_substrate_is_a_deploy_error(tmp_path, stub_tailoring):
    """A skill with no primitives cannot route a single tool call."""
    P = _load(PROXY, "_arm_no_frozen")
    cand = _candidate(tmp_path, store_skill=True)
    (cand / "primitive_tools" / "functions.py").unlink()
    a = P.Adapter()
    a.apply(cand)
    assert a._deploy_error and "primitive_tools" in a._deploy_error


# --- apply() must never raise -----------------------------------------------------------

def test_apply_installs_the_tailoring_for_a_valid_candidate(tmp_path, stub_tailoring, monkeypatch):
    P = _load(PROXY, "_arm_apply_ok")
    # Stop after install(): the store deploy needs live services.
    monkeypatch.setattr(P, "_blackbox_env",
                        lambda: (_ for _ in ()).throw(RuntimeError("no stack")))
    a = P.Adapter()
    a.apply(_candidate(tmp_path, store_skill=True))
    assert "install" in stub_tailoring


def test_apply_never_raises_when_the_deploy_fails(tmp_path, stub_tailoring, monkeypatch):
    """cap-evolve enters live() inline, so a raise aborts the whole run with the budget half
    spent over one flaky restart. It must be recorded instead."""
    P = _load(PROXY, "_arm_apply_raise")
    monkeypatch.setattr(P, "_blackbox_env",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    a = P.Adapter()
    a.apply(_candidate(tmp_path, store_skill=True))      # must not raise
    assert a._deploy_error and "boom" in a._deploy_error


def test_a_deploy_error_errors_the_rollouts_so_the_candidate_is_excluded(tmp_path):
    """An errored rollout is EXCLUDED by the harness; a 0.0 would be recorded as a measurement.
    That difference is the whole point of not raising. Checked BEFORE the tau2 imports, so a
    dead stack does not need an importable benchmark to be reported."""
    from cap_evolve import Task

    P = _load(PROXY, "_arm_errored")
    a = P.Adapter()
    a._deploy_error = "stack down"
    tasks = [Task(id="9", input="9")]
    out = a.run_batch(tasks, tmp_path, seed=0)
    assert out["9"].error and "stack down" in out["9"].error
    trials = a.run_trials(tasks, tmp_path, n_trials=3, base_seed=0)
    assert len(trials["9"]) == 3 and all(t.error for t in trials["9"])


# --- delivery wiring --------------------------------------------------------------------

def test_the_proxy_arm_registers_its_own_domain_and_agent():
    """A separate domain name is what lets a run dir say WHICH arm produced a number."""
    P = _load(PROXY, "_arm_names")
    D = _load(DIRECT, "_direct_names")
    assert P.DOMAIN == "airline_skillberry"
    assert P.AGENT == "llm_agent_skillberry"
    assert D.DOMAIN == "airline" and P.DOMAIN != D.DOMAIN


def test_proxy_concurrency_defaults_low(monkeypatch):
    """Every agent call funnels through ONE proxy and ONE store process."""
    monkeypatch.delenv("TAU2_MAX_CONCURRENCY", raising=False)
    P = _load(PROXY, "_arm_conc")
    a = P.Adapter()
    assert a._max_concurrency() == 4
    monkeypatch.setenv("TAU2_MAX_CONCURRENCY", "7")
    assert a._max_concurrency() == 7, "an explicit value must win"


def test_the_proxy_agent_args_carry_no_route_of_ours():
    """The proxy route and this rollout's context header are added by the tailoring's agent
    factory, the only place that knows the env_id. Anything here would fight it."""
    P = _load(PROXY, "_arm_args")
    args = P.Adapter()._agent_llm_args("ibm/skillberry-local")
    assert args == {"temperature": 0.0}
    for k in ("api_base", "base_url", "api_key"):
        assert k not in args


def test_verify_is_declared_only_by_the_proxy_arm(stub_tailoring):
    """The direct arm patches nothing and depends on no private tau2 seam, so it has nothing to
    assert — and `check` must not invoke a seam contract for it."""
    P = _load(PROXY, "_arm_verify_bb")
    D = _load(DIRECT, "_arm_verify_direct")
    assert P.Adapter().verify() == {"notes": ["stub"]}
    assert stub_tailoring == ["verify"]
    assert not hasattr(D.Adapter(), "verify"), "the direct adapter must declare no verify()"
