"""Expose a skill package as a Candidate and report authoring-rule validity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from agent_capo import Candidate

import abstract


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="skill-package")
    p.add_argument("--path", required=True, help="the skill package dir (contains SKILL.md)")
    args = p.parse_args(argv)
    parts = abstract.materialize(Path(args.path))
    v = abstract.validate(Path(args.path))
    cand = Candidate(id="seed", component="skill-package", text_parts=parts, dir=str(args.path))
    print(json.dumps({"candidate": cand.to_dict(), "valid": v}, indent=2))
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
