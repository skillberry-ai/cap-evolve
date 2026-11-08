"""cap-evolve adapter: VANILLA tau2-bench airline, blackbox (Skillberry) delivery arm.

The capability is the airline agent's TOOL SURFACE, delivered as the store skill ``my_skill``:
each ``my_skill/scripts/<tool>.py`` is one tool the Skillberry Proxy-Agent (SPA) injects, and
each calls a frozen ``env_<tool>`` primitive that runs tau2's real tool inside tau2's own
EnvironmentManager (the env service, port 8004). The agent under test is tau2's stock
``llm_agent`` (registered as ``llm_agent_skillberry``) whose model is the sentinel
``ibm/skillberry-local``, routed to SPA; the user simulator stays on the gateway.

tau2 is never edited: the tailoring that makes it SPA-aware lives in ``tau2_tailoring.py``
beside this file. Contract: core/cap_evolve/adapter.py + docs/ADAPTER_CONTRACT.md.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
import sys
import time
from pathlib import Path

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

SKILL_NAME = "my_skill"
FROZEN_TAG = "tau2_airline_primitives"
N_PRIMITIVES = 14
MAX_CONCURRENCY = 5
FALLBACK_MODEL = "aws/gpt-oss-120b"

_HERE = Path(__file__).resolve()
PROJECT_DIR = _HERE.parents[1]
PRIMITIVES = PROJECT_DIR / "seed_capability" / "primitive_tools" / "functions.py"


def _load_dotenv() -> None:
    """Walk up from this file to the first ``.env``; setdefault each KEY=VALUE (no python-dotenv)."""
    for parent in _HERE.parents:
        env = parent / ".env"
        if not env.is_file():
            continue
        for raw in env.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, val)
        return


def _route(model: str) -> str:
    """The litellm route ``openai/<model>``, normalized once and idempotently."""
    m = model.strip()
    while m.startswith("openai/"):
        m = m[len("openai/"):]
    return f"openai/{m}"


def _bare(model: str) -> str:
    return _route(model)[len("openai/"):]


def _blackbox_scripts() -> Path:
    skills = os.environ.get("CAPEVOLVE_SKILLS_DIR")
    if skills:
        return Path(skills) / "interventions" / "llm-proxies" / "blackbox" / "scripts"
    for p in _HERE.parents:
        cand = p / "skills" / "interventions" / "llm-proxies" / "blackbox" / "scripts"
        if cand.is_dir():
            return cand
    raise RuntimeError("cannot locate skills/interventions/llm-proxies/blackbox/scripts")


def _blackbox_env():
    scripts = str(_blackbox_scripts())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import blackbox_env
    return blackbox_env


def _tailoring():
    if str(_HERE.parent) not in sys.path:
        sys.path.insert(0, str(_HERE.parent))
    import tau2_tailoring
    return tau2_tailoring


class Adapter(CapabilityAdapter):

    def __init__(self) -> None:
        _load_dotenv()
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        self._tau2_tasks = None
        self._apply_error: str | None = "apply() has not run for this candidate"
        self._last_dir: Path | None = None

    # ------------------------------------------------------------------ models (#3b)
    def agent_model(self) -> str:
        """The GATEWAY agent model, bare. TAU2_AGENT_MODEL is the one source; else SPA_MODEL_NAME."""
        m = os.environ.get("TAU2_AGENT_MODEL") or os.environ.get("SPA_MODEL_NAME") or FALLBACK_MODEL
        return _bare(m)

    def user_model(self) -> str:
        return _bare(os.environ.get("TAU2_USER_MODEL") or FALLBACK_MODEL)

    def runner_model(self) -> str | None:
        return self.agent_model()

    def _gateway_args(self) -> dict:
        base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
        if not base or not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_BASE_URL / OPENAI_API_KEY not set — put them in the repo .env")
        return {"api_base": base, "temperature": 0.0}      # NO api_key: litellm reads the env

    # ------------------------------------------------------------------ tasks
    def _tau2_task_map(self) -> dict:
        if self._tau2_tasks is None:
            from tau2.domains.airline.environment import get_tasks
            self._tau2_tasks = {str(t.id): t for t in get_tasks("base")}
        return self._tau2_tasks

    def tasks(self, split: str) -> list[Task]:
        return [Task(id=tid, input=None, metadata={"domain": "airline"})
                for tid in self._tau2_task_map()]

    # ------------------------------------------------------------------ delivery
    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """Deploy the candidate as the ONLY store skill and restart SPA. NEVER raises."""
        self._apply_error = None
        try:
            if edits:
                self.materialize(candidate_dir, edits)
            cdir = Path(candidate_dir).resolve()
            skill_dir = cdir / SKILL_NAME
            if not (skill_dir / "SKILL.md").exists():
                self._apply_error = f"{SKILL_NAME}/SKILL.md missing under {cdir}"
                return
            if not (cdir / "primitive_tools" / "functions.py").exists():
                self._apply_error = f"primitive_tools/functions.py missing under {cdir}"
                return
            _tailoring().install("blackbox")
            bb = _blackbox_env()
            protect = bb.Protection(tags=(FROZEN_TAG,))
            if len(protect.present_names()) < N_PRIMITIVES:
                bb.import_standalone_tools(str(PRIMITIVES), tags=(FROZEN_TAG,))
            bb.reset_store_to_skill(skill_dir, SKILL_NAME, protect)
            bb.restart_spa(SKILL_NAME, SPA_MODEL_NAME=_route(self.agent_model()))
        except Exception as e:  # noqa: BLE001 — a failed deploy errors the candidate, never the run
            self._apply_error = f"{type(e).__name__}: {e}"

    # ------------------------------------------------------------------ running
    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        return self.run_trials([task], ctx, n_trials=1, base_seed=seed)[task.id][0]

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        return {tid: rs[0] for tid, rs in
                self.run_trials(tasks, ctx, n_trials=1, base_seed=seed).items()}

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int, base_seed: int) -> dict:
        known = self._tau2_task_map()
        out: dict = {t.id: [Rollout(task_id=t.id, error="unknown task") for _ in range(n_trials)]
                     for t in tasks if t.id not in known}
        todo = [t for t in tasks if t.id in known]
        if not todo:
            return out
        if self._apply_error:
            for t in todo:
                out[t.id] = [Rollout(task_id=t.id, error=f"deploy failed: {self._apply_error}")
                             for _ in range(n_trials)]
            return out

        from tau2.data_model.simulation import TextRunConfig
        from tau2.runner import run_tasks

        tailoring = _tailoring()
        bb = _blackbox_env()
        ctx = Path(ctx).resolve()
        native = ctx.parent.parent / "native_sims" / ctx.name
        native.mkdir(parents=True, exist_ok=True)
        while True:
            stamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:6]}"
            save_path = native / f"results_{stamp}.json"
            if not save_path.exists():
                break
            time.sleep(1.0)           # an existing results file is a run tau2 would RESUME
        log_path = native / f"started_env_ids_{stamp}.txt"

        try:
            gateway = self._gateway_args()
            config = TextRunConfig(
                domain=tailoring.DOMAIN, agent=tailoring.AGENT,
                llm_agent=tailoring.SENTINEL,
                llm_args_agent={"custom_llm_provider": "openai", "base_url": bb.spa_base_url(),
                                "api_key": "EMPTY", "temperature": 0.0},
                user="user_simulator", llm_user=_route(self.user_model()),
                llm_args_user=gateway,
                num_trials=n_trials, max_steps=100, max_errors=10,
                max_concurrency=MAX_CONCURRENCY, seed=base_seed, verbose_logs=False, workers=0)
            tailoring.begin_batch(log_path)
            results = run_tasks(config, [known[t.id] for t in todo], save_path=save_path,
                                console_display=False)
        except Exception as e:  # noqa: BLE001 — infra failure: exclude, never score 0.0
            for t in todo:
                out[t.id] = [Rollout(task_id=t.id, error=f"run_tasks failed: {type(e).__name__}: {e}")
                             for _ in range(n_trials)]
            return out
        finally:
            try:
                tailoring.sweep(log_path)
            except Exception:  # noqa: BLE001
                pass
        self._last_dir = native

        by: dict = {}
        for sim in results.simulations:
            by[(str(sim.task_id), int(sim.trial or 0))] = sim
        for t in todo:
            out[t.id] = [self._to_rollout(by[(t.id, k)]) if (t.id, k) in by
                         else Rollout(task_id=t.id, error="omitted") for k in range(n_trials)]
        return out

    @staticmethod
    def _to_rollout(sim) -> Rollout:
        output = ""
        for m in reversed(sim.messages or []):
            if getattr(m, "role", None) == "assistant" and getattr(m, "content", None):
                output = m.content
                break
        term = getattr(sim.termination_reason, "value", sim.termination_reason)
        error = None
        if term == "infrastructure_error" or sim.reward_info is None:
            error = (sim.info or {}).get("error") or "infrastructure_error"
        return Rollout(task_id=str(sim.task_id), output=output,
                       trace=sim.model_dump(mode="json"),
                       cost_usd=float(sim.agent_cost or 0) + float(sim.user_cost or 0),
                       error=error)

    def trajectories(self, split: str, ctx=None):
        return self._last_dir

    # ------------------------------------------------------------------ scoring (#4)
    def score(self, task: Task, rollout: Rollout) -> Score:
        trace = rollout.trace if isinstance(rollout.trace, dict) else None
        ri = (trace or {}).get("reward_info")
        if not ri:
            return Score(task_id=task.id, reward=0.0, feedback="no simulation recorded")
        reward = float(ri.get("reward") or 0.0)
        if reward >= 1.0:
            return Score(task_id=task.id, reward=reward, feedback="pass: all reward checks met")
        return Score(task_id=task.id, reward=reward,
                     feedback=_feedback(ri, trace.get("messages") or []))


# ---------------------------------------------------------------------- gold-safe feedback

def _calls_with_results(messages: list) -> list:
    """[(name, arguments, parsed_result)] for every assistant tool call, paired BY POSITION."""
    out = []
    i = 0
    while i < len(messages):
        m = messages[i]
        calls = (m.get("tool_calls") or []) if m.get("role") == "assistant" else []
        results = []
        j = i + 1
        while j < len(messages) and messages[j].get("role") == "tool":
            results.append(messages[j].get("content"))
            j += 1
        for n, tc in enumerate(calls):
            res = results[n] if n < len(results) else None
            try:
                res = json.loads(res) if isinstance(res, str) else res
            except ValueError:
                pass
            out.append((tc.get("name"), tc.get("arguments") or {}, res))
        i = j if calls else i + 1
    return out


def _profile_payment_ids(calls: list) -> list:
    ids = []
    for name, _, res in calls:
        if name == "get_user_details" and isinstance(res, dict):
            ids.extend((res.get("payment_methods") or {}).keys())
    return sorted(set(ids))


def _payment_ids_in(value) -> list:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v.get("payment_id") for v in value if isinstance(v, dict) and v.get("payment_id")]
    return []


def _feedback(ri: dict, messages: list) -> str:
    calls = _calls_with_results(messages)
    lines = [f"reward={float(ri.get('reward') or 0.0):.2f}"]
    db = ri.get("db_check") or {}
    if db and not db.get("db_match"):
        lines.append("DB check FAILED: the final database differs from the expected end state.")
    available = _profile_payment_ids(calls)
    for chk in ri.get("action_checks") or []:
        if chk.get("action_match"):
            continue
        act = chk.get("action") or {}
        name = act.get("name")
        gold_args = act.get("arguments") or {}
        keys = act.get("compare_args") or list(gold_args)
        mine = [a for n, a, _ in calls if n == name]
        if not mine:
            lines.append(f"{name}: expected call was never made by the agent.")
            continue
        last = mine[-1]
        diffs = [k for k in keys if last.get(k) != gold_args.get(k)]
        if not diffs:
            lines.append(f"{name}: called, but no call matched the required arguments.")
            continue
        for k in diffs:
            val = last.get(k, "<missing>")
            msg = f"{name}: argument {k}={json.dumps(val, default=str)} is wrong"
            if "payment" in k and available:
                bad = [p for p in _payment_ids_in(val) if p not in available]
                if bad:
                    msg += f" ({bad} not on the user's profile; available={available})"
            lines.append(msg + ".")
    comm = [c for c in (ri.get("communicate_checks") or []) if not c.get("met")]
    if comm:
        said = " ".join(str(m.get("content") or "") for m in messages if m.get("role") == "assistant")
        unstated = [str(res) for n, _, res in calls
                    if n == "calculate" and res is not None and str(res) not in said]
        msg = f"{len(comm)} required piece(s) of information were not communicated to the user"
        if unstated:
            msg += f"; the agent computed {unstated} with calculate but never stated it"
        lines.append(msg + ".")
    for chk in ri.get("env_assertions") or []:
        if not chk.get("met"):
            lines.append("an environment assertion on the final state failed.")
    for chk in ri.get("nl_assertions") or []:
        if not chk.get("met"):
            lines.append("a natural-language assertion about the conversation was not met.")
    return "\n".join(lines)
