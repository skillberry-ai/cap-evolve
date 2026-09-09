"""Scoring and gold-safe feedback shared by BOTH tau2-airline arms.

`direct/adapters/adapter.py` and `spa/adapters/adapter.py` carried these members
byte-identically (~250 lines). A fix to the STOP-leak regex or the `_localize_*`
heuristics had to be applied twice and would silently drift if only one copy was
updated (#479). They now live here once, mixed into each arm's `Adapter`.

Deployed like `gateway.py`: each arm's `setup.sh` copies this file into
`$PROJECT/adapters/`, and `adapter.py` imports it as a sibling module after putting its
own directory on `sys.path`.

WHAT IS DELIBERATELY *NOT* HERE:

* `_native_sims_enabled`, `_split_of`, `_sim_save_path` — those stay inline in all four
  tau2 adapters in this repo. `core/tests/test_tau2_native_sims.py` extracts that region
  from each `adapter.py` TEXTUALLY and asserts one digest, and the other two adapters
  (`examples/tau2_airline`, `templates/adapters/tau2_bench`) ship standalone and cannot
  import this module. Moving them would break that guard.
* `_user_profile_facts` — genuinely differs per arm, so each `Adapter` overrides it. The
  mixin calls it as `cls._user_profile_facts(...)`, so normal MRO picks up the override.

CONTRACT the including class must satisfy: set `self._traj_dirs: dict[str, Path]` in its
`__init__` (used by `trajectories`), and define `_user_profile_facts`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from cap_evolve import Rollout, Score, Task


# docs/TAU2_SUMMARY.md row 7: tau2's user simulator sometimes emits ``###STOP###`` in the
# SAME message as reasoning that explicitly plans to continue. That ends the conversation
# early for a reason that measures nothing about the agent, so it is recorded as infra
# noise (an errored rollout the harness EXCLUDES) rather than scored against the tools.
import re

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
    """The PRIMARY reward plus shown-only secondaries (never gate accept/reject).

    ``cost_usd`` is shown for continuity with the direct arm, but under this intervention
    SPA reports no token usage, so the agent side of it is 0 = NOT MEASURED, not free.
    """
    metrics = [{"name": "reward", "value": float(reward), "primary": True, "direction": "higher"}]
    db_check = (reward_info or {}).get("db_check") or {}
    if "db_match" in db_check:
        metrics.append({"name": "db_match", "value": 1.0 if db_check.get("db_match") else 0.0,
                        "primary": False, "direction": "higher"})
    metrics.append({"name": "cost_usd", "value": float(getattr(rollout, "cost_usd", 0.0) or 0.0),
                    "primary": False, "direction": "lower"})
    return metrics


class Tau2ScoringMixin:
    """The shared scoring + gold-safe feedback surface for both arms."""

    # ---- native trajectories ---------------------------------------------
    def trajectories(self, split: str, ctx=None):
        """tau2's native results dir for ``split`` (full transcript + reward_info).

        The last dir ``_sim_save_path`` produced for this split, so it is already scoped to
        ONE candidate and ONE split. The harness still PREFERS its own per-tag rollout JSON
        for ``./trajectories/`` and uses this as the native-dir fallback; either way the
        optimizer reads unmodified traces, since that JSON carries the same ``messages``
        plus the ``tau2_reward_info`` breakdown this adapter stashes in ``metadata``.
        Returns ``None`` when native sims are off (``CAPEVOLVE_NATIVE_SIMS=0``).
        """
        d = self._traj_dirs.get(split)
        return d if d and Path(d).is_dir() else None

    # ---- running ---------------------------------------------------------

    #: The tau2 domain the including arm evaluates. Each Adapter overrides it — "airline"
    #: for the in-process environment, "airline_skillberry" for the HTTP-fronted one — and
    #: it is stamped into every rollout's metadata below.
    DOMAIN: str = ""

    @classmethod
    def _sim_to_rollout(cls, sim) -> Rollout:
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
                "domain": cls.DOMAIN,
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

    @classmethod
    def _derive_total_cost(cls, meta: dict):
        """Deterministic best-effort sum of amounts the AGENT ITSELF observed, or None.

        A classmethod rather than a staticmethod so the ``_iter_agent_tool_calls`` lookup
        stays late-bound to the concrete ``Adapter``, as the original ``Adapter.``-prefixed
        call did. Hard-coding the class name here would silently ignore an arm override.
        """
        import json

        total, found = 0.0, False
        for _name, args in cls._iter_agent_tool_calls(meta):
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
