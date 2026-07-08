"""tau2-bench adapter template — optimize the airline agent's POLICY + TOOLS.

Ready-to-use cap-evolve adapter for tau2-bench (https://github.com/sierra-research/tau2-bench).
Supports ANY litellm-compatible provider — configure via env vars (see model_config.py).

SETUP:
  1. Clone & install tau2-bench:
       git clone https://github.com/sierra-research/tau2-bench ../tau2-bench
       pip install -e ../tau2-bench

  2. Copy this directory to .capevolve/project/adapters/

  3. Set env vars (in .env or shell):
       MODEL=gpt-4.1-mini  OPENAI_API_KEY=sk-…       # OpenAI
       MODEL=anthropic/claude-sonnet-4-6  ANTHROPIC_API_KEY=…  # Anthropic
       MODEL=ollama/qwen2.5:7b-instruct  API_BASE=http://localhost:11434  # local
       MODEL=hosted_vllm/openai/gpt-oss-120b  RITS_API_KEY=…  # IBM RITS
       MODEL=litellm_proxy/my-model  LITELLM_PROXY_API_BASE=http://proxy:4000  LITELLM_PROXY_API_KEY=…

  4. Run: cap-evolve check && cap-evolve run

WHAT THIS OPTIMIZES:
  - The airline domain's system-prompt policy (policy/policy.md)
  - Optionally the tool implementations (tools/tools.py)

HOW IT WORKS:
  - tasks()      → all 50 airline tasks from tau2 (stable, no network).
  - run_batch()  → tau2's own batch runner (run_tasks) with your model.
  - score()      → tau2's own reward in [0,1] with gold-safe feedback.
  - apply()      → overrides the registry's airline env constructor.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import model_config

DOMAIN = "airline"


# ---------------------------------------------------------------------------
# Candidate building helpers (pure; no network)
# ---------------------------------------------------------------------------


def _load_candidate_tools_class(tools_path: Path):
    """Import a candidate tools/tools.py and return its AirlineTools class."""
    if not tools_path.exists():
        return None, set()
    spec = importlib.util.spec_from_file_location(
        f"capevolve_candidate_tools_{abs(hash(str(tools_path)))}_{id(object())}",
        tools_path,
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    cls = getattr(mod, "AirlineTools", None)
    remove = set(getattr(mod, "REMOVE_TOOLS", set()) or set())
    return cls, remove


def _build_candidate_tools(candidate_dir: Path):
    """Instantiate the candidate AirlineTools from tools/tools.py on the FlightDB."""
    from tau2.domains.airline.data_model import FlightDB
    from tau2.domains.airline.tools import AirlineTools as _PristineAirlineTools
    from tau2.domains.airline.utils import AIRLINE_DB_PATH

    db = FlightDB.load(AIRLINE_DB_PATH)
    tools_path = candidate_dir / "tools" / "tools.py"
    cand_cls, remove = _load_candidate_tools_class(tools_path)
    AirlineToolsClass = cand_cls or _PristineAirlineTools

    if not remove:
        return AirlineToolsClass(db)

    _remove = set(remove)
    _base_get_tools = AirlineToolsClass.get_tools

    def get_tools(self, include=None):
        tools_map = _base_get_tools(self, include=include)
        return {k: v for k, v in tools_map.items() if k not in _remove}

    def has_tool(self, tool_name: str) -> bool:
        return tool_name not in _remove and tool_name in self.tools

    CandidateTools = type(
        "CandidateAirlineTools",
        (AirlineToolsClass,),
        {"get_tools": get_tools, "has_tool": has_tool},
    )
    return CandidateTools(db)


def _read_candidate_policy(candidate_dir: Path) -> str:
    """Read the candidate policy; fall back to tau2's canonical policy."""
    policy_path = candidate_dir / "policy" / "policy.md"
    if policy_path.exists():
        return policy_path.read_text(encoding="utf-8")
    from tau2.domains.airline.utils import AIRLINE_POLICY_PATH

    return Path(AIRLINE_POLICY_PATH).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class Adapter(CapabilityAdapter):

    _original_env_ctor = None

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return ALL 50 tau2 airline tasks for any split (stable, non-empty)."""
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        tau2_tasks = airline_get_tasks(None)
        return [
            Task(
                id=str(t.id),
                input=str(getattr(t, "id", "")),
                metadata={"domain": DOMAIN},
            )
            for t in tau2_tasks
        ]

    # ---- running ---------------------------------------------------------

    def _tau2_tasks_by_id(self):
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        return {str(t.id): t for t in airline_get_tasks(None)}

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run a batch of airline tasks through tau2's own batch runner.

        Uses the model configured via MODEL env var (see model_config.py).
        """
        from tau2.data_model.simulation import TextRunConfig
        from tau2.runner import run_tasks

        by_id = self._tau2_tasks_by_id()
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]
        results: dict[str, Rollout] = {}

        for t in tasks:
            if t.id not in by_id:
                results[t.id] = Rollout(
                    task_id=t.id, error=f"task id {t.id} not found in airline task set"
                )
        if not tau2_tasks:
            return results

        llm_kwargs = model_config.llm_kwargs()
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "100"))

        config = TextRunConfig(
            domain=DOMAIN,
            agent="llm_agent",
            llm_agent=model_config.MODEL,
            llm_args_agent=dict(llm_kwargs),
            user="user_simulator",
            llm_user=model_config.MODEL,
            llm_args_user=dict(llm_kwargs),
            num_trials=1,
            max_steps=100,
            max_errors=10,
            max_concurrency=max_concurrency,
            seed=int(seed),
        )

        import contextlib

        with contextlib.redirect_stdout(sys.stderr):
            sim_results = run_tasks(
                config,
                tau2_tasks,
                save_path=None,
                console_display=False,
            )

        for sim in sim_results.simulations:
            rollout = self._sim_to_rollout(sim)
            results[str(rollout.task_id)] = rollout

        for t in tasks:
            if t.id not in results:
                results[t.id] = Rollout(
                    task_id=t.id,
                    error="no simulation produced for task (tau2 returned nothing)",
                    metadata={"domain": DOMAIN, "tau2_reward": 0.0},
                )
        return results

    @staticmethod
    def _sim_to_rollout(sim) -> Rollout:
        """Map one tau2 SimulationRun to a cap-evolve Rollout."""
        from tau2.data_model.simulation import TerminationReason

        infra_reasons = {
            TerminationReason.INFRASTRUCTURE_ERROR,
            TerminationReason.UNEXPECTED_ERROR,
        }

        task_id = str(sim.task_id)
        reward_info = sim.reward_info
        reward = (
            float(reward_info.reward)
            if reward_info is not None and reward_info.reward is not None
            else 0.0
        )
        agent_cost = sim.agent_cost or 0.0
        user_cost = sim.user_cost or 0.0
        term = sim.termination_reason
        error = None
        if term in infra_reasons:
            error = f"tau2 terminated for infrastructure reason: {term}"

        try:
            messages = [m.model_dump() for m in sim.get_messages()]
        except Exception:
            messages = None

        reward_info_dump = (
            reward_info.model_dump(mode="json") if reward_info is not None else None
        )

        return Rollout(
            task_id=task_id,
            output=messages,
            trace=messages,
            cost_usd=float(agent_cost) + float(user_cost),
            tokens=0,
            error=error,
            metadata={
                "domain": DOMAIN,
                "tau2_reward": reward,
                "tau2_reward_info": reward_info_dump,
                "termination_reason": str(term),
            },
        )

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run a single task by delegating to run_batch."""
        batch = self.run_batch([task], ctx, seed=seed)
        return batch.get(task.id, Rollout(task_id=task.id, error="no rollout produced"))

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Score a rollout with tau2's own reward; gold-SAFE feedback."""
        meta = rollout.metadata or {}

        if rollout.error:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=(
                    "Rollout did not complete for an infrastructure reason "
                    f"({rollout.error}). This is uncontrollable noise, not an agent "
                    "policy/tool failure; do not optimize against it."
                ),
            )

        reward = float(meta.get("tau2_reward", 0.0) or 0.0)
        reward_info = meta.get("tau2_reward_info") or {}
        feedback = self._build_feedback(reward, reward_info)
        return Score(task_id=task.id, reward=reward, feedback=feedback)

    @staticmethod
    def _build_feedback(reward: float, reward_info: dict) -> str:
        """Build gold-SAFE learning signal from tau2's reward breakdown."""
        if not reward_info:
            if reward >= 1.0:
                return "Task fully solved (reward 1.0)."
            return (
                f"Task scored {reward:.3f}. No detailed check breakdown is available "
                "for this rollout."
            )

        lines: list[str] = [f"Task reward: {reward:.3f}."]

        db_check = reward_info.get("db_check")
        if db_check is not None and not db_check.get("db_match", True):
            lines.append(
                "Database state does NOT match the expected final state — a "
                "required write (book/update/cancel) was missing, wrong, or extra."
            )

        action_checks = reward_info.get("action_checks") or []
        failed_actions = [ac for ac in action_checks if not ac.get("action_match", True)]
        if failed_actions:
            names = []
            for ac in failed_actions:
                action = ac.get("action") or {}
                name = action.get("name") or action.get("func_name") or "an action"
                names.append(str(name))
            lines.append(f"Failed action(s): {', '.join(names)}.")

        communicate_checks = reward_info.get("communicate_checks") or []
        missed_comm = [c for c in communicate_checks if not c.get("met", True)]
        if missed_comm:
            lines.append(
                f"{len(missed_comm)} required piece(s) of information were not clearly "
                "communicated to the user."
            )

        nl_assertions = reward_info.get("nl_assertions") or []
        missed_nl = [n for n in nl_assertions if not n.get("met", True)]
        if missed_nl:
            lines.append(f"{len(missed_nl)} behavioral expectation(s) were not met.")

        env_assertions = reward_info.get("env_assertions") or []
        missed_env = [e for e in env_assertions if not e.get("met", True)]
        if missed_env:
            lines.append(f"{len(missed_env)} environment assertion(s) failed.")

        if reward >= 1.0 and len(lines) == 1:
            lines.append("All checks passed.")

        return " ".join(lines)

    # ---- making a candidate live ----------------------------------------

    def apply(self, candidate_dir, edits=None) -> None:
        """Make candidate_dir the live airline capability (policy + tools)."""
        if edits:
            self.materialize(candidate_dir, edits)

        candidate_dir = Path(candidate_dir)

        from tau2.environment.environment import Environment
        from tau2.registry import registry

        if Adapter._original_env_ctor is None:
            Adapter._original_env_ctor = registry._domains.get(DOMAIN)

        if Adapter._original_env_ctor is not None:
            registry._domains[DOMAIN] = Adapter._original_env_ctor

        policy_text = _read_candidate_policy(candidate_dir)

        def candidate_get_environment(db=None, solo_mode: bool = False):
            if solo_mode:
                raise ValueError("Airline domain does not support solo mode")
            tools = _build_candidate_tools(candidate_dir)
            return Environment(
                domain_name=DOMAIN,
                policy=policy_text,
                tools=tools,
            )

        registry._domains[DOMAIN] = candidate_get_environment
