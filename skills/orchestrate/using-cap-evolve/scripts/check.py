"""Behavioral check for using-cap-evolve.

Asserts the router actually routes, and that the three misroutes issue #339
reproduced stay fixed:

  * fresh (empty base) -> `fresh` / intake; a scaffolded base is not `fresh`.
  * a run dir with no `state.json` is NOT reported as `scaffolded` (it would send
    the agent to implement an adapter that already exists).
  * a newer live run is never masked by an older sealed one (which would claim a
    sealed headline number while an optimization is mid-flight).
  * `running` routes to `--resume` and `finalized` to `--reuse-baseline` — report
    continues nothing.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401


def main() -> int:
    rep = {"ok": False, "problems": [], "notes": []}
    try:
        import run
        if not hasattr(run, "main") or not hasattr(run, "resolve_state"):
            rep["problems"].append("run.py missing main()/resolve_state()")
        else:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td) / ".capevolve"
                base.mkdir(parents=True)
                fresh = run.resolve_state(base)
                if fresh.get("state") != "fresh":
                    rep["problems"].append(f"empty base should be 'fresh', got {fresh.get('state')!r}")
                if "intake" not in (fresh.get("next") or ""):
                    rep["problems"].append("fresh state must route to intake")

                # scaffolded: project dir + capevolve.yaml, no run, no adapter
                proj = base / "project"
                proj.mkdir(parents=True)
                (proj / "capevolve.yaml").write_text("capability_path: seed\n", encoding="utf-8")
                scaffolded = run.resolve_state(base)
                if scaffolded.get("state") == "fresh":
                    rep["problems"].append("base with capevolve.yaml should not be 'fresh'")
                rep["notes"].append(f"fresh -> {fresh.get('next')}; "
                                    f"scaffolded -> {scaffolded.get('next')}")

                # case A: a run dir mid-create (no state.json) must not read as scaffolded.
                (base / "run_20260101_000000").mkdir()
                started = run.resolve_state(base)
                if started.get("state") == "scaffolded":
                    rep["problems"].append("a run dir with no state.json must not resolve to "
                                           "'scaffolded' (sends the agent to re-implement)")
                if "--resume" not in (started.get("next") or ""):
                    rep["problems"].append("a half-created run must route to `run --resume`")

                # case C: newer live run must not be masked by an older sealed one.
                sealed = base / "run_20260101_000000"
                (sealed / "state.json").write_text("{}", encoding="utf-8")
                (sealed / "splits.json").write_text('{"test_used": true}', encoding="utf-8")
                fin = run.resolve_state(base)
                if fin.get("state") != "finalized":
                    rep["problems"].append(f"sealed run should be 'finalized', got {fin.get('state')!r}")
                if "--reuse-baseline" not in (fin.get("next") or ""):
                    rep["problems"].append("'finalized' must offer a new run with --reuse-baseline, "
                                           "not just a report")

                live = base / "run_20260202_000000"
                live.mkdir()
                (live / "state.json").write_text("{}", encoding="utf-8")
                (live / "splits.json").write_text('{"test_used": false}', encoding="utf-8")
                mid = run.resolve_state(base)
                if mid.get("state") != "running":
                    rep["problems"].append(f"a newer unsealed run must win over an older sealed "
                                           f"one; got {mid.get('state')!r}")
                if "--resume" not in (mid.get("next") or ""):
                    rep["problems"].append("'running' must route to `cap-evolve run --resume`")
                rep["notes"].append(f"run_started -> {started.get('next')}; "
                                    f"finalized -> {fin.get('state')}; running -> {mid.get('next')}")
    except Exception as e:  # noqa: BLE001
        rep["problems"].append(f"import/exec failed: {e}")
    rep["ok"] = not rep["problems"]
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
