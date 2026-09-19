"""Generate the tier task lists for the two skillberry_benchmarks_tau2_airline arms.

Run once from the repo root; committed output is what CI reads. Kept as a script rather than
hand-written JSON so the two arms can never drift from each other — a direct-vs-spa
comparison is only meaningful over the SAME task ids.

    python3 ci/benchmarks/lib/make_arm_tiers.py
"""

import json
import pathlib

# smoke deliberately reuses ci/benchmarks/tau2/smoke's ids: the arms deliver the same airline
# tasks by a different route, so sharing the id set makes the three legs (tau2 / direct / spa)
# directly comparable instead of three different samples of the same benchmark.
SMOKE = ["17", "40", "12", "8", "37", "23", "25", "22", "19", "11"]
# integration is the single task the arms' own split_ids_task9.json pins, and the same task
# ci/benchmarks/tau2/integration uses.
INTEGRATION = ["9"]
# full is every airline task, matching each arm's committed split_ids.json (all 50, no holdout).
FULL = [str(i) for i in range(50)]

# PROVENANCE, not a pin — run_suite.sh's AGENT_MODEL is authoritative (see its note on
# tasks.json's "agent" field). aws/gpt-oss-120b is what both arms were curated against.
#
# NB for the spa arm this is deliberately NOT `ibm/skillberry-local`. That sentinel is not a
# gateway model: it tells the runner to route the agent turn through the Proxy-Agent, which
# then calls THIS model. Recording the sentinel here would make sync_models.py report the
# tier as pinning an "unserved agent" on every scheduled pass.
AGENT = "aws/gpt-oss-120b"

TIERS = {
    "smoke": (SMOKE, "repr"),
    "integration": (INTEGRATION, "integration"),
    "full": (FULL, "full"),
}
ARMS = ("skillberry_tau2_direct", "skillberry_tau2_spa")


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]  # ci/benchmarks
    for arm in ARMS:
        for tier, (ids, tag) in TIERS.items():
            d = root / arm / tier
            d.mkdir(parents=True, exist_ok=True)
            rows = [{"id": i, "tag": tag, "agent": AGENT} for i in ids]
            (d / "tasks.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
            print(f"  {d.relative_to(root.parents[1])}/tasks.json  ({len(ids)} tasks)")


if __name__ == "__main__":
    main()
