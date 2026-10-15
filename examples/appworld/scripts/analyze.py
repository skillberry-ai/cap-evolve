"""Analysis + results draft for the final window (README: Final window).

    python analyze.py      # reads runs/final/results.jsonl, writes runs/final/results.json and RESULTS.md

TGC = mean over tasks of the mean over trials of success; SGC = a scenario passes in trial k iff
all its tasks pass in trial k, averaged over k and scenarios. Paired differences use a
scenario-clustered paired bootstrap (56 clusters, 10,000 resamples), 95% percentile CI, no
multiplicity correction. A cell that is still infra-errored is scored 0 (primary) and dropped in
the sensitivity analysis. Only rewards and counters are read; no test trajectory is opened.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awpaths import CAPE_RUN, MANIFEST, ROOT_FULL, RUNS, read_split  # noqa: E402

FINAL = RUNS / "final"
ARMS = ("seed", "cape-hc", "altk")
TRIALS = 2
DIFF = {1: "Easy", 2: "Medium", 3: "Hard"}
B = 10000
PAIRS = (("cape-hc", "seed"), ("altk", "seed"), ("cape-hc", "altk"))
COLLEAGUES = {"no memory": (39.9, 21.4), "ALTK-Evolve": (56.0, 37.5)}


def load_cells(ids: list[str]) -> tuple[dict, dict]:
    """(arm, task, trial) -> record; the last non-error attempt wins, else the last error."""
    cells: dict = {}
    for line in (FINAL / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        key = (r["arm"], r["task_id"], r["trial"])
        if key not in cells or cells[key].get("infra_error") or not r.get("infra_error"):
            cells[key] = r
    missing = {k: v for k, v in cells.items() if v.get("infra_error")}
    for arm in ARMS:
        for t in ids:
            for k in range(TRIALS):
                if (arm, t, k) not in cells:
                    missing[(arm, t, k)] = {"infra_error": "never ran"}
    return cells, missing


def succ(cells, arm, t, k, drop_missing=False):
    r = cells.get((arm, t, k))
    if r is None or r.get("infra_error"):
        return None if drop_missing else 0.0
    return 1.0 if r.get("success") else 0.0


def tgc(cells, arm, tasks, drop_missing=False):
    per = []
    for t in tasks:
        v = [x for k in range(TRIALS) if (x := succ(cells, arm, t, k, drop_missing)) is not None]
        if v:
            per.append(sum(v) / len(v))
    return sum(per) / len(per) if per else float("nan")


def sgc(cells, arm, scen_tasks: dict, drop_missing=False):
    vals = []
    for k in range(TRIALS):
        for s, ts in scen_tasks.items():
            v = [succ(cells, arm, t, k, drop_missing) for t in ts]
            if drop_missing and any(x is None for x in v):
                continue
            vals.append(1.0 if all(x == 1.0 for x in v) else 0.0)
    return sum(vals) / len(vals) if vals else float("nan")


def bootstrap(cells, a, b, scen_tasks, rng):
    scens = sorted(scen_tasks)
    d_t, d_s = [], []
    for _ in range(B):
        pick = [rng.choice(scens) for _ in scens]
        tasks = [t for s in pick for t in scen_tasks[s]]
        st = {f"{s}#{i}": scen_tasks[s] for i, s in enumerate(pick)}
        d_t.append(tgc(cells, a, tasks) - tgc(cells, b, tasks))
        d_s.append(sgc(cells, a, st) - sgc(cells, b, st))

    def ci(xs):
        xs = sorted(xs)
        return [xs[int(0.025 * B)], xs[int(0.975 * B) - 1]]
    return ci(d_t), ci(d_s)


def pct(x):
    return f"{100 * x:.1f}"


def optimizer_usage() -> dict:
    out = {}
    st = CAPE_RUN / "state.json"
    if st.is_file():
        sp = json.loads(st.read_text()).get("spent", {})
        out["cape-hc"] = {"usd": sp.get("optimizer_usd"), "tokens": sp.get("optimizer_tokens"),
                          "iterations": sp.get("iterations"), "metric_calls": sp.get("metric_calls"),
                          "best_val": sp.get("best_val")}
    u = RUNS / "altk/optimizer_usage.jsonl"
    if u.is_file():
        rows = [json.loads(l) for l in u.read_text().splitlines()]
        out["altk"] = {"calls": len(rows), "errors": sum(bool(r.get("error")) for r in rows),
                       "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in rows),
                       "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in rows)}
    return out


def main() -> int:
    ids = read_split("test_normal")
    diff = {t: json.loads((ROOT_FULL / "data/tasks" / t / "ground_truth/metadata.json").read_text())["difficulty"]
            for t in ids}
    scen: dict = defaultdict(list)
    for t in ids:
        scen[t.split("_")[0]].append(t)
    cells, missing = load_cells(ids)
    rng = random.Random(0)
    res: dict = {"n_tasks": len(ids), "n_scenarios": len(scen), "trials": TRIALS, "arms": {}, "pairs": {},
                 "missing_cells": {f"{a}|{t}|{k}": v.get("infra_error") for (a, t, k), v in missing.items()}}
    for arm in ARMS:
        recs = [r for (a, _, _), r in cells.items() if a == arm and not r.get("infra_error")]
        by_d = {}
        for d, name in DIFF.items():
            ts = [t for t in ids if diff[t] == d]
            by_d[name] = {"n": len(ts), "tgc": tgc(cells, arm, ts)}
        def mean(key):
            v = [float(r.get(key) or 0) for r in recs]
            return statistics.mean(v) if v else float("nan")
        res["arms"][arm] = {
            "tgc": tgc(cells, arm, ids), "sgc": sgc(cells, arm, scen),
            "tgc_drop_missing": tgc(cells, arm, ids, True), "sgc_drop_missing": sgc(cells, arm, scen, True),
            "by_difficulty": by_d,
            "episodes": len(recs), "missing": sum(1 for (a, _, _) in missing if a == arm),
            "prompt_tokens_per_task": mean("prompt_tokens"), "completion_tokens_per_task": mean("completion_tokens"),
            "steps_per_task": mean("n_steps"),
            "step_cap_hits": sum(1 for r in recs if r.get("termination") == "max_steps"),
            "context_exceeded": sum(1 for r in recs if r.get("termination") == "context_exceeded"),
            "token_cap_hits": sum(1 for r in recs if r.get("termination") == "token_cap"),
            "complete_task_not_called": sum(1 for r in recs if not r.get("complete_task_called")),
            "collateral_damage": sum(1 for r in recs if r.get("collateral_damage")),
            "fs_probe": sum(1 for r in recs if r.get("fs_probe")),
            "max_prompt_tokens": max((int(r.get("max_prompt_tokens") or 0) for r in recs), default=0),
        }
    for a, b in PAIRS:
        ci_t, ci_s = bootstrap(cells, a, b, scen, rng)
        res["pairs"][f"{a} - {b}"] = {"d_tgc": res["arms"][a]["tgc"] - res["arms"][b]["tgc"], "ci_tgc": ci_t,
                                      "d_sgc": res["arms"][a]["sgc"] - res["arms"][b]["sgc"], "ci_sgc": ci_s}
    res["optimizer_usage"] = optimizer_usage()
    sel = RUNS / "altk/dose_selection.json"
    res["altk_dose_selection"] = json.loads(sel.read_text()) if sel.is_file() else None
    ms = RUNS / "altk/mining_summary.json"
    res["altk_mining"] = json.loads(ms.read_text()) if ms.is_file() else None
    res["manifest"] = {k: v for k, v in json.loads(MANIFEST.read_text()).items() if not k.endswith("freeze")}
    (FINAL / "results.json").write_text(json.dumps(res, indent=1))

    L = ["| arm | TGC | SGC | Δ TGC vs seed [95% CI] | Δ SGC vs seed [95% CI] | missing cells |", "|---|---|---|---|---|---|"]
    for arm in ARMS:
        r = res["arms"][arm]
        p = res["pairs"].get(f"{arm} - seed")
        dt = f"{pct(p['d_tgc'])} [{pct(p['ci_tgc'][0])}, {pct(p['ci_tgc'][1])}]" if p else "—"
        ds = f"{pct(p['d_sgc'])} [{pct(p['ci_sgc'][0])}, {pct(p['ci_sgc'][1])}]" if p else "—"
        L.append(f"| {arm} | {pct(r['tgc'])} | {pct(r['sgc'])} | {dt} | {ds} | {r['missing']} |")
    p = res["pairs"]["cape-hc - altk"]
    L += ["", f"cape-hc − altk: Δ TGC {pct(p['d_tgc'])} [{pct(p['ci_tgc'][0])}, {pct(p['ci_tgc'][1])}], "
              f"Δ SGC {pct(p['d_sgc'])} [{pct(p['ci_sgc'][0])}, {pct(p['ci_sgc'][1])}]."]
    D = ["| arm | " + " | ".join(f"{n} (n={res['arms']['seed']['by_difficulty'][n]['n']})" for n in DIFF.values()) + " |",
         "|---|---|---|---|"]
    for arm in ARMS:
        D.append(f"| {arm} | " + " | ".join(pct(res["arms"][arm]["by_difficulty"][n]["tgc"]) for n in DIFF.values()) + " |")
    C = ["| arm | prompt tok/task | completion tok/task | steps/task | step-cap hits | context exceeded | "
         "complete_task not called | collateral damage | max prompt tok |", "|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        r = res["arms"][arm]
        C.append(f"| {arm} | {r['prompt_tokens_per_task']:,.0f} | {r['completion_tokens_per_task']:,.0f} | "
                 f"{r['steps_per_task']:.1f} | {r['step_cap_hits']} | {r['context_exceeded']} | "
                 f"{r['complete_task_not_called']} | {r['collateral_damage']} | {r['max_prompt_tokens']:,} |")
    (FINAL / "tables.md").write_text("## Main\n\n" + "\n".join(L) + "\n\n## By difficulty (TGC)\n\n" + "\n".join(D)
                                     + "\n\n## Target cost per episode (final window)\n\n" + "\n".join(C) + "\n")
    print((FINAL / "tables.md").read_text())
    print(json.dumps(res["optimizer_usage"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
