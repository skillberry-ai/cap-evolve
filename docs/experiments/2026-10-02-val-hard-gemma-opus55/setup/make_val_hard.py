#!/usr/bin/env python3
"""Build a HARDER 40-task val for the probe tier, from test tasks outside the 100-task test subset.

Rule (fixed before any run uses it):
  pool  = full_verified test tasks NOT in the probe test subset, scored (no infra error) by the empty
          seed and by all three #538 champions (runs 36466624841, 36523096755, 36622615059).
  mixed   = 1 or 2 of the 3 champions pass                -> all of them
  regress = seed passes, 0 of 3 champions pass            -> all of them
  allfail = seed fails, 0 of 3 champions pass             -> 5, random.Random(607)
  easy    = all 3 champions pass                          -> 2, random.Random(607), as anchors
  val_hard = mixed + regress + 5 allfail + 2 easy = 40 tasks.

Why: on the original val, round 1 already reaches ~0.95, so the gate cannot accept later rounds. The
123 pool tasks every #538 champion solves are that ceiling; the 31 "mixed" ones are solvable but not
reliably, which is where a later round can show a gain.

    python3 make_val_hard.py --metrics a.jsonl b.jsonl c.jsonl --dataset dataset.json --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

PROBE = Path(__file__).resolve().parent.parent / "full_verified_probe"
PARENT = PROBE.parent / "full_verified"
RUNS = ("36466624841", "36523096755", "36622615059")
SEED = 607


def digest(ids) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def build(metrics: list[Path], dataset: Path):
    parent = json.loads((PARENT / "split_ids.json").read_text())
    probe = json.loads((PROBE / "split_ids.json").read_text())
    kind = {str(x["id"]): x["instruction_type"] for x in json.loads(dataset.read_text())}
    seed, champs = {}, {}
    for f in metrics:
        for r in map(json.loads, f.read_text().splitlines()):
            if r.get("reward_opt") is None or r.get("reward_baseline") is None or r.get("opt_infra"):
                continue
            seed[r["task"]] = float(r["reward_baseline"])
            champs.setdefault(r["task"], []).append(float(r["reward_opt"]))
    sub = set(probe["test"])
    pool = sorted(t for t in parent["test"] if t not in sub and len(champs.get(t, [])) == len(metrics))
    k = {t: int(sum(champs[t])) for t in pool}
    mixed = [t for t in pool if 0 < k[t] < len(metrics)]
    regress = [t for t in pool if k[t] == 0 and seed[t] >= 1]
    allfail = [t for t in pool if k[t] == 0 and seed[t] < 1]
    easy = [t for t in pool if k[t] == len(metrics)]
    rng = random.Random(SEED)
    val = sorted(mixed + regress + rng.sample(allfail, 5) + rng.sample(easy, 2))
    assert len(val) == 40, len(val)
    assert not set(val) & (set(probe["train"]) | sub)
    out_split = {"train": probe["train"], "val": val, "test": probe["test"]}
    tasks = [dict(t, tag="full_verified_probe") for t in json.loads((PARENT / "tasks.json").read_text())
             if str(t["id"]) in set(out_split["train"]) | set(val) | sub]
    source = {
        "rule": "mixed(1-2 of 3 #538 champions pass) + regress(seed pass, 0/3) + 5 allfail + 2 easy, seed 607",
        "runs": list(RUNS), "seed": SEED,
        "pool": len(pool), "groups": {"mixed": len(mixed), "regress": len(regress),
                                      "allfail": len(allfail), "easy": len(easy)},
        "val_by_type": {t: sum(kind[v] == t for v in val) for t in sorted({kind[v] for v in val})},
        "val_seed_reward": sum(seed[v] for v in val) / len(val),
        "val_538_champion_mean": sum(sum(champs[v]) / len(champs[v]) for v in val) / len(val),
        "original_val_538_seed_reward": None,
        "sha256_sorted_ids": {s: digest(v) for s, v in out_split.items()},
        "per_task": {v: {"seed": seed[v], "champions_538": champs[v], "type": kind[v]} for v in val},
    }
    return out_split, tasks, source


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metrics", type=Path, nargs=3, required=True)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    split, tasks, source = build(a.metrics, a.dataset)
    print(json.dumps({k: v for k, v in source.items() if k != "per_task"}, indent=2))
    print("val:", " ".join(split["val"]))
    if a.write:
        (PROBE / "split_ids.json").write_text(json.dumps(split, indent=1, sort_keys=True) + "\n")
        (PROBE / "tasks.json").write_text(json.dumps(tasks, indent=2) + "\n")
        (PROBE / "val_hard_source.json").write_text(json.dumps(source, indent=2) + "\n")


if __name__ == "__main__":
    main()
