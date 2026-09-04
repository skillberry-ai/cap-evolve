"""The production tau2_airline adapter (examples/tau2_airline/adapters/adapter.py — the one
actually run by capevolve.yaml with the RITS/proxy-routed ``aws/gpt-oss-120b`` target model
and ``run_trials``) hardcoded ``cost_usd=agent_cost + user_cost`` and ``tokens=0``, so every
evaluate/optimization/intake event reported $0.00 despite real token counts and real elapsed
time — exactly the bug already fixed in ``templates/adapters/tau2_bench/adapter.py`` (see
``test_tau2_eval_cost.py``) but never ported to the example that production runs actually use.

This mirrors that fix's tests against the production adapter to prove the port landed.
"""

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "examples" / "tau2_airline" / "adapters" / "adapter.py"


def _load_adapter_module():
    for p in (REPO / "core", ADAPTER.parent, ADAPTER.parent.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    llm_utils = types.ModuleType("tau2.utils.llm_utils")

    def get_token_usage(messages):
        usage = {"completion_tokens": 0, "prompt_tokens": 0}
        for m in messages:
            u = getattr(m, "usage", None)
            if u is None:
                continue
            usage["completion_tokens"] += u["completion_tokens"]
            usage["prompt_tokens"] += u["prompt_tokens"]
        return usage

    llm_utils.get_token_usage = get_token_usage
    for name, mod in (
        ("tau2", types.ModuleType("tau2")),
        ("tau2.utils", types.ModuleType("tau2.utils")),
        ("tau2.utils.llm_utils", llm_utils),
    ):
        sys.modules.setdefault(name, mod)

    spec = importlib.util.spec_from_file_location("_tau2_airline_adapter_cost", ADAPTER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Msg:
    def __init__(self, cost=None, usage=None):
        self.cost = cost
        self.usage = usage


class _Sim:
    def __init__(self, agent_cost, user_cost, messages):
        self.agent_cost = agent_cost
        self.user_cost = user_cost
        self._messages = messages

    def get_messages(self):
        return self._messages


_USAGE = {"prompt_tokens": 100, "completion_tokens": 20}


def test_priced_run_is_reported_as_before():
    mod = _load_adapter_module()
    sim = _Sim(1.25, 0.75, [_Msg(cost=1.0, usage=_USAGE), _Msg(cost=1.0, usage=_USAGE)])
    cost, tokens, meta = mod._cost_and_tokens(sim)
    assert cost == 2.0
    assert meta["cost_source"] == "tau2"
    assert tokens == 240, "tokens must be recovered, not hardcoded to 0"


def test_unpriced_run_reports_tokens_and_says_it_is_unpriced():
    """The bug: RITS/proxy target models (aws/gpt-oss-120b) go unpriced and this used to
    be indistinguishable from a genuinely free run — cost_usd read 0.0 either way."""
    mod = _load_adapter_module()
    sim = _Sim(None, None, [_Msg(cost=None, usage=_USAGE), _Msg(cost=None, usage=_USAGE)])
    cost, tokens, meta = mod._cost_and_tokens(sim)
    assert cost == 0.0
    assert meta["cost_source"] == "unpriced"
    assert meta["messages_missing_cost"] == 2
    assert tokens == 240, "tokens are the honest fallback unit and must survive"


def test_no_cost_is_ever_invented_from_a_rate_table():
    mod = _load_adapter_module()
    sim = _Sim(None, None, [_Msg(cost=None, usage={"prompt_tokens": 10**6,
                                                   "completion_tokens": 10**6})])
    cost, tokens, meta = mod._cost_and_tokens(sim)
    assert cost == 0.0
    assert tokens == 2_000_000
    src = ADAPTER.read_text(encoding="utf-8")
    for banned in ("completion_cost", "cost_per_token", "model_cost", "litellm.model_prices"):
        assert banned not in src, f"{banned} would synthesize a price"


def test_cost_metadata_reaches_the_rollout():
    src = ADAPTER.read_text(encoding="utf-8")
    assert "cost_usd=cost_usd" in src and "tokens=tokens" in src
    assert "**cost_meta," in src, "cost_source must land in Rollout.metadata"
    assert "tokens=0," not in src, "the hardcoded zero must be gone"
    assert "float(agent_cost) + float(user_cost)" not in src, "the unguarded sum must be gone"


def test_a_sim_whose_messages_explode_still_yields_a_rollout():
    mod = _load_adapter_module()

    class _Bad(_Sim):
        def get_messages(self):
            raise RuntimeError("tau2 internals changed")

    cost, tokens, meta = mod._cost_and_tokens(_Bad(None, None, []))
    assert (cost, tokens) == (0.0, 0)
    assert meta["cost_source"] == "unpriced"


class _TermReason:
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    UNEXPECTED_ERROR = "unexpected_error"
    USER_STOP = "user_stop"


class _RewardInfo:
    def __init__(self, reward):
        self.reward = reward

    def model_dump(self, mode="json"):
        return {"reward": self.reward}


class _RollMsg:
    def __init__(self, role, content, cost=None, usage=None):
        self.role = role
        self.content = content
        self.cost = cost
        self.usage = usage

    def model_dump(self):
        return {"role": self.role, "content": self.content}


class _RollSim:
    def __init__(self, messages, reward=0.0, term=_TermReason.USER_STOP,
                 agent_cost=None, user_cost=None):
        self.task_id = "7"
        self.reward_info = _RewardInfo(reward)
        self.agent_cost = agent_cost
        self.user_cost = user_cost
        self.termination_reason = term
        self._messages = messages

    def get_messages(self):
        return self._messages


def _load_adapter_module_with_termination_reason():
    sim_mod = types.ModuleType("tau2.data_model.simulation")
    sim_mod.TerminationReason = _TermReason
    sys.modules["tau2.data_model.simulation"] = sim_mod
    return _load_adapter_module()


def test_sim_to_rollout_reports_real_tokens_and_unpriced_cost_for_gptoss():
    """End-to-end: a real-token, unpriced (RITS/proxy) simulation must NOT collapse to a
    Rollout that reads exactly like a genuinely free/zero-usage run."""
    mod = _load_adapter_module_with_termination_reason()
    messages = [
        _RollMsg("assistant", "booking your flight", usage={"prompt_tokens": 500_000,
                                                             "completion_tokens": 300_000}),
    ]
    sim = _RollSim(messages, reward=1.0, agent_cost=None, user_cost=None)
    rollout = mod.Adapter._sim_to_rollout(sim)
    assert rollout.cost_usd == 0.0
    assert rollout.tokens == 800_000, "real token usage must reach the Rollout"
    assert rollout.metadata["cost_source"] == "unpriced"
