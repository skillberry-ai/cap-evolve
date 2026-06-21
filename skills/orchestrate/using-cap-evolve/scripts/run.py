"""using-cap-evolve — resolve where the user is and recommend the next command.

This router does NOT optimize. It inspects the on-disk state of a cap-evolve
project and prints a routing decision the agent (or the orchestrator) acts on:

    {state, next, sequence, reason, intent}

States (a simple, deterministic state machine over the project dir):
  fresh       — no .capevolve/project/        -> next: /cap-evolve:intake
  scaffolded  — capevolve.yaml exists, check not yet green
                                              -> next: /cap-evolve:implement-and-check
  ready       — `cap-evolve check` is green   -> next: baseline / `cap-evolve run`
  running     — a run_* dir exists, test unused
                                              -> next: continue / report
  finalized   — splits.json test_used         -> next: /cap-evolve:report

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
    runs = sorted((r for r in base.glob("run_*") if (r / "state.json").exists()),
                  key=lambda r: r.name)
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


def resolve_state(base: Path) -> dict:
    base = Path(base)
    project = base / "project"
    yaml = project / "capevolve.yaml"

    if not project.is_dir():
        return {"state": "fresh", "next": "/cap-evolve:intake",
                "reason": "no .capevolve/project/ — start with intake (Phase 1)."}

    run = _latest_run(base)
    if run is not None:
        sp = run / "splits.json"
        if sp.exists():
            try:
                spd = json.loads(sp.read_text(encoding="utf-8"))
            except Exception:
                spd = {}
            if spd.get("test_used"):
                return {"state": "finalized", "next": "/cap-evolve:report",
                        "run": str(run),
                        "reason": "test is sealed/used — the headline number is recorded."}
        return {"state": "running", "next": "/cap-evolve:report",
                "run": str(run),
                "reason": "a run is in progress — report shows status; continue the algorithm loop."}

    if not yaml.exists():
        return {"state": "fresh", "next": "/cap-evolve:intake",
                "reason": "project dir exists but no capevolve.yaml — run intake."}

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
        "host_agnostic": "follow RUN.md (no plugin / non-Claude host)",
    }
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
