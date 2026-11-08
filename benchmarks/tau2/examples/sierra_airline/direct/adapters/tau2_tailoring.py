"""tau2 tailoring — supplies what vanilla tau2 lacks for the DIRECT arm, from OUTSIDE the clone.

vendor/tau2-bench stays byte-identical to upstream: an edited benchmark is no longer the
benchmark, and its numbers stop being comparable to anyone else's tau2 results. Everything
here goes through tau2's public extension points (the registry) plus one narrow wrapper.

Importing this module has NO side effects (no tau2 import, no registration, no network):
`cap-evolve check` imports the adapter offline. The one entry point is `install(arm)`,
called from the adapter's apply(). It is IDEMPOTENT — every phase is a fresh process, the
loop's iterations share one, and each tau2 registration raises on a duplicate name.

  T1  domain + task set "airline_candidate": an env factory that execs the CURRENT
      candidate's tools/tools.py fresh on every construction, on a freshly loaded FlightDB
      (trials run in parallel; a shared DB leaks state between them).
  T2  GOLD IS PRISTINE: EnvironmentEvaluator.calculate_reward is wrapped so that, inside
      one call, the 1st construction (PREDICTED) is the candidate env and the 2nd (GOLD) is
      tau2's own "airline" env. Otherwise a candidate that breaks a write tool changes both
      sides of the DB check and scores as if correct.
  T3  the agent stays tau2's stock "llm_agent".

install() first checks that tau2 is at TAU2_REFERENCE_SHA, the commit this module was created
from, then ASSERTs the seams it relies on (S1–S10) offline, before anything is registered; a
failure raises SeamError naming the commit or the seam.
"""

from __future__ import annotations

import functools
import importlib.util
import inspect
import itertools
import sys
import threading
from pathlib import Path

DIRECT_DOMAIN = "airline_candidate"
_PRISTINE_DOMAIN = "airline"
_MARK = "_capevolve_tailoring"          # attribute set on every wrapper/factory we install

_COMMIT_FILE = Path(__file__).resolve().parents[3] / "vendor" / "tau2-bench.COMMIT"

_lock = threading.Lock()
_load_seq = itertools.count()
_tls = threading.local()               # .reward_scope: {"n": constructions} during calculate_reward
_state: dict = {"tools_path": None, "installed": set()}


class SeamError(RuntimeError):
    """A tau2 API this module depends on is not what the seam table says."""

# The tau2 commit this module (and adapter.py beside it) was created from, when the benchmark
# was onboarded with ../../PROMPT.md. Must equal TAU2_REFERENCE_SHA in ../setup.sh. install()
# refuses any other commit: the seams were located and verified on this one only.
TAU2_REFERENCE_SHA = "4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699"


