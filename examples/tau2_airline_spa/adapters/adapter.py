"""Project adapter — optimize tau2-bench AIRLINE via SPA + Skillberry Store.

Wires cap-evolve to the tau2 airline domain with LLM calls routed through
Skillberry Proxy-Agent (SPA). The 14 primitive tools are frozen STANDALONE tools
in the store. Exactly ONE skill — ``airline_skill`` — is loaded and served to the
agent; the optimizer modifies it in place (SKILL.md prompt enrichment plus the
wrapper/composite tools under scripts/).

  * ``tasks``      -> all 50 airline tasks (stable, non-empty for every split).
  * ``run_batch``  -> tau2's own batch runner (``run_tasks``) with LLM calls
                      routed through SPA (agent) or direct upstream (user sim).
  * ``run_target`` -> thin wrapper over ``run_batch`` for one task.
  * ``score``      -> tau2's own reward in [0,1] (deterministic given a rollout);
                      gold-AWARE but gold-SAFE, ARGUMENT-LEVEL feedback.
  * ``apply``      -> deletes + re-imports the candidate's ``airline_skill`` in the
                      store, restarts SPA with SKILL_NAME=airline_skill, waits
                      for health. Frozen primitives are never touched.

``cap-evolve check`` does NO live LLM call: ``tasks``/``score``/``materialize``
are network-free, and SPA endpoint resolution is lazy.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import spa_env

DOMAIN = "airline_skillberry"

# The one skill in the store, modified in place by the optimizer.
SKILL_NAME = spa_env.SKILL_NAME

TAU2_LOG_DIR = Path(os.environ.get("TAU2_LOG_DIR", "/tmp"))


# Open /dev/tty once at module load — this is the controlling terminal and is
# immune to capture_output=True, pipes, and any fd redirection by cap-evolve.
try:
    _tty = open("/dev/tty", "w")  # noqa: SIM115
except OSError:
    _tty = None


@contextlib.contextmanager
def _tee_to_log(label: str = "run"):
    """Capture stdout, mirror it to /dev/tty (bypasses capture) and save to a log file."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = TAU2_LOG_DIR / f"tau2_{DOMAIN}_{label}_{timestamp}.log"
    buf = io.StringIO()

    class Tee:
        def write(self, data):
            buf.write(data)
            if data and _tty:
                _tty.write(data)
                _tty.flush()

        def flush(self):
            buf.flush()

    old_stdout = sys.stdout
    sys.stdout = Tee()
    try:
        yield log_path
    finally:
        sys.stdout = old_stdout
        log_path.write_text(buf.getvalue(), encoding="utf-8")
        if _tty:
            _tty.write(f"  tau2 log: {log_path}\n")
            _tty.flush()


