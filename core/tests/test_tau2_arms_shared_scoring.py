"""The two tau2-airline arms share ONE scoring/feedback implementation (#479).

`direct/adapters/adapter.py` and `spa/adapters/adapter.py` used to carry ~250 lines of
scoring and gold-safe feedback byte-identically. A fix to the STOP-leak regex or to a
`_localize_*` heuristic had to be applied twice and drifted silently if only one copy was
touched. Both now mix in `Tau2ScoringMixin` from `examples/.../scoring.py`.

This test pins the three properties that make that refactor safe:

1. both arms really inherit the shared mixin, and no longer define the moved members;
2. `score()` produces IDENTICAL output on both arms across the interesting branches —
   the check that catches a hook accidentally binding to the shared copy instead of the
   arm's override;
3. the shared module contains no hard-coded ``Adapter.`` reference. That was a real bug
   found while moving the code: `_derive_total_cost` was a ``@staticmethod`` calling
   ``Adapter._iter_agent_tool_calls``, which resolved inside `adapter.py` and raised
   ``NameError`` once moved — swallowed by `_build_feedback`'s ``except Exception`` and
   silently degrading the feedback to its generic fallback.

`_user_profile_facts` deliberately stays per-arm, and `_native_sims_enabled` /
`_split_of` / `_sim_save_path` deliberately stay inline in every tau2 adapter — see
`test_tau2_native_sims.py`, which extracts that region textually from each `adapter.py`.
"""

import ast
import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ARMS = REPO / "examples" / "skillberry_benchmarks_tau2_airline"
SHARED = ARMS / "scoring.py"
ARM_NAMES = ("direct", "spa")

MOVED = ("score", "_sim_to_rollout", "_build_feedback", "_derive_total_cost",
         "_localize_action", "_localize_communicate", "_iter_agent_tool_calls",
         "trajectories")


@pytest.fixture(autouse=True)
def _isolated_modules():
    """Restore every module name this test binds.

    It stubs ``gateway`` and imports ``scoring`` plus two same-named adapters. Leaving any
    of those in ``sys.modules`` would hand a later test the wrong module — the trap
    `test_tau2_native_sims.py` documents for the shared ``tau2`` stubs.
    """
    names = ("gateway", "scoring", "tau2", "tau2.data_model",
             "tau2.data_model.simulation")
    before = {k: sys.modules.get(k) for k in names}
    paths = list(sys.path)
    try:
        yield
    finally:
        for k in [k for k in sys.modules if k.startswith("_arm_adapter_")]:
            del sys.modules[k]
        for k, v in before.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.path[:] = paths


