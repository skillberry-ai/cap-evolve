"""Project adapter — optimize tau2-bench AIRLINE's TOOL SURFACE, delivered DIRECTLY.

The capability is the airline agent's TOOLS ONLY. tau2's system prompt (the airline
policy) is NOT part of it and is never edited: the policy reaches the agent exactly as the
benchmark ships it, while the agent's TOOLS come from the candidate's ``tools/tools.py``,
which this adapter installs into tau2's own airline environment in this process.

  * ``tasks``        -> all 50 tau2 airline tasks (stable, network-free).
  * ``run_trials``   -> ONE ``tau2.run.run_tasks`` call for the whole task x trial grid
                        (the fast path cap-evolve prefers), grouped by ``sim.trial``.
  * ``run_batch``    -> the same call with ``num_trials=1`` (one cap-evolve trial).
  * ``run_target``   -> one task via ``run_batch``.
  * ``score``        -> tau2's OWN reward (``sim.reward_info.reward``), read from what the
                        run stashed — never re-run, so it is deterministic. Feedback is
                        gold-AWARE but gold-SAFE and ARGUMENT-LEVEL.
  * ``apply``        -> overrides the registry's airline env constructor so tau2 builds an
                        ``Environment`` with the CANDIDATE tools and tau2's own policy.
                        Guarded on the CANDIDATE'S SHAPE, and it NEVER raises.
  * ``trajectories`` -> the dir of tau2's native per-eval results (full transcript +
                        reward_info), under the run dir.

Nothing here touches the network at import time, so ``cap-evolve check`` stays offline.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import time
from pathlib import Path

# Sibling helper modules (gateway.py) importable regardless of the caller's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import gateway

DOMAIN = "airline"                # tau2's plain airline domain (in-process environment)
N_PRIMITIVES = 14                 # tau2's airline tool surface, the seed's starting point


# docs/TAU2_SUMMARY.md row 7: tau2's user simulator sometimes emits ``###STOP###`` in the
# SAME message as reasoning that explicitly plans to continue. That ends the conversation
# early for a reason that measures nothing about the agent, so it is recorded as infra
# noise (an errored rollout the harness EXCLUDES) rather than scored against the tools.
_STOP_LEAK_RE = re.compile(
    r"###\s*stop\s*###.{0,400}\b(?:continue|continuing|wait\s+for|must\s+wait|"
    r"keep\s+(?:going|talking)|not\s+(?:done|finished)\s+yet)\b"
    r"|\b(?:continue|continuing|wait\s+for|must\s+wait|"
    r"keep\s+(?:going|talking)|not\s+(?:done|finished)\s+yet)\b.{0,400}###\s*stop\s*###",
    re.I | re.S,
)


def _leaked_stop_continuation(messages) -> bool:
    """True iff a USER-simulator turn emits ``###STOP###`` next to leaked reasoning that
    plans to continue. Only ``user`` turns are inspected — the simulator's own voice."""
    for m in messages or []:
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str) and _STOP_LEAK_RE.search(c):
                return True
    return False


def _shown_metrics(reward: float, reward_info: dict, rollout) -> list:
    """The PRIMARY reward plus shown-only secondaries (never gate accept/reject)."""
    metrics = [{"name": "reward", "value": float(reward), "primary": True, "direction": "higher"}]
    db_check = (reward_info or {}).get("db_check") or {}
    if "db_match" in db_check:
        metrics.append({"name": "db_match", "value": 1.0 if db_check.get("db_match") else 0.0,
                        "primary": False, "direction": "higher"})
    # The gateway does not meter spend for this run, so 0.0 here means NOT MEASURED.
    metrics.append({"name": "cost_usd", "value": float(getattr(rollout, "cost_usd", 0.0) or 0.0),
                    "primary": False, "direction": "lower"})
    return metrics


# ---------------------------------------------------------------------------
# Building the candidate tool surface (pure; no network)
# ---------------------------------------------------------------------------


