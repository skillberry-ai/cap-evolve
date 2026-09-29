"""The tau2 seam contract, run against the INSTALLED benchmark.

Marked `seam_contract` and excluded from the default run, because it answers a different
question from every other test here:

    a unit test failing  -> OUR code is wrong
    THIS failing         -> UPSTREAM MOVED

The benchmark is onboarded at latest `main`, not a pin, so that distinction is the whole point.
Two of the seams the tailoring depends on fail SILENTLY — if `llm_args` stops reaching the
client the context header vanishes and the proxy falls back to one shared session; if the
pre-evaluation merge stops firing the DB check goes false. Either reads as a worse capability
rather than broken wiring, so CI asserts them before a single rollout is paid for.

    pytest -m seam_contract core/tests/test_tau2_seam_contract.py

Needs tau2 importable and NO services — everything here is inspection plus in-process stubs.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "examples" / "tau2_airline" / "blackbox" / "adapters" / "tau2_tailoring.py"

pytestmark = pytest.mark.seam_contract

tau2 = pytest.importorskip(
    "tau2", reason="the seam contract needs the benchmark installed (see ci_setup.sh)")


def _tailoring():
    if str(MOD.parent) not in sys.path:
        sys.path.insert(0, str(MOD.parent))
    spec = importlib.util.spec_from_file_location("_tau2_tailoring_contract", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verify_passes_against_the_installed_tau2():
    """The single most valuable assertion in the repo for this arm: vanilla tau2 still accepts
    the tailoring. On failure the message names the seam, the version+commit, and the cost."""
    T = _tailoring()
    out = T.verify()
    assert out["notes"], out
    # The version+commit note is what makes a failure actionable rather than a mystery.
    assert any("tau2" in n for n in out["notes"]), out


def test_install_is_idempotent_against_the_real_registry():
    """register_domain RAISES on a duplicate name, and every phase is a fresh process that
    loads the adapter again — so re-entry must be a no-op, not an error."""
    T = _tailoring()
    T.install()
    T.install()
    from tau2.registry import registry

    assert T.DOMAIN in registry.get_domains()
    assert registry.get_agent_factory(T.AGENT_NAME) is not None


def test_the_arms_domain_is_side_effect_free():
    """The evaluator re-invokes the registered domain constructor 1-3 MORE times per rollout. If
    building it started a remote session, each evaluation would orphan remote environments and
    make this rollout's env_id ambiguous."""
    T = _tailoring()
    T.install()
    from tau2.registry import registry

    ctor = registry.get_env_constructor(T.DOMAIN)
    env_a, env_b = ctor(), ctor()          # would POST /start_environment if coupled
    assert env_a is not env_b
    assert env_a.get_domain_name() == T.DOMAIN
    # Real tools matter: the evaluator's set_state replay rebuilds a local DB through them, and
    # that reconstruction is what makes db_match computable under this arm.
    assert env_a.get_tools(), "the arm's environment must carry tau2's real airline tools"


def test_a_moved_passthrough_seam_is_caught_rather_than_silently_tolerated():
    """Simulate the likeliest upstream hardening — `generate` filtering unknown kwargs — and
    assert verify() REFUSES. A contract that can only pass is worthless."""
    T = _tailoring()
    import tau2.agent.llm_agent as agent_mod
    import tau2.utils.llm_utils as llm_utils

    original = llm_utils.generate

    def hardened(model, messages, tools=None, tool_choice=None, call_name=None, **kw):
        kw.pop("extra_headers", None)
        return original(model, messages, tools=tools, tool_choice=tool_choice,
                        call_name=call_name, **kw)

    llm_utils.generate = hardened
    agent_had = hasattr(agent_mod, "generate")
    agent_original = getattr(agent_mod, "generate", None)
    if agent_had:
        agent_mod.generate = hardened
    try:
        with pytest.raises(T.SeamError) as ei:
            T.verify()
        msg = str(ei.value)
        assert "passthrough" in msg
        assert "env_id" in msg, "the message must say what breaking this actually costs"
    finally:
        llm_utils.generate = original
        if agent_had:
            agent_mod.generate = agent_original