def _load_arm(arm: str):
    """Import an arm's adapter with ``gateway`` stubbed; no network, no credentials."""
    adapters = ARMS / arm / "adapters"
    # ARMS itself carries scoring.py in the repo; setup.sh copies it beside adapter.py in a
    # deployed project, where the adapter's own directory already covers the import.
    for p in (REPO / "core", adapters, ARMS):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    gw = types.ModuleType("gateway")
    gw.agent_model = gw.user_model = lambda: "aws/gpt-oss-120b"
    for name in ("llm_args", "agent_llm_args", "upstream_llm_args"):
        setattr(gw, name, lambda *a, **k: {})
    gw.llm_args_for = lambda m: {}
    gw.load_env = gw.register_zero_cost = lambda *a, **k: None
    gw.gateway_credentials = lambda *a, **k: ("http://stub", "stub")
    sys.modules["gateway"] = gw
    # _sim_to_rollout imports tau2 lazily for TerminationReason; CI has no tau2 install.
    for name, mod in (("tau2", types.ModuleType("tau2")),
                      ("tau2.data_model", types.ModuleType("tau2.data_model")),
                      ("tau2.data_model.simulation", types.ModuleType("tau2.data_model.simulation"))):
        sys.modules.setdefault(name, mod)
    sys.modules["tau2.data_model.simulation"].TerminationReason = types.SimpleNamespace(
        TASK_FAILED="task_failed")
    sys.modules.pop("scoring", None)          # re-import per arm; never reuse a cached copy
    spec = importlib.util.spec_from_file_location(f"_arm_adapter_{arm}", adapters / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Rollout:
    """Only the attributes ``score()`` reads."""

    def __init__(self, metadata=None, trace=None, error=None, cost_usd=0.0):
        self.metadata, self.trace, self.error = metadata or {}, trace, error
        self.cost_usd, self.output, self.tokens = cost_usd, None, 0
        self.task_id = "0"


class _Task:
    id = "0"


TRACE = [
    {"role": "assistant", "tool_calls": [
        {"name": "get_user_details", "arguments": {"user_id": "sara_doe_496"}}]},
    {"role": "tool", "content": '{"payment_methods": {"credit_card_1": {}},'
                                ' "reservations": ["ZFA04Y"]}'},
    {"role": "assistant", "tool_calls": [
        {"name": "book_reservation", "arguments": {
            "cabin": "basic economy", "insurance": "none", "payment_methods": "[]"}}]},
]

CASES = {
    "clean_pass": _Rollout({"tau2_reward": 1.0,
                            "tau2_reward_info": {"db_check": {"db_match": True}}}, TRACE),
    "no_breakdown": _Rollout({"tau2_reward": 0.25, "tau2_reward_info": {}}, TRACE),
    "db_mismatch": _Rollout({"tau2_reward": 0.0,
                             "tau2_reward_info": {"db_check": {"db_match": False}}}, TRACE),
    "action_check": _Rollout({"tau2_reward": 0.0, "tau2_reward_info": {
        "db_check": {"db_match": False},
        "action_checks": [{"action_match": False, "action": {
            "name": "book_reservation",
            "compare_args": ["cabin", "insurance"]}}]}}, TRACE),
    "communicate": _Rollout({"tau2_reward": 0.5, "tau2_reward_info": {
        "communicate_checks": [{"met": False, "info": "total price"}]}}, TRACE),
    "nl_and_env": _Rollout({"tau2_reward": 0.0, "tau2_reward_info": {
        "nl_assertions": [{"met": False}], "env_assertions": [{"met": False}]}}, TRACE),
    "infra_error": _Rollout(error="tau2 terminated for an infrastructure reason"),
}


def _scores(arm: str) -> dict:
    mod = _load_arm(arm)
    adapter = mod.Adapter.__new__(mod.Adapter)      # no __init__: score() needs no state
    out = {}
    for name, rollout in CASES.items():
        s = adapter.score(_Task(), rollout)
        out[name] = (s.reward, s.feedback, tuple(m["name"] for m in (s.metrics or [])))
    return out


# --- the refactor actually happened ------------------------------------------------

def test_both_arms_mix_in_the_shared_scoring_module():
    assert SHARED.is_file(), f"missing shared module: {SHARED}"
    for arm in ARM_NAMES:
        mod = _load_arm(arm)
        bases = [b.__name__ for b in mod.Adapter.__mro__]
        assert "Tau2ScoringMixin" in bases, f"{arm}: Adapter does not mix in Tau2ScoringMixin"


@pytest.mark.parametrize("arm", ARM_NAMES)
def test_moved_members_are_not_redefined_in_the_arm(arm):
    """The point of #479: one source, not two. A re-added copy would shadow the mixin."""
    text = (ARMS / arm / "adapters" / "adapter.py").read_text()
    for name in MOVED:
        assert f"    def {name}(" not in text, (
            f"{arm}/adapters/adapter.py redefines {name}, which lives in scoring.py — "
            "that shadows the shared implementation and reintroduces the drift #479 fixed")


def test_shared_module_has_no_hardcoded_adapter_reference():
    """``Adapter`` is not a name in scoring.py; use ``cls.`` so overrides still resolve.

    Parsed with ``ast`` rather than grepped, so prose that merely mentions ``Adapter``
    (this module's own docstrings do) cannot fail the check while a real reference hides.
    """
    tree = ast.parse(SHARED.read_text())
    refs = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "Adapter"]
    assert not refs, (
        "scoring.py references the name Adapter at line(s) "
        f"{[n.lineno for n in refs]} — it raises NameError here, and _build_feedback's "
        "`except Exception` swallows it, silently degrading the feedback to its fallback")


# --- behaviour is identical across the arms, and correct ---------------------------

def test_the_arms_score_identically():
    """One implementation means one result. A hook bound to the wrong copy shows up here."""
    direct, spa = _scores("direct"), _scores("spa")
    assert direct == spa, "the arms disagree on score() despite sharing the implementation"


def test_the_shared_feedback_still_localises_each_failure_kind():
    """Guards the moved logic itself, not just that the two copies agree.

    The communicate case is the regression this caught during the move: with a broken
    ``_derive_total_cost`` lookup it silently fell back to the generic "1 required
    piece(s) of information" wording instead of naming the computed total.
    """
    s = _scores("spa")
    assert s["clean_pass"][1] == "Task reward: 1.000. All checks passed."
    assert "No detailed check breakdown" in s["no_breakdown"][1]
    assert "Database state does NOT match" in s["db_mismatch"][1]
    assert "Action-level defects" in s["action_check"][1]
    assert "did not state the computed total cost" in s["communicate"][1], (
        "communicate feedback fell back to the generic wording — _localize_communicate "
        "or _derive_total_cost is raising")
    assert "behavioral expectation" in s["nl_and_env"][1]
    assert "environment assertion" in s["nl_and_env"][1]
    assert "infrastructure reason" in s["infra_error"][1]
    assert s["infra_error"][0] == 0.0


