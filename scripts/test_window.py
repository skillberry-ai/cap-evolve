#!/usr/bin/env python3
"""Held-out TEST scoring for one frozen champion, with an interleaved seed anchor (Boaz, 2026-10-22; deviation from §9).

Usage: test_window.py <out_dir> <arm> <search_seed> <champion_dir> [--anchor-trials 3] [--k 3]

  * The champion directory is FROZEN first: its file tree is copied to <out_dir>/champion/ and the sha256 of every file
    is recorded in registry.json BEFORE the first episode, so the scored bytes are provably the frozen ones.
  * The episode order is (champion x k + seed x anchor) on the 280 official test tasks, interleaved in one shuffled order
    with a fixed seed. order.jsonl and its sha256 are written to registry.json before scoring. The seed anchor in the
    same window measures endpoint drift: the headline is the paired per-task delta vs the same-window seed (§9 estimator).
  * Every episode goes through the SAME adapter as search (run_target + score: same agent, LibreOffice recalc, helper
    gate). Infra errors get up to 3 retries with a fresh seed (§9.4) and otherwise count as missing, never 0.
  * Trial seeds are disjoint from every search: 900_000_000 + 1000*cell + 100*attempt + trial.
Writes results.jsonl (one row per episode) and summary.json (per-cell mean, paired delta vs seed with CR1 SE by task).
"""
import argparse
import hashlib
import json
import math
import random
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import adapter as sb  # on PYTHONPATH via node_env.sh

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("arm"); ap.add_argument("search_seed", type=int); ap.add_argument("champion")
ap.add_argument("--k", type=int, default=3); ap.add_argument("--anchor-trials", type=int, default=3)
# --resume (2026-10-25, Boaz): finish a window whose job died (host lost). It re-uses the FROZEN champion and the
# registered order, verified against registry.json's sha256s, keeps every finished episode in results.jsonl and runs
# only the episodes with no final row. Without --resume behaviour is unchanged (an existing dir is refused).
ap.add_argument("--resume", action="store_true")
# --champion-first (2026-10-27, Boaz): run ALL champion episodes first, write summary_champion_only.json (champion score, no pairing),
# then the seed episodes, then the normal paired summary.json. If time runs out the champion-only result still exists, and it can be
# compared with the seed score of the other windows (the seed barely moves: 0.636-0.653 in every finished window). Opt-in; the
# default order (champion and seed interleaved in one shuffle) is unchanged for every other window.
ap.add_argument("--champion-first", action="store_true")
a = ap.parse_args()
out = Path(a.out)
if out.exists() and not a.resume:
    sys.exit(f"refusing to overwrite an existing test window: {out}")
if a.resume and not (out / "registry.json").exists():
    sys.exit(f"--resume needs a registered window: {out}/registry.json missing")
if a.resume and (out / "summary.json").exists():
    sys.exit(f"--resume: window already finished: {out}/summary.json")
out.mkdir(parents=True, exist_ok=a.resume)
REPO = Path(sb.__file__).resolve().parents[3]
SPLIT = json.loads((REPO / "ci/benchmarks/spreadsheetbench/full_verified/split_ids.json").read_text())
TEST = [str(t) for t in SPLIT["test"]]
assert len(TEST) == 280, len(TEST)
SEED_DIR = Path(sb.__file__).resolve().parent / "seed_capability_v2"


