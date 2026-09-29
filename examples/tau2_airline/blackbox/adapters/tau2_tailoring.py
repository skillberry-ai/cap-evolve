"""Skillberry tailoring for tau2 — applied from OUTSIDE an unmodified benchmark.

The blackbox arm needs five things that stock tau2 does not do. Historically they were
obtained by *forking* tau2 (a `[skillberry]` build carrying header injection, a sentinel
model route, an `airline_skillberry` domain, two trajectory merges and a `disconnect`). A
benchmark edited to suit the intervention is no longer the benchmark: its numbers stop being
comparable to anyone else's, and the fork has to be re-based forever.

This module supplies the same five things against **vanilla upstream tau2**, preferring
tau2's own public extension points and falling back to a narrow, asserted wrapper only where
no seam exists:

  1. context headers on the agent's LLM call  -> `llm_args` (public, unpatched)
  2. SPA sentinel routing                     -> `llm_args` (public, unpatched)
  3. a domain for the arm                      -> `registry.register_domain` (public)
     + `registry.register_agent_factory`       (public)
  4a. the env-service trajectory, BEFORE evaluation  -> wraps `Orchestrator.get_trajectory`
  4b. the proxy trajectory, AFTER evaluation         -> wraps `runner.run_simulation`
  5. vMCP disconnect at session end                  -> same wrapper as 4b

`install()` performs the registrations and installs the wrappers; it is idempotent because
every cap-evolve phase is a separate process that loads the adapter afresh. `verify()` asserts
every seam above and is what makes it safe to track tau2's latest `main` rather than a pin —
see its docstring for why that matters more than it sounds.

Nothing here touches the network at import time, so `cap-evolve check` stays offline.

WHERE `env_id` LIVES, and why not on the environment
----------------------------------------------------
Each rollout needs its own RES environment, and its id must reach (a) the LLM call's context
header, so the store routes that rollout's tool executions to it, and (b) both merge
wrappers. The obvious home is the environment — which is where the fork put it — but
`evaluate_simulation` re-invokes the registered domain constructor 1-3 MORE times per rollout
(`evaluator/evaluator.py:158,173,198,281`). An environment that starts a remote session in
`__init__` therefore orphans one remote env per evaluation and leaves the id ambiguous.

So the domain here returns a PLAIN vanilla `Environment`, byte-equivalent to tau2's own
`airline` — side-effect-free, so the evaluator may build it as often as it likes, and backed
by real `AirlineTools` so the evaluator's `set_state` replay reconstructs a local DB and
`db_match` is computable. The remote session is owned by the AGENT instead: the agent factory
runs exactly once per rollout, is never called by the evaluator, and already receives `task`.
`env_id` is an attribute of the agent, and both wrappers read it from `orchestrator.agent`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# --- what the proxy stack is, and how tau2 is told to talk to it -------------------
# The sentinel is a MODEL NAME, not a URL: tau2 passes it straight through to litellm, and
# the `base_url` we inject alongside it in `llm_args` is what actually points at SPA. Keeping
# it recognisable matters because it must never be offered as a real gateway model.
SENTINEL_MODEL = "ibm/skillberry-local"
DEFAULT_SPA_URL = "http://127.0.0.1:7000"
DEFAULT_RES_URL = "http://127.0.0.1:8004"

# The header family the store and the proxy both read. Flattened to dash-separated keys
# because HTTP headers are flat; see `flatten_keys`.
SKILLBERRY_CONTEXT = "skillberry-context"

# The registered names this module adds to tau2's registry. The domain is deliberately a
# SEPARATE name from "airline" even though the environment is identical: the arm has to be
# selectable, and a run dir that cannot say which arm produced it cannot be compared.
DOMAIN = "airline_skillberry"
AGENT_NAME = "llm_agent_skillberry"

# The RES is started with tau2's OWN airline domain — the remote environment is plain vanilla
# tau2, and `orchestrator/environment_manager.py` is upstream code, not ours.
RES_DOMAIN = "airline"

_TIMEOUT = 60


def spa_url() -> str:
    return (os.environ.get("SPA_AGENT_URL") or DEFAULT_SPA_URL).rstrip("/")


def res_url() -> str:
    """The benchmark's environment service. Same env var the frozen primitives read, so the
    skill's tools and this module can never disagree about which service holds the state."""
    return (os.environ.get("SPA_REMOTE_ENV_URL") or DEFAULT_RES_URL).rstrip("/")


