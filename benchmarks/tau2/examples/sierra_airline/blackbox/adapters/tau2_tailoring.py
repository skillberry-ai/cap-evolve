"""Outside-in tailoring of VANILLA tau2-bench for the blackbox (Skillberry) delivery arm.

tau2 itself is never edited. Everything here goes through tau2's public extension points
(``registry.register_domain`` / ``register_tasks`` / ``register_agent_factory``) plus two narrow
wrappers where tau2 offers none (``Orchestrator.get_trajectory`` and
``tau2.runner.batch.run_single_task``).

Importing this module has NO side effects. The single entry point is :func:`install`, which is
idempotent (each phase is a fresh process, but the algorithm loop's iterations share one). It
first checks that tau2 is at ``TAU2_REFERENCE_SHA``, the commit this module was created from.

One trial = one SESSION, tracked by a thread-local scope (B0):
  IDLE  -> no trial in progress (the default; the main thread always)
  ARMED -> the run_single_task wrapper started an attempt; no remote env yet
  OPEN  -> the trial's remote env exists in tau2's EnvironmentManager (env service)
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

log = logging.getLogger("tau2_tailoring")

DOMAIN = "airline_skillberry"
AGENT = "llm_agent_skillberry"
SENTINEL = "ibm/skillberry-local"
PLUGIN = "tau2"

IDLE, ARMED, OPEN = "IDLE", "ARMED", "OPEN"

_scope = threading.local()
_install_lock = threading.Lock()
_log_lock = threading.Lock()
_session_log: Optional[Path] = None
_attempts: dict = {}
_spa_base_url_fn = None          # set by install(): blackbox_env.spa_base_url


# --------------------------------------------------------------------------- scope (B0)

def _state() -> dict:
    st = getattr(_scope, "st", None)
    if st is None:
        st = {"state": IDLE}
        _scope.st = st
    return st


def _set_idle() -> None:
    _scope.st = {"state": IDLE}


# --------------------------------------------------------------------------- HTTP helpers

def env_service_url() -> str:
    return (os.environ.get("SPA_REMOTE_ENV_URL") or "http://127.0.0.1:8004").rstrip("/")


def _http(method: str, url: str, body: Optional[dict] = None, headers: Optional[dict] = None,
          timeout: float = 60.0) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""


def _spa_url() -> str:
    return _spa_base_url_fn().rstrip("/")


def _headers(env_id: str, task_id: str) -> dict:
    return {
        "skillberry-context-plugin": PLUGIN,
        "skillberry-context-env_id": str(env_id),
        "skillberry-context-task_id": str(task_id),
    }


# --------------------------------------------------------------------------- session log (B5)

def begin_batch(log_path: Path) -> None:
    """Set the session log for the NEXT run_tasks call; reset its attempt counters."""
    global _session_log
    with _log_lock:
        _session_log = Path(log_path)
        _session_log.parent.mkdir(parents=True, exist_ok=True)
        _session_log.touch()
        _attempts.clear()


def _next_attempt(task_id: str, seed) -> int:
    with _log_lock:
        key = (str(task_id), seed)
        _attempts[key] = _attempts.get(key, 0) + 1
        return _attempts[key]


def _log_session(task_id: str, seed, attempt: int, env_id: str) -> None:
    with _log_lock:
        if _session_log is None:
            log.warning("no session log set; env_id %s not recorded", env_id)
            return
        with open(_session_log, "a", encoding="utf-8") as f:
            f.write(f"{task_id} {seed}-{attempt} {env_id}\n")


def sweep(log_path: Path) -> list[str]:
    """Stop every env_id in ``log_path`` that the env service still holds. Returns those stopped."""
    stopped = []
    p = Path(log_path)
    if not p.exists():
        return stopped
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        env_id = parts[2]
        try:
            st, _ = _http("GET", f"{env_service_url()}/{env_id}/info", timeout=15)
            if st == 200:
                _http("POST", f"{env_service_url()}/{env_id}/stop_environment", body={}, timeout=15)
                stopped.append(env_id)
        except Exception as e:  # noqa: BLE001 — bookkeeping must not fail the batch
            log.warning("sweep of env %s failed: %s", env_id, e)
    return stopped


# --------------------------------------------------------------------------- seam ASSERTs (S1–S10)

class SeamError(RuntimeError):
    pass

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



def _sha() -> str:
    try:
        import tau2
        root = Path(tau2.__file__).resolve().parents[2]
        f = root.parent / (root.name + ".COMMIT")
        if f.exists():
            return f.read_text().strip()
        head = (root / ".git" / "HEAD").read_text().strip()
        return head
    except Exception:  # noqa: BLE001
        return "<unknown>"


def _assert(cond: bool, seam: str, what: str) -> None:
    if not cond:
        raise SeamError(f"seam {seam} does not hold at tau2 SHA {_sha()}: {what}")


def _assert_seams() -> None:
    import tau2.runner
    import tau2.runner.batch as batch
    import tau2.utils.llm_utils as llm_utils
    from tau2.data_model.simulation import TextRunConfig
    from tau2.registry import registry
    from tau2.agent.llm_agent import create_llm_agent
    from tau2.orchestrator.orchestrator import Orchestrator
    from tau2.evaluator.evaluator_env import EnvironmentEvaluator
    import tau2.environment.environment as environment_mod

    # S1 batch runner
    params = inspect.signature(tau2.runner.run_tasks).parameters
    _assert(all(p in params for p in ("config", "tasks", "save_path")), "S1",
            "tau2.runner.run_tasks lacks config/tasks/save_path")
    # S2 run config
    fields = TextRunConfig.model_fields
    need = ("domain", "agent", "llm_agent", "llm_args_agent", "user", "llm_user", "llm_args_user",
            "num_trials", "max_steps", "max_errors", "max_concurrency", "seed", "verbose_logs",
            "workers")
    _assert(all(f in fields for f in need), "S2",
            f"TextRunConfig missing {[f for f in need if f not in fields]}")
    # S3 registry
    sigs = {
        "register_domain": ("get_environment", "name"),
        "register_tasks": ("get_tasks", "name", "get_task_splits"),
        "register_agent_factory": ("factory", "name", "task_filter", "metadata"),
        "get_domains": (), "get_task_sets": (),
        "get_env_constructor": ("name",), "get_agent_factory": ("name",),
    }
    for meth, names in sigs.items():
        fn = getattr(registry, meth, None)
        _assert(callable(fn), "S3", f"registry.{meth} missing")
        ps = inspect.signature(fn).parameters
        _assert(all(n in ps for n in names), "S3", f"registry.{meth} lacks {names}")
    # S4 agent factory call
    import tau2.runner.build as build
    src = inspect.getsource(build.build_agent)
    call = src[src.find("agent_factory(\n"):] if "agent_factory(\n" in src else src
    _assert("llm_args=llm_args" in call and "task=task" in call, "S4",
            "build_agent does not pass llm_args and task to the factory")
    # S5 stock LLM agent: OFFLINE PROOF that llm_args reach litellm.completion unfiltered
    from tau2.data_model.message import UserMessage

    class _Probe(Exception):
        pass

    seen: dict = {}

    def _stub(**kwargs):
        seen.update(kwargs)
        raise _Probe()

    orig = llm_utils.completion
    try:
        llm_utils.completion = _stub
        agent = create_llm_agent(tools=[], domain_policy="p", llm="probe",
                                 llm_args={"extra_headers": {"x-probe": "1"}})
        try:
            agent.generate_next_message(UserMessage(role="user", content="hi"),
                                        agent.get_init_state())
        except _Probe:
            pass
    finally:
        llm_utils.completion = orig
    _assert(seen.get("extra_headers") == {"x-probe": "1"}, "S5",
            "llm_args.extra_headers did not reach litellm.completion")
    # S6 trajectory finalize
    _assert(callable(getattr(Orchestrator, "get_trajectory", None)), "S6",
            "Orchestrator.get_trajectory missing")
    # S7 per-trial worker
    _assert(inspect.isfunction(batch.run_single_task), "S7",
            "tau2.runner.batch.run_single_task is not a function")
    _assert("return run_single_task(" in inspect.getsource(batch), "S7",
            "the batch module no longer calls run_single_task by name")
    # S8 env constructions (inspect follows __wrapped__ on a re-install)
    cr_src = inspect.getsource(inspect.unwrap(EnvironmentEvaluator.calculate_reward))
    i_pred = cr_src.find("predicted_environment = environment_constructor(")
    i_gold = cr_src.find("gold_environment = environment_constructor(")
    _assert(0 <= i_pred < i_gold, "S8", "predicted/gold construction order changed")
    # S9 replay
    env_src = inspect.getsource(environment_mod)
    for s in ("Tool call id mismatch", "Tool message expected", "Tool message not expected"):
        _assert(s in env_src, "S9", f"set_state error string {s!r} missing")
    # S10 messages
    try:
        from tau2.data_model.message import AssistantMessage, ToolCall, ToolMessage  # noqa: F401
    except ImportError as e:
        raise SeamError(f"seam S10 does not hold at tau2 SHA {_sha()}: {e}") from e


# --------------------------------------------------------------------------- B1 domain

def _local_airline_env():
    from tau2.domains.airline.data_model import FlightDB
    from tau2.domains.airline.tools import AirlineTools
    from tau2.domains.airline.utils import AIRLINE_DB_PATH, AIRLINE_POLICY_PATH
    from tau2.environment.environment import Environment

    with open(AIRLINE_POLICY_PATH, "r") as fp:
        policy = fp.read()
    return Environment(domain_name=DOMAIN, policy=policy,
                       tools=AirlineTools(FlightDB.load(AIRLINE_DB_PATH)))


def get_environment(db=None, solo_mode: bool = False, **env_kwargs):
    """Factory for ``airline_skillberry``. Only an ARMED construction starts a remote env."""
    if solo_mode:
        raise ValueError("Airline domain does not support solo mode")
    env = _local_airline_env()
    st = _state()
    if st["state"] != ARMED:
        return env              # main-thread get_info build, or one of the evaluator's builds
    status, body = _http("POST", f"{env_service_url()}/start_environment",
                         body={"domain": "airline"})
    if status != 200:
        raise RuntimeError(f"env service /start_environment returned HTTP {status}")
    env_id = json.loads(body)["env_id"]
    st.update(state=OPEN, env_id=env_id)
    _log_session(st["task_id"], st["seed"], st["attempt"], env_id)
    env.env_id = env_id
    return env


def _get_tasks(task_split_name: Optional[str] = "base"):
    from tau2.domains.airline.environment import get_tasks
    return get_tasks(task_split_name)


# --------------------------------------------------------------------------- B2 agent factory

def create_skillberry_agent(tools, domain_policy, **kwargs):
    from tau2.agent.llm_agent import create_llm_agent

    st = _state()
    task = kwargs.get("task")
    llm_args = dict(kwargs.get("llm_args") or {})
    if st["state"] == OPEN and task is not None:
        extra = dict(llm_args.get("extra_headers") or {})
        extra.update(_headers(st["env_id"], task.id))
        llm_args["extra_headers"] = extra
    else:
        log.warning("agent built outside an OPEN session (state=%s); no Skillberry headers",
                    st["state"])
    return create_llm_agent(tools, domain_policy, llm=kwargs.get("llm"), llm_args=llm_args)


# --------------------------------------------------------------------------- B4 merges

def _parse_messages(dicts: list) -> list:
    from tau2.data_model.message import AssistantMessage, ToolMessage

    out = []
    for d in dicts:
        role = d.get("role")
        try:
            if role == "assistant":
                out.append(AssistantMessage(**d))
            elif role == "tool":
                out.append(ToolMessage(**d))
        except Exception as e:  # noqa: BLE001
            log.warning("could not parse a %s message: %s", role, e)
    return out


def _sorted_renumbered(messages: list) -> list:
    msgs = sorted(messages, key=lambda m: m.timestamp or "")
    for i, m in enumerate(msgs):
        m.turn_idx = i
    return msgs


def _wrap_get_trajectory(orig):
    @functools.wraps(orig)
    def get_trajectory(self):
        result = orig(self)          # already a sorted deep copy; self.trajectory untouched
        env_id = getattr(getattr(self, "environment", None), "env_id", None)
        if not env_id:
            return result
        try:
            status, body = _http("GET", f"{env_service_url()}/{env_id}/trajectory")
            if status != 200:
                log.warning("env trajectory for %s returned HTTP %s", env_id, status)
                return result
            remote = _parse_messages(json.loads(body).get("trajectory") or [])
        except Exception as e:  # noqa: BLE001
            log.warning("env trajectory fetch for %s failed: %s", env_id, e)
            return result
        return _sorted_renumbered(list(result) + remote)
    get_trajectory._capevolve_wrapper = True
    return get_trajectory


def _tool_call_name(tc: dict) -> Optional[str]:
    return tc.get("name") or (tc.get("function") or {}).get("name")


def _merge_proxy_trajectory(sim, env_id: str, task_id: str) -> None:
    """B4 (ii): AFTER evaluation, add the proxy-side compound/skill calls to sim.messages."""
    status, body = _http("GET", f"{_spa_url()}/trajectory", headers=_headers(env_id, task_id))
    if status != 200:
        log.warning("proxy trajectory for %s returned HTTP %s", env_id, status)
        return
    dicts = json.loads(body).get("trajectory") or []
    names = {t.name for t in _local_airline_env().get_tools()}
    id_to_name = {}
    for d in dicts:
        for tc in d.get("tool_calls") or []:
            id_to_name[tc.get("id")] = _tool_call_name(tc)
    kept = []
    for d in dicts:
        role = d.get("role")
        if role == "assistant":
            calls = [tc for tc in (d.get("tool_calls") or []) if _tool_call_name(tc) not in names]
            if not calls and not d.get("content"):
                continue
            d = dict(d)
            d["tool_calls"] = [
                {"id": tc.get("id") or "", "name": _tool_call_name(tc),
                 "arguments": _arguments(tc), "requestor": "assistant"} for tc in calls
            ] or None
            kept.append(d)
        elif role == "tool":
            call_id = d.get("id") or d.get("tool_call_id") or ""
            if id_to_name.get(call_id) in names:
                continue
            d = dict(d)
            d["id"] = call_id
            if not isinstance(d.get("content"), str):
                d["content"] = json.dumps(d.get("content"), default=str)
            kept.append(d)
    parsed = _parse_messages(kept)
    sim.messages = _sorted_renumbered(list(sim.messages or []) + parsed)


def _arguments(tc: dict) -> dict:
    args = tc.get("arguments")
    if args is None:
        args = (tc.get("function") or {}).get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"raw": args}
    return args or {}


# --------------------------------------------------------------------------- B5 session lifecycle

def _wrap_run_single_task(orig):
    @functools.wraps(orig)
    def run_single_task(config, task, *args, **kwargs):
        seed = kwargs.get("seed")
        _scope.st = {"state": ARMED, "task_id": task.id, "seed": seed,
                     "attempt": _next_attempt(task.id, seed)}
        try:
            sim = orig(config, task, *args, **kwargs)
            st = _state()
            if st["state"] == OPEN:
                try:
                    _merge_proxy_trajectory(sim, st["env_id"], task.id)
                except Exception as e:  # noqa: BLE001
                    log.warning("proxy trajectory merge failed for task %s: %s", task.id, e)
            return sim
        finally:
            st = _state()
            if st["state"] == OPEN:
                env_id = st["env_id"]
                try:
                    _http("POST", f"{_spa_url()}/disconnect", body={},
                          headers=_headers(env_id, task.id), timeout=30)
                except Exception as e:  # noqa: BLE001
                    log.warning("SPA disconnect for %s failed: %s", env_id, e)
                try:
                    _http("POST", f"{env_service_url()}/{env_id}/stop_environment", body={},
                          timeout=30)
                except Exception as e:  # noqa: BLE001
                    log.warning("stop_environment for %s failed: %s", env_id, e)
            _set_idle()
    run_single_task._capevolve_wrapper = True
    return run_single_task


# --------------------------------------------------------------------------- install

def install(arm: str) -> None:
    """Install the tailoring for ``arm``. Idempotent; runs the offline seam ASSERTs first."""
    if arm != "blackbox":
        raise ValueError(f"this project is onboarded for the blackbox arm only, not {arm!r}")
    with _install_lock:
        assert_pinned_tau2()
        _assert_seams()

        global _spa_base_url_fn
        import sys
        rel = "interventions/llm-proxies/blackbox/scripts"
        if os.environ.get("CAPEVOLVE_SKILLS_DIR"):
            scripts = Path(os.environ["CAPEVOLVE_SKILLS_DIR"]) / rel
        else:
            scripts = next(p / "skills" / rel for p in Path(__file__).resolve().parents
                           if (p / "skills" / rel).is_dir())
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import blackbox_env
        _spa_base_url_fn = blackbox_env.spa_base_url

        import litellm
        if SENTINEL not in litellm.model_cost:
            litellm.register_model({SENTINEL: {"input_cost_per_token": 0.0,
                                               "output_cost_per_token": 0.0,
                                               "litellm_provider": "openai", "mode": "chat"}})

        from tau2.registry import registry
        import tau2.runner.batch as batch
        from tau2.orchestrator.orchestrator import Orchestrator

        if DOMAIN not in registry.get_domains():
            registry.register_domain(get_environment, DOMAIN)
        if DOMAIN not in registry.get_task_sets():
            registry.register_tasks(_get_tasks, DOMAIN)
        if registry.get_agent_factory(AGENT) is None:
            registry.register_agent_factory(create_skillberry_agent, AGENT)
        if not getattr(Orchestrator.get_trajectory, "_capevolve_wrapper", False):
            Orchestrator.get_trajectory = _wrap_get_trajectory(Orchestrator.get_trajectory)
        if not getattr(batch.run_single_task, "_capevolve_wrapper", False):
            batch.run_single_task = _wrap_run_single_task(batch.run_single_task)
