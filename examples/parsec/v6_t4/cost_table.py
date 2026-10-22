#!/usr/bin/env python3
"""Table 2: cost, tokens and time per arm (Seed, T-opt, T-mrg x3 cumulative over T-opt, Global).

Every number is read from the run records:
  eval $ / tokens   G: events.jsonl `evaluate` records; T-opt: per-task state.json `spent`;
                    T-mrg: per-task baseline.json via collect_evals (3 + 2 trial suites)
  opt $ / tokens    G, T-opt: state.json optimizer_usd / optimizer_tokens; merge: merge_cost.json
  eval time         agent time summed over every trial (rollout parsec_usage_window end - start),
                    the same definition for every arm; compute, not wall clock
  opt time          optimizer_seconds summed over optimizer calls; merge: merge_cost.json wall
Seed = the three Seed reference measurements made in the G run (train 10 trials, validation 4,
test 10). They are shared by every arm and are not charged to G.
"""
import datetime as dt, glob, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GW = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/parsec-intake_v6")
G, GS = GW / ".capevolve/v6_g2_e1/run_g2_e1", GW / ".capevolve.sealed/run_g2_e1"
SEED_TAGS = {("feedback", "seed"), ("test", "FINAL_seed"), ("confirm", "final__seed")}


def trial_secs(files):
    s = 0.0
    for f in files:
        w = ((json.loads(Path(f).read_text()).get("rollout") or {}).get("metadata") or {}).get("parsec_usage_window") or {}
        if w.get("start") and w.get("end"):
            s += (dt.datetime.fromisoformat(w["end"]) - dt.datetime.fromisoformat(w["start"])).total_seconds()
    return s


def row(eu, et, es, ou=0.0, ot=0, os_=0.0):
    return {"eval_usd": eu, "opt_usd": ou, "total_usd": eu + ou, "eval_tokens": et, "opt_tokens": ot,
            "total_tokens": et + ot, "eval_hours": es / 3600, "opt_hours": os_ / 3600, "total_hours": (es + os_) / 3600}


def add(a, b):
    return {k: a[k] + b[k] for k in a}


ev = [e for e in map(json.loads, open(G / "events.jsonl")) if e["kind"] == "evaluate"]
seed_ev = [e for e in ev if (e["split"], e["tag"]) in SEED_TAGS]
g_ev = [e for e in ev if (e["split"], e["tag"]) not in SEED_TAGS]
g_files = glob.glob(f"{G}/rollouts/*/*.json") + glob.glob(f"{GS}/rollouts/confirm/*.json")
is_seed = lambda f: any(p in f for p in ("__seed__t", "__FINAL_seed__", "__final__seed__"))  # noqa: E731
gst = json.loads((G / "state.json").read_text())["spent"]

rows = {}
rows["Seed"] = row(sum(e["cost_usd"] for e in seed_ev), sum(e["tokens"] for e in seed_ev),
                   trial_secs([f for f in g_files if is_seed(f)]))
rows["Global"] = row(sum(e["cost_usd"] for e in g_ev), sum(e["tokens"] for e in g_ev),
                     trial_secs([f for f in g_files if not is_seed(f)]),
                     gst["optimizer_usd"], gst["optimizer_tokens"], gst["optimizer_seconds"])

t = {"usd": 0, "optimizer_usd": 0, "runner_tokens": 0, "optimizer_tokens": 0, "optimizer_seconds": 0}
for st in glob.glob(str(ROOT / ".capevolve/v6_t2_e1_*/run_*/state.json")):
    sp = json.loads(Path(st).read_text())["spent"]
    for k in t:
        t[k] += sp.get(k) or 0
rows["T-opt"] = row(t["usd"], t["runner_tokens"], trial_secs(glob.glob(str(ROOT / ".capevolve/v6_t2_e1_*/run_*/rollouts/*/*.json"))),
                    t["optimizer_usd"], t["optimizer_tokens"], t["optimizer_seconds"])

mc = json.loads((ROOT / "results/v6_t4_e1/merge_cost.json").read_text())["methods"]
merge = {"m1": (0.0, 0, mc["m1_order"]["wall_seconds"]), "m2": (0.0, 0, mc["m2_nonconflict"]["wall_seconds"]),
         "m3": (mc["m3_smart"]["usd_estimate"], mc["m3_smart"]["tokens"]["total"], mc["m3_smart"]["wall_seconds"])}
names = {"m1": "T-mrg · merge by order", "m3": "T-mrg · smart merge", "m2": "T-mrg · non-conflicting hunks"}
increments = {}
for m in ("m1", "m3", "m2"):
    c = json.loads((ROOT / f"results/v6_t4_e1/eval/v6t4_{m}_5t.json").read_text())["cost"]
    files = [f for s in (m, m + "x") for f in glob.glob(str(ROOT / f".capevolve/v5_v6t4_{s}_*/run_*/rollouts/*/*.json"))]
    inc = row(c["eval_usd"], c["eval_tokens"], trial_secs(files), *merge[m])
    increments[names[m]] = inc
    rows[names[m]] = add(rows["T-opt"], inc)

out = {"rows": rows, "t_mrg_increment_over_t_opt": increments, "definitions": __doc__}
(ROOT / "results/v6_t4_e1/cost_table.json").write_text(json.dumps(out, indent=1))
for k, r in rows.items():
    print(f"{k:32s} ${r['eval_usd']:7.2f} ${r['opt_usd']:7.2f} ${r['total_usd']:8.2f} | "
          f"{r['eval_tokens']/1e6:6.1f}M {r['opt_tokens']/1e6:6.1f}M {r['total_tokens']/1e6:6.1f}M | "
          f"{r['eval_hours']:6.1f}h {r['opt_hours']:5.1f}h {r['total_hours']:6.1f}h")
print("increments:")
for k, r in increments.items():
    print(f"{k:32s} ${r['eval_usd']:7.2f} ${r['opt_usd']:7.2f} | {r['eval_tokens']/1e6:6.1f}M {r['opt_tokens']/1e6:6.1f}M | {r['eval_hours']:6.1f}h {r['opt_hours']*3600:7.0f}s")
