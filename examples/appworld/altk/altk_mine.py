"""Mine ALTK-Evolve guidelines from the seed's official-train rollouts (README: ALTK-Evolve arm). Python 3.12 venv.

    python altk_mine.py ROLLOUT_DIR [--workers 8]

ROLLOUT_DIR holds ``<task>__seed__t0.json`` from the cape-hc baseline (train = val, so they are
under rollouts/val/). Only the 90 official ``train`` ids are mined; dev ids are skipped. Each
trajectory goes through ``save_trajectory`` (standard mode, segmentation on: library defaults),
then the store is consolidated losslessly (threshold 0.80). Idempotent per task id.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import altk_common  # noqa: E402

NAMESPACE = "aw_train"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rollout_dir")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--train-ids", default=str(altk_common.EVAL / "root_opt/data/datasets/train.txt"))
    args = ap.parse_args()
    altk_common.setup(namespace=NAMESPACE)
    from altk_evolve.frontend.client.evolve_client import EvolveClient
    from altk_evolve.frontend.mcp import mcp_server
    from to_messages import load

    train = Path(args.train_ids).read_text().split()
    if len(train) != 90:
        print(f"expected 90 official train ids, got {len(train)}", file=sys.stderr)
        return 1
    files = {t: Path(args.rollout_dir) / f"{t}__seed__t0.json" for t in train}
    missing = [t for t, f in files.items() if not f.is_file()]
    if missing:
        print(f"{len(missing)} train rollouts missing, e.g. {missing[:3]}", file=sys.stderr)
        return 1
    errored = [t for t, f in files.items() if json.loads(f.read_text())["rollout"].get("error")]

    done_path = altk_common.ALTK_DIR / "mined.json"
    done = json.loads(done_path.read_text()) if done_path.is_file() else {}
    todo = [t for t in train if t not in done and t not in errored]
    altk_common.log(f"mining {len(todo)} of {len(train)} train trajectories ({len(done)} already, "
                    f"{len(errored)} infra-errored skipped)", "mine")

    def one(tid: str):
        t0 = time.time()
        try:
            mcp_server.save_trajectory(json.dumps(load(files[tid])), task_id=tid, namespace_id=NAMESPACE)
            # save_trajectory returns the trajectory entities only; count this task's guidelines in the store
            n = len(EvolveClient().get_all_entities(
                NAMESPACE, filters={"type": "guideline", "metadata.source_task_id": tid}, limit=10000))
            return tid, {"guidelines": n, "seconds": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001 — the library already logs and skips; we count it
            return tid, {"guidelines": 0, "error": f"{type(e).__name__}: {str(e)[:300]}"}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for tid, res in pool.map(one, todo):
            done[tid] = res
            done_path.write_text(json.dumps(done, indent=1))
            altk_common.log(f"mined {len(done)}/{len(train)} ({tid}: {res.get('guidelines')} guidelines"
                            f"{', error' if res.get('error') else ''})", "mine")

    client = EvolveClient()
    before = client.get_all_entities(NAMESPACE, filters={"type": "guideline"}, limit=10000)
    sup_before = sum(int((e.metadata or {}).get("support", 1) or 1) for e in before)
    altk_common.log(f"consolidating {len(before)} guidelines (support {sup_before}), lossless", "consolidate")
    result = client.consolidate_guidelines(NAMESPACE, mode="lossless")
    after = client.get_all_entities(NAMESPACE, filters={"type": "guideline"}, limit=10000)
    sup_after = sum(int((e.metadata or {}).get("support", 1) or 1) for e in after)
    summary = {
        "train_trajectories": len(train), "infra_errored_skipped": errored,
        "mined_ok": sum(1 for r in done.values() if not r.get("error")),
        "mining_errors": {t: r["error"] for t, r in done.items() if r.get("error")},
        "zero_guideline_trajectories": sum(1 for r in done.values() if not r.get("guidelines")),
        "guidelines_before": len(before), "support_before": sup_before,
        "guidelines_after": len(after), "support_after": sup_after,
        "support_conserved": sup_before == sup_after,
        "consolidation": result.model_dump() if hasattr(result, "model_dump") else str(result),
        "optimizer_usage": altk_common.usage_totals(),
    }
    (altk_common.ALTK_DIR / "mining_summary.json").write_text(json.dumps(summary, indent=1))
    altk_common.log(f"consolidated {len(before)} -> {len(after)} guidelines, support {sup_before} -> {sup_after}",
                    "consolidate")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
