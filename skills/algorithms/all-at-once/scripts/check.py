"""Verify the algorithm wires to the shared hill-climb loop and exposes main()."""
from __future__ import annotations
import json, sys
import _bootstrap  # noqa: F401
def main() -> int:
    rep = {"ok": False, "problems": [], "notes": []}
    try:
        from agent_capo import harness
        if not hasattr(harness, "hill_climb_loop"):
            rep["problems"].append("core harness missing hill_climb_loop")
        import run
        for attr in ("main", "FOCUS", "ALGO"):
            if not hasattr(run, attr):
                rep["problems"].append(f"run.py missing {attr}")
        rep["notes"].append(f"focus={getattr(run,'FOCUS','?')} via shared loop")
    except Exception as e:  # noqa: BLE001
        rep["problems"].append(f"import failed: {e}")
    rep["ok"] = not rep["problems"]
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1
if __name__ == "__main__":
    sys.exit(main())
