#!/usr/bin/env python3
"""Stop / SubagentStop — refuse to "finish" while the honesty gate is red.

An optimizer iteration is only legitimately done when the project still passes
``cap-evolve check`` (the adapter contract holds: real splits, deterministic
scorer, pure materialize, no stubs) AND no regression marker has been left by the
gate. This CORE-OWNED hook blocks the agent from declaring completion until then:
on Stop / SubagentStop it re-runs the deterministic check and exits 2 (with a
reason) if it is not green, so Claude Code keeps the turn going instead of
letting a half-finished, dishonest iteration end.

Stop semantics (Claude Code): exit 0 = allow stop; exit 2 = block stop, stderr is
shown to the model so it knows what to fix. ``stop_hook_active`` in the payload
guards against an infinite loop — if we already blocked once this chain, we allow
the stop (the model has seen the reason and chosen to end).

No-ops (exit 0) when:
  * not inside a CapEvolve run dir;
  * ``$CAPEVOLVE_NO_GATE_HOOK=1`` (explicit opt-out for non-optimization sessions);
  * the run is already finalized (state ``test_used`` true) — the gate has served
    its purpose and the headline number is recorded.
Fails open on internal error.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _hooklib as H  # noqa: E402


def _gate_regression_pending(run_dir: Path) -> str | None:
    """Return a reason string if a no-regression marker is unsatisfied, else None.

    The gate (core) may drop a ``GATE_BLOCK`` marker file in the run dir naming an
    unresolved regression. This is a cheap, file-based contract so the hook needs
    no live engine state. Absent the marker, there is nothing pending here.
    """
    marker = run_dir / "GATE_BLOCK"
    if marker.exists():
        try:
            txt = marker.read_text(encoding="utf-8").strip()
        except Exception:
            txt = ""
        return txt or "a gate no-regression block is in effect"
    return None


def _agent_mode(run_dir: Path) -> bool:
    """True iff the run's project spec declares ``orchestration_mode: agent``.

    Tolerant read of ``capevolve.yaml``: prefer the core reader when importable,
    else a simple line scan. Defaults to "deterministic" on any ambiguity so the
    hook only nudges when agent mode is unambiguously configured.
    """
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

    mode = "deterministic"
    if H.core_importable():
        try:
            from cap_evolve.specfile import read_yaml
            data = read_yaml(text) or {}
            mode = str(data.get("orchestration_mode") or "deterministic")
        except Exception:
            mode = _scan_orchestration_mode(text)
    else:
        mode = _scan_orchestration_mode(text)
    return mode.strip() == "agent"


def _scan_orchestration_mode(text: str) -> str:
    """Line-scan fallback: the value of a top-level ``orchestration_mode:`` key."""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line or line[:1].isspace():
            continue  # only top-level (unindented) keys
        key, sep, val = line.partition(":")
        if sep and key.strip() == "orchestration_mode":
            return val.strip().strip("'\"") or "deterministic"
    return "deterministic"


def _check_failed_reason(run_dir: Path) -> str | None:
    """Run ``cap-evolve check`` on the run's project; return a reason if not green."""
    proj = H.project_dir_for(run_dir)
    if proj is None:
        # No project to check yet (pre-intake). Nothing to gate on.
        return None
    if not H.core_importable():
        # Can't run the real check — fail open rather than block on missing core.
        return None
    try:
        from cap_evolve.check import run_check
    except Exception:
        return None
    try:
        rep = run_check(proj)
    except Exception as e:
        return f"cap-evolve check raised: {e}"
    if not rep.ok:
        problems = "; ".join(rep.problems) or "see `cap-evolve check` output"
        return problems
    return None


def decide(payload: dict) -> int:
    if os.environ.get("CAPEVOLVE_NO_GATE_HOOK") == "1":
        return 0
    # Avoid infinite Stop loops: if we've already blocked once this chain, relent.
    if payload.get("stop_hook_active"):
        return 0

    run_dir = H.find_run_dir(H.hook_cwd(payload))
    if run_dir is None:
        return 0
    run_dir = run_dir.resolve()

    # Already finalized? The seal is burned; the gate has done its job.
    state = run_dir / "state.json"
    if state.exists():
        try:
            st = json.loads(state.read_text(encoding="utf-8"))
            sp = run_dir / "splits.json"
            if sp.exists():
                spd = json.loads(sp.read_text(encoding="utf-8"))
                if spd.get("test_used"):
                    return 0
            _ = st  # state available for future budget-aware rules
        except Exception:
            pass

    reg = _gate_regression_pending(run_dir)
    if reg:
        return H.emit_block(
            "cap-evolve: cannot finish this iteration — a no-regression block is "
            f"pending: {reg}. Resolve it (or revert the regressing edit) before "
            "ending. Remove the run-dir GATE_BLOCK marker only once the gate clears."
        )

    reason = _check_failed_reason(run_dir)
    if reason:
        return H.emit_block(
            "cap-evolve: cannot finish — `cap-evolve check` is RED for this run's "
            f"project: {reason}. An iteration may only end with a green check, so the "
            "next score stays honest. Fix the adapter/contract, then stop."
        )

    # Agent mode: nudge the driver to keep going until the loop's stop_condition is
    # met and the run is sealed. Fires once per Stop chain (stop_hook_active relents).
    if not payload.get("stop_hook_active") and _agent_mode(run_dir):
        # not finalized (checked above: test_used would have returned 0 already)
        return H.emit_block(
            "cap-evolve (agent mode): the run is not finalized. Re-read your "
            "stop_condition — if it isn't met and budget remains, keep driving the "
            "algorithm's Agent-mode loop (evaluate->gate->accept/revert), verifying each "
            "round wrote its run-dir artifacts. When done, seal with `cap-evolve finalize`."
        )
    return 0


def main() -> int:
    try:
        payload = H.read_payload()
        return decide(payload)
    except Exception as e:
        print(f"cap-evolve require_green_check hook: internal error ignored: {e}",
              file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