def tree_sha(d: Path) -> dict:
    return {str(f.relative_to(d)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(d.rglob("*")) if f.is_file() and "__pycache__" not in f.parts}


src = Path(a.champion)
frozen = out / "champion"
if a.resume:
    # verify, never re-freeze: the bytes scored after the resume must be the bytes registered before episode 1
    reg = json.loads((out / "registry.json").read_text())
    assert (reg["arm"], reg["search_seed"], reg["k"], reg["anchor_trials"]) == (a.arm, a.search_seed, a.k, a.anchor_trials), \
        "resume arguments differ from the registered window"
    champ_sha, seed_sha = tree_sha(frozen), tree_sha(SEED_DIR)
    assert champ_sha == reg["champion_tree_sha256"], "frozen champion changed since registration"
    assert seed_sha == reg["seed_tree_sha256"], "seed capability changed since registration"
    assert hashlib.sha256((out / "order.jsonl").read_bytes()).hexdigest() == reg["order_sha256"], "order.jsonl changed"
    order = [json.loads(x) for x in (out / "order.jsonl").read_text().splitlines()]
    inert = reg["inert_champion"]
    cells = [("champion", frozen, a.k), ("seed", SEED_DIR, a.anchor_trials)]
else:
    # 1) freeze: copy the champion's agent surfaces only (optimizer bookkeeping like PROCESS.md is not part of the agent)
    frozen.mkdir()
    for rel in ("prompt.md", "task_template.md"):
        if (src / rel).exists():
            shutil.copy2(src / rel, frozen / rel)
    if (src / "skills").is_dir():
        shutil.copytree(src / "skills", frozen / "skills", ignore=shutil.ignore_patterns("__pycache__"))
    champ_sha, seed_sha = tree_sha(frozen), tree_sha(SEED_DIR)
    inert = champ_sha == {k: v for k, v in seed_sha.items() if not k.endswith(".gitkeep")} or champ_sha == seed_sha

    # 2) order: interleave champion x k and seed x anchor, fixed shuffle seed
    cells = [("champion", frozen, a.k), ("seed", SEED_DIR, a.anchor_trials)]
    order = [{"cell": c, "task_id": t, "trial": j} for c, _, k in cells for t in TEST for j in range(k)]
    random.Random(f"exp895-test-{a.arm}-s{a.search_seed}").shuffle(order)
    if a.champion_first:   # keep the registered shuffle inside each cell, champion cell first
        order = [o for o in order if o["cell"] == "champion"] + [o for o in order if o["cell"] == "seed"]
    (out / "order.jsonl").write_text("".join(json.dumps(o) + "\n" for o in order))
    order_sha = hashlib.sha256((out / "order.jsonl").read_bytes()).hexdigest()
    reg = {"arm": a.arm, "search_seed": a.search_seed, "champion_src": str(src), "champion_tree_sha256": champ_sha,
           "seed_tree_sha256": seed_sha, "inert_champion": inert, "order_sha256": order_sha, "n_episodes": len(order),
           "k": a.k, "anchor_trials": a.anchor_trials, "champion_first": bool(a.champion_first), "registered_at": time.time(),
           "analysis": "headline = mean over 280 test tasks of (champion per-task mean - same-window seed per-task mean); "
                       "CR1 SE clustered by task; t interval on 279 df. Infra-missing trials are dropped, never scored 0."}
    (out / "registry.json").write_text(json.dumps(reg, indent=1))
    print("REGISTERED", json.dumps({k: reg[k] for k in ("arm", "search_seed", "inert_champion", "order_sha256", "n_episodes")}),
          flush=True)

# 3) score
A = sb.Adapter()
tasks = {t.id: t for t in A.tasks("test")}
cdir = {c: d for c, d, _ in cells}
cidx = {c: i for i, (c, _, _) in enumerate(cells)}
lock = threading.Lock()

# Resume: an episode is FINAL if it has a non-infra row, or an infra row at attempt 3 (all 4 attempts used; it is
# missing data, exactly as an uninterrupted window would record it). Everything else re-runs from its NEXT attempt, so
# every trial seed stays unique and a re-run never repeats an attempt the dead job already made.
key = lambda o: (o["cell"], o["task_id"], o["trial"])  # noqa: E731
final, next_attempt = {}, {}
if a.resume and (out / "results.jsonl").exists():
    for x in (out / "results.jsonl").read_text().splitlines():
        try:
            r = json.loads(x)
        except ValueError:
            continue                      # a line cut off when the host died
        k = key(r)
        if r["error_kind"] != "infra" or r["attempt"] >= 3:
            final[k] = r
        next_attempt[k] = max(next_attempt.get(k, 0), r["attempt"] + 1)
    print("RESUME", json.dumps({"final": len(final), "to_run": sum(1 for o in order if key(o) not in final),
                                "partial_attempts": sum(1 for k in next_attempt if k not in final)}), flush=True)
res_f = open(out / "results.jsonl", "a", buffering=1)


def run(o):
    if key(o) in final:
        return final[key(o)]
    row = None
    for attempt in range(next_attempt.get(key(o), 0), 4):
        seed = 900_000_000 + 1000 * cidx[o["cell"]] + 100 * attempt + o["trial"]
        t0 = time.time()
        r = A.run_target(tasks[o["task_id"]], cdir[o["cell"]], seed=seed)
        s = A.score(tasks[o["task_id"]], r)
        kind = "none" if not r.error else ("candidate" if (r.metadata or {}).get("error_kind") == "candidate" else "infra")
        row = {**o, "attempt": attempt, "trial_seed": seed, "reward": s.reward, "error_kind": kind,
               "error_text": (r.error or "")[:300], "wall_s": round(time.time() - t0, 1), "t_end": time.time()}
        with lock:
            res_f.write(json.dumps(row) + "\n")
        if kind != "infra":
            return row
    return row


champion_first = bool(reg.get("champion_first"))
phases = [[o for o in order if o["cell"] == "champion"], [o for o in order if o["cell"] == "seed"]] if champion_first else [order]
rows = []
for pi, ph in enumerate(phases):
    with ThreadPoolExecutor(max_workers=sb.CONCURRENCY) as ex:
        rows += list(ex.map(run, ph))
    if champion_first and pi == 0:
        cm = {}
        for r in rows:
            if r["error_kind"] != "infra":
                cm.setdefault(r["task_id"], []).append(r["reward"])
        cm = {t: sum(v) / len(v) for t, v in cm.items()}
        co = {"arm": a.arm, "search_seed": a.search_seed, "inert_champion": inert, "phase": "champion_only (seed not yet run)",
              "champion_test_mean": sum(cm.values()) / len(cm) if cm else None, "n_tasks_with_data": len(cm),
              "missing_tasks": len(TEST) - len(cm), "infra_missing_trials": sum(1 for r in rows if r["error_kind"] == "infra"),
              "candidate_error_trials": sum(1 for r in rows if r["error_kind"] == "candidate")}
        (out / "summary_champion_only.json").write_text(json.dumps(co, indent=1))
        print("CHAMPION_PHASE_DONE", json.dumps(co), flush=True)

# 4) summary (registered analysis)
per = {c: {} for c, _, _ in cells}
for r in rows:
    if r["error_kind"] != "infra":
        per[r["cell"]].setdefault(r["task_id"], []).append(r["reward"])
mean = {c: {t: sum(v) / len(v) for t, v in d.items()} for c, d in per.items()}
both = [t for t in TEST if t in mean["champion"] and t in mean["seed"]]
d = [mean["champion"][t] - mean["seed"][t] for t in both]
n = len(d)
dbar = sum(d) / n if n else float("nan")
se = math.sqrt(sum((x - dbar) ** 2 for x in d) / (n - 1) / n) if n > 1 else float("nan")
summ = {"arm": a.arm, "search_seed": a.search_seed, "inert_champion": inert,
        "champion_test_mean": sum(mean["champion"].values()) / len(mean["champion"]) if mean["champion"] else None,
        "seed_test_mean": sum(mean["seed"].values()) / len(mean["seed"]) if mean["seed"] else None,
        "paired_delta": dbar, "paired_se_cr1": se, "ci95": [dbar - 1.968 * se, dbar + 1.968 * se], "n_tasks_paired": n,
        "missing_tasks": {c: len(TEST) - len(mean[c]) for c in mean},
        "infra_missing_trials": sum(1 for r in rows if r["error_kind"] == "infra"),
        "candidate_error_trials": sum(1 for r in rows if r["error_kind"] == "candidate")}
(out / "summary.json").write_text(json.dumps(summ, indent=1))
print("TEST_WINDOW_DONE", json.dumps(summ), flush=True)
