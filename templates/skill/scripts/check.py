"""Per-skill gate for <skill-name>.

Verifies that this skill's abstract methods are implemented and run
deterministically on a tiny smoke input, then prints a JSON report. Exit 0 only
when green. The orchestration prompt requires every involved skill's check to be
green before spending optimization budget.
"""

from __future__ import annotations

import json
import sys

import _bootstrap  # noqa: F401  (locates agent_capo)

import abstract


def main() -> int:
    report = {"skill": "<skill-name>", "ok": False, "stubs": [], "problems": [], "notes": []}

    # 1. detect unimplemented methods by scanning their SOURCE for the marker.
    #    (Calling probes with no args would misclassify a stub that declares
    #    required positional args — the TypeError would be swallowed.)
    import inspect
    marker = getattr(abstract, "IMPLEMENT_MARKER", "IMPLEMENT ME")
    for name in dir(abstract):
        if name.startswith("_"):
            continue
        obj = getattr(abstract, name)
        if not callable(obj) or getattr(obj, "__module__", None) != abstract.__name__:
            continue
        try:
            src = inspect.getsource(obj)
        except (OSError, TypeError):
            continue
        if f'NotImplementedError' in src and marker in src:
            report["stubs"].append(name)

    if report["stubs"]:
        report["problems"].append(
            "unimplemented methods: " + ", ".join(report["stubs"])
        )
        print(json.dumps(report, indent=2))
        return 1

    # 2. TODO per skill: run a deterministic smoke call and assert stability.
    report["notes"].append("no smoke test defined for the template; add one per skill")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
