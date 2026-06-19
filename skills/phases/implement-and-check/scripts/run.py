"""implement-and-check — the HARD GATE before any optimization budget is spent.

Runs ``cap-evolve check`` on the project adapter and (optionally) each involved skill's
own ``check.py``. Aggregates the results; exits non-zero if anything is unfilled
or non-deterministic, listing exactly what to fix.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.check import run_check


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="implement-and-check")
    p.add_argument("--project", default=".capevolve/project")
    p.add_argument("--skill-check", action="append", default=[],
                   help="path to a skill's scripts/check.py to also run (repeatable)")
    p.add_argument("--no-pipeline-selftest", action="store_true",
                   help="skip the pipeline-wiring self-test that runs after the check passes")
    args = p.parse_args(argv)

    report = {"ok": True, "project": {}, "skills": []}

    proj = run_check(Path(args.project))
    report["project"] = proj.to_dict()
    report["ok"] = report["ok"] and proj.ok

    for chk in args.skill_check:
        proc = subprocess.run([sys.executable, chk], capture_output=True, text=True)
        try:
            out = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            out = {"ok": proc.returncode == 0, "raw": proc.stdout[-500:], "stderr": proc.stderr[-500:]}
        out["_check"] = chk
        report["skills"].append(out)
        report["ok"] = report["ok"] and bool(out.get("ok"))

    # Only once the adapter contract is green is the pipeline-wiring self-test
    # meaningful: it proves the optimizer would get its trajectories + guidance +
    # a fully-rendered INSTRUCTIONS.md. A red check short-circuits it (nothing to
    # wire yet).
    if report["ok"] and not args.no_pipeline_selftest:
        from pipeline_selftest import selftest
        report["pipeline_selftest"] = selftest(Path(args.project))
        report["ok"] = report["ok"] and report["pipeline_selftest"]["ok"]

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
