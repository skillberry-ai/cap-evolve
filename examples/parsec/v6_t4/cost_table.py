#!/usr/bin/env python3
"""Table 2: what each arm cost, from the per-trial records.

Table 2a, cost to BUILD the deployable bundle (no test, no post-hoc measurement):
  T-opt          its 34 searches: candidate evaluations + optimizer (the reused Seed trials excluded)
  T-mrg          T-opt + the merge (scripts: 10 s, no LLM; smart merge: the LLM merger)
  Global         its search: train screens and incumbent sweeps + validation gates + optimizer
Table 2b, cost to MEASURE a frozen bundle, at the same 5 trials per task for every arm:
  test (66 tasks)  T-mrg: its 5 trials; Global: its first 5 of 10 test trials (t0-t4)
  train (67 tasks) T-mrg only (Global's train numbers come from its search sweeps)

Columns: eval = target agent; optim = optimizer agent (+ the smart merge's LLM merger).
Dollars and tokens are the trial records' own cost_usd/tokens, and state.json for the optimizer.
Time is each trial's agent run time (rollout parsec_usage_window end - start) plus each optimizer
call's duration, summed: compute, not wall clock.
Not counted anywhere: the shared Seed measurements, and the T-mrg eval projects' own finalize step,
which re-scored some tasks a second time (unused; reported separately as harness overhead).
"""
import datetime as dt, glob, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GW = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/parsec-intake_v6")
G, GS = GW / ".capevolve/v6_g2_e1/run_g2_e1", GW / ".capevolve.sealed/run_g2_e1"
SPLITS = json.loads((G / "splits.json").read_text())
TRAIN, TEST = set(SPLITS["feedback"]), set(SPLITS["test"])
SEED = ("__seed__t", "__FINAL_seed__", "__final__seed__")


def trials(files):
    usd = tok = sec = n = 0
    for f in files:
        r = json.loads(Path(f).read_text()).get("rollout") or {}
        w = (r.get("metadata") or {}).get("parsec_usage_window") or {}
        usd += r.get("cost_usd") or 0
        tok += r.get("tokens") or 0
        if w.get("start") and w.get("end"):
            sec += (dt.datetime.fromisoformat(w["end"]) - dt.datetime.fromisoformat(w["start"])).total_seconds()
        n += 1
    return {"usd": usd, "tokens": tok, "hours": sec / 3600, "trials": n}


def row(ev, ou=0.0, ot=0, oh=0.0):
    return {"eval_usd": ev["usd"], "opt_usd": ou, "total_usd": ev["usd"] + ou,
            "eval_tokens": ev["tokens"], "opt_tokens": ot, "total_tokens": ev["tokens"] + ot,
            "eval_hours": ev["hours"], "opt_hours": oh, "total_hours": ev["hours"] + oh, "eval_trials": ev["trials"]}


task_of = lambda f: Path(f).name.split("__")[0]  # noqa: E731
g_feed = [f for f in glob.glob(f"{G}/rollouts/feedback/*.json") if not any(s in f for s in SEED)]
g_conf = [f for f in glob.glob(f"{GS}/rollouts/confirm/*.json") if not any(s in f for s in SEED)]
g_gates = [f for f in g_conf if "__final__champion__" not in f]
g_remeasure = [f for f in g_conf if "__final__champion__" in f]
g_test = glob.glob(f"{G}/rollouts/test/*__FINAL__t*.json")
g_test5 = [f for f in g_test if int(re.search(r"__t(\d+)\.json$", f).group(1)) < 5]
gst = json.loads((G / "state.json").read_text())["spent"]

t = {"optimizer_usd": 0, "optimizer_tokens": 0, "optimizer_seconds": 0}
for st in glob.glob(str(ROOT / ".capevolve/v6_t2_e1_*/run_*/state.json")):
    sp = json.loads(Path(st).read_text())["spent"]
    for k in t:
        t[k] += sp.get(k) or 0
