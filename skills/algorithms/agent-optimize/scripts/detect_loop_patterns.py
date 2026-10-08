"""detect_loop_patterns — find agent-driven tool-call loops in persisted rollouts.

Issue #684 item 7: cost/latency reduction was never a candidate design lever in the real
run this issue diagnoses — every candidate's JOURNAL.md left the cost-reduction hypothesis
line unfilled, and `cost`/`num_messages` were declared objectives that no edit ever
targeted. The concrete, mechanically-detectable signal this script looks for: the SAME
tool called N+ times in a row, by the agent itself, within one rollout (e.g.
`get_reservation_details` once per reservation across N reservations) — a candidate for a
NEW composite/bulk tool that does the whole loop in ONE deterministic call instead of N
agent-driven ones.

Pure trace analysis, no LLM call: cheap enough to run every round for free whenever
`cost`/`latency`/`num_messages` is a declared objective (see SKILL.md's diagnose step).

Reads the same on-disk rollout records diagnose.py reads — core's `rollouts/<split>/
<task_id>__<tag>__t<k>.json` files (``{"input":..., "rollout": Rollout.to_dict(), "score":
Score.to_dict()}``) — and extracts tool-call names the same runner-agnostic way
`skills/phases/diagnose/scripts/cluster.py:_call_names` does (``rollout.tool_calls``, or an
OpenAI-style message list in ``rollout.trace``): no project/adapter needed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir


def _call_names(rollout: dict) -> list[str]:
    """Ordered tool-call names from a rollout dict — mirrors cluster.py's `_call_names`
    (same two core/wire shapes), minus its `"!mutates"` sentinel, which would otherwise
    break a same-name-in-a-row count by inserting a token between repeats."""
    out: list[str] = []

    def add(call) -> None:
        if isinstance(call, str):
            out.append(call)
        elif isinstance(call, dict):
            fn = call.get("function")
            name = call.get("name") or (fn.get("name") if isinstance(fn, dict) else None)
            if name:
                out.append(str(name))

    for call in rollout.get("tool_calls") or []:
        add(call)
    trace = rollout.get("trace")
    if isinstance(trace, list):
        for msg in trace:
            if not isinstance(msg, dict):
                continue
            for call in msg.get("tool_calls") or []:
                add(call)
    return out


def _load_records(run_dir: RunDir, tag: str, split: str) -> list[dict]:
    """Same glob diagnose.py uses: one file per (task, trial) for this tag/split."""
    out = []
    d = run_dir.rollouts / split
    if not d.exists():
        return out
    for f in sorted(d.glob(f"*__{tag}__t*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["__file"] = str(f)
        out.append(rec)
    return out


def find_loops(records: list[dict], min_n: int = 3) -> list[dict]:
    """Maximal runs of the SAME tool called >= `min_n` times in a row, one rollout at a
    time. Returns one entry per run found (a rollout with two separate loops over
    different tools yields two entries)."""
    patterns = []
    for rec in records:
        task_id = (rec.get("rollout") or {}).get("task_id") or (rec.get("score") or {}).get("task_id")
        names = _call_names(rec.get("rollout") or {})
        i = 0
        while i < len(names):
            j = i
            while j < len(names) and names[j] == names[i]:
                j += 1
            run_len = j - i
            if run_len >= min_n:
                patterns.append({
                    "tool": names[i],
                    "repeat_count": run_len,
                    "task_id": task_id,
                    "file": rec.get("__file"),
                })
            i = j
    return patterns


def summarize(patterns: list[dict]) -> dict:
    """Group by tool: a 'cost-reduction opportunity cluster' per repeated tool, with
    the tasks it recurs on and the worst repeat count — what SKILL.md's diagnose step
    proposes a composite/bulk tool against."""
    by_tool: dict[str, dict] = {}
    for p in patterns:
        s = by_tool.setdefault(p["tool"], {"tasks": [], "max_repeat_count": 0, "occurrences": 0})
        s["tasks"].append(p["task_id"])
        s["max_repeat_count"] = max(s["max_repeat_count"], p["repeat_count"])
        s["occurrences"] += 1
    for s in by_tool.values():
        s["tasks"] = sorted(set(s["tasks"]))
    return by_tool


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="detect_loop_patterns")
    p.add_argument("-r", "--run-dir", required=True)
    p.add_argument("-t", "--tag", required=True, help="candidate id whose rollouts to scan")
    p.add_argument("--split", default="val")
    p.add_argument("--min-n", type=int, default=3,
                    help="minimum same-tool-in-a-row repeat count to flag (default 3)")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    records = _load_records(run_dir, args.tag, args.split)
    patterns = find_loops(records, min_n=args.min_n)
    by_tool = summarize(patterns)
    print(json.dumps({
        "run_dir": str(run_dir.root), "tag": args.tag, "split": args.split,
        "min_n": args.min_n, "n_rollouts_scanned": len(records),
        "patterns": patterns, "by_tool": by_tool,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
