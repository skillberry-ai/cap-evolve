"""using-cap-evolve — resolve where the user is and recommend the next command.

This router does NOT optimize. It inspects the on-disk state of a cap-evolve
project and prints a routing decision the agent (or the orchestrator) acts on:

    {state, next, sequence, reason, intent}

States (a simple, deterministic state machine over the project dir):
  fresh       — no .capevolve/project/, or no capevolve.yaml
                                              -> next: /cap-evolve:intake
  scaffolded  — capevolve.yaml exists, check not yet green
                                              -> next: /cap-evolve:implement-and-check
  ready       — `cap-evolve check` is green, no run yet
                                              -> next: baseline / `cap-evolve run`
  run_started — a run_* dir with no state.json (a torn/partial create — see
                RunDir.create's exist_ok contract in core/cap_evolve/rundir.py)
                                              -> next: `cap-evolve run --resume --run-ts`
  running     — a run_* dir, test split not used
                                              -> next: `cap-evolve run --resume`
  finalized   — splits.json test_used         -> next: a NEW run with --reuse-baseline
                                                 (report only inspects the sealed one)

Runs are globbed unconditionally. Requiring state.json would hide a run that is
mid-create behind an older sealed one and report it as `finalized` while an
optimization is in flight — the worst answer this router can give.

The check is best-effort: if core isn't importable we fall back to "is there a
capevolve.yaml" rather than failing. Pure stdlib + cap_evolve (optional).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401


PHASE_CHAIN = ["intake", "implement-and-check", "baseline",
               "<algorithm>", "finalize", "report"]


def _latest_run(base: Path) -> Path | None:
    runs = sorted((r for r in base.glob("run_*") if r.is_dir()), key=lambda r: r.name)
    return runs[-1] if runs else None


def _check_green(project: Path) -> bool | None:
    """True/False if we can run the real check, None if core unavailable."""
    try:
        from cap_evolve.check import run_check
    except Exception:
        return None
    try:
        return run_check(project).ok
    except Exception:
        return False


def _run_state(run: Path) -> dict:
    """Classify the newest run dir. Never claims a seal it cannot read."""
    ts = run.name[len("run_"):]
    sp = run / "splits.json"
    if not (run / "state.json").exists() and not sp.exists():
        return {"state": "run_started", "next": f"cap-evolve run --resume --run-ts {ts}",
                "run": str(run),
                "reason": "a run dir exists but has no state.json — a torn/partial create. "
                          "Resume it by ts (plain --resume skips a run with no state.json); "
                          "the adapter is already implemented, do not re-run intake."}
    if sp.exists():
        try:
            spd = json.loads(sp.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            return {"state": "running", "next": f"cap-evolve run --resume --run-ts {ts}",
                    "run": str(run),
                    "reason": f"splits.json is unreadable ({e}) — the split is an "
                              "honesty-critical artifact, so the seal cannot be confirmed "
                              "either way. Inspect it before spending more budget."}
        if spd.get("test_used"):
            return {"state": "finalized",
                    "next": ("cap-evolve run --spec .capevolve/project/capevolve.yaml "
                             f"--reuse-baseline {run}"),
                    "run": str(run),
                    "reason": "test is sealed/used — this run's headline number is recorded "
                              "and cannot be re-scored. For another attempt start a new run "
                              "reusing this baseline; `/cap-evolve:report` only inspects it."}
    return {"state": "running", "next": f"cap-evolve run --resume --run-ts {ts}",
            "run": str(run),
            "reason": "a run is in progress and the test split is still sealed — resume it "
                      "at iteration N+1; `/cap-evolve:report` shows status without continuing."}


def resolve_state(base: Path) -> dict:
    base = Path(base)
    project = base / "project"
    yaml = project / "capevolve.yaml"

    if not project.is_dir():
        return {"state": "fresh", "next": "/cap-evolve:intake",
                "reason": "no .capevolve/project/ — start with intake (Phase 1)."}

    run = _latest_run(base)
    if run is not None:
        return _run_state(run)

    if not yaml.exists():
        return {"state": "fresh", "next": "/cap-evolve:intake",
                "reason": "project dir exists but no capevolve.yaml — run intake. Warn the "
                          "user first if the dir is non-empty: intake scaffolds into it."}

    green = _check_green(project)
    if green is True:
        return {"state": "ready", "next": "/cap-evolve:baseline",
                "reason": "cap-evolve check is green — baseline then the algorithm, "
                          "or `cap-evolve run --spec` for the automatic path."}
    if green is False:
        return {"state": "scaffolded", "next": "/cap-evolve:implement-and-check",
                "reason": "capevolve.yaml present but `cap-evolve check` is not green — "
                          "implement the adapter and pass the hard gate first."}
    # green is None: core not importable here — recommend the gate step conservatively.
    return {"state": "scaffolded", "next": "/cap-evolve:implement-and-check",
            "reason": "capevolve.yaml present; could not run check here — verify the "
                      "hard gate via implement-and-check before baseline."}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="using-cap-evolve")
    p.add_argument("intent", nargs="*", help="free-text 'what to optimize' (echoed back)")
    p.add_argument("--base", default=".capevolve")
    args = p.parse_args(argv)

    decision = resolve_state(Path(args.base))
    decision["sequence"] = PHASE_CHAIN
    decision["intent"] = " ".join(args.intent) or None
    decision["run_modes"] = {
        "standalone": "drive /cap-evolve:<phase> turn by turn",
        "automatic": "cap-evolve run --spec .capevolve/project/capevolve.yaml",
        "agent_handoff": "orchestration_mode: agent — run stops after baseline, you drive",
        "host_agnostic": "follow RUN.md (no plugin / non-Claude host)",
    }
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