def _tau2_head() -> str:
    """HEAD of the tau2 checkout that `import tau2` resolves to, read from its .git (no git
    subprocess). "" when tau2 is not a git checkout or HEAD cannot be read."""
    try:
        import tau2

        root = Path(tau2.__file__).resolve().parents[2]
        git = root / ".git"
        if git.is_file():                                   # a worktree / submodule pointer
            git = (root / git.read_text().split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text().strip()
        if not head.startswith("ref:"):
            return head                                     # detached: the SHA itself
        ref = head.split(" ", 1)[1]
        if (git / ref).is_file():
            return (git / ref).read_text().strip()
        for line in (git / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    except Exception:  # noqa: BLE001
        pass
    return ""


def assert_pinned_tau2() -> None:
    """Refuse to tailor a tau2 other than TAU2_REFERENCE_SHA (run ../setup.sh to check it out)."""
    head = _tau2_head()
    if head != TAU2_REFERENCE_SHA:
        raise SeamError(
            f"tau2 is at {head or 'an unknown commit'}, but this snapshot was created from "
            f"TAU2_REFERENCE_SHA {TAU2_REFERENCE_SHA}. Run its setup.sh to check that commit out; "
            f"a newer tau2 needs a new onboarding with PROMPT.md.")



def tau2_sha() -> str:
    try:
        return _COMMIT_FILE.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def _seam(seam_id: str, ok: bool, what: str) -> None:
    if not ok:
        raise SeamError(f"seam {seam_id} failed at tau2 {tau2_sha()}: {what}")


# ---------------------------------------------------------------------------------------
# current candidate (set by the adapter's apply())
# ---------------------------------------------------------------------------------------

def set_candidate(tools_path) -> None:
    """Point the airline_candidate factory at a candidate's tools/tools.py."""
    _state["tools_path"] = Path(tools_path).resolve() if tools_path else None


def _finish_models(mod, name: str) -> None:
    """Resolve forward references in pydantic models the candidate defines, while its module
    is still registered: pydantic finds the module in sys.modules to do that, and without it
    tau2's `openai_schema` (the schema the agent is sent) fails with "not fully defined"."""
    from pydantic import BaseModel

    for obj in list(vars(mod).values()):
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == name:
            obj.model_rebuild()


def load_toolkit_class(tools_path):
    """Exec tools.py fresh (unique module name per load) and return a REMOVE_TOOLS-aware
    subclass of its AirlineTools. Filtering is done on the `tools` property (what live
    calls dispatch through), get_tools() and has_tool() — never by deleting attributes."""
    path = Path(tools_path)
    name = f"_capevolve_candidate_tools_{next(_load_seq)}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load candidate tools from {path}")
    mod = importlib.util.module_from_spec(spec)
    # Registered ONLY while the file executes, and while its own pydantic models are
    # finished; always unregistered afterwards. A load runs once per trial in a process
    # shared by the whole run, so an entry left per load would grow without bound. Nothing
    # needs it later: tau2 builds tool schemas from the functions' annotation objects
    # (environment/tool.py), not by looking the module up.
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
        _finish_models(mod, name)
    finally:
        sys.modules.pop(name, None)
    base = getattr(mod, "AirlineTools", None)
    if base is None:
        raise ImportError(f"{path} defines no AirlineTools class")
    removed = frozenset(getattr(mod, "REMOVE_TOOLS", None) or ())

    class CandidateAirlineTools(base):
        @property
        def tools(self):
            return {n: f for n, f in super().tools.items() if n not in removed}

        def get_tools(self, include=None):
            return super().get_tools(include)

        def has_tool(self, tool_name: str) -> bool:
            return tool_name in self.tools

    CandidateAirlineTools.__name__ = base.__name__
    CandidateAirlineTools.__qualname__ = base.__qualname__
    return CandidateAirlineTools


def _airline_policy() -> str:
    from tau2.domains.airline.utils import AIRLINE_POLICY_PATH

    with open(AIRLINE_POLICY_PATH, "r") as fp:
        return fp.read()


# ---------------------------------------------------------------------------------------
# T1 — the candidate environment factory
# ---------------------------------------------------------------------------------------

def _candidate_environment(db=None, solo_mode: bool = False, **env_kwargs):
    if solo_mode:
        raise ValueError("Airline domain does not support solo mode")
    scope = getattr(_tls, "reward_scope", None)
    if scope is not None:
        scope["n"] += 1
        if scope["n"] >= 2:          # GOLD inside calculate_reward: tau2's own airline env
            from tau2.registry import registry

            return registry.get_env_constructor(_PRISTINE_DOMAIN)()
    from tau2.domains.airline.data_model import FlightDB
    from tau2.domains.airline.utils import AIRLINE_DB_PATH
    from tau2.environment.environment import Environment

    tools_path = _state["tools_path"]
    if tools_path is None:
        raise RuntimeError("no candidate set: the adapter's apply() must call set_candidate()")
    toolkit_cls = load_toolkit_class(tools_path)
    if db is None:
        db = FlightDB.load(AIRLINE_DB_PATH)   # FRESH DB on every construction
    return Environment(
        domain_name=DIRECT_DOMAIN,
        policy=_airline_policy(),
        tools=toolkit_cls(db),
    )


setattr(_candidate_environment, _MARK, True)


def _airline_tasks(task_split_name="base"):
    from tau2.domains.airline.environment import get_tasks

    return get_tasks(task_split_name)


# ---------------------------------------------------------------------------------------
# T2 — pristine gold
# ---------------------------------------------------------------------------------------

def _install_pristine_gold() -> None:
    from tau2.evaluator.evaluator_env import EnvironmentEvaluator

    current = EnvironmentEvaluator.__dict__["calculate_reward"]
    func = current.__func__
    if getattr(func, _MARK, False):
        return
    original = func

    @functools.wraps(original)
    def calculate_reward(cls, environment_constructor, *args, **kwargs):
        if not getattr(environment_constructor, _MARK, False):
            return original(cls, environment_constructor, *args, **kwargs)
        previous = getattr(_tls, "reward_scope", None)
        _tls.reward_scope = {"n": 0}
        try:
            return original(cls, environment_constructor, *args, **kwargs)
        finally:
            _tls.reward_scope = previous

    setattr(calculate_reward, _MARK, True)
    EnvironmentEvaluator.calculate_reward = classmethod(calculate_reward)


# ---------------------------------------------------------------------------------------
# seam ASSERTs (S1–S10), all offline
# ---------------------------------------------------------------------------------------

def _params(fn) -> set:
    return set(inspect.signature(fn).parameters)


def assert_seams() -> None:
    import tau2.runner
    import tau2.runner.batch as batch
    import tau2.runner.build as build
    import tau2.utils.llm_utils as llm_utils
    from tau2.registry import registry

    # S1 batch runner
    _seam("S1", {"config", "tasks", "save_path"} <= _params(tau2.runner.run_tasks),
          "tau2.runner.run_tasks lacks config/tasks/save_path")

    # S2 run config
    from tau2.data_model.simulation import TextRunConfig

    need = {"domain", "agent", "llm_agent", "llm_args_agent", "user", "llm_user",
            "llm_args_user", "num_trials", "max_steps", "max_errors", "max_concurrency",
            "seed", "verbose_logs", "workers"}
    missing = need - set(TextRunConfig.model_fields)
    _seam("S2", not missing, f"TextRunConfig lacks fields {sorted(missing)}")

    # S3 registry
    want = {
        "register_domain": {"get_environment", "name"},
        "register_tasks": {"get_tasks", "name", "get_task_splits"},
        "register_agent_factory": {"factory", "name", "task_filter", "metadata"},
        "get_domains": set(),
        "get_task_sets": set(),
        "get_env_constructor": {"name"},
        "get_agent_factory": {"name"},
    }
    for meth, params in want.items():
        fn = getattr(registry, meth, None)
        _seam("S3", callable(fn) and params <= _params(fn),
              f"registry.{meth} missing or lacks parameters {sorted(params)}")

    # S4 agent factory call
    src = inspect.getsource(build.build_agent)
    _seam("S4", "agent_factory(" in src and "llm_args=llm_args" in src and "task=task" in src,
          "build_agent's agent_factory(...) call does not pass llm_args and task")

    # S5 stock LLM agent: llm_args reach litellm unfiltered (offline proof)
    from tau2.agent.llm_agent import create_llm_agent
    from tau2.data_model.message import UserMessage

    class _Probe(Exception):
        pass

    seen: dict = {}

    def _stub(**kwargs):
        seen.update(kwargs)
        raise _Probe()

    from loguru import logger

    orig = llm_utils.completion
    llm_utils.completion = _stub
    logger.disable("tau2.utils.llm_utils")   # generate() logs the probe's deliberate raise
    try:
        agent = create_llm_agent(tools=[], domain_policy="p", llm="probe",
                                 llm_args={"extra_headers": {"x-probe": "1"}})
        try:
            agent.generate_next_message(UserMessage(role="user", content="hi"),
                                        agent.get_init_state())
        except _Probe:
            pass
    finally:
        llm_utils.completion = orig
        logger.enable("tau2.utils.llm_utils")
    _seam("S5", seen.get("extra_headers") == {"x-probe": "1"},
          "llm_args did not reach litellm.completion unfiltered")

    # S6 trajectory finalize
    from tau2.orchestrator.orchestrator import Orchestrator

    _seam("S6", callable(getattr(Orchestrator, "get_trajectory", None)),
          "Orchestrator.get_trajectory missing")

    # S7 per-trial worker
    _seam("S7", inspect.isfunction(getattr(batch, "run_single_task", None))
          and "return run_single_task(" in inspect.getsource(batch),
          "tau2.runner.batch.run_single_task missing or not called by name")

    # S8 env constructions (inspect follows __wrapped__ on a second install)
    from tau2.evaluator.evaluator_env import EnvironmentEvaluator

    src = inspect.getsource(EnvironmentEvaluator.calculate_reward)
    p = src.find("predicted_environment = environment_constructor(")
    g = src.find("gold_environment = environment_constructor(")
    _seam("S8", 0 <= p < g, "calculate_reward does not build PREDICTED before GOLD")

    # S9 replay
    from tau2.environment import environment as env_mod

    src = inspect.getsource(env_mod)
    for s in ("Tool call id mismatch", "Tool message expected", "Tool message not expected"):
        _seam("S9", s in src, f"Environment.set_state lacks error string {s!r}")

    # S10 messages
    try:
        from tau2.data_model.message import AssistantMessage, ToolCall, ToolMessage  # noqa: F401
    except ImportError as e:
        _seam("S10", False, f"message classes do not import: {e}")


# ---------------------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------------------

def install(arm: str) -> None:
    """Install the tailoring for `arm`. Idempotent; raises SeamError on a seam mismatch."""
    if arm != "direct":
        raise ValueError(f"this project tailors only the 'direct' arm, not {arm!r}")
    with _lock:
        assert_pinned_tau2()
        assert_seams()
        from tau2.registry import registry

        if DIRECT_DOMAIN not in registry.get_domains():
            registry.register_domain(_candidate_environment, DIRECT_DOMAIN)
        if DIRECT_DOMAIN not in registry.get_task_sets():
            registry.register_tasks(_airline_tasks, DIRECT_DOMAIN)
        _install_pristine_gold()
        _state["installed"].add(arm)
