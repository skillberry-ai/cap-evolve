"""tau2 runs reported $0.0000 of eval spend despite real rollouts, so they could not be costed.

`sim.agent_cost` / `sim.user_cost` come from tau2's `get_cost`, which is ALL-OR-NOTHING: it
returns None the moment ANY non-tool message lacks a per-message `cost`. The adapter's
`sim.agent_cost or 0.0` collapsed that None into 0.0, so "the provider did not price this"
and "this was free" produced the identical number — and `litellm_proxy/...` gateway aliases,
which is what every CI benchmark uses, are exactly the unpriced case. Run 30684845463 spent
real money on 10 tasks × 3 iterations and reported eval $0.00 (only the $25.90 optimizer
cost was visible).

The adapter now recovers tokens (which tau2 exposes per-message and the adapter was throwing
away with a hardcoded `tokens=0`), salvages a partial cost from whatever the provider DID
price, and records `cost_source` so a 0.0 can be read as "unpriced" rather than "free". It
deliberately does not price tokens from a public rate table: the gateway's real rates are
not knowable here, and a fabricated dollar figure sitting next to measured ones is worse
than an absent one.
"""

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "templates" / "adapters" / "tau2_bench" / "adapter.py"


def _load_adapter_module():
    """Import the tau2 adapter with `cap_evolve`/`model_config` real and `tau2` stubbed.

    tau2-bench is a heavy external install that CI does not have; the cost helper only
    touches `tau2.utils.llm_utils.get_token_usage`, so that one function is stubbed.
    """
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

    spec = importlib.util.spec_from_file_location("_tau2_adapter_cost", ADAPTER)
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
    assert cost == 2.0, "tau2's own total wins when it has one"
    assert meta["cost_source"] == "tau2"
    assert tokens == 240, "tokens must be recovered, not hardcoded to 0"


def test_unpriced_run_reports_tokens_and_says_it_is_unpriced():
    """The bug: this used to be indistinguishable from a genuinely free run."""
    mod = _load_adapter_module()
    sim = _Sim(None, None, [_Msg(cost=None, usage=_USAGE), _Msg(cost=None, usage=_USAGE)])
    cost, tokens, meta = mod._cost_and_tokens(sim)
    assert cost == 0.0
    assert meta["cost_source"] == "unpriced", "0.0 must be readable as unknown, not free"
    assert meta["messages_missing_cost"] == 2
    assert tokens == 240, "tokens are the honest fallback unit and must survive"


def test_partially_priced_run_salvages_what_the_provider_gave():
    """tau2 discards the whole run's cost over ONE unpriced message; partial beats zero."""
    mod = _load_adapter_module()
    sim = _Sim(None, None, [
        _Msg(cost=0.4, usage=_USAGE),
        _Msg(cost=None, usage=_USAGE),
        _Msg(cost=0.1, usage=_USAGE),
    ])
    cost, tokens, meta = mod._cost_and_tokens(sim)
    assert abs(cost - 0.5) < 1e-9
    assert meta["cost_source"] == "partial_messages"
    assert meta["messages_missing_cost"] == 1
    assert tokens == 360


def test_no_cost_is_ever_invented_from_a_rate_table():
    """A fabricated dollar figure next to measured ones is worse than an absent one."""
    mod = _load_adapter_module()
    sim = _Sim(None, None, [_Msg(cost=None, usage={"prompt_tokens": 10**6,
                                                   "completion_tokens": 10**6})])
    cost, tokens, meta = mod._cost_and_tokens(sim)
    assert cost == 0.0, "two million tokens must not become a guessed dollar amount"
    assert tokens == 2_000_000
    src = ADAPTER.read_text(encoding="utf-8")
    for banned in ("completion_cost", "cost_per_token", "model_cost", "litellm.model_prices"):
        assert banned not in src, f"{banned} would synthesize a price"


def test_missing_usage_is_counted_not_silently_dropped():
    mod = _load_adapter_module()
    sim = _Sim(None, None, [_Msg(cost=None, usage=None), _Msg(cost=None, usage=_USAGE)])
    cost, tokens, meta = mod._cost_and_tokens(sim)
    assert tokens == 120, "usage-bearing messages still count"
    assert meta["messages_missing_usage"] == 1


def test_a_sim_whose_messages_explode_still_yields_a_rollout():
    """Cost accounting must never be able to fail a rollout that otherwise succeeded."""
    mod = _load_adapter_module()

    class _Bad(_Sim):
        def get_messages(self):
            raise RuntimeError("tau2 internals changed")

    cost, tokens, meta = mod._cost_and_tokens(_Bad(None, None, []))
    assert (cost, tokens) == (0.0, 0)
    assert meta["cost_source"] == "unpriced"


def test_cost_metadata_reaches_the_rollout():
    """The flags are only useful if they are actually attached to the record."""
    src = ADAPTER.read_text(encoding="utf-8")
    assert "cost_usd=cost_usd" in src and "tokens=tokens" in src
    assert "**cost_meta," in src, "cost_source must land in Rollout.metadata"
    assert "tokens=0," not in src, "the hardcoded zero must be gone"


def test_the_all_or_nothing_upstream_behavior_is_documented():
    """If a tau2 upgrade makes get_cost partial, this fallback can be simplified — the
    reason it exists must be findable in the code, not just in a PR."""
    src = ADAPTER.read_text(encoding="utf-8")
    assert "ALL-OR-NOTHING" in src
    assert "get_cost" in src
