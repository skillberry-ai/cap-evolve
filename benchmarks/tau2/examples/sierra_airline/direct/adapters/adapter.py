"""Project adapter — tau2-bench airline, DIRECT arm (the candidate's tool code runs in-process).

Contract (authoritative: core/cap_evolve/adapter.py + docs/ADAPTER_CONTRACT.md):
  tasks(split)                   -> list[Task]   # all 50 airline "base" tasks; the harness filters by split ids
  run_target(task, ctx, *, seed) -> Rollout      # one trial through run_trials
  score(task, rollout)           -> Score        # tau2's recorded reward + argument-level, gold-safe feedback
  run_trials / run_batch                         # ALL trials in ONE tau2 run_tasks call

How a candidate reaches the model: apply() installs the tailoring (adapters/tau2_tailoring.py,
domain "airline_candidate", pristine gold) and points it at <candidate>/tools/tools.py; tau2's
stock llm_agent then sees that candidate's AirlineTools. vendor/tau2-bench is never edited.

Credentials: OPENAI_BASE_URL / OPENAI_API_BASE / OPENAI_API_KEY come from the repo-root .env
(or the shell). The key is NEVER put in llm_args — tau2 records llm_args in its results file,
which is copied to the optimizer and committed. litellm reads OPENAI_API_KEY on the openai/ route.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import tau2_tailoring  # noqa: E402  (no side effects on import)

ARM = "direct"
DOMAIN = tau2_tailoring.DIRECT_DOMAIN
AGENT = "llm_agent"
USER = "user_simulator"
MAX_CONCURRENCY = 125
FALLBACK_MODEL = "aws/gpt-oss-120b"


def _load_dotenv() -> None:
    """Walk up from this file to the first .env; setdefault each KEY=VALUE (shell wins)."""
    for d in [_HERE, *_HERE.parents]:
        f = d / ".env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                if key:
                    os.environ.setdefault(key, val)
            return


_load_dotenv()
# Skip litellm's remote cost-map fetch, which otherwise stalls the tau2/litellm import.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


def _bare_model(env_key: str) -> str:
    m = (os.environ.get(env_key) or "").strip()
    if not m and env_key == "TAU2_AGENT_MODEL":
        # PROMPT.md #2b/#3b: TAU2_AGENT_MODEL is the one source; if it is unset but
        # SPA_MODEL_NAME is set, the agent model is SPA_MODEL_NAME without `openai/`.
        # Same rule as the blackbox arm, so both arms run the same agent model.
        m = (os.environ.get("SPA_MODEL_NAME") or "").strip().removeprefix("openai/")
    return m or FALLBACK_MODEL


def _litellm_model(bare: str) -> str:
    """Route as openai/<model>, idempotently (openai/openai/... 404s)."""
    return bare if bare.startswith("openai/") else f"openai/{bare}"


def _gateway_llm_args() -> dict:
    base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE") or ""
    return {"api_base": base, "temperature": 0.0}


def _airline_tasks() -> list:
    from tau2.domains.airline.environment import get_tasks

    return get_tasks("base")


class Adapter(CapabilityAdapter):

    def __init__(self) -> None:
        self._tau2_tasks = None
        self._apply_error: str | None = None
        self._last_native_dir: Path | None = None

    # ---- data ------------------------------------------------------------------------

    def _tasks_by_id(self) -> dict:
        if self._tau2_tasks is None:
            self._tau2_tasks = {str(t.id): t for t in _airline_tasks()}
        return self._tau2_tasks

    def tasks(self, split: str) -> list[Task]:
        # The harness calls tasks("all") and filters by the frozen split file; every split
        # name returns the same stable 50 tasks. No gold goes into Task.target.
        out = []
        for tid, t in self._tasks_by_id().items():
            instr = getattr(t.user_scenario, "instructions", None)
            reason = getattr(instr, "reason_for_call", None)   # the user's side, not gold
            out.append(Task(id=tid, input=reason, metadata={"domain": "airline"}))
        return out

    def runner_model(self) -> str | None:
        return _bare_model("TAU2_AGENT_MODEL")

    # ---- making a candidate live -----------------------------------------------------

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """Install the tailoring and make candidate_dir/tools/tools.py the live toolkit.
        NEVER raises: an error is recorded and run_trials returns errored rollouts, so the
        harness EXCLUDES the candidate instead of scoring it 0.0."""
        self._apply_error = None
        try:
            self.materialize(candidate_dir, edits)
            tools_py = Path(candidate_dir) / "tools" / "tools.py"
            if not tools_py.is_file():
                self._apply_error = f"apply: candidate has no tools/tools.py ({candidate_dir})"
                return
            tau2_tailoring.install(ARM)
            # Load once here so a broken candidate fails fast instead of burning tau2 retries.
            from tau2.domains.airline.data_model import FlightDB
            from tau2.domains.airline.utils import AIRLINE_DB_PATH

            toolkit = tau2_tailoring.load_toolkit_class(tools_py)(FlightDB.load(AIRLINE_DB_PATH))
            if not toolkit.get_tools():
                self._apply_error = "apply: candidate toolkit exposes no tools"
                return
            tau2_tailoring.set_candidate(tools_py)
        except Exception as e:  # noqa: BLE001 — apply must never raise
            self._apply_error = f"apply failed: {type(e).__name__}: {e}"

    # ---- running ---------------------------------------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        return self.run_trials([task], ctx, n_trials=1, base_seed=seed)[task.id][0]

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        return {tid: rs[0] for tid, rs in
                self.run_trials(tasks, ctx, n_trials=1, base_seed=seed).items()}

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int, base_seed: int) -> dict:
        n_trials = max(1, int(n_trials))
        # Unknown ids FIRST — before any path is computed or tau2 is called.
        known_ids = set(self._tasks_by_id())
        out: dict = {}
        runnable = []
        for t in tasks:
            if str(t.id) not in known_ids:
                out[t.id] = [Rollout(task_id=t.id, error="unknown task") for _ in range(n_trials)]
            else:
                runnable.append(t)
        if not runnable:
            return out

        def _all_errored(msg: str) -> dict:
            for t in runnable:
                out[t.id] = [Rollout(task_id=t.id, error=msg) for _ in range(n_trials)]
            return out

        if self._apply_error:
            return _all_errored(self._apply_error)
        if tau2_tailoring._state["tools_path"] is None:
            return _all_errored("no candidate applied (apply() was not called)")

        from tau2.data_model.simulation import TextRunConfig
        from tau2.runner import run_tasks

        ctx = Path(ctx)
        native_dir = ctx.parent.parent / "native_sims" / ctx.name
        save_path = self._new_results_path(native_dir)

        llm_args = _gateway_llm_args()
        config = TextRunConfig(
            domain=DOMAIN,
            agent=AGENT,
            llm_agent=_litellm_model(_bare_model("TAU2_AGENT_MODEL")),
            llm_args_agent=dict(llm_args),
            user=USER,
            llm_user=_litellm_model(_bare_model("TAU2_USER_MODEL")),
            llm_args_user=dict(llm_args),
            num_trials=n_trials,
            max_steps=100,
            max_errors=10,
            max_concurrency=MAX_CONCURRENCY,
            seed=int(base_seed),
            verbose_logs=False,
            workers=0,
        )
        by_id = self._tasks_by_id()
        try:
            results = run_tasks(config, [by_id[str(t.id)] for t in runnable],
                                save_path=save_path, console_display=False)
        except Exception as e:  # noqa: BLE001 — infra failure, never a 0.0 score
            return _all_errored(f"run_tasks failed: {type(e).__name__}: {e}")
        self._last_native_dir = native_dir

        grouped: dict = {}
        for sim in results.simulations:
            grouped.setdefault(str(sim.task_id), []).append(sim)
        for t in runnable:
            sims = sorted(grouped.get(str(t.id), []),
                          key=lambda s: (s.trial if s.trial is not None else 1 << 30))
            rollouts = [self._to_rollout(s) for s in sims[:n_trials]]
            rollouts += [Rollout(task_id=t.id, error="omitted")
                         for _ in range(n_trials - len(rollouts))]
            out[t.id] = rollouts
        return out

    @staticmethod
    def _new_results_path(native_dir: Path) -> Path:
        # A NEW file per call: tau2 treats an existing results file as a run to resume and
        # prompts on stdin.
        native_dir.mkdir(parents=True, exist_ok=True)
        while True:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            p = native_dir / f"results_{stamp}_{os.getpid()}.json"
            if not p.exists():
                return p
            time.sleep(0.2)

    @staticmethod
    def _to_rollout(sim) -> Rollout:
        trace = sim.model_dump(mode="json")
        output = ""
        for m in reversed(sim.messages or []):
            if getattr(m, "role", None) == "assistant" and getattr(m, "content", None):
                output = m.content
                break
        term = getattr(sim.termination_reason, "value", sim.termination_reason)
        error = None
        if term == "infrastructure_error" or sim.reward_info is None:
            error = (sim.info or {}).get("error") or "infrastructure_error"
        return Rollout(
            task_id=str(sim.task_id),
            output=output,
            trace=trace,
            cost_usd=float(sim.agent_cost or 0.0) + float(sim.user_cost or 0.0),
            error=error,
            metadata={"trial": sim.trial, "seed": sim.seed, "termination_reason": term},
        )

    def trajectories(self, split: str, ctx=None):
        return self._last_native_dir

    # ---- scoring ---------------------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        trace = rollout.trace if isinstance(rollout.trace, dict) else None
        ri = (trace or {}).get("reward_info")
        if not ri:
            return Score(task_id=task.id, reward=0.0, feedback="no simulation recorded")
        reward = float(ri.get("reward") or 0.0)
        return Score(task_id=task.id, reward=reward, feedback=_feedback(trace, ri, reward),
                     raw={"db_match": ((ri.get("db_check") or {}).get("db_match"))})


# ---------------------------------------------------------------------------------------
# feedback: argument-level, gold-SAFE (never print a gold VALUE; gold arg KEYS are fine)
# ---------------------------------------------------------------------------------------

def _short(v, n: int = 240) -> str:
    s = json.dumps(v, sort_keys=True, default=str) if not isinstance(v, str) else repr(v)
    return s if len(s) <= n else s[: n - 3] + "..."


def _calls_and_results(messages: list) -> list:
    """[(call, result_content)] — the n-th tool message after an assistant turn answers its
    n-th call. Paired BY POSITION, never by id (ids may be empty)."""
    pairs = []
    i = 0
    while i < len(messages):
        m = messages[i]
        calls = (m.get("tool_calls") or []) if m.get("role") == "assistant" else []
        if calls:
            j = i + 1
            results = []
            while j < len(messages) and messages[j].get("role") == "tool":
                results.append(messages[j].get("content"))
                j += 1
            for k, c in enumerate(calls):
                pairs.append((c, results[k] if k < len(results) else None))
            i = j
        else:
            i += 1
    return pairs


def _parse(content):
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


def _profile(pairs: list) -> dict:
    """What the agent itself saw: the user's payment methods + reservations, from its own
    get_user_details results (latest wins)."""
    prof: dict = {}
    for c, res in pairs:
        if c.get("name") == "get_user_details":
            u = _parse(res)
            if isinstance(u, dict):
                prof["payment_methods"] = sorted((u.get("payment_methods") or {}).keys())
                prof["reservations"] = list(u.get("reservations") or [])
    return prof


def _arg_context(key: str, prof: dict) -> str:
    if "payment" in key and prof.get("payment_methods") is not None:
        return f"; available on the user's profile={prof['payment_methods']}"
    if key == "reservation_id" and prof.get("reservations") is not None:
        return f"; the user's reservations={prof['reservations']}"
    return ""


def _feedback(trace: dict, ri: dict, reward: float) -> str:
    messages = trace.get("messages") or []
    pairs = _calls_and_results(messages)
    prof = _profile(pairs)
    lines = [f"reward={reward:.2f}"]
    term = trace.get("termination_reason")
    if term not in ("agent_stop", "user_stop"):
        lines.append(f"simulation ended early: termination_reason={term}")
    info = ri.get("info") or {}
    if isinstance(info, dict) and info.get("note"):
        lines.append(f"note: {info['note']}")

    db = ri.get("db_check") or {}
    if db and not db.get("db_match"):
        lines.append("DB check FAILED: the final database differs from the expected end state "
                     "(a write was missing, extra, or had a wrong argument).")

    for chk in ri.get("action_checks") or []:
        if chk.get("action_match"):
            continue
        act = chk.get("action") or {}
        name = act.get("name")
        ttype = chk.get("tool_type") or "?"
        keys = act.get("compare_args")
        if keys is None:
            keys = list((act.get("arguments") or {}).keys())
        gold_args = act.get("arguments") or {}
        made = [c for c, _ in pairs if c.get("name") == name]
        if not made:
            lines.append(f"{name} ({ttype}): the required call was never made.")
            continue
        localized = False
        for c in made[:3]:
            args = c.get("arguments") or {}
            diffs = []
            for k in keys:
                if k not in args:
                    diffs.append(f"{k} missing")
                elif args.get(k) != gold_args.get(k):
                    diffs.append(f"{k}={_short(args.get(k))} is not what the task required"
                                 + _arg_context(k, prof))
            if diffs:
                localized = True
                lines.append(f"{name} ({ttype}): " + "; ".join(diffs))
        if not localized:
            lines.append(f"{name} ({ttype}): call did not match the required action.")

    tool_text = [(c.get("name"), res) for c, res in pairs if isinstance(res, str)]
    for i, chk in enumerate(ri.get("communicate_checks") or []):
        if chk.get("met"):
            continue
        val = str(chk.get("info") or "")
        seen_in = next((n for n, res in tool_text if val and val in res), None)
        if seen_in:
            lines.append(f"communicate: the value {val!r} appeared in your own {seen_in} result "
                         "but was never stated to the user.")
        else:
            lines.append(f"communicate: a required piece of information (check #{i + 1}) was "
                         "not stated to the user.")
    if len(lines) == 1:
        lines.append("all checks passed." if reward >= 1.0 else "no failing check localized.")
    return "\n".join(lines)
