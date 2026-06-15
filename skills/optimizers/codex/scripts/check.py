"""Wiring check: run.py imports and exposes main() (does not require the external CLI)."""
from __future__ import annotations
import json, sys
import _bootstrap  # noqa: F401
def main() -> int:
    rep = {"ok": False, "problems": [], "notes": []}
    try:
        import run
        if not hasattr(run, "main"):
            rep["problems"].append("run.py missing main()")
        else:
            rep["notes"].append("optimizer wiring present (external CLI not required for check)")
    except Exception as e:  # noqa: BLE001
        rep["problems"].append(f"import failed: {e}")
    rep["ok"] = not rep["problems"]
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1
if __name__ == "__main__":
    sys.exit(main())
