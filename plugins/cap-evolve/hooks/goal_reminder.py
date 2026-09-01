#!/usr/bin/env python3
"""PostToolUse (Bash) — the missing ``/goal`` enforcement: a fixed-cadence, harness-owned
reminder of the parsed ``stop_condition`` predicates and the run's MEASURED state.

Issue #401: "no /goal-style constraint enforcement exists — constraints parse into
predicates but there's no live mechanism forcing a Claude-Code-driven optimizer to
check/report against them mid-run." An agent-optimize session is prose-driven (no
deterministic loop), so a spend/constraints check only happens when the agent
remembers to run ``spend.py`` itself. This hook makes the re-check happen regardless:
it counts Bash calls made while inside an agent-mode run dir and, every
``CAPEVOLVE_GOAL_CADENCE`` calls (default 12), re-surfaces the predicates +
measured spend/wallclock/protected-tasks state as ``additionalContext`` — visible to
the model on its next turn without it having to ask.

No-ops (exit 0, no context) when: not inside a CapEvolve run dir; not agent mode
(deterministic loops already self-check via the loop's own convergence/budget code);
core is not importable; or the cadence has not elapsed. Fails open on internal error,
matching every other hook in this plugin.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _hooklib as H  # noqa: E402

DEFAULT_CADENCE = 12


def _agent_mode(run_dir: Path) -> bool:
    """Mirrors require_green_check.py's check (kept local to avoid cross-hook coupling)."""
    proj = H.project_dir_for(run_dir)
    if proj is None:
        return False
    spec = proj / "capevolve.yaml"
    if not spec.exists():
        return False
    try:
        text = spec.read_text(encoding="utf-8")
    except Exception:
        return False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line or line[:1].isspace():
            continue
        key, sep, val = line.partition(":")
        if sep and key.strip() == "orchestration_mode":
            return val.strip().strip("'\"") == "agent"
    return False


def _tick(run_dir: Path, cadence: int) -> int:
    """Increment and return the persisted Bash-call counter for this run dir."""
    marker = run_dir / "GOAL_REMINDER_COUNT"
    n = 0
    try:
        n = int(marker.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        n = 0
    n += 1
    try:
        marker.write_text(str(n), encoding="utf-8")
    except Exception:
        pass
    return n


def _wallclock(rd) -> float:
    """Seconds since the run's FIRST recorded event — the same measurement ``spend.py``
    makes. Passing 0.0 instead reported every ``max_wallclock`` predicate as wholly
    unspent, which is the one thing this hook exists not to do."""
    import time
    try:
        with rd.events_path.open(encoding="utf-8") as f:
            first = json.loads(f.readline())
        return max(0.0, time.time() - float(first.get("t") or 0.0))
    except Exception:  # noqa: BLE001
        try:
            return max(0.0, time.time() - rd.state_path.stat().st_mtime)
        except Exception:  # noqa: BLE001
            return 0.0


def _goal_context(run_dir: Path) -> str | None:
    """Build the reminder text from MEASURED state — never from anything remembered."""
    from cap_evolve import RunDir, harness
    from cap_evolve.constraints import check_constraints, parse_constraints
    from cap_evolve.loop import has_valid_trials
    from cap_evolve.specfile import spec_for_run

    rd = RunDir.open(run_dir)
    project = H.project_dir_for(run_dir)
    spec = spec_for_run(rd, project)
    parsed = parse_constraints(str(spec.get("stop_condition") or ""))
    if not parsed["predicates"] and not parsed["ambiguous"]:
        return None  # nothing to enforce

    best_id = rd.best_id
    best = harness.split_result_from_rollouts(rd, best_id, "val") if best_id else None
    spent = rd.spent
    stop, stop_reason = rd.budget_exhausted()

    regressed: list[str] = []
    if best_id and best_id != "seed":
        try:
            seed = harness.split_result_from_rollouts(rd, "seed", "val")
            s = {pt["task_id"]: pt.get("reward", 0.0) for pt in (seed.per_task or [])
                 if has_valid_trials(pt)}
            b = {pt["task_id"]: pt.get("reward", 0.0) for pt in ((best.per_task if best else []) or [])
                 if has_valid_trials(pt)}
            regressed = sorted(t for t, r in s.items() if t in b and b[t] < r - 1e-9)
        except Exception:
            regressed = []

    checked = check_constraints(
        parsed, best_val=(best.reward if best else None), usd=spent.total_usd,
        wallclock_seconds=_wallclock(rd), iterations=spent.iterations, stall=spent.stall,
        metric_calls=spent.metric_calls, regressed_tasks=regressed,
    )
    rec = "stop" if stop else checked["recommendation"]

    lines = [
        "cap-evolve /goal check (fixed-cadence harness reminder, not a suggestion):",
        f"  stop_condition: {parsed['text']!r}",
        f"  predicates: {json.dumps(checked['predicates'])}",
        f"  measured spend: {json.dumps(spent.to_dict())}",
        f"  regressed protected tasks: {regressed}",
        f"  recommendation: {rec}",
    ]
    if stop:
        lines.append(f"  hard stop reason: {stop_reason}")
    if checked["ambiguous"]:
        lines.append(f"  UNCHECKABLE clauses (ask the user, do not guess): "
                     f"{json.dumps(checked['ambiguous'])}")
    return "\n".join(lines)


def decide(payload: dict) -> int:
    if os.environ.get("CAPEVOLVE_NO_GOAL_HOOK") == "1":
        return 0
    run_dir = H.find_run_dir(H.hook_cwd(payload))
    if run_dir is None or not _agent_mode(run_dir):
        return 0
    if not H.core_importable():
        return 0

    cadence = int(os.environ.get("CAPEVOLVE_GOAL_CADENCE", str(DEFAULT_CADENCE)) or DEFAULT_CADENCE)
    if cadence <= 0:
        return 0
    n = _tick(run_dir, cadence)
    if n % cadence != 0:
        return 0

    try:
        ctx = _goal_context(run_dir)
    except Exception as e:
        print(f"cap-evolve goal_reminder hook: internal error ignored: {e}", file=sys.stderr)
        return 0
    if not ctx:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": ctx}}))
    return 0


def main() -> int:
    try:
        payload = H.read_payload()
        return decide(payload)
    except Exception as e:
        print(f"cap-evolve goal_reminder hook: internal error ignored: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
