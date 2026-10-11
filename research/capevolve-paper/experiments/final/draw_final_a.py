#!/usr/bin/env python3
"""draw_final_a.py: the seeded, stratified Suite A final-task draw (decisions.md 2026-10-11 11:35; final_set_candidates.md section 1).

    draw_final_a.py --selftest                 synthetic pool; checks determinism / allocation / one-per-family (no real ids read)
    draw_final_a.py --T 70 --write             THE DRAW.  Run only at freeze, on the coordinator's word.  Writes
                                               protocol/final_set/suiteA_final_tasks.json (+ .sha256) and refuses to overwrite.

Pool: protocol/final_set/sb912_residual_pool.json, `ids` (294 eligible under the recalculated reward).  Rule:
  1. drop ids whose family shares a prefix with a dev-exposed task (family_dev_exposed_members > 0): 55 ids, leaves 239;
  2. strata = gold_has_formula_in_range x instruction_type (4 cells);
  3. proportional allocation of T over the strata by largest remainder (ties by stratum name), capped at stratum size;
  4. inside a stratum a seeded sha256-counter shuffle of the sorted ids picks the sample, at most ONE task per family;
  5. seed 20261013, n = 1 trial per task (trials are set in order.py).
The output carries the pool hash, the draw parameters and this script's hash, and is hashed before any scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402
from order import HashRng, family_of_sb_id  # noqa: E402

POOL = C.PAPER / "protocol/final_set/sb912_residual_pool.json"
OUT = C.PAPER / "protocol/final_set/suiteA_final_tasks.json"


def stratum(r):
    return "%s|%s" % ("formula" if r.get("gold_has_formula_in_range") else "literal",
                      "cell" if str(r.get("instruction_type", "")).startswith("Cell") else "sheet")


def allocate(sizes, T):
    tot = sum(sizes.values())
    T = min(T, tot)
    raw = {k: T * v / tot for k, v in sizes.items()}
    base = {k: min(int(raw[k]), sizes[k]) for k in sizes}
    rem = T - sum(base.values())
    order = sorted(sizes, key=lambda k: (-(raw[k] - int(raw[k])), k))
    i = 0
    while rem > 0 and i < 10 * len(order):
        k = order[i % len(order)]
        if base[k] < sizes[k]:
            base[k] += 1
            rem -= 1
        i += 1
    return base


def draw(records, T, seed=C.ORDER_SEED, drop_sibling_exposed=True):
    recs = [r for r in records if not (drop_sibling_exposed and r.get("family_dev_exposed_members", 0) > 0)]
    strata = {}
    for r in recs:
        strata.setdefault(stratum(r), []).append(r)
    alloc = allocate({k: len(v) for k, v in strata.items()}, T)
    chosen = []
    used_fam = set()
    for k in sorted(strata):
        pool = sorted(strata[k], key=lambda r: str(r["id"]))
        HashRng(seed, "suiteA-draw|%s" % k).shuffle(pool)
        n = 0
        for r in pool:
            fam = str(r.get("family") or family_of_sb_id(r["id"]))
            if fam in used_fam:
                continue
            used_fam.add(fam)
            chosen.append({"id": str(r["id"]), "family": fam, "stratum": k, "instruction_type": r["instruction_type"],
                           "gold_has_formula_in_range": r["gold_has_formula_in_range"]})
            n += 1
            if n >= alloc[k]:
                break
    chosen.sort(key=lambda t: t["id"])
    return chosen, alloc, {k: len(v) for k, v in strata.items()}, len(recs)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--T", type=int, default=70)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        recs = [{"id": "%d-%d" % (i // 3, i % 3), "family": str(i // 3), "instruction_type": "Cell-Level" if i % 2 else "Sheet-Level",
                 "gold_has_formula_in_range": (i % 5) < 3, "family_dev_exposed_members": 1 if i % 11 == 0 else 0} for i in range(300)]
        c1, al, sz, n = draw(recs, 70)
        c2, _, _, _ = draw(recs, 70)
        assert c1 == c2, "not deterministic"
        assert len(c1) == 70 and len({t["family"] for t in c1}) == 70, "size / one-per-family"
        assert sum(al.values()) == 70
        assert not any(int(t["id"].split("-")[0]) * 3 + int(t["id"].split("-")[1]) in range(0, 300, 11) for t in c1), "exposed sibling drawn"
        print("selftest ok: pool %d -> strata %s -> alloc %s" % (n, sz, al))
        return 0
    if not a.write:
        sys.exit("refusing to draw without --write (the draw happens once, at freeze)")
    if OUT.exists():
        sys.exit("final Suite A task file already exists: %s (never redraw)" % OUT)
    pool = C.jload(POOL)
    chosen, alloc, sizes, n = draw(pool["ids"], a.T)
    doc = {"suite": "A", "seed": C.ORDER_SEED, "T": len(chosen), "n_trials_per_task": 1, "pool_file": str(POOL.relative_to(C.PAPER)), "pool_file_sha256": C.file_sha(POOL),
           "pool_sorted_ids_sha256": pool["summary"]["sorted_ids_sha256"], "n_after_sibling_exclusion": n, "stratum_sizes": sizes, "allocation": alloc,
           "draw_script_sha256": C.file_sha(__file__), "drawn_utc": C.now_utc(), "tasks": chosen,
           "tasks_sorted_ids_sha256": hashlib.sha256("\n".join(sorted(t["id"] for t in chosen)).encode()).hexdigest()}
    C.write_json_atomic(OUT, doc)
    OUT.with_suffix(".sha256").write_text("%s  %s\n" % (C.sha256_file(OUT), OUT.name))
    print("wrote", OUT, "T =", len(chosen), "sha256", C.sha256_file(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