def _load_candidate_tools_class(tools_path: Path):
    """Import a candidate ``tools/tools.py``; return ``(AirlineTools_class, REMOVE_TOOLS)``.

    Each call execs the file FRESH under a unique module name, so the optimizer's edits are
    picked up and no module state leaks between ``apply`` calls.
    """
    spec = importlib.util.spec_from_file_location(
        f"capevolve_candidate_tools_{abs(hash(str(tools_path)))}_{id(object())}", tools_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = getattr(mod, "AirlineTools", None)
    if cls is None:
        raise RuntimeError(f"{tools_path} defines no AirlineTools class")
    return cls, set(getattr(mod, "REMOVE_TOOLS", set()) or set())


def _build_candidate_tools(candidate_dir: Path):
    """Instantiate the candidate's ``AirlineTools`` on a FRESHLY loaded ``FlightDB``.

    The candidate file IS the implementation: its class carries the real tool bodies plus
    any optimizer edits (guards, new composite tools). The DB is reloaded per environment
    so each simulation starts from tau2's pristine state — the reward's db_check compares
    against that.

    ``REMOVE_TOOLS`` is honoured at the ``get_tools`` boundary rather than by deleting
    attributes: ``_func_tools`` is a metaclass-managed class property with no setter.
    """
    from tau2.domains.airline.data_model import FlightDB
    from tau2.domains.airline.utils import AIRLINE_DB_PATH

    db = FlightDB.load(AIRLINE_DB_PATH)
    cls, remove = _load_candidate_tools_class(candidate_dir / "tools" / "tools.py")
    if not remove:
        return cls(db)

    _remove = set(remove)
    _base_get_tools = cls.get_tools

    def get_tools(self, include=None):
        return {k: v for k, v in _base_get_tools(self, include=include).items()
                if k not in _remove}

    def has_tool(self, tool_name: str) -> bool:
        return tool_name not in _remove and tool_name in self.tools

    return type("CandidateAirlineTools", (cls,),
                {"get_tools": get_tools, "has_tool": has_tool})(db)


class Adapter(CapabilityAdapter):

    # Snapshot of tau2's pristine airline env constructor (process-global, set on 1st apply).
    _original_env_ctor = None

    def __init__(self) -> None:
        self._deploy_error: str | None = None
        self._traj_dirs: dict[str, Path] = {}

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """ALL 50 tau2 airline tasks for any split (the harness filters by pinned ids).

        Network-free: ``get_tasks`` reads tau2's own task file. Deliberately NOT the
        domain's environment constructor, which would build a whole environment.
        """
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        return [Task(id=str(t.id), input=str(t.id), metadata={"domain": DOMAIN})
                for t in airline_get_tasks()]

    def _tau2_tasks_by_id(self) -> dict:
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        return {str(t.id): t for t in airline_get_tasks()}

    def runner_model(self) -> str | None:
        """The CONSUMING model: what the AGENT UNDER TEST reads the tools with."""
        # Strip the litellm route + vendor prefix so the id resolves to a capability tier
        # rather than looking like an unknown model.
        return gateway.agent_model().split("/")[-1]

    # ---- trajectories ----------------------------------------------------

    def _traj_dir(self, ctx, split: str) -> Path:
        """``<run_dir>/trajectories/<split>/`` — derived from the candidate dir the harness
        yields (``<run_dir>/candidates/<id>``), so the traces live under the run that
        produced them. Falls back to a project-local dir off-run."""
        d = None
        try:
            c = Path(ctx)
            if c.parent.name == "candidates":
                d = c.parent.parent / "trajectories" / split
        except Exception:  # noqa: BLE001
            d = None
        if d is None:
            d = Path(__file__).resolve().parents[1] / "trajectories" / split
        d.mkdir(parents=True, exist_ok=True)
        self._traj_dirs[split] = d
        return d

    def _split_of(self, ctx, task_ids: list[str]) -> str:
        """Which split this batch is, read from the run's own ``splits.json``.

        ``run_batch``/``run_trials`` are not told the split and the trajectory directory
        must not mix them. With the pinned no-holdout split every split holds the same
        ids, so ties resolve in val's favour — val is the split the optimizer reads.
        """
        try:
            import json

            c = Path(ctx)
            splits = json.loads((c.parent.parent / "splits.json").read_text(encoding="utf-8"))
            want = set(task_ids)
            for name in ("val", "train", "test"):
                ids = {str(i) for i in (splits.get(name) or [])}
                if ids and want <= ids:
                    return name
        except Exception:  # noqa: BLE001
            pass
        return "eval"

    def trajectories(self, split: str, ctx=None):
        """tau2's native per-eval results dir for ``split`` (full transcript + reward_info).

        This engine PREFERS its own per-tag rollout JSON for ``./trajectories/`` — that copy
        can be scoped to the one candidate the optimizer forks from, which a native results
        dir cannot — and uses this as the native-dir fallback. Either way the optimizer reads
        unmodified traces: the per-rollout JSON carries the same ``messages`` plus the
        ``tau2_reward_info`` breakdown this adapter stashes in ``metadata``.
        """
        d = self._traj_dirs.get(split)
        return d if d and Path(d).is_dir() else None

    # ---- running ---------------------------------------------------------

    def _errored(self, tasks: list[Task], why: str, n: int) -> dict:
        return {t.id: [Rollout(task_id=t.id, error=why) for _ in range(n)] for t in tasks}

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int,
                   base_seed: int) -> dict[str, list[Rollout]]:
        """Run the WHOLE task x trial grid in ONE tau2 ``run_tasks`` call.

        cap-evolve calls this once per candidate instead of looping ``run_batch`` per
        trial; per-trial persistence downstream is unchanged, so pass^k / SE / resume keep
        working. Returns ``{task_id: [t0, t1, ...]}`` in trial order.
        """
        n_trials = max(1, int(n_trials))
        if self._deploy_error:
            # A failed deployment is infrastructure noise, not a verdict on the capability:
            # erroring the rollouts makes the harness EXCLUDE this candidate instead of
            # scoring it 0.0.
            return self._errored(tasks, f"candidate deploy failed: {self._deploy_error}", n_trials)

        by_id = self._tau2_tasks_by_id()
        results: dict[str, list[Rollout]] = {t.id: [None] * n_trials for t in tasks}
        for t in tasks:
            if t.id not in by_id:
                results[t.id] = [Rollout(task_id=t.id, error=f"task id {t.id} not in the "
                                         "airline task set") for _ in range(n_trials)]
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]
        if not tau2_tasks:
            return results

        split = self._split_of(ctx, [t.id for t in tasks])
        save_to = (self._traj_dir(ctx, split)
                   / f"results_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.json")

        agent_m, user_m = gateway.agent_model(), gateway.user_model()
        # Validates the gateway credentials at CONFIG time (loudly) rather than as a wall
        # of 401s that would read as a bad capability.
        args = gateway.llm_args()
        gateway.register_zero_cost(agent_m, user_m)
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "125"))

        import contextlib

        from tau2.run import run_tasks

        # tau2 reconfigures loguru to print() and reports progress on STDOUT; the skills'
        # stdout is a pure-JSON contract, so tau2's goes to stderr for the duration.
        with contextlib.redirect_stdout(sys.stderr):
            sim_results = run_tasks(
                domain=DOMAIN,
                tasks=tau2_tasks,
                agent="llm_agent",
                user="user_simulator",
                llm_agent=agent_m,
                llm_args_agent=dict(args),
                llm_user=user_m,
                llm_args_user=dict(args),
                num_trials=n_trials,
                max_steps=100,
                max_errors=10,
                max_concurrency=max_concurrency,
                seed=int(base_seed),
                save_to=save_to,
                console_display=False,
                log_level=os.environ.get("TAU2_LOG_LEVEL", "WARNING"),
            )

        for sim in sim_results.simulations:
            slot = results.setdefault(str(sim.task_id), [None] * n_trials)
            trial = int(getattr(sim, "trial", 0) or 0)
            if 0 <= trial < n_trials:
                slot[trial] = self._sim_to_rollout(sim)
        return results

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """One cap-evolve trial: ``run_trials`` with ``n_trials=1``."""
        batch = self.run_trials(tasks, ctx, n_trials=1, base_seed=int(seed))
        out: dict[str, Rollout] = {}
        for t in tasks:
            trials = batch.get(t.id) or []
            out[t.id] = trials[0] if trials and trials[0] is not None else Rollout(
                task_id=t.id, error="no simulation produced for task (tau2 returned nothing)")
        return out

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """One task, via ``run_batch`` (the base contract requires this method)."""
        return self.run_batch([task], ctx, seed=seed).get(
            task.id, Rollout(task_id=task.id, error="no rollout produced"))

    @staticmethod
    def _sim_to_rollout(sim) -> Rollout:
        """One tau2 ``SimulationRun`` -> one ``Rollout`` (pure).

        The reward and the full ``reward_info`` breakdown are stashed in metadata so
        ``score`` reads a recorded number instead of re-running anything.
        """
        from tau2.data_model.simulation import TerminationReason

        reward_info = sim.reward_info
        reward = (float(reward_info.reward)
                  if reward_info is not None and reward_info.reward is not None else 0.0)
        term = sim.termination_reason
        error = None
        # In this build TASK_FAILED is set only on the exception path in run_tasks, and a
        # missing reward_info means the simulation never got as far as being evaluated —
        # both are infrastructure, not agent behaviour.
        if term == TerminationReason.TASK_FAILED:
            error = f"tau2 terminated for an infrastructure reason: {term}"
        elif reward_info is None:
            error = "tau2 produced no reward_info for this simulation (not evaluated)"

        try:
            messages = [m.model_dump(mode="json") for m in sim.messages]
        except Exception:  # noqa: BLE001
            messages = None

        if error is None and reward < 1.0 and _leaked_stop_continuation(messages):
            error = ("tau2 user-simulator emitted ###STOP### alongside leaked reasoning that "
                     "explicitly planned to continue the conversation (documented artifact, "
                     "docs/TAU2_SUMMARY.md row 7) — uncontrollable noise, not a tool failure.")

        return Rollout(
            task_id=str(sim.task_id),
            output=messages,
            trace=messages,
            cost_usd=float(sim.agent_cost or 0.0) + float(sim.user_cost or 0.0),
            tokens=0,
            error=error,
            metadata={
                "domain": DOMAIN,
                "tau2_reward": reward,
                "tau2_reward_info": (reward_info.model_dump(mode="json")
                                     if reward_info is not None else None),
                "termination_reason": str(term),
            },
        )

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """tau2's own reward, plus a gold-SAFE, ARGUMENT-LEVEL learning signal.

        DETERMINISTIC on a fixed rollout: everything is read from what the run recorded.
        """
        meta = rollout.metadata or {}
        if rollout.error:
            return Score(task_id=task.id, reward=0.0,
                         feedback=("Rollout did not complete for an infrastructure reason "
                                   f"({rollout.error}). This is uncontrollable noise, not a "
                                   "tool-surface failure; do not optimize against it."),
                         metrics=_shown_metrics(0.0, {}, rollout))

        reward = float(meta.get("tau2_reward", 0.0) or 0.0)
        reward_info = meta.get("tau2_reward_info") or {}
        ctx = dict(meta)
        ctx["trace"] = rollout.trace or rollout.output or meta.get("trace") or []
        return Score(task_id=task.id, reward=reward,
                     feedback=self._build_feedback(reward, reward_info, ctx),
                     metrics=_shown_metrics(reward, reward_info, rollout))

    # ---- gold-safe rollout introspection (argument-level feedback) --------
    #
    # Everything below reads ONLY the agent's own messages / tool calls / observed tool
    # results. ``reward_info`` is used to learn WHICH check and WHICH argument KEY failed;
    # the gold VALUES stored beside those keys are never read or printed.

    @staticmethod
    def _iter_agent_tool_calls(meta: dict):
        """(tool_name, arguments) for every assistant tool call, in trace order."""
        for msg in meta.get("trace") or []:
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls") or []:
                if isinstance(tc, dict) and tc.get("name"):
                    args = tc.get("arguments")
                    yield str(tc["name"]), (args if isinstance(args, dict) else {})

    @staticmethod
    def _user_profile_facts(meta: dict) -> dict:
        """What the AGENT ITSELF observed about the user's own state (gold-safe).

        Parsed from the agent's own ``get_user_details`` / ``get_reservation_details`` tool
        RESULTS, so the feedback can say what WAS available without reading gold.
        """
        import json

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
            try:
                obj = json.loads(content)
            except Exception:  # noqa: BLE001
                obj = None
            if isinstance(obj, dict):
                pm = obj.get("payment_methods")
                ids = (list(pm.keys()) if isinstance(pm, dict)
                       else [e.get("id") for e in pm if isinstance(e, dict)]
                       if isinstance(pm, list) else [])
                for pid in ids:
                    if pid and str(pid) not in seen_p:
                        seen_p.add(str(pid))
                        payment_ids.append(str(pid))
                res = obj.get("reservations")
                if isinstance(res, list):
                    for rid in res:
                        if str(rid) not in seen_r:
                            seen_r.add(str(rid))
                            reservation_ids.append(str(rid))
                rid = obj.get("reservation_id")
                if rid and str(rid) not in seen_r:
                    seen_r.add(str(rid))
                    reservation_ids.append(str(rid))
            else:
                for pid in re.findall(r"\b(?:credit_card|gift_card|certificate)_\d+\b", content):
                    if pid not in seen_p:
                        seen_p.add(pid)
                        payment_ids.append(pid)
        return {"payment_methods": payment_ids, "reservation_ids": reservation_ids}

    @classmethod
    def _localize_action(cls, gold_name: str, gold_keys: list[str], meta: dict,
                         facts: dict) -> str:
        """Argument-level detail for one failed action check — the AGENT's own values only."""
        calls = [a for (n, a) in cls._iter_agent_tool_calls(meta) if n == gold_name]
        if not calls:
            return f"{gold_name}: was never called (or not called correctly)"
        keys = gold_keys or sorted({k for c in calls for k in c})
        used = calls[-1]          # the state the agent settled on; deterministic
        parts = []
        for k in keys:
            v = used.get(k, "<missing>")
            detail = f"{k}={v!r}"
            kl = k.lower()
            if "payment" in kl and facts.get("payment_methods") and v not in facts["payment_methods"]:
                detail += f" (not on the user's profile; available={facts['payment_methods']})"
            elif "reservation" in kl and facts.get("reservation_ids") and v not in facts["reservation_ids"]:
                detail += f" (not among the user's reservations; held={facts['reservation_ids']})"
            parts.append(detail)
        return f"{gold_name}: agent used " + ", ".join(parts)

    @classmethod
    def _localize_communicate(cls, check: dict, meta: dict, facts: dict) -> str | None:
        """A derivable un-stated value for a missed communicate check, or None.

        The check's ``info`` text can embed the gold answer, so it is CLASSIFIED, never
        echoed: only a value the agent could compute from its own observations is named.
        """
        info = str(check.get("info") or "").lower()
        if "total" in info and ("cost" in info or "price" in info or "$" in info):
            total = cls._derive_total_cost(meta)
            if total is not None:
                return ("did not state the computed total cost (derivable from your own "
                        f"observed amounts: ${total:.2f})")
            return ("did not state the computed total cost (sum the amounts you already "
                    "observed and state it)")
        return None

    @staticmethod
    def _derive_total_cost(meta: dict):
        """Deterministic best-effort sum of amounts the AGENT ITSELF observed, or None."""
        import json

        total, found = 0.0, False
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
        for msg in meta.get("trace") or []:
            if not isinstance(msg, dict) or msg.get("role") != "tool":
                continue
            content = msg.get("content")
            if not isinstance(content, str):
                continue
            try:
                obj = json.loads(content)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(obj, dict):
                for k in ("total", "total_cost", "amount"):
                    if isinstance(obj.get(k), (int, float)):
                        total += float(obj[k])
                        found = True
        return total if found else None

    @classmethod
    def _build_feedback(cls, reward: float, reward_info: dict, meta: dict) -> str:
        """The learning signal: per failing check, WHERE the defect is, at argument level."""
        if not reward_info:
            if reward >= 1.0:
                return "Task fully solved (reward 1.0)."
            return (f"Task scored {reward:.3f}. No detailed check breakdown is available "
                    "for this rollout.")

        facts = cls._user_profile_facts(meta)
        lines = [f"Task reward: {reward:.3f}."]

        db_check = reward_info.get("db_check")
        if db_check is not None and not db_check.get("db_match", True):
            lines.append("Database state does NOT match the expected final state — a required "
                         "write (book/update/cancel) was missing, wrong, or extra. See the "
                         "per-action detail below for the specific wrong argument.")

        details = []
        for ac in reward_info.get("action_checks") or []:
            if ac.get("action_match", True):
                continue
            action = ac.get("action") or {}
            name = action.get("name") or action.get("func_name") or "an action"
            gold_keys = action.get("compare_args")
            if not gold_keys:
                gold_args = action.get("arguments")
                gold_keys = sorted(gold_args.keys()) if isinstance(gold_args, dict) else []
            try:
                details.append(cls._localize_action(str(name), list(gold_keys or []), meta, facts))
            except Exception:  # noqa: BLE001
                details.append(f"{name}: not performed correctly (right tool, right arguments)")
        if details:
            lines.append("Action-level defects (your own wrong values): " + "; ".join(details) + ".")

        missed_comm = [c for c in (reward_info.get("communicate_checks") or [])
                       if not c.get("met", True)]
        if missed_comm:
            comm = []
            for c in missed_comm:
                try:
                    d = cls._localize_communicate(c, meta, facts)
                except Exception:  # noqa: BLE001
                    d = None
                if d:
                    comm.append(d)
            lines.append("Communication misses: " + "; ".join(comm) + "." if comm else
                         f"{len(missed_comm)} required piece(s) of information were not clearly "
                         "communicated to the user. State the confirmations/details (e.g. the "
                         "computed total, the new flight times) the policy requires you to convey.")

        missed_nl = [n for n in (reward_info.get("nl_assertions") or []) if not n.get("met", True)]
        if missed_nl:
            lines.append(f"{len(missed_nl)} behavioral expectation(s) were not met. Re-check the "
                         "policy steps for this scenario.")
        missed_env = [e for e in (reward_info.get("env_assertions") or []) if not e.get("met", True)]
        if missed_env:
            lines.append(f"{len(missed_env)} environment assertion(s) failed (the resulting "
                         "system state was not as required).")
        if reward >= 1.0 and len(lines) == 1:
            lines.append("All checks passed.")
        return " ".join(lines)

    # ---- making a candidate live -----------------------------------------

    def apply(self, candidate_dir, edits=None) -> None:
        """Install ``candidate_dir``'s TOOLS as the live airline tool surface.

        Overrides the registry's airline env constructor so tau2's ``run_tasks`` builds an
        ``Environment(domain_name="airline", policy=<tau2's own policy>,
        tools=<candidate AirlineTools>)``. The POLICY is read from tau2 itself and is NOT
        part of the capability — the tool surface is the only edit surface.

        Guarded on the CANDIDATE'S SHAPE (are candidate tools present?), not on the spec:
        a spec/seed mismatch then fails loudly here instead of silently delivering the
        candidate the other way.

        NEVER raises. cap-evolve enters ``live()`` inline, so an exception would abort the
        whole run over one bad candidate; instead the failure is recorded and the rollouts
        come back errored, which makes the harness EXCLUDE the candidate rather than score
        it 0.0 — correct, because a failed deployment is infra noise, not a verdict.
        """
        if edits:
            self.materialize(candidate_dir, edits)
        self._deploy_error = None          # never inherit the previous candidate's

        cdir = Path(candidate_dir)
        tools_py = cdir / "tools" / "tools.py"
        if not tools_py.exists():
            # The SPA arm's candidate is ONE skill package (my_skill/SKILL.md + scripts/).
            # Naming it here is what turns a spec/seed mismatch into a loud failure.
            hint = ("; this candidate looks like the SPA arm's skill package, so the spec "
                    "and the seed disagree about the delivery path"
                    if (cdir / "my_skill").exists() else "")
            self._deploy_error = (
                f"tools/tools.py missing under {cdir}{hint}. This project is the DIRECT arm, "
                "whose candidate is the airline TOOL SURFACE as importable code.")
            return

        try:
            from tau2.environment.environment import Environment
            from tau2.registry import registry
            from tau2.domains.airline.utils import AIRLINE_POLICY_PATH

            # Snapshot tau2's pristine constructor exactly once, and reset to it before
            # installing the new candidate's (idempotent across repeated applies).
            if Adapter._original_env_ctor is None:
                Adapter._original_env_ctor = registry._domains.get(DOMAIN)
            if Adapter._original_env_ctor is not None:
                registry._domains[DOMAIN] = Adapter._original_env_ctor

            # tau2's OWN policy, unchanged: it is not part of this capability.
            policy_text = Path(AIRLINE_POLICY_PATH).read_text(encoding="utf-8")

            # Fail HERE if the candidate's code is broken (a syntax error, a bad import, a
            # tool whose signature no longer yields a schema), rather than inside every
            # simulation: a candidate that cannot even be built is a deploy failure, so the
            # harness excludes it instead of scoring the optimizer's syntax error as 0.0.
            probe_tools = _build_candidate_tools(cdir)
            n = len(probe_tools.get_tools())
            if n == 0:
                self._deploy_error = (
                    f"the candidate exposes NO tools (REMOVE_TOOLS removed all {N_PRIMITIVES}?)")
                return

            def candidate_get_environment(db=None, solo_mode: bool = False):
                if solo_mode:
                    raise ValueError("Airline domain does not support solo mode")
                return Environment(domain_name=DOMAIN, policy=policy_text,
                                   tools=_build_candidate_tools(cdir))

            registry._domains[DOMAIN] = candidate_get_environment
        except Exception as e:  # noqa: BLE001 — see the docstring: must not raise
            self._deploy_error = f"{type(e).__name__}: {e}"