t_cands = [f for f in glob.glob(str(ROOT / ".capevolve/v6_t2_e1_*/run_*/rollouts/*/*.json")) if "__seed__" not in f]
topt = row(trials(t_cands), t["optimizer_usd"], t["optimizer_tokens"], t["optimizer_seconds"] / 3600)

mc = json.loads((ROOT / "results/v6_t4_e1/merge_cost.json").read_text())["methods"]
merge = {"m1": (0.0, 0, mc["m1_order"]["wall_seconds"]), "m2": (0.0, 0, mc["m2_nonconflict"]["wall_seconds"]),
         "m3": (mc["m3_smart"]["usd_estimate"], mc["m3_smart"]["tokens"]["total"], mc["m3_smart"]["wall_seconds"])}
names = {"m1": "T-mrg · merge by order", "m3": "T-mrg · smart merge", "m2": "T-mrg · non-conflicting hunks"}

build = {"T-opt": topt}
measure, overhead = {}, {}
for m in ("m1", "m3", "m2"):
    u, k, s = merge[m]
    build[names[m]] = {**topt, "opt_usd": topt["opt_usd"] + u, "total_usd": topt["total_usd"] + u,
                       "opt_tokens": topt["opt_tokens"] + k, "total_tokens": topt["total_tokens"] + k,
                       "opt_hours": topt["opt_hours"] + s / 3600, "total_hours": topt["total_hours"] + s / 3600,
                       "merge": {"usd": u, "tokens": k, "seconds": s}}
    files = [f for sfx in ("", "x") for f in glob.glob(str(ROOT / f".capevolve/v5_v6t4_{m}{sfx}_*/run_*/rollouts/*/*.json"))]
    designed = [f for f in files if "__seed__t" in Path(f).name]   # the eval projects tag the frozen bundle "seed"
    measure[names[m]] = {"test": trials([f for f in designed if task_of(f) in TEST]),
                         "train": trials([f for f in designed if task_of(f) in TRAIN])}
    overhead[names[m]] = trials([f for f in files if "__FINAL__" in Path(f).name])
build["Global"] = row({k: a + b for (k, a), b in zip(trials(g_feed).items(), trials(g_gates).values())},
                      gst["optimizer_usd"], gst["optimizer_tokens"], gst["optimizer_seconds"] / 3600)
measure["Global"] = {"test": trials(g_test5), "test_10_trials": trials(g_test),
                     "validation_remeasure_cand_0002": trials(g_remeasure)}
build["Global"]["eval_parts"] = {"train screens + incumbent sweeps": trials(g_feed), "validation gates": trials(g_gates)}

out = {"build": build, "measure_5_trials": measure, "harness_overhead_unused": overhead, "definitions": __doc__}
(ROOT / "results/v6_t4_e1/cost_table.json").write_text(json.dumps(out, indent=1))
print("2a BUILD")
for k, r in build.items():
    print(f"  {k:32s} ${r['eval_usd']:7.2f} ${r['opt_usd']:7.2f} ${r['total_usd']:7.2f} | {r['eval_tokens']/1e6:6.1f}M "
          f"{r['opt_tokens']/1e6:6.1f}M {r['total_tokens']/1e6:6.1f}M | {r['eval_hours']:6.1f}h {r['opt_hours']:5.1f}h "
          f"{r['total_hours']:6.1f}h | trials {r['eval_trials']}")
print("2b MEASURE (5 trials/task)")
for k, d in measure.items():
    for sp, v in d.items():
        print(f"  {k:32s} {sp:32s} ${v['usd']:7.2f} {v['tokens']/1e6:6.1f}M {v['hours']:6.1f}h trials {v['trials']}")
print("harness overhead (unused finalize re-scores)")
for k, v in overhead.items():
    print(f"  {k:32s} ${v['usd']:6.2f} {v['tokens']/1e6:5.1f}M {v['hours']:5.1f}h trials {v['trials']}")
