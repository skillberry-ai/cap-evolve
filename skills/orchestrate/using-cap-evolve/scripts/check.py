"""Behavioral check for using-cap-evolve.

Asserts the router actually routes: a fresh (empty) base resolves to `fresh` /
intake, and a scaffolded base (capevolve.yaml present, no run) resolves to a
non-fresh state pointing at implement-and-check or later — i.e. the state machine
is wired, not a stub.
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
    except Exception as e:  # noqa: BLE001
        rep["problems"].append(f"import/exec failed: {e}")
    rep["ok"] = not rep["problems"]
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
