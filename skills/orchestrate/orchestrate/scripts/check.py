"""Wiring check for orchestrate."""
from __future__ import annotations
import json, sys
import _bootstrap  # noqa: F401
def main() -> int:
    rep = {"ok": False, "problems": [], "notes": []}
    try:
        import run
        if not hasattr(run, "main"):
            rep["problems"].append("run.py missing main()")
        from cap_evolve.specfile import read_yaml  # noqa: F401
        rep["notes"].append("orchestrate wiring ok")
    except Exception as e:  # noqa: BLE001
        rep["problems"].append(f"import failed: {e}")
    rep["ok"] = not rep["problems"]
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1
if __name__ == "__main__":
    sys.exit(main())
