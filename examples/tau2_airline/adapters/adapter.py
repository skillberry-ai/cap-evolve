"""Project adapter — optimize tau2-bench AIRLINE (system-prompt POLICY + TOOLS) via IBM RITS.

Wires cap-evolve to the tau2 airline domain:

  * ``tasks``      -> all 50 airline tasks (stable, non-empty for every split).
  * ``run_batch``  -> tau2's own batch runner (``run_tasks``) with a RITS-backed
                      ``TextRunConfig``; maps each ``SimulationRun`` to a ``Rollout``.
  * ``run_target`` -> thin wrapper over ``run_batch`` for one task.
  * ``score``      -> tau2's own reward in [0,1] (deterministic given a rollout);
                      gold-AWARE but gold-SAFE, ARGUMENT-LEVEL feedback: for each
                      failing check it names the wrong argument key + the AGENT'S OWN
                      wrong value (never the gold value) and what was available on the
                      user's own profile/state, so the optimizer can localize the fix.
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

        agent_m = rits.agent_model()
        user_m = rits.user_model()
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "100"))

        config = TextRunConfig(
            domain=DOMAIN,
            agent="llm_agent",
            llm_agent=agent_m,
            llm_args_agent=rits.llm_args_for(agent_m),
            user="user_simulator",
            llm_user=user_m,
            llm_args_user=rits.llm_args_for(user_m),
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

        for sim in sim_results.simulations:
            rollout = self._sim_to_rollout(sim)
            results[str(rollout.task_id)] = rollout

        # Any requested task with no simulation -> infra error rollout.
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
        """Map one tau2 ``SimulationRun`` to a cap-evolve ``Rollout`` (pure).

        Shared by ``run_batch`` and ``run_trials`` so the sim→Rollout contract
        (reward stashed in metadata for ``score``, infra-error detection, message
        trace, agent+user cost) is defined in exactly one place.
        """
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

    def run_trials(
        self, tasks: list[Task], ctx, *, n_trials: int, base_seed: int
    ) -> dict[str, list[Rollout]]:
        """Run ALL trials of a task batch in ONE tau2 ``run_tasks`` call.

        Builds a single ``TextRunConfig`` with ``num_trials=n_trials`` and
        ``seed=int(base_seed)``, calls tau2 ``run_tasks`` once, then groups the
        returned ``SimulationRun``s by ``(task_id, trial)``. Returns
        ``{task_id: [rollout_t0, rollout_t1, ...]}`` — a list of length ``n_trials``
        in trial order, None-filling any (task, trial) tau2 didn't produce. This is
        much faster than looping ``run_batch`` per trial because tau2 schedules the
        whole task×trial grid under one concurrency pool.
        """
        import os

        import rits  # sibling module
        from tau2.data_model.simulation import TextRunConfig
        from tau2.runner import run_tasks

        n_trials = int(n_trials)
        by_id = self._tau2_tasks_by_id()
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]

        # Pre-seed every requested task with a None-filled trial list so missing
        # (task, trial) pairs surface as None (the harness records them as failures).
        results: dict[str, list[Rollout]] = {t.id: [None] * n_trials for t in tasks}

        # Tasks we couldn't map -> infra error rollout for every trial.
        for t in tasks:
            if t.id not in by_id:
                results[t.id] = [
                    Rollout(task_id=t.id, error=f"task id {t.id} not found in airline task set")
                    for _ in range(n_trials)
                ]
        if not tau2_tasks or n_trials <= 0:
            return results

        agent_m = rits.agent_model()
        user_m = rits.user_model()
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "125"))

        config = TextRunConfig(
            domain=DOMAIN,
            agent="llm_agent",
            llm_agent=agent_m,
            llm_args_agent=rits.llm_args_for(agent_m),
            user="user_simulator",
            llm_user=user_m,
            llm_args_user=rits.llm_args_for(user_m),
            num_trials=n_trials,
            max_steps=100,
            max_errors=10,
            max_concurrency=max_concurrency,
            seed=int(base_seed),
        )

        # tau2 prints progress to stdout; the cap-evolve skills' stdout is a pure-JSON
        # contract, so redirect tau2's stdout to stderr for the duration.
        import contextlib
        import sys
        with contextlib.redirect_stdout(sys.stderr):
            sim_results = run_tasks(
                config,
                tau2_tasks,
                save_path=None,
                console_display=False,
            )

        # Group each SimulationRun into its task's per-trial slot by sim.trial.
        for sim in sim_results.simulations:
            task_id = str(sim.task_id)
            trial = int(getattr(sim, "trial", 0) or 0)
            slot = results.get(task_id)
            if slot is None:
                slot = results[task_id] = [None] * n_trials
            if 0 <= trial < n_trials:
                slot[trial] = self._sim_to_rollout(sim)

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

        # Surface the message trace to the feedback builder so it can localize
        # defects from the agent's OWN tool calls / observed state (gold-safe).
        # Prefer rollout.trace, then rollout.output, then any trace in metadata.
        ctx = dict(meta)
        ctx["trace"] = rollout.trace or rollout.output or meta.get("trace") or []

        feedback = self._build_feedback(reward, reward_info, ctx)
        return Score(task_id=task.id, reward=reward, feedback=feedback)

    # ---- gold-safe rollout introspection (for argument-level feedback) ----
    #
    # The learning signal must localize the defect: name the wrong ARGUMENT key
    # and the AGENT'S OWN wrong value (never the gold value), the wrong target id,
    # and — for communication misses — the value the agent failed to state when it
    # is derivable from the agent's own observed state. Everything below reads ONLY
    # the agent's own messages/tool-calls/tool-results and the user's own profile
    # (as the agent observed it via get_user_details). It NEVER reads the gold/
    # expected arguments stored in reward_info's action_check.action — those keys
    # are used solely to know WHICH argument matters; the gold VALUES are not read.

    @staticmethod
    def _iter_agent_tool_calls(meta: dict):
        """Yield (tool_name, arguments) for every ASSISTANT tool call in the trace.

        Pure read of the agent's own messages. Deterministic order (trace order).
        """
        for msg in meta.get("trace") or []:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name")
                args = tc.get("arguments") or {}
                if name:
                    yield str(name), (args if isinstance(args, dict) else {})

    @staticmethod
    def _user_profile_facts(meta: dict) -> dict:
        """Derive what the AGENT observed about the user's own profile/state.

        Reads only ``get_user_details``/``get_reservation_details`` TOOL RESULTS in
        the trace (the agent's own observations — gold-safe). Returns:
          {"payment_methods": [...ids...], "reservation_ids": [...ids...]}
        Best-effort and deterministic; returns empty lists when nothing is parseable.
        """
        import json
        import re

        payment_ids: list[str] = []
        reservation_ids: list[str] = []
        seen_p: set[str] = set()
        seen_r: set[str] = set()

        for msg in meta.get("trace") or []:
            if not isinstance(msg, dict) or msg.get("role") != "tool":
                continue
            content = msg.get("content")
            if not isinstance(content, str) or not content:
                continue
            obj = None
            try:
                obj = json.loads(content)
            except Exception:
                obj = None

            if isinstance(obj, dict):
                pm = obj.get("payment_methods")
                if isinstance(pm, dict):
                    for pid in pm.keys():
                        if pid not in seen_p:
                            seen_p.add(pid)
                            payment_ids.append(str(pid))
                elif isinstance(pm, list):
                    for entry in pm:
                        pid = entry.get("id") if isinstance(entry, dict) else None
                        if pid and pid not in seen_p:
                            seen_p.add(pid)
                            payment_ids.append(str(pid))
                res = obj.get("reservations")
                if isinstance(res, list):
                    for rid in res:
                        rid = str(rid)
                        if rid not in seen_r:
                            seen_r.add(rid)
                            reservation_ids.append(rid)
                rid = obj.get("reservation_id")
                if rid and str(rid) not in seen_r:
                    seen_r.add(str(rid))
                    reservation_ids.append(str(rid))
            else:
                # Fall back to regex over the raw text for known id shapes.
                for pid in re.findall(r"\b(?:credit_card|gift_card|certificate)_\d+\b", content):
                    if pid not in seen_p:
                        seen_p.add(pid)
                        payment_ids.append(pid)

        return {"payment_methods": payment_ids, "reservation_ids": reservation_ids}

    @classmethod
    def _localize_action(cls, gold_name: str, gold_keys: list[str], meta: dict, facts: dict) -> str:
        """Argument-level, gold-SAFE detail for one failed action check.

        ``gold_keys`` are the argument KEYS that matter (names only — gold-safe).
        We report the AGENT'S OWN value for those keys from its own call(s) of
        ``gold_name``; we never read or print the gold values. For id-shaped keys
        we surface what was AVAILABLE on the user's own profile/state.
        """
        agent_calls = [args for (n, args) in cls._iter_agent_tool_calls(meta) if n == gold_name]
        if not agent_calls:
            return f"{gold_name}: was never called (or not called correctly)"

        keys = gold_keys or sorted({k for c in agent_calls for k in c.keys()})
        # Use the LAST call of the tool (the state the agent settled on); deterministic.
        used = agent_calls[-1]
        parts: list[str] = []
        for k in keys:
            v = used.get(k, "<missing>")
            detail = f"{k}={v!r}"
            kl = k.lower()
            if "payment" in kl and facts.get("payment_methods"):
                avail = facts["payment_methods"]
                if v not in avail:
                    detail += f" (not on the user's profile; available={avail})"
            elif ("reservation" in kl or kl in {"reservation_id", "target", "res_id"}) and facts.get(
                "reservation_ids"
            ):
                avail = facts["reservation_ids"]
                if v not in avail:
                    detail += f" (not among the user's reservations; held={avail})"
            parts.append(detail)
        return f"{gold_name}: agent used " + ", ".join(parts)

    @classmethod
    def _localize_communicate(cls, check: dict, meta: dict, facts: dict) -> str | None:
        """Name a derivable un-stated value for a missed communicate check (gold-safe).

        We only surface a concrete value the agent could have computed from its OWN
        observed state (e.g. a total cost summed from the user's observed payment/
        reservation data). The check's ``info`` text may embed the gold answer, so we
        DO NOT echo it verbatim — we classify the topic and, when a total is derivable,
        name the computed value. Returns None when nothing is safely derivable.
        """
        info = str(check.get("info") or "").lower()
        if "total" in info and ("cost" in info or "price" in info or "$" in info):
            total = cls._derive_total_cost(meta)
            if total is not None:
                return f"did not state the computed total cost (derivable from your own observed amounts: ${total:.2f})"
            return "did not state the computed total cost (sum the amounts you already observed and state it)"
        return None

    @staticmethod
    def _derive_total_cost(meta: dict):
        """Best-effort, deterministic sum of payment amounts the AGENT itself observed.

        Reads only the agent's own tool-call arguments / tool results in the trace
        (e.g. ``payment``/``amount`` fields). Returns a float total or None.
        """
        import json

        total = 0.0
        found = False
        # From the agent's own write-tool-call payment arguments.
        for _name, args in Adapter._iter_agent_tool_calls(meta):
            pay = args.get("payment") if isinstance(args, dict) else None
            if isinstance(pay, dict) and isinstance(pay.get("amount"), (int, float)):
                total += float(pay["amount"])
                found = True
            elif isinstance(args.get("amount"), (int, float)):
                total += float(args["amount"])
                found = True
        if found:
            return total
        # Otherwise from observed tool results carrying an "amount"/"total".
        for msg in meta.get("trace") or []:
            if not isinstance(msg, dict) or msg.get("role") != "tool":
                continue
            content = msg.get("content")
            if not isinstance(content, str):
                continue
            try:
                obj = json.loads(content)
            except Exception:
                continue
            if isinstance(obj, dict):
                for k in ("total", "total_cost", "amount"):
                    if isinstance(obj.get(k), (int, float)):
                        total += float(obj[k])
                        found = True
        return total if found else None

    @classmethod
    def _build_feedback(cls, reward: float, reward_info: dict, meta: dict) -> str:
        """Argument-level, gold-SAFE learning signal.

        For each failing check we localize the defect: name the wrong ARGUMENT key +
        the AGENT'S OWN wrong value (never the gold value), the wrong target id, and
        — for communicate misses — the un-stated computed value when derivable from
        the agent's own state. A tool-name-only signal is too coarse for the optimizer
        to localize a fix. Falls back to the tool-name message when a piece cannot be
        safely derived. Deterministic on a fixed rollout.
        """
        if not reward_info:
            if reward >= 1.0:
                return "Task fully solved (reward 1.0)."
            return (
                f"Task scored {reward:.3f}. No detailed check breakdown is available "
                "for this rollout."
            )

        facts = cls._user_profile_facts(meta)
        lines: list[str] = [f"Task reward: {reward:.3f}."]

        # DB check (final environment state matches expectation).
        db_check = reward_info.get("db_check")
        if db_check is not None and not db_check.get("db_match", True):
            lines.append(
                "Database state does NOT match the expected final state — a "
                "required write (book/update/cancel) was missing, wrong, or extra. "
                "See the per-action detail below for the specific wrong argument."
            )

        # Action checks: localize each failed action at the ARGUMENT level.
        action_checks = reward_info.get("action_checks") or []
        details: list[str] = []
        for ac in action_checks:
            if ac.get("action_match", True):
                continue
            action = ac.get("action") or {}
            name = action.get("name") or action.get("func_name") or "an action"
            # KEYS that matter (names only — gold-safe). Prefer compare_args; else the
            # gold arg keys (keys, not values). Values are never read.
            gold_keys = action.get("compare_args")
            if not gold_keys:
                gold_args = action.get("arguments")
                gold_keys = sorted(gold_args.keys()) if isinstance(gold_args, dict) else []
            try:
                details.append(cls._localize_action(str(name), list(gold_keys or []), meta, facts))
            except Exception:
                details.append(f"{name}: not performed correctly (right tool, right arguments)")
        if details:
            lines.append("Action-level defects (your own wrong values): " + "; ".join(details) + ".")

        # Communicate checks: name the un-stated derivable value when possible.
        communicate_checks = reward_info.get("communicate_checks") or []
        missed_comm = [c for c in communicate_checks if not c.get("met", True)]
        if missed_comm:
            comm_details: list[str] = []
            for c in missed_comm:
                try:
                    d = cls._localize_communicate(c, meta, facts)
                except Exception:
                    d = None
                if d:
                    comm_details.append(d)
            if comm_details:
                lines.append("Communication misses: " + "; ".join(comm_details) + ".")
            else:
                lines.append(
                    f"{len(missed_comm)} required piece(s) of information were not clearly "
                    "communicated to the user. State the confirmations/details (e.g. the "
                    "computed total, the new flight times) the policy requires you to convey."
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
