#!/usr/bin/env python3
"""Reconstruct final.json for v6_g2_e1 from already-completed test rollouts.

The run's finalize driver (LSF job 1702040) completed BOTH test-split evaluations
(cand_0005 as "FINAL", seed as "FINAL_seed" — 660 rollouts each, logged in
events.jsonl with final rewards) and then crashed (exit 255, apparent host
instability on cccxc436) while starting the free train/val bookend report, before
final.json was written and before commit_test() sealed the test split.

This script does NOT re-score test (that would be a second, dishonest look at the
held-out set). It reads the 1320 test rollout files already on disk, reconstructs
the two SplitResults the exact way cap-evolve's own resume path does
(split_result_from_rollouts), writes final.json with the honest test comparison,
marks the train/val bookend as skipped (crash, not fabricated), and commits the
test seal via RunDir.commit_test() — the same seal-on-success call finalize()
itself would have made.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "core")
from cap_evolve.rundir import RunDir  # noqa: E402
from cap_evolve.harness import split_result_from_rollouts  # noqa: E402

RUN_DIR = Path(".capevolve/v6_g2_e1/run_g2_e1")


def cost_tokens_from_events(tag: str) -> tuple[float, int, float]:
    """Pull cost_usd/tokens/seconds for one FINAL* evaluate event from events.jsonl —
    split_result_from_rollouts doesn't carry run-level cost, but the event already does."""
    for line in (RUN_DIR / "events.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e.get("kind") == "evaluate" and e.get("split") == "test" and e.get("tag") == tag:
            return e.get("cost_usd", 0.0), e.get("tokens", 0), e.get("seconds", 0.0)
    raise RuntimeError(f"no evaluate/test event found for tag={tag!r}")


def main() -> int:
    run_dir = RunDir.open(RUN_DIR)

    if (RUN_DIR / "final.json").exists():
        print("final.json already exists — refusing to overwrite", file=sys.stderr)
        return 1

    splits = run_dir.read_splits()
    if splits.test_used:
        print("test seal already committed — nothing to do", file=sys.stderr)
        return 1

    best_id = run_dir.best_id
    assert best_id == "cand_0005", f"expected champion cand_0005, got {best_id!r}"

    best = split_result_from_rollouts(run_dir, "FINAL", split="test")
    base = split_result_from_rollouts(run_dir, "FINAL_seed", split="test")

    best_cost, best_tok, best_sec = cost_tokens_from_events("FINAL")
    base_cost, base_tok, base_sec = cost_tokens_from_events("FINAL_seed")

    best_dict = best.to_dict()
    best_dict.update(cost_usd=best_cost, tokens=best_tok, seconds=best_sec)
    base_dict = base.to_dict()
    base_dict.update(cost_usd=base_cost, tokens=base_tok, seconds=base_sec)

    payload = {
        "test": best_dict,
        "best_id": best_id,
        "test_baseline": base_dict,
        "baseline_id": "seed",
        "test_delta": round(best.reward - base.reward, 6),
        "best": {
            "val": {"status": "skipped: finalize crashed (LSF job 1702040, exit 255) "
                               "before the train/val bookend ran; not fabricated"},
            "train": {"status": "skipped: finalize crashed (LSF job 1702040, exit 255) "
                                 "before the train/val bookend ran; not fabricated"},
            "test": best_dict,
        },
        "seed": {
            "val": {"status": "skipped: finalize crashed (LSF job 1702040, exit 255) "
                               "before the train/val bookend ran; not fabricated"},
            "train": {"status": "skipped: finalize crashed (LSF job 1702040, exit 255) "
                                 "before the train/val bookend ran; not fabricated"},
            "test": base_dict,
        },
        "train_equals_val": bool(splits.train) and set(splits.train) == set(splits.val),
        "reconstruction_note": (
            "This final.json was reconstructed from already-completed test rollouts "
            "after the finalize driver (LSF job 1702040) crashed (exit 255) during the "
            "post-test train/val bookend step — NOT during test scoring. Both test "
            "evaluations (cand_0005 as 'FINAL', seed as 'FINAL_seed') had already fully "
            "completed and were logged in events.jsonl before the crash. No test "
            "rollout was re-run or re-scored; this script only re-reads the 1320 "
            "rollout files already on disk via split_result_from_rollouts(), the same "
            "function cap-evolve's own resume path uses. The train/val bookend was "
            "never run and is marked skipped above, not fabricated."
        ),
    }

    (RUN_DIR / "final.json").write_text(json.dumps(payload, indent=2))
    run_dir.commit_test()
    run_dir.log_event("finalize", test_reward=best.reward, test_baseline_reward=base.reward,
                       test_delta=payload["test_delta"], best_id=best_id,
                       reconstructed_after_crash=True)

    print(json.dumps({"test": best_dict["reward"], "test_baseline": base_dict["reward"],
                       "test_delta": payload["test_delta"], "best_id": best_id}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
