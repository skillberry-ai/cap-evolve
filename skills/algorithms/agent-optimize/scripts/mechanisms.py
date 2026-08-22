"""Shared mechanism ledger for a per-task fan-out: what was found, who owns it, what it did.

K parallel optimisers on K different tasks keep rediscovering ONE cause. Measured on one
multi-turn tool-use benchmark: four of nine independently found the same root cause, and two
independently implemented the same fix — which then collided at merge, and
only one of the two had actually been measured. Both problems are the same problem: findings
lived in the coordinator's head instead of on disk.

So put them on disk. Every optimiser LISTS before it diagnoses (someone may already have your
bug, and if they own the fix you must not write a second one) and APPENDS when it finds a
mechanism (so the next optimiser does not pay for it again). This is what makes a fan-out
compound instead of merely parallel, and it replaces a broadcast the coordinator has to
remember to send.

    python mechanisms.py list --run-dir R [--file tools/tools.py]
    python mechanisms.py add  --run-dir R --owner t17 --status proposed \\
        --mechanism "<the cause, one sentence>" \\
        --evidence "3/5 failing trials commit to the first id probed" \\
        --touches <function-the-fix-edits>
    python mechanisms.py add  --run-dir R --owner t17 --status rejected \\
        --mechanism "invite the agent to ask which listed trip they meant" \\
        --evidence "user simulator invents a non-existent trip; 2/4 failures that round"

``status`` is the whole point of the ledger, so it is required:
  * ``proposed``  — diagnosed, edit written, not yet measured. Do not build on it.
  * ``verified``  — measured to move its target with the canary intact. Reuse, never rewrite.
  * ``rejected``  — measured at or below control, or actively harmful. Do not retry this form;
    a later attempt at the same failure must be structurally DIFFERENT.
"""

import argparse
import json
import os
import time
from pathlib import Path



def ledger(run_dir: Path) -> Path:
    return Path(run_dir) / "mechanisms.jsonl"


def add(args) -> int:
    row = {
        "seq": int(time.time() * 1000),
        "owner": args.owner,
        "status": args.status,
        "mechanism": args.mechanism,
        "evidence": args.evidence,
        "touches": sorted(set(args.touches or [])),
        "tasks": sorted(set(args.task or [])),
        "supersedes": sorted(set(args.supersedes or [])),
    }
    path = ledger(args.run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, sort_keys=True) + "\n"
    # O_APPEND makes a single small write atomic across the concurrent optimisers, so no
    # lock file is needed and a crashed optimiser cannot leave a half-written row.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    print(json.dumps({"added": row, "ledger": str(path)}, indent=2))
    return 0


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            continue          # a torn row is skipped, never fatal
    return rows


def lst(args) -> int:
    rows = read(ledger(args.run_dir))
    if args.file:
        rows = [r for r in rows if any(args.file in t for t in r.get("touches") or [])]
    if args.task:
        # A fan-out ledger grows past what is useful to paste at an optimiser: this one
        # reached 99 findings, and handing all of them to each of K subagents spends their
        # context on other people's tasks. Relevance = rows about THIS task, plus every row
        # with no task attached, because those are the cross-cutting facts (measurement
        # defects, canary bands, variance warnings) that apply to everyone and are exactly
        # what a filtered view must not hide.
        rows = [r for r in rows
                if args.task in (r.get("tasks") or []) or not (r.get("tasks") or [])]
    if args.compact:
        rows = [{k: v for k, v in r.items() if k != "evidence"} for r in rows]
    superseded = {sq for r in rows for sq in (r.get("supersedes") or [])}
    by = {"verified": [], "proposed": [], "rejected": []}
    dead = []
    for r in rows:
        if str(r.get("seq")) in superseded:
            dead.append(r)
            continue
        by.setdefault(r.get("status", "proposed"), []).append(r)
    owned = sorted({t for r in by["verified"] + by["proposed"]
                    for t in (r.get("touches") or [])})
    print(json.dumps({
        "count": len(rows),
        "verified": by["verified"],
        "proposed": by["proposed"],
        "rejected": by["rejected"],
        "already_owned_do_not_reimplement": owned,
        "superseded_do_not_act_on": [
            {"seq": r.get("seq"), "owner": r.get("owner"), "was": r.get("status"),
             "mechanism": (r.get("mechanism") or "")[:160]} for r in dead],
        "reminder": ("if your bug is listed as verified or proposed, its owner writes the fix — "
                     "rebase onto their copy and spend your iterations elsewhere; if it is "
                     "listed as rejected, a retry must be structurally different"),
    }, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--run-dir", required=True)
    a.add_argument("--owner", required=True, help="the optimiser tag that found it")
    a.add_argument("--status", required=True, choices=["proposed", "verified", "rejected"])
    a.add_argument("--mechanism", required=True, help="the CAUSE, in one sentence")
    a.add_argument("--evidence", required=True, help="what you measured or saw in the trace")
    a.add_argument("--touches", action="append", default=[],
                   help="function/file the fix edits (repeatable) — this is the collision key")
    a.add_argument("--task", action="append", default=[])
    a.add_argument("--supersedes", action="append", default=[],
                   help="seq id(s) this row replaces. A finding that turns out to be wrong cannot "
                        "just be contradicted by a newer row: on this run three separate "
                        "`verified` rows were later disproved, and a reader of the listing saw "
                        "both the claim and its refutation with no way to tell which won. A "
                        "superseded row is dropped from `verified`/`proposed` and reported "
                        "separately, so the ledger's own history stays auditable without "
                        "misleading the next optimiser. Repeatable.")
    a.set_defaults(fn=add)

    l = sub.add_parser("list")
    l.add_argument("--run-dir", required=True)
    l.add_argument("--file", default="", help="only rows whose touches mention this")
    l.add_argument("--task", default="", help="only rows about THIS task, plus every "
                                              "task-independent row (those apply to everyone)")
    l.add_argument("--compact", action="store_true",
                   help="drop the evidence field: mechanism + status + touches only")
    l.set_defaults(fn=lst)

    args = ap.parse_args(argv)
    args.run_dir = Path(args.run_dir)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
