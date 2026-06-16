"""Expose a tools/MCP artifact as a Candidate and report policy + validity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import Candidate

import abstract


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mcp-tool")
    p.add_argument("--path", required=True, help="capability dir with tools.json (+ policy.json)")
    args = p.parse_args(argv)
    parts = abstract.materialize(Path(args.path))
    policy = abstract.load_policy(Path(args.path))
    v = abstract.validate(Path(args.path))
    cand = Candidate(id="seed", component="mcp-tool", text_parts=parts, dir=str(args.path))
    print(json.dumps({"candidate": cand.to_dict(), "policy": policy, "valid": v}, indent=2))
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
