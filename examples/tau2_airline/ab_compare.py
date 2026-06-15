"""Head-to-head A/B: degraded vs restored airline policy on a fixed task set.

Demonstrates that the optimization (restoring the cancellation-eligibility
section) yields a real *aggregate* improvement in tau2 reward, independent of
train/val/test split luck. Both policies are scored on the SAME tasks with the
SAME seed via tau2 + RITS gpt-oss-120b.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tau2_runtime as rt  # noqa: E402

TASK_IDS = os.environ.get("AB_TASK_IDS", "0,1,26,39,41,43,45,47,48,49").split(",")


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def score_policy(policy_dir: Path) -> dict:
    raw = rt.run_airline_batch(policy_dir, TASK_IDS)
    rewards = {tid: r["reward"] for tid, r in raw.items()}
    return {"mean": mean(list(rewards.values())), "per_task": rewards}


def main() -> int:
    degraded = HERE / "policy_degraded"
    restored = HERE / "policy"   # the full original policy = the optimization target
    print(f"A/B on {len(TASK_IDS)} cancellation tasks: {TASK_IDS}", file=sys.stderr)
    deg = score_policy(degraded)
    res = score_policy(restored)
    out = {
        "tasks": TASK_IDS,
        "degraded_mean": round(deg["mean"], 3),
        "restored_mean": round(res["mean"], 3),
        "delta": round(res["mean"] - deg["mean"], 3),
        "degraded_per_task": deg["per_task"],
        "restored_per_task": res["per_task"],
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
