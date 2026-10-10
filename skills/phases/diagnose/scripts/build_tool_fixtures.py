"""build_tool_fixtures — harvest replayable tool calls from a parent's rollouts (issue #716).

Writes ``$R/tool_fixtures.jsonl``: ``{tool, args, result, task_id, trace_id, pre_write: true}``.

Only calls made BEFORE the first state-changing call of a trajectory are kept: their result
depends only on the task's initial state, so it is reproducible. Later results depend on the
mutated database and are excluded. A write call that itself ERRORED did not change state, so
it neither ends the window nor is hidden — it is the most useful fixture (the real arguments
an agent sent to a write tool that rejected them). Whether a call writes uses
``cluster._mutates`` (name heuristic; an adapter's explicit ``mutates: true`` wins).

Fixtures are deduped by (tool, canonical-args hash) and sorted, so the file is deterministic.
Replay is only valid for deterministic tool paths; stateful sequences are not covered.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

import cluster as _cluster

from cap_evolve import RunDir


def fixtures_from(records: list[dict]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for rec in records:
        ro = rec.get("rollout") or {}
        tid = str(rec.get("score", {}).get("task_id"))
        trace_id = Path(rec.get("__file") or "").stem or None
        for c in _cluster.trace_calls(ro):
            if c["result"] is None:
                continue                     # never answered: nothing to replay against
            if (c["mutates"] or _cluster._mutates(c["name"])) and not c["error"]:
                break                        # first state change: later results are state-dependent
            key = (c["name"], hashlib.sha1(
                json.dumps(c["args"], sort_keys=True, default=str).encode()).hexdigest())
            seen.setdefault(key, {"tool": c["name"], "args": c["args"], "result": c["result"],
                                  "task_id": tid, "trace_id": trace_id, "pre_write": True})
    return [seen[k] for k in sorted(seen)]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="build_tool_fixtures")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--tag", default="seed", help="parent tag(s) to harvest, comma-separated")
    p.add_argument("--split", default="val", choices=["train", "val"])
    p.add_argument("--only-failing", action="store_true",
                   help="harvest only from trials that failed (reward < 1)")
    args = p.parse_args(argv)
    run_dir = RunDir.open(Path(args.run_dir))
    # by path: other skills ship a run.py too, so a bare `import run` can hit the wrong one
    spec = importlib.util.spec_from_file_location("diagnose_run", Path(__file__).with_name("run.py"))
    _run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_run)
    recs = _run._load_records(run_dir, args.tag, args.split)
    if args.only_failing:
        recs = [r for r in recs if (r.get("score", {}).get("reward") or 0) < 1.0]
    rows = fixtures_from(recs)
    out = run_dir.root / "tool_fixtures.jsonl"
    out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({"fixtures": len(rows), "path": str(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
