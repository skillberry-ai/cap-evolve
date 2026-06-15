"""``python -m agent_capo <command>`` — JSON-over-stdout entry for any host.

Skills that can't import the package call these subcommands and parse the JSON.
Keep this surface small and stable; it is the host-agnostic contract.
"""

from __future__ import annotations

import json
import sys

from . import __version__
from .check import _main as check_main
from .splits import make_splits


def _cmd_version(argv: list[str]) -> int:
    print(json.dumps({"version": __version__}))
    return 0


def _cmd_splits(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="agent_capo splits")
    p.add_argument("--ids", required=True, help="comma-separated task ids OR @path to a file of ids (one per line)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ratios", default="0.5,0.25,0.25")
    args = p.parse_args(argv)

    if args.ids.startswith("@"):
        ids = [l.strip() for l in open(args.ids[1:], encoding="utf-8") if l.strip()]
    else:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    ratios = tuple(float(x) for x in args.ratios.split(","))
    sp = make_splits(ids, seed=args.seed, ratios=ratios)
    print(json.dumps(sp.to_dict(), indent=2))
    return 0


COMMANDS = {
    "version": _cmd_version,
    "splits": _cmd_splits,
    "check": check_main,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: python -m agent_capo {version|splits|check} [args]", file=sys.stderr)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    fn = COMMANDS.get(cmd)
    if fn is None:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main())