def _shown_metrics(reward: float, reward_info: dict, rollout) -> list:
    """Shown-only secondary metrics for display; the GATE still uses reward (primary)."""
    metrics = [{"name": "reward", "value": float(reward), "primary": True, "direction": "higher"}]
    db_check = (reward_info or {}).get("db_check") or {}
    if "db_match" in db_check:
        metrics.append({"name": "db_match", "value": 1.0 if db_check.get("db_match") else 0.0,
                        "primary": False, "direction": "higher"})
    metrics.append({"name": "cost_usd", "value": float(getattr(rollout, "cost_usd", 0.0) or 0.0),
                    "primary": False, "direction": "lower"})
    return metrics


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class Adapter(CapabilityAdapter):

    _current_skill_name: str = SKILL_NAME  # fixed: there is only ever one skill
    _last_sim_path: "Path | None" = None   # set by run_batch/run_trials; read by trajectories()

    # Set by apply() when this candidate could NOT be deployed (store refresh or SPA
    # restart failed, or the candidate has no usable skill package). While it is set,
    # run_batch/run_trials return errored rollouts instead of evaluating whatever SPA
    # happens to be serving. Cleared at the top of every apply(), so a failure never
    # leaks into the next candidate.
    _deploy_error: "str | None" = None

    # ---- deployment failures --------------------------------------------

    @staticmethod
    def _deploy_error_rollout(task_id: str) -> Rollout:
        """An errored Rollout standing in for a task that could not be evaluated.

        Setting ``Rollout.error`` is the contract the harness already understands:
        the trial is marked errored, excluded from the split mean and from paired
        deltas, and NOT counted as a 0.0 (``core/cap_evolve/loop.py`` —
        ``aggregate_scores`` drops tasks with no valid trial). So a candidate we
        could not deploy costs that candidate, never the whole run.
        """
        return Rollout(
            task_id=task_id,
            error=f"candidate deployment failed: {Adapter._deploy_error}",
            metadata={"domain": DOMAIN, "tau2_reward": 0.0},
        )

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return ALL 50 tau2 airline tasks for any split (stable, non-empty)."""
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        tau2_tasks = airline_get_tasks()
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
        return {str(t.id): t for t in airline_get_tasks()}

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run a batch of airline tasks through tau2's own batch runner.

        LLM calls for the agent are routed through SPA (via ibm/skillberry-local
        model string). User simulator calls go directly to the upstream LLM.
        """
        if Adapter._deploy_error:
            return {t.id: self._deploy_error_rollout(t.id) for t in tasks}

        from tau2.run import run_tasks
        from tau2.utils.utils import DATA_DIR, get_now

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

        agent_m = spa_env.agent_model()
        user_m = spa_env.user_model()
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "3"))
        save_to = DATA_DIR / "simulations" / f"{get_now()}_{DOMAIN}_llm_agent_skillberry-local_user_simulator.json"
        Adapter._last_sim_path = save_to

        with _tee_to_log("batch"):
            sim_results = run_tasks(
                domain=DOMAIN,
                tasks=tau2_tasks,
                agent="llm_agent",
                user="user_simulator",
                llm_agent=agent_m,
                llm_args_agent=spa_env.llm_args_for(agent_m),
                llm_user=user_m,
                llm_args_user=spa_env.llm_args_for(user_m),
                num_trials=1,
                max_steps=100,
                max_errors=10,
                max_concurrency=max_concurrency,
                seed=int(seed),
                save_to=save_to,
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
        """Map one tau2 SimulationRun to a cap-evolve Rollout.

        SimulationRun exposes the full conversation via .messages (list[Message]).
        We serialise each Message with model_dump() so the optimizer can read the
        complete user<->agent exchange — including tool calls and tool responses —
        directly from the cap-evolve rollout JSON that lands in trajectories/.
        """
        from tau2.data_model.simulation import TerminationReason

        infra_reasons = {
            TerminationReason.TOO_MANY_ERRORS,
            TerminationReason.TASK_FAILED,
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

        # sim.messages is the authoritative list[Message] on SimulationRun.
        # Do NOT call sim.get_messages() — that method does not exist on this tau2 version.
        messages = None
        try:
            raw = sim.messages  # list[Message]
            if raw:
                messages = [
                    m.model_dump(mode="json") if hasattr(m, "model_dump") else dict(m)
                    for m in raw
                ]
        except Exception as _e:
            messages = [{"_trace_error": str(_e)}]

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
        """Run ALL trials in ONE tau2 run_tasks call."""
        n_trials = int(n_trials)

        if Adapter._deploy_error:
            return {
                t.id: [self._deploy_error_rollout(t.id) for _ in range(max(n_trials, 1))]
                for t in tasks
            }

        from tau2.run import run_tasks
        from tau2.utils.utils import DATA_DIR, get_now

        by_id = self._tau2_tasks_by_id()
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]

        results: dict[str, list[Rollout]] = {t.id: [None] * n_trials for t in tasks}

        for t in tasks:
            if t.id not in by_id:
                results[t.id] = [
                    Rollout(task_id=t.id, error=f"task id {t.id} not found in airline task set")
                    for _ in range(n_trials)
                ]
        if not tau2_tasks or n_trials <= 0:
            return results

        agent_m = spa_env.agent_model()
        user_m = spa_env.user_model()
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "3"))
        save_to = DATA_DIR / "simulations" / f"{get_now()}_{DOMAIN}_llm_agent_skillberry-local_user_simulator.json"
        Adapter._last_sim_path = save_to

        with _tee_to_log("trials"):
            sim_results = run_tasks(
                domain=DOMAIN,
                tasks=tau2_tasks,
                agent="llm_agent",
                user="user_simulator",
                llm_agent=agent_m,
                llm_args_agent=spa_env.llm_args_for(agent_m),
                llm_user=user_m,
                llm_args_user=spa_env.llm_args_for(user_m),
                num_trials=n_trials,
                max_steps=100,
                max_errors=10,
                max_concurrency=max_concurrency,
                seed=int(base_seed),
                save_to=save_to,
                console_display=False,
            )

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
        """Run a single task by delegating to run_batch."""
        batch = self.run_batch([task], ctx, seed=seed)
        return batch.get(task.id, Rollout(task_id=task.id, error="no rollout produced"))

    def trajectories(self, split: str, ctx=None):
        """Return the tau2 native simulation dir so the optimizer reads full agent traces.

        tau2 writes the complete user<->agent conversation (all messages, tool calls,
        user turns, reward_info) to data/simulations/<timestamp>_*.json via save_to.
        We return that file's parent directory so cap-evolve copies the simulation
        file into workdir/trajectories/ for the optimizer to read.
        Fallback: return the simulations dir directly so the optimizer reads
        the most-recent file (sorted by timestamp prefix).
        """
        p = Adapter._last_sim_path
        if p is not None and Path(p).exists():
            return Path(p).parent
        try:
            from tau2.utils.utils import DATA_DIR
            sim_dir = DATA_DIR / "simulations"
            if sim_dir.is_dir():
                return sim_dir
        except Exception:
            pass
        return None

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Score a rollout with tau2's own reward; gold-AWARE, gold-SAFE feedback."""
        meta = rollout.metadata or {}

        if rollout.error:
            if str(rollout.error).startswith("candidate deployment failed"):
                feedback = (
                    f"This candidate was never evaluated ({rollout.error}). The store "
                    "refresh or the SPA restart failed, so no reward was measured — "
                    "the result says nothing about the skill itself."
                )
            else:
                feedback = (
                    "Rollout did not complete for an infrastructure reason "
                    f"({rollout.error}). This is uncontrollable noise, not an agent "
                    "policy/tool failure; do not optimize against it."
                )
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=feedback,
                metrics=_shown_metrics(0.0, {}, rollout),
            )

        reward = float(meta.get("tau2_reward", 0.0) or 0.0)
        reward_info = meta.get("tau2_reward_info") or {}

        ctx = dict(meta)
        ctx["trace"] = rollout.trace or rollout.output or meta.get("trace") or []

        feedback = self._build_feedback(reward, reward_info, ctx)
        return Score(
            task_id=task.id, reward=reward, feedback=feedback,
            metrics=_shown_metrics(reward, reward_info, rollout),
        )

    # ---- making a candidate live ----------------------------------------

    def apply(self, candidate_dir, edits=None) -> None:
        """Deploy the candidate's ``airline_skill``: re-import it, restart SPA.

        There is exactly ONE skill in the store. The optimizer modifies it in
        place, so deploying a candidate means replacing it:

        Because cap-evolve calls ``live()`` -> ``apply()`` before EVERY evaluation,
        and the baseline is handed the seed, this is also what guarantees that each
        ``cap-evolve run`` starts against a store refreshed from the seed skill.

        1. Write edits to candidate_dir (pure) if any.
        2. Refresh the store via spa_env.reset_store_to_skill:
           a. DELETE ``airline_skill`` with ALL of its tools and snippets, so no
              stale wrapper survives a candidate that removed or renamed one (the
              store's own cascade cannot do this — it silently leaves tools behind).
           b. Purge leftover non-primitive tools/snippets orphaned by earlier runs.
           c. Import the candidate's ``airline_skill/`` fresh.
           d. Verify every frozen primitive is still present.
        3. Restart SPA with SKILL_NAME=airline_skill.

        The frozen primitive tools are standalone in the store, belong to no skill
        manifest, and are additionally tag-guarded, so step 2 never touches them.

        NEVER RAISES for a deployment failure. A store refresh that fails or an SPA
        that will not come back up is per-candidate infrastructure noise: it is
        recorded in ``_deploy_error`` and turned into errored rollouts by
        ``run_batch``/``run_trials``, so the harness excludes the candidate instead of
        the run dying with the budget half spent.
        """
        if edits:
            self.materialize(candidate_dir, edits)

        candidate_dir = Path(candidate_dir)
        skill_dir = candidate_dir / SKILL_NAME

        # Start every deployment from a clean slate: a failure recorded for the
        # PREVIOUS candidate must never suppress this one's evaluation.
        Adapter._deploy_error = None

        if not (skill_dir / "SKILL.md").exists():
            Adapter._deploy_error = (
                f"{SKILL_NAME}/SKILL.md not found under {candidate_dir} — the "
                f"candidate must contain the single {SKILL_NAME}/ skill package"
            )
            return

        try:
            # Full refresh: drop the current skill (its tools + snippets), purge any
            # orphans left by earlier runs, then import this candidate. Raises if the
            # store ends up inconsistent or a frozen primitive went missing.
            spa_env.reset_store_to_skill(skill_dir, SKILL_NAME)

            spa_env.restart_spa(SKILL_NAME)
        except RuntimeError as e:
            # A store refresh or an SPA restart that will not come up is INFRA noise,
            # not a verdict on this candidate's capability. Raising here would escape
            # ``live()`` (core/cap_evolve/harness.py enters it inline) and abort the
            # whole run, losing the remaining budget over one flaky restart. Record it
            # instead: run_batch/run_trials then return errored rollouts, which the
            # harness already excludes from the mean rather than scoring 0.0.
            Adapter._deploy_error = str(e)
            return

        Adapter._current_skill_name = SKILL_NAME

    # ---- gold-safe feedback builder --------------------------------------

    @staticmethod
    def _iter_agent_tool_calls(meta: dict):
        """Yield (tool_name, arguments) for every ASSISTANT tool call in the trace."""
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
        """Derive what the AGENT observed about the user's own profile/state."""
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
                for pid in re.findall(r"\b(?:credit_card|gift_card|certificate)_\d+\b", content):
                    if pid not in seen_p:
                        seen_p.add(pid)
                        payment_ids.append(pid)

        return {"payment_methods": payment_ids, "reservation_ids": reservation_ids}

    @classmethod
    def _localize_action(cls, gold_name: str, gold_keys: list[str], meta: dict, facts: dict) -> str:
        """Argument-level, gold-SAFE detail for one failed action check."""
        agent_calls = [args for (n, args) in cls._iter_agent_tool_calls(meta) if n == gold_name]
        if not agent_calls:
            return f"{gold_name}: was never called (or not called correctly)"

        keys = gold_keys or sorted({k for c in agent_calls for k in c.keys()})
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
        """Name a derivable un-stated value for a missed communicate check (gold-safe)."""
        info = str(check.get("info") or "").lower()
        if "total" in info and ("cost" in info or "price" in info or "$" in info):
            total = cls._derive_total_cost(meta)
            if total is not None:
                return f"did not state the computed total cost (derivable from your own observed amounts: ${total:.2f})"
            return "did not state the computed total cost (sum the amounts you already observed and state it)"
        return None

    @staticmethod
    def _derive_total_cost(meta: dict):
        """Best-effort sum of payment amounts the AGENT itself observed."""
        import json

        total = 0.0
        found = False
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
        """Argument-level, gold-SAFE learning signal."""
        if not reward_info:
            if reward >= 1.0:
                return "Task fully solved (reward 1.0)."
            return (
                f"Task scored {reward:.3f}. No detailed check breakdown is available "
                "for this rollout."
            )

        facts = cls._user_profile_facts(meta)
        lines: list[str] = [f"Task reward: {reward:.3f}."]

        db_check = reward_info.get("db_check")
        if db_check is not None and not db_check.get("db_match", True):
            lines.append(
                "Database state does NOT match the expected final state — a "
                "required write (book/update/cancel) was missing, wrong, or extra."
            )

        action_checks = reward_info.get("action_checks") or []
        details: list[str] = []
        for ac in action_checks:
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
            except Exception:
                details.append(f"{name}: not performed correctly (right tool, right arguments)")
        if details:
            lines.append("Action-level defects (your own wrong values): " + "; ".join(details) + ".")

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
                    "communicated to the user."
                )

        nl_assertions = reward_info.get("nl_assertions") or []
        missed_nl = [n for n in nl_assertions if not n.get("met", True)]
        if missed_nl:
            lines.append(
                f"{len(missed_nl)} behavioral expectation(s) were not met."
            )

        env_assertions = reward_info.get("env_assertions") or []
        missed_env = [e for e in env_assertions if not e.get("met", True)]
        if missed_env:
            lines.append(
                f"{len(missed_env)} environment assertion(s) failed."
            )

        if reward >= 1.0 and len(lines) == 1:
            lines.append("All checks passed.")

        return " ".join(lines)
