#!/usr/bin/env python3
"""Rebuild a published history record's per-task rows + suite rollup from a run's artifact.

WHY THIS EXISTS
    Held-out runs published before the fix in `metrics.suite_report` carry
    `reward_opt: null` on every task and `suite: null`, so the benchmarks page shows "—" in
    the reward column (see that function's docstring for the pairing bug). The numbers were
    never lost — they are in the run's `final.json`, which the run's artifact retains — so a
    record can be repaired without re-running anything.

    The aggregate job checks out at the DISPATCH sha, so a run already in flight when the
    fix merged will also publish a stale record. This repairs those too.

USAGE
    # 1. get the run's artifact (contains ui/data/runs_*_file_path_final_json.json)
    gh run download <run_id> --repo <owner>/<repo> --dir /tmp/art
    # 2. rewrite the record in place
    python3 ci/benchmarks/utils/rebuild_record.py /tmp/art records/<run_id>__<tier>-<bench>.json
    # 3. inspect, then commit the record to the benchmark-history branch

Idempotent: re-running on an already-correct record produces identical output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from record import rollup  # noqa: E402  (the SAME rollup the aggregate job uses)


def _find_final_json(artifact_dir: Path) -> dict:
    """Pull `final.json`'s contents out of a downloaded artifact's UI snapshot."""
    hits = sorted(artifact_dir.rglob("*file_path_final_json.json"))
    if not hits:
        raise SystemExit(f"no final.json snapshot under {artifact_dir} — artifact expired or "
                         "predates the UI export step")
    wrapper = json.loads(hits[0].read_text(encoding="utf-8"))
    text = wrapper.get("text")
    if wrapper.get("truncated"):
        raise SystemExit(f"{hits[0]} is truncated — cannot rebuild from it")
    if not text:
        raise SystemExit(f"{hits[0]} carries no text payload")
    return json.loads(text)


def rebuild_tasks(record: dict, final: dict) -> list[dict]:
    """Per-task rows paired the way `metrics.suite_report` now pairs them.

    Held-out: seed (`test_baseline`) vs best (`test`) on the SAME sealed tasks. If the two
    task sets differ the run was not held out and its existing rows are already correct.
    """
    existing = list(record.get("tasks") or [])
    # Only repair records that actually show the bug. A record whose rows already carry an
    # opt reward (any no-holdout run) is correct as published — leave it exactly as it is, so
    # this is safe to point at every record in the directory.
    if any(t.get("reward_opt") is not None for t in existing):
        return existing

    opt = {p["task_id"]: p for p in ((final.get("test") or {}).get("per_task") or [])}
    base = {p["task_id"]: p for p in ((final.get("test_baseline") or {}).get("per_task") or [])}
    if not opt or set(opt) != set(base):
        return existing

    template = (record.get("tasks") or [{}])[0]
    rows = []
    for tid, o in opt.items():
        b = base[tid]
        rb, ro = b.get("reward"), o.get("reward")
        # An infra-errored side has no meaningful delta — match metrics.py's treatment.
        infra = bool((o.get("raw") or {}).get("errored")) or bool((b.get("raw") or {}).get("errored"))
        rows.append({
            "bench": record.get("bench") or template.get("bench"),
            "tier": record.get("tier") or template.get("tier"),
            "task": tid,
            "reward_baseline": rb,
            "reward_opt": ro,
            "reward_delta": (round(ro - rb, 6)
                             if isinstance(rb, (int, float)) and isinstance(ro, (int, float))
                             and not infra else None),
            "opt_infra": infra,
            "run_dir": template.get("run_dir", ""),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact_dir", type=Path)
    ap.add_argument("record", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    final = _find_final_json(args.artifact_dir)

    before_opt = sum(1 for t in (record.get("tasks") or []) if t.get("reward_opt") is not None)
    tasks = rebuild_tasks(record, final)
    after_opt = sum(1 for t in tasks if t.get("reward_opt") is not None)

    record["tasks"] = tasks
    # rollup() returns None unless BOTH sides are present, which is exactly why suite was
    # null before; recompute it from the repaired rows using the aggregate job's own code.
    record["suite"] = (rollup(tasks, record.get("steps") or [])
                       if record.get("conclusion") == "success" else None)
    record["rebuilt_from_artifact"] = True

    s = record["suite"]
    print(f"{args.record.name}: tasks {len(tasks)} | reward_opt present {before_opt} -> {after_opt}")
    print("  suite: " + (f"{s['reward_base']:.4f} -> {s['reward_opt']:.4f} (n={s['n']})"
                         if s else "None (no valid pairing / run not successful)"))
    if args.dry_run:
        print("  (dry run — not written)")
        return 0
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"  written: {args.record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
