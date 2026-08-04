"""mechanism-probe entry — report which proposal-declaration fields a PROCESS.md carries.

Presence only, by design: ``cap_evolve.proposal_quality`` is the single parser (the same
one the harness logs from), and it cannot tell a mechanism from a knob. That judgement
stays in the prompt (SKILL.md) where it shapes the proposal, not in a heuristic that
could reject a real improvement.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import proposal_quality


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mechanism-probe")
    p.add_argument("--process", default="PROCESS.md",
                   help="the PROCESS.md carrying the proposal declaration")
    args = p.parse_args(argv)
    proc = Path(args.process)
    q = proposal_quality.parse(proc.parent if proc.name == "PROCESS.md" else proc)
    print(json.dumps({"enforcement": "advisory", **q}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
