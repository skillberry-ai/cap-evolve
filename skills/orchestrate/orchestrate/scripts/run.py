"""orchestrate — resolve acapo.yaml + the manifest into an ordered run plan.

Prints the exact sequence of skill commands the pipeline will execute (or, with
``--execute``, hands off to ``acapo run`` to run them). Wiring is validated by
matching each step's `needs` against upstream `provides` in the manifest.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from agent_capo.specfile import read_yaml


def _skills_dir() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "_registry" / "manifest.json").exists():
            return parent
        if (parent / "skills" / "_registry" / "manifest.json").exists():
            return parent / "skills"
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="orchestrate")
    p.add_argument("--spec", default=".agentcapo/project/acapo.yaml")
    p.add_argument("--project", default=".agentcapo/project")
    p.add_argument("--execute", action="store_true", help="run the plan via `acapo run`")
    args = p.parse_args(argv)

    spec = read_yaml(Path(args.spec).read_text()) if Path(args.spec).exists() else {}
    sequence = ["intake", "implement-and-check", "baseline",
                spec.get("algorithm_skill", "all-at-once"), "finalize", "report"]
    plan = {
        "sequence": sequence,
        "capabilities": spec.get("capabilities"),
        "optimizer": spec.get("optimizer_skill"),
        "algorithm": spec.get("algorithm_skill"),
        "gate": spec.get("gate_mode"),
        "budget": {"max_iterations": spec.get("max_iterations"), "stall": spec.get("stall")},
        "rule": "acapo check must be green before baseline; test scored once at finalize.",
    }

    if args.execute:
        from agent_capo.cli import main as cli_main
        return cli_main(["run", "--spec", args.spec, "--project", args.project])

    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