@pytest.mark.parametrize("arm", ARM_NAMES)
def test_gold_values_are_never_echoed(arm):
    """The property this feedback stack exists to preserve.

    It may name the failing argument KEY and the agent's OWN wrong value; it must never
    surface the gold value sitting beside that key in ``reward_info``. Distinctive
    sentinels make a leak unmistakable.
    """
    mod = _load_arm(arm)
    adapter = mod.Adapter.__new__(mod.Adapter)
    rollout = _Rollout({"tau2_reward": 0.0, "tau2_reward_info": {
        "db_check": {"db_match": False},
        "action_checks": [{"action_match": False, "action": {
            "name": "book_reservation",
            "arguments": {"cabin": "GOLDCABIN_5f3a", "insurance": "GOLDINS_9b21"}}}]}}, TRACE)
    feedback = adapter.score(_Task(), rollout).feedback
    for gold in ("GOLDCABIN_5f3a", "GOLDINS_9b21"):
        assert gold not in feedback, f"{arm}: feedback leaked the gold value {gold!r}"
    # and it is still useful: the failing KEYS are named
    assert "cabin" in feedback and "insurance" in feedback, (
        f"{arm}: feedback named no argument key, so it carries no signal")


# --- the per-arm hook stays per-arm ------------------------------------------------

@pytest.mark.parametrize("arm", ARM_NAMES)
def test_user_profile_facts_stays_in_the_arm(arm):
    """It genuinely differs per arm; the mixin calls it as ``cls._user_profile_facts``."""
    text = (ARMS / arm / "adapters" / "adapter.py").read_text()
    assert "def _user_profile_facts(" in text, f"{arm}: the per-arm hook was moved out"
    assert "def _user_profile_facts(" not in SHARED.read_text(), (
        "scoring.py defines _user_profile_facts — it must stay per-arm or the arms would "
        "silently share one implementation")

# --- the moved code must not reference names that live in adapter.py ----------------

def test_shared_module_never_reaches_for_an_adapter_level_name():
    """No name that lives in `adapter.py` may be referenced from `scoring.py`.

    This is the exact bug class that bit twice while moving the code:
    `Adapter._iter_agent_tool_calls` (raised NameError, swallowed by `_build_feedback`'s
    `except Exception`, silently degrading feedback to its generic fallback) and `DOMAIN`
    in `_sim_to_rollout` (killed a live baseline). Both resolved fine *inside* adapter.py
    and only broke once relocated — so compare the two namespaces directly rather than
    relying on an optional linter.
    """
    shared_tree = ast.parse(SHARED.read_text())
    shared_defines = {n.name for n in ast.walk(shared_tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    shared_defines |= {t.id for n in ast.walk(shared_tree) if isinstance(n, ast.Assign)
                       for t in n.targets if isinstance(t, ast.Name)}
    shared_defines |= {a.asname or a.name.split(".")[0]
                       for n in ast.walk(shared_tree)
                       if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    referenced = {n.id for n in ast.walk(shared_tree)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}

    for arm in ARM_NAMES:
        tree = ast.parse((ARMS / arm / "adapters" / "adapter.py").read_text())
        arm_level = {n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        arm_level |= {t.id for n in tree.body if isinstance(n, ast.Assign)
                      for t in n.targets if isinstance(t, ast.Name)}
        # Class-body names too: `DOMAIN = DOMAIN` on the Adapter is reachable only through
        # `cls.`/`self.`, so a bare reference to it from scoring.py is the same bug.
        for cls_node in (n for n in tree.body if isinstance(n, ast.ClassDef)):
            arm_level |= {t.id for n in cls_node.body if isinstance(n, ast.Assign)
                          for t in n.targets if isinstance(t, ast.Name)}
            arm_level |= {n.target.id for n in cls_node.body
                          if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
        leaked = sorted((referenced & arm_level) - shared_defines)
        assert not leaked, (
            f"scoring.py references {leaked}, which {arm}/adapters/adapter.py defines but "
            "scoring.py does not — that raises NameError at runtime. Bind it as a class "
            "attribute or method on the Adapter and reach it through `cls.`/`self.`")


@pytest.mark.parametrize("arm", ARM_NAMES)
def test_sim_to_rollout_stamps_the_arms_own_domain(arm):
    """`_sim_to_rollout` is shared but the domain it stamps is per-arm.

    It is a classmethod reading ``cls.DOMAIN`` precisely so each Adapter's binding wins; a
    module-level constant in scoring.py would stamp one arm's domain onto both.
    """
    mod = _load_arm(arm)
    expected = {"direct": "airline", "spa": "airline_skillberry"}[arm]
    assert mod.Adapter.DOMAIN == expected, f"{arm}: Adapter.DOMAIN is {mod.Adapter.DOMAIN!r}"

    class _Sim:
        """The few attributes _sim_to_rollout reads off a tau2 SimulationRun."""

        task_id = "0"
        reward_info = None
        termination_reason = None
        agent_cost = user_cost = 0.0
        messages: list = []

    rollout = mod.Adapter._sim_to_rollout(_Sim())
    assert rollout.metadata["domain"] == expected, (
        f"{arm}: rollout metadata stamped {rollout.metadata['domain']!r}, not {expected!r} — "
        "cls.DOMAIN is not resolving to the arm's binding")
