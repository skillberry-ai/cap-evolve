"""Pipeline/run script for <skill-name>.

Assumes `check.py` is green. Wires the implemented abstract methods into
`cap_evolve`, performs this skill's step, and prints a single JSON object to
stdout (the contract surface consumed by downstream skills / non-Python hosts).
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap  # noqa: F401

import abstract  # noqa: F401  (the implemented methods)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="<skill-name> run")
    p.add_argument("--run-dir", default=None, help="path to the active .capevolve/run_* dir")
    # add skill-specific args here
    args = p.parse_args(argv)

    result = {
        "skill": "<skill-name>",
        # fill with this skill's output (shape documented in SKILL.md / meta.yaml provides)
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