# --- pure helpers -----------------------------------------------------------------

def flatten_keys(data: dict, prefix: str = "") -> dict:
    """Flatten a nested dict into dash-separated keys, for use as HTTP headers.

    ``{"skillberry-context": {"env_id": "x"}}`` -> ``{"skillberry-context-env_id": "x"}``.
    A copy of the benchmark-side helper the store and proxy were built against; kept here so
    this module imports nothing from a tailored build.
    """
    out: dict[str, str] = {}
    for key, value in (data or {}).items():
        name = f"{prefix}-{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten_keys(value, name))
        elif value is not None:
            out[name] = str(value)
    return out


def context_headers(env_id: str, task_id: str | None) -> dict:
    """The Skillberry context for one rollout, as flat headers.

    ``env_id`` is what routes a store-hosted tool to THIS rollout's environment. Its absence
    is not an error at the proxy — SPA defaults it to the string ``"default"`` — which is
    precisely why it must never go missing silently: every rollout would then share one store
    session, tools would mutate the wrong environment, and the only symptom would be a lower
    score that reads as a worse capability. ``verify()`` exists for this.
    """
    return flatten_keys({SKILLBERRY_CONTEXT: {
        "plugin": "tau2", "env_id": env_id, "task_id": task_id}})


def _http(method: str, url: str, *, headers: dict | None = None, body: Any = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/json", "Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


# --- 3. the domain: a PLAIN vanilla environment -----------------------------------

def get_airline_skillberry_environment(**kwargs):
    """The arm's domain. Deliberately IDENTICAL to tau2's own ``airline`` environment.

    It exists only so the arm has its own selectable domain name. It starts nothing and holds
    no remote state, which is what lets `evaluate_simulation` construct it 1-3 extra times per
    rollout without orphaning remote environments — and its real ``AirlineTools`` are what let
    the evaluator's ``set_state`` replay rebuild a local DB so ``db_match`` is computable.

    ``**kwargs`` is passed through to tau2's factory rather than filtered: the run path calls
    with none, the evaluator passes ``solo_mode`` (and any ``env_kwargs``), and tau2's own
    factory is the right thing to decide what is valid.
    """
    from tau2.domains.airline.environment import get_environment as _airline_env

    env = _airline_env(**kwargs)
    # Same object shape, own name — so `get_domain_name()` reports the arm, not "airline".
    env.domain_name = DOMAIN
    return env


# --- 1 + 2 + the remote session: the agent factory --------------------------------

def _start_remote_env() -> str:
    """Start this rollout's environment on the RES and return its id.

    One POST per rollout. Raising here is contained: the agent factory catches it and degrades
    to a plain agent, because an exception escaping into tau2's simulation costs THREE full
    re-runs (`runner/progress.py` retries) rather than one failed rollout.
    """
    out = _http("POST", f"{res_url()}/start_environment", body={"domain": RES_DOMAIN})
    env_id = (out or {}).get("env_id")
    if not env_id:
        raise RuntimeError(f"environment service returned no env_id: {out!r}")
    return str(env_id)


def skillberry_agent_factory(tools, domain_policy, **kwargs):
    """Build a VANILLA ``LLMAgent`` wired to reach the model through SPA.

    No tau2 class is subclassed and nothing is patched. Everything the fork achieved by
    editing ``llm_utils.generate`` is expressed in ``llm_args``, which vanilla tau2 forwards
    to ``generate`` and on to ``litellm.completion`` unfiltered:

      * ``extra_headers`` — this rollout's Skillberry context
      * ``base_url`` / ``api_key`` / ``custom_llm_provider`` — the route to SPA

    The agent also carries ``skillberry_env_id`` so the two merge wrappers can find this
    rollout's remote environment from ``orchestrator.agent`` without a thread-local.

    A failure to start the remote environment degrades to a plain agent with the session id
    unset, which the wrappers treat as "nothing to merge". That is deliberate: a dead RES
    should surface as an unmerged trace and a visibly wrong score, not as a 3x retry storm.
    """
    from tau2.agent.llm_agent import LLMAgent

    task = kwargs.get("task")
    llm_args = dict(kwargs.get("llm_args") or {})

    env_id = ""
    try:
        env_id = _start_remote_env()
    except Exception as e:  # noqa: BLE001 — see docstring: never raise into a simulation
        _warn(f"could not start a remote environment for task "
              f"{getattr(task, 'id', '?')}: {e}")

    if env_id:
        llm_args["extra_headers"] = {
            **(llm_args.get("extra_headers") or {}),
            **context_headers(env_id, str(getattr(task, "id", "") or "") or None),
        }
    # The proxy route. `api_key` is a placeholder because SPA authenticates nothing; the REAL
    # upstream credential lives in SPA's own environment. Never put a real key in `llm_args`:
    # tau2 persists llm_args verbatim into its results JSON, which cap-evolve copies to the
    # optimizer and `store: git` commits.
    llm_args.setdefault("base_url", spa_url())
    llm_args.setdefault("api_key", "EMPTY")
    llm_args.setdefault("custom_llm_provider", "openai")

    agent = LLMAgent(tools=tools, domain_policy=domain_policy,
                     llm=kwargs.get("llm") or SENTINEL_MODEL, llm_args=llm_args)
    agent.skillberry_env_id = env_id
    agent.skillberry_task_id = str(getattr(task, "id", "") or "")
    return agent


# --- 4a. the env-service trajectory, merged BEFORE evaluation ---------------------

def _remote_trajectory(env_id: str) -> list:
    """The messages the RES recorded for this rollout, as tau2 message objects.

    These are the PRIMITIVE calls: the store executed them against the remote environment, so
    tau2's own trajectory never saw them. They are properly paired (an assistant message
    carrying the tool call, then its tool result), which is why they are legal input to the
    evaluator's ``set_state`` replay.
    """
    from tau2.data_model.message import AssistantMessage, ToolMessage

    out = _http("GET", f"{res_url()}/{env_id}/trajectory")
    msgs = []
    for m in (out or {}).get("trajectory") or []:
        role = m.get("role")
        if role == "assistant":
            msgs.append(AssistantMessage(**m))
        elif role == "tool":
            msgs.append(ToolMessage(**m))
    return msgs


def _renumber(messages: list) -> list:
    """Sort by timestamp and reassign ``turn_idx`` — tau2's own trajectory contract."""
    from copy import deepcopy

    ordered = sorted(deepcopy(messages), key=lambda m: getattr(m, "timestamp", "") or "")
    for i, m in enumerate(ordered):
        m.turn_idx = i
    return ordered


# --- 4b + 5. the proxy trajectory, merged AFTER evaluation, then disconnect -------

def _proxy_trajectory(env_id: str, task_id: str | None, env_tool_names: set) -> list:
    """The COMPOUND calls SPA made on the agent's behalf, minus the primitives.

    Primitive calls already arrive via the env service (4a); keeping SPA's copy too would
    double them. What is unique here is the skill's own higher-level tools, which exist
    nowhere in tau2's view of the world.
    """
    from tau2.data_model.message import AssistantMessage, ToolMessage

    out = _http("GET", f"{spa_url()}/trajectory", headers=context_headers(env_id, task_id))
    msgs, keep_ids = [], set()
    for m in (out or {}).get("trajectory") or []:
        role = m.get("role")
        if role == "assistant":
            calls = [c for c in (m.get("tool_calls") or [])
                     if (c.get("name") or "") not in env_tool_names]
            if not calls:
                continue
            keep_ids.update(c.get("id") for c in calls)
            msgs.append(AssistantMessage(**{**m, "tool_calls": calls}))
        elif role == "tool" and m.get("id") in keep_ids:
            msgs.append(ToolMessage(**m))
    return msgs


def _disconnect(env_id: str, task_id: str | None) -> None:
    """Tear down this rollout's vMCP server. Without it SPA leaks one per rollout."""
    _http("POST", f"{spa_url()}/disconnect", headers=context_headers(env_id, task_id))


def _finish_rollout(orchestrator, simulation) -> None:
    """Merge the proxy trajectory into an ALREADY-EVALUATED simulation, then disconnect.

    The window matters and is narrow. ``evaluate_simulation`` replays ``simulation.messages``
    through ``Environment.set_state``, which raises on a tool result that has no matching
    preceding call — so these filtered compound calls must land AFTER evaluation. They must
    also land BEFORE the batch runner's ``save_fn``, or the persisted ``results.json`` (the
    trace the optimizer reads) would disagree with the object returned in memory.
    ``run_simulation`` is the only point that sits inside both bounds.
    """
    agent = getattr(orchestrator, "agent", None)
    env_id = str(getattr(agent, "skillberry_env_id", "") or "")
    if not env_id:
        return
    task_id = str(getattr(agent, "skillberry_task_id", "") or "") or None
    try:
        env = getattr(orchestrator, "environment", None)
        names = {t.name for t in (env.get_tools() if env else [])}
        extra = _proxy_trajectory(env_id, task_id, names)
        if extra:
            simulation.messages = _renumber(list(simulation.messages or []) + extra)
    except Exception as e:  # noqa: BLE001 — a degraded trace beats a failed rollout
        _warn(f"could not merge the proxy trajectory for env {env_id}: {e}")
    try:
        _disconnect(env_id, task_id)
    except Exception as e:  # noqa: BLE001
        _warn(f"could not disconnect env {env_id}: {e}")


def _warn(msg: str) -> None:
    import sys
    print(f"[tau2_tailoring] {msg}", file=sys.stderr, flush=True)


# --- install ----------------------------------------------------------------------

_INSTALLED = False


def install() -> None:
    """Register the domain + agent and install the two wrappers. IDEMPOTENT.

    Every cap-evolve phase is a separate process that loads the adapter itself, and
    ``register_domain`` RAISES on a duplicate name, so re-entry must be a no-op rather than an
    error. Called from the adapter's ``apply()`` — never at import, so ``check`` stays offline.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from tau2.registry import registry

    if DOMAIN not in registry.get_domains():
        registry.register_domain(get_airline_skillberry_environment, DOMAIN)
        from tau2.domains.airline.environment import get_tasks as _airline_tasks
        registry.register_tasks(_airline_tasks, DOMAIN)
    if registry.get_agent_factory(AGENT_NAME) is None:
        registry.register_agent_factory(skillberry_agent_factory, AGENT_NAME)

    _install_trajectory_wrapper()
    _install_simulation_wrapper()
    _INSTALLED = True


_MARK = "_capevolve_skillberry_wrapped"


def _install_trajectory_wrapper() -> None:
    """Wrap ``Orchestrator.get_trajectory`` so the PRIMITIVE calls reach the evaluator.

    This is the one seam tau2 offers nothing public for, and it is reward-critical rather than
    cosmetic: under this arm every real mutation happens in the store against the remote
    environment, so without these messages the evaluator's replay reconstructs nothing,
    ``db_match`` is false and reward collapses to 0 — silently, and looking exactly like a bad
    capability. `_finalize` calls this to build ``SimulationRun.messages``, which is why the
    merge lands before evaluation from here.
    """
    import functools

    from tau2.orchestrator.orchestrator import Orchestrator

    original = Orchestrator.get_trajectory
    if getattr(original, _MARK, False):
        return

    @functools.wraps(original)
    def wrapper(self):
        merged = original(self)
        env_id = str(getattr(getattr(self, "agent", None), "skillberry_env_id", "") or "")
        if not env_id:
            return merged
        try:
            remote = _remote_trajectory(env_id)
        except Exception as e:  # noqa: BLE001 — never raise inside a simulation
            _warn(f"could not read the env-service trajectory for {env_id}: {e}")
            return merged
        return _renumber(list(merged) + remote) if remote else merged

    setattr(wrapper, _MARK, True)
    Orchestrator.get_trajectory = wrapper


def _install_simulation_wrapper() -> None:
    """Wrap ``runner.run_simulation`` for the post-evaluation merge + disconnect.

    Patched at BOTH bindings: ``tau2.runner.batch`` imports the name at module load, so
    rebinding only ``tau2.runner.simulation`` would leave the batch path — the one every run
    actually uses — unwrapped, and the failure would be a silently unmerged trace.
    """
    import functools
    import importlib

    simulation = importlib.import_module("tau2.runner.simulation")
    original = simulation.run_simulation
    if getattr(original, _MARK, False):
        return

    @functools.wraps(original)
    def wrapper(orchestrator, *args, **kwargs):
        sim = original(orchestrator, *args, **kwargs)
        try:
            _finish_rollout(orchestrator, sim)
        except Exception as e:  # noqa: BLE001
            _warn(f"post-simulation tailoring failed: {e}")
        return sim

    setattr(wrapper, _MARK, True)
    simulation.run_simulation = wrapper
    for mod in ("tau2.runner.batch",):
        try:
            m = importlib.import_module(mod)
            if getattr(m, "run_simulation", None) is original:
                m.run_simulation = wrapper
        except Exception:  # noqa: BLE001 — a missing binding is reported by verify()
            pass


# --- verify: the seam contract ----------------------------------------------------

class SeamError(RuntimeError):
    """A seam this tailoring depends on is gone. Naming it is the whole point."""


def _seam_error(seam: str, detail: str, consequence: str) -> SeamError:
    return SeamError(
        f"tau2 seam {seam!r} no longer holds.\n"
        f"  running against: tau2 {_tau2_version()} @ {_tau2_commit() or '(unknown commit)'}\n"
        f"  what moved: {detail}\n"
        f"  what it costs: {consequence}\n"
        "  This tailoring was written against the commit recorded in the run. Changing the "
        "tau2 commit changes the code it hooks, so validating it is YOUR responsibility.")


def _tau2_version() -> str:
    """tau2's version. It exposes no ``__version__``, so the installed dist is the source."""
    try:
        import tau2
        v = getattr(tau2, "__version__", "") or ""
        if v:
            return str(v)
    except Exception:  # noqa: BLE001
        pass
    try:
        from importlib.metadata import version
        return str(version("tau2"))
    except Exception:  # noqa: BLE001
        return "?"


def _tau2_commit() -> str:
    try:
        import subprocess
        import tau2
        root = os.path.dirname(os.path.dirname(os.path.dirname(tau2.__file__)))
        out = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()[:12] if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def verify() -> dict:
    """Assert every seam this tailoring depends on. OFFLINE — starts and calls nothing remote.

    Why this is not optional hardening: the benchmark is onboarded at latest ``main``, not a
    pin, and the two highest-risk seams fail SILENTLY. If ``llm_args`` stops reaching litellm,
    the context header vanishes, SPA defaults ``env_id`` to ``"default"``, every rollout shares
    one store session and the score drops with no error anywhere. If the trajectory wrapper
    stops firing, the primitives never reach the evaluator and ``db_match`` goes false. Both
    read as a worse capability rather than broken wiring, so they are asserted here — inside
    `cap-evolve check`, before any budget is spent.

    Returns ``{"notes": [...]}``; raises :class:`SeamError` naming the seam that moved.
    """
    import inspect

    notes = [f"tau2 {_tau2_version()} @ {_tau2_commit() or '(unknown commit)'}"]

    # (a) the registration APIs, and that build_agent still hands the factory `task`.
    from tau2.registry import registry
    for fn, needed in ((registry.register_domain, {"get_environment", "name"}),
                       (registry.register_agent_factory, {"factory", "name"}),
                       (registry.register_tasks, {"get_tasks", "name"})):
        missing = needed - set(inspect.signature(fn).parameters)
        if missing:
            raise _seam_error(
                f"registry.{fn.__name__}", f"parameters {sorted(missing)} are gone",
                "the arm cannot be registered at all")

    # The capture target is MODULE-level, not a closure local, because verify() must be
    # re-entrant: `register_agent_factory` RAISES on a duplicate name, so a second call cannot
    # re-register and would otherwise be handed the FIRST call's closure — leaving this call's
    # dict empty and reporting a moved seam that never moved.
    _PROBE_KWARGS.clear()
    # The name is unique PER MODULE INSTANCE. tau2's registry keeps the function object it was
    # given, so a fixed name means a second instance of this module (a fresh
    # spec_from_file_location import, which both the check gate and the contract test do) would
    # find the name taken, skip registering, and then read an empty dict written by the FIRST
    # instance's function — reporting a moved seam that never moved.
    name = f"__capevolve_probe_agent_{id(_PROBE_KWARGS):x}__"
    if registry.get_agent_factory(name) is None:
        registry.register_agent_factory(_probe_agent_factory, name)
    from tau2.runner.build import build_agent
    build_agent(name, get_airline_skillberry_environment(), llm="m", llm_args={"a": 1},
                task=None)
    probe = dict(_PROBE_KWARGS)
    if "task" not in probe or "llm_args" not in probe:
        raise _seam_error(
            "build_agent -> agent factory kwargs",
            f"the factory no longer receives {sorted({'task', 'llm_args'} - set(probe))}",
            "the context header loses task_id, or the SPA route is never applied")
    notes.append("agent factory receives task + llm_args")

    # (b) the highest-risk seam, PROVED rather than inspected: does `llm_args` actually reach
    #     litellm? Nothing in tau2 documents that it does; it works because kwargs are splatted
    #     twice. A reasonable upstream hardening patch would break it with no error at all.
    import tau2.utils.llm_utils as llm_utils
    seen: dict = {}

    def _fake_completion(**kw):
        seen.update(kw)
        raise _ProbeDone()

    original = llm_utils.completion
    llm_utils.completion = _fake_completion
    # tau2 logs any exception out of `generate` at ERROR level. Our probe deliberately raises
    # to stop before any real work, so without this the gate prints a stack-trace-shaped ERROR
    # on the SUCCESS path — which reads as a failure to anyone running `cap-evolve check`.
    try:
        from loguru import logger as _loguru
        _loguru.disable("tau2")
    except Exception:  # noqa: BLE001 — noise suppression is optional, never required
        _loguru = None
    try:
        from tau2.agent.llm_agent import LLMAgent
        from tau2.data_model.message import UserMessage
        agent = LLMAgent(tools=[], domain_policy="probe", llm="probe-model",
                         llm_args={"extra_headers": {"x-capevolve-probe": "1"},
                                   "base_url": "http://127.0.0.1:1/probe"})
        try:
            agent.generate_next_message(UserMessage(role="user", content="ping"),
                                        agent.get_init_state())
        except _ProbeDone:
            pass
        except Exception:  # noqa: BLE001 — we only care whether the kwargs arrived
            pass
    finally:
        llm_utils.completion = original
        if _loguru is not None:
            _loguru.enable("tau2")
    if (seen.get("extra_headers") or {}).get("x-capevolve-probe") != "1":
        raise _seam_error(
            "llm_args -> litellm.completion passthrough",
            "extra_headers set on the agent never reached the client call",
            "the Skillberry context header is dropped; SPA falls back to env_id "
            "\"default\", every rollout shares one store session and reward collapses")
    if seen.get("base_url") != "http://127.0.0.1:1/probe":
        raise _seam_error(
            "llm_args -> litellm.completion passthrough (base_url)",
            "base_url set on the agent never reached the client call",
            "the agent talks to the upstream model directly instead of through SPA, so "
            "the capability under test is never delivered")
    notes.append("llm_args reaches litellm (extra_headers + base_url proved)")

    # (c) the wrapped entry point, at both bindings.
    import importlib
    sim_mod = importlib.import_module("tau2.runner.simulation")
    params = list(inspect.signature(sim_mod.run_simulation).parameters.values())
    if not params or params[0].name != "orchestrator":
        raise _seam_error("runner.run_simulation(orchestrator, ...)",
                          f"the first parameter is now {params[0].name if params else '(none)'}",
                          "the wrapper reads the wrong object and the proxy merge is skipped")
    if params[0].kind is inspect.Parameter.KEYWORD_ONLY:
        raise _seam_error("runner.run_simulation(orchestrator, ...)",
                          "the orchestrator is now keyword-only",
                          "the wrapper's positional passthrough breaks")
    batch = importlib.import_module("tau2.runner.batch")
    if not callable(getattr(batch, "run_simulation", None)):
        raise _seam_error("tau2.runner.batch.run_simulation",
                          "the batch runner no longer binds run_simulation by name",
                          "the batch path runs unwrapped and traces are silently unmerged")
    notes.append("run_simulation wrappable at both bindings")

    # (d) the orchestrator seam, and that the agent is reachable from it.
    from tau2.orchestrator.orchestrator import Orchestrator
    if not callable(getattr(Orchestrator, "get_trajectory", None)):
        raise _seam_error("Orchestrator.get_trajectory",
                          "the method is gone",
                          "the primitive calls never reach the evaluator, db_match goes "
                          "false and reward collapses to 0")
    if "agent" not in inspect.signature(Orchestrator.__init__).parameters:
        raise _seam_error("Orchestrator(agent=...)",
                          "the orchestrator no longer holds the agent",
                          "neither wrapper can find this rollout's env_id")
    notes.append("Orchestrator.get_trajectory + .agent present")

    return {"notes": notes}


class _ProbeDone(Exception):
    """Raised by the verify() stub to stop the agent before any real work happens."""


#: Where the probe agent factory records the kwargs tau2 handed it. Module-level so verify()
#: stays re-entrant — see the comment at its use site.
_PROBE_KWARGS: dict = {}


def _probe_agent_factory(tools, domain_policy, **kwargs):
    """A throwaway agent factory, registered once, used by verify() to prove that tau2 still
    hands a factory the kwargs the real one depends on (notably ``task`` and ``llm_args``)."""
    _PROBE_KWARGS.clear()
    _PROBE_KWARGS.update(kwargs)
    return object()
