"""Project adapter — optimize tau2-bench AIRLINE (system-prompt POLICY + TOOLS) via IBM RITS.

Wires cap-evolve to the tau2 airline domain:

  * ``tasks``      -> all 50 airline tasks (stable, non-empty for every split).
  * ``run_batch``  -> tau2's own batch runner (``run_tasks``) with a RITS-backed
                      ``TextRunConfig``; maps each ``SimulationRun`` to a ``Rollout``.
  * ``run_target`` -> thin wrapper over ``run_batch`` for one task.
  * ``score``      -> tau2's own reward in [0,1] (deterministic given a rollout);
                      gold-AWARE but gold-SAFE feedback from reward_info checks.
  * ``apply``      -> makes a candidate LIVE by overriding the registry's airline
                      env constructor (candidate policy + candidate tools). Idempotent;
                      always resets to a pristine snapshot before applying.

``cap-evolve check`` does NO live LLM call: ``tasks``/``score``/``materialize`` are
network-free, and RITS endpoint resolution is lazy (only on a real ``run_batch``).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Make sibling helper modules (rits.py) importable regardless of caller cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

DOMAIN = "airline"


# ---------------------------------------------------------------------------
# Candidate building helpers (pure; no network)
# ---------------------------------------------------------------------------


def _load_candidate_tools_class(tools_path: Path):
    """Import a candidate ``tools/tools.py`` and return its ``AirlineTools`` class.

    Each call execs the file FRESH (unique module name) so the candidate's live
    code — including any edits the optimizer made — is reloaded and no module
    state leaks between ``apply`` calls. Returns ``(AirlineTools_class, REMOVE_TOOLS)``
    or ``(None, set())`` when the file is absent (pristine fallback).
    """
    if not tools_path.exists():
        return None, set()
    spec = importlib.util.spec_from_file_location(
        f"capevolve_candidate_tools_{abs(hash(str(tools_path)))}_{id(object())}",
        tools_path,
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    cls = getattr(mod, "AirlineTools", None)
    remove = set(getattr(mod, "REMOVE_TOOLS", set()) or set())
    return cls, remove


def _build_candidate_tools(candidate_dir: Path):
    """Instantiate the candidate ``AirlineTools`` from ``tools/tools.py`` on the FlightDB.

    The candidate file IS the implementation: its ``AirlineTools`` class carries the
    real tool bodies (and any optimizer edits / added composite tools). We exec it
    fresh, instantiate it with a freshly-loaded ``FlightDB`` (so state resets each
    apply), and optionally drop tools listed in the module's ``REMOVE_TOOLS`` set.
    Falls back to tau2's pristine ``AirlineTools`` when no candidate file exists.
    """
    from tau2.domains.airline.data_model import FlightDB
    from tau2.domains.airline.tools import AirlineTools as _PristineAirlineTools
    from tau2.domains.airline.utils import AIRLINE_DB_PATH

    db = FlightDB.load(AIRLINE_DB_PATH)

    tools_path = candidate_dir / "tools" / "tools.py"
    cand_cls, remove = _load_candidate_tools_class(tools_path)
    AirlineToolsClass = cand_cls or _PristineAirlineTools

    if not remove:
        return AirlineToolsClass(db)

    # Remove tools from the exposed set by filtering at the get_tools boundary
    # (``_func_tools`` is a metaclass-managed class property with no setter).
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
    """Read the candidate policy text; fall back to tau2's canonical policy."""
    policy_path = candidate_dir / "policy" / "policy.md"
    if policy_path.exists():
        return policy_path.read_text(encoding="utf-8")
    from tau2.domains.airline.utils import AIRLINE_POLICY_PATH

    return Path(AIRLINE_POLICY_PATH).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class Adapter(CapabilityAdapter):

    # Snapshot of the pristine airline env constructor (set on first apply).
    _original_env_ctor = None

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return ALL 50 tau2 airline tasks for any split (stable, non-empty).

        The harness filters by frozen split ids; returning the full set keeps
        ``tasks`` deterministic and free of network.
        """
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        tau2_tasks = airline_get_tasks(None)  # all tasks, no split filtering
        out: list[Task] = []
        for t in tau2_tasks:
            out.append(
                Task(
                    id=str(t.id),
                    input=str(getattr(t, "id", "")),
                    metadata={"domain": DOMAIN},
                )
            )
        return out

    # ---- running ---------------------------------------------------------

    def _tau2_tasks_by_id(self):
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        return {str(t.id): t for t in airline_get_tasks(None)}

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run a batch of airline tasks through tau2's own batch runner.

        Builds a RITS-backed ``TextRunConfig`` and calls ``run_tasks`` with
        ``num_trials=1`` (cap-evolve owns trials) and ``seed=int(seed)`` so each
        cap-evolve trial is an independent draw. Returns ``{task_id: Rollout}``.
        """
        import os

        import rits  # sibling module
        from tau2.data_model.simulation import TextRunConfig
        from tau2.data_model.simulation import TerminationReason
        from tau2.runner import run_tasks

        by_id = self._tau2_tasks_by_id()
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]
        results: dict[str, Rollout] = {}

        # Tasks we couldn't map -> infra error rollouts (shouldn't happen).
        for t in tasks:
            if t.id not in by_id:
                results[t.id] = Rollout(
                    task_id=t.id, error=f"task id {t.id} not found in airline task set"
                )
        if not tau2_tasks:
            return results

        llm_args = rits.llm_args()
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "100"))

        config = TextRunConfig(
            domain=DOMAIN,
            agent="llm_agent",
            llm_agent=rits.LITELLM_MODEL,
            llm_args_agent=dict(llm_args),
            user="user_simulator",
            llm_user=rits.LITELLM_MODEL,
            llm_args_user=dict(llm_args),
            num_trials=1,
            max_steps=100,
            max_errors=10,
            max_concurrency=max_concurrency,
            seed=int(seed),
        )

        # tau2's run_tasks reconfigures loguru to print() and emits progress to
        # STDOUT. The cap-evolve skills' stdout is a pure-JSON contract, so redirect
        # tau2's stdout to stderr for the duration to keep that contract intact.
        import contextlib
        import sys
        with contextlib.redirect_stdout(sys.stderr):
            sim_results = run_tasks(
                config,
                tau2_tasks,
                save_path=None,
                console_display=False,
            )

        infra_reasons = {
            TerminationReason.INFRASTRUCTURE_ERROR,
            TerminationReason.UNEXPECTED_ERROR,
        }

        for sim in sim_results.simulations:
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

            results[task_id] = Rollout(
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

        # Any requested task with no simulation -> infra error rollout.
        for t in tasks:
            if t.id not in results:
                results[t.id] = Rollout(
                    task_id=t.id,
                    error="no simulation produced for task (tau2 returned nothing)",
                    metadata={"domain": DOMAIN, "tau2_reward": 0.0},
                )
        return results

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run a single task by delegating to ``run_batch`` (base class requires this)."""
        batch = self.run_batch([task], ctx, seed=seed)
        return batch.get(task.id, Rollout(task_id=task.id, error="no rollout produced"))

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Score a rollout with tau2's own reward; gold-AWARE, gold-SAFE feedback.

        Deterministic given the rollout: reads the reward/reward_info stashed in
        ``rollout.metadata`` during ``run_batch``. Infra-errored rollouts -> 0.0
        with feedback noting it's uncontrollable.
        """
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

        feedback = self._build_feedback(reward, reward_info, meta)
        return Score(task_id=task.id, reward=reward, feedback=feedback)

    @staticmethod
    def _build_feedback(reward: float, reward_info: dict, meta: dict) -> str:
        """Summarize missed checks WITHOUT printing the literal gold answer."""
        if not reward_info:
            if reward >= 1.0:
                return "Task fully solved (reward 1.0)."
            return (
                f"Task scored {reward:.3f}. No detailed check breakdown is available "
                "for this rollout."
            )

        lines: list[str] = [f"Task reward: {reward:.3f}."]

        # DB check (final environment state matches expectation).
        db_check = reward_info.get("db_check")
        if db_check is not None:
            if not db_check.get("db_match", True):
                lines.append(
                    "Database state does NOT match the expected final state — a "
                    "required write (book/update/cancel) was missing, wrong, or extra."
                )

        # Action checks: which required actions were not performed correctly.
        action_checks = reward_info.get("action_checks") or []
        missed_actions = []
        for ac in action_checks:
            if not ac.get("action_match", True):
                action = ac.get("action") or {}
                name = action.get("name") or action.get("func_name") or "an action"
                missed_actions.append(str(name))
        if missed_actions:
            uniq = sorted(set(missed_actions))
            lines.append(
                "Required action(s) not performed correctly (right tool, right "
                f"arguments): {', '.join(uniq)}. Review when/how these tools are used."
            )

        # Communicate checks: required info not communicated to the user.
        communicate_checks = reward_info.get("communicate_checks") or []
        missed_comm = [c for c in communicate_checks if not c.get("met", True)]
        if missed_comm:
            lines.append(
                f"{len(missed_comm)} required piece(s) of information were not clearly "
                "communicated to the user. Make sure to state confirmations/details the "
                "policy requires you to convey."
            )

        # NL assertions.
        nl_assertions = reward_info.get("nl_assertions") or []
        missed_nl = [n for n in nl_assertions if not n.get("met", True)]
        if missed_nl:
            lines.append(
                f"{len(missed_nl)} behavioral expectation(s) were not met. Re-check the "
                "policy steps for this scenario."
            )

        # Env assertions.
        env_assertions = reward_info.get("env_assertions") or []
        missed_env = [e for e in env_assertions if not e.get("met", True)]
        if missed_env:
            lines.append(
                f"{len(missed_env)} environment assertion(s) failed (the resulting "
                "system state was not as required)."
            )

        if reward >= 1.0 and len(lines) == 1:
            lines.append("All checks passed.")

        return " ".join(lines)

    # ---- making a candidate live ----------------------------------------

    def apply(self, candidate_dir, edits=None) -> None:
        """Make ``candidate_dir`` the live airline capability (policy + tools).

        Overrides the registry's airline env constructor so tau2's ``run_tasks``
        builds an ``Environment(domain_name="airline", policy=<candidate policy>,
        tools=<candidate AirlineTools>)``. Idempotent and safe to call repeatedly:
        the pristine constructor is snapshotted once and always reset before
        installing the new candidate's constructor.
        """
        # Write edits first (pure), if any.
        if edits:
            self.materialize(candidate_dir, edits)

        candidate_dir = Path(candidate_dir)

        from tau2.environment.environment import Environment
        from tau2.registry import registry

        # Snapshot the pristine constructor exactly once (process-global).
        if Adapter._original_env_ctor is None:
            Adapter._original_env_ctor = registry._domains.get(DOMAIN)

        # Reset to pristine before installing the new candidate (idempotency).
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
