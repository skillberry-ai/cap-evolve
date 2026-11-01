#!/usr/bin/env python3
"""Serving usage on the sealed test split: what one trial of each deployable bundle costs.

For every arm, each test task's valid trials are averaged (cost_usd, tokens, agent seconds from
the rollout's parsec_usage_window), then:
  per trial  = mean over the 66 tasks of those per-task means
  per sweep  = sum over the 66 tasks (one trial of every test task)
Errored trials are excluded (their recorded cost is 0). T-opt has no row: its 34 bundles are
not deployable and were never run on test.
Sources: Global and Seed, the v6_g2_e1 sealed test (tags FINAL, FINAL_seed; 10 trials/task);
T-mrg, the 5-trial evaluations (seeds 0-4; eval projects tag the frozen bundle "seed").
"""
import collections, datetime as dt, glob, json, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
G = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/"
         "parsec-intake_v6/.capevolve/v6_g2_e1/run_g2_e1")
TEST = set(json.loads((G / "splits.json").read_text())["test"])


def usage(files):
    per = collections.defaultdict(list)
    for f in files:
        task = Path(f).name.split("__")[0]
        if task not in TEST:
            continue
        r = json.loads(Path(f).read_text()).get("rollout") or {}
        w = (r.get("metadata") or {}).get("parsec_usage_window") or {}
        if r.get("error") or not (w.get("start") and w.get("end")):
            continue
        s = (dt.datetime.fromisoformat(w["end"]) - dt.datetime.fromisoformat(w["start"])).total_seconds()
        per[task].append((r.get("cost_usd") or 0, r.get("tokens") or 0, s))
    m = {t: [st.fmean(x[i] for x in v) for i in range(3)] for t, v in per.items()}
    all_s = [x[2] for v in per.values() for x in v]
    return {"tasks": len(m), "trials": sum(map(len, per.values())),
            "per_trial": {"usd": st.fmean(v[0] for v in m.values()), "tokens": st.fmean(v[1] for v in m.values()),
                          "seconds": st.fmean(v[2] for v in m.values()), "median_seconds": st.median(all_s)},
            "per_sweep": {"usd": sum(v[0] for v in m.values()), "tokens": sum(v[1] for v in m.values()),
                          "hours": sum(v[2] for v in m.values()) / 3600}}


mrg = lambda m: [f for s in (m, m + "x") for f in glob.glob(str(ROOT / f".capevolve/v5_v6t4_{s}_*/run_*/rollouts/*/*__seed__t*.json"))]  # noqa: E731
rows = {"Seed": usage(glob.glob(f"{G}/rollouts/test/*__FINAL_seed__t*.json")),
        "T-mrg · merge by order": usage(mrg("m1")),
        "T-mrg · smart merge": usage(mrg("m3")),
        "T-mrg · non-conflicting hunks": usage(mrg("m2")),
        "Global": usage(glob.glob(f"{G}/rollouts/test/*__FINAL__t*.json"))}
(ROOT / "results/v6_t4_e1/test_usage.json").write_text(json.dumps({"rows": rows, "definitions": __doc__}, indent=1))
for k, r in rows.items():
    p, s = r["per_trial"], r["per_sweep"]
    print(f"{k:31s} tasks {r['tasks']} trials {r['trials']:4d} | per trial ${p['usd']:.3f} {p['tokens']/1e3:5.1f}k "
          f"{p['seconds']:5.0f}s (median {p['median_seconds']:4.0f}s) | per sweep ${s['usd']:6.2f} {s['tokens']/1e6:5.2f}M {s['hours']:5.2f}h")
