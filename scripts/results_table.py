#!/usr/bin/env python3
"""Per-seed train / val / test table for exp895 (login-node safe: reads small files only).
Test = paired same-window delta from runs/test/<arm>_s<seed>/summary.json (n>=250 tasks). Train/val = seed vs champion on the
search ledger (same candidates, infra rows dropped), restricted to tasks both candidates have. Writes runs/.watch/full_table.json."""
import collections, glob, json, os, sys
EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(EXP)
S = json.load(open("../sbv400-main/ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"))
TR = {str(x) for x in S["train"]}; VA = {str(x) for x in S["val"]}
def j(p):
    try: return json.load(open(p))
    except Exception: return None
def per_task(rows):
    d = collections.defaultdict(list)
    for r in rows:
        if r["error_kind"] != "infra": d[str(r["task_id"])].append(r["reward"])
    return {t: sum(v) / len(v) for t, v in d.items()}
def cmp(a, b, ids):
    t = [x for x in ids if x in a and x in b]
    return (sum(a[x] for x in t) / len(t), sum(b[x] for x in t) / len(t), len(t)) if t else None
def ledger(arm, s):
    p = f"runs/{arm}/search_s{s}/rollouts.jsonl"
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []
def by_cand(rows, cid): return per_task([r for r in rows if r["candidate_id"] == cid])
def ledger_arm(arm, s, sv, cv, st, ct):
    rows = ledger(arm, s)
    return cmp(by_cand(rows, sv), by_cand(rows, cv), VA), cmp(by_cand(rows, st), by_cand(rows, ct), TR)
ARMS = ("skillopt", "trace2skill", "meta_harness", "evoskill", "gepa", "gepa_full", "miprov2", "wikiskill", "ace", "capevolve", "capevolve_v2")
res = {}
for arm in ARMS:
    for s in (0, 1, 2):
        x = j(f"runs/test/{arm}_s{s}/summary.json")
        if not (x and (x.get("n_tasks_paired") or 0) >= 250 and x["paired_delta"] == x["paired_delta"]): continue
        run = f"runs/{arm}/search_s{s}"
        try:
            if arm in ("capevolve", "capevolve_v2"):
                R = run + "/work/.capevolve/run_main"; ch = j(R + "/champion.json")["champion"]
                pt = collections.defaultdict(lambda: collections.defaultdict(list))
                for f in glob.glob(R + "/rollouts/val/*.json"):
                    cid = os.path.basename(f).split("__")[1]
                    if cid not in ("seed", ch): continue
                    sc = json.load(open(f))["score"]
                    if (sc.get("feedback") or "").startswith("Rollout failed") or (sc.get("raw") or {}).get("errored"): continue
                    pt[cid][str(sc["task_id"])].append(sc["reward"])
                m = lambda c: {t: sum(v) / len(v) for t, v in pt[c].items()}
                v, t = cmp(m("seed"), m(ch), VA), cmp(m("seed"), m(ch), TR)
            elif arm == "skillopt":
                sm = j(run + "/run_summary.json"); h = sm["champion"]["skill_hash"]; rows = ledger(arm, s)
                base = sorted({r["candidate_id"].split(":")[1] for r in rows if r["candidate_id"].startswith("sel_baseline:")})[0]
                v, t = ledger_arm(arm, s, "sel_baseline:" + base, "sel:" + h, "train:" + base, "train:" + h)
            elif arm == "trace2skill":
                ch = j(run + "/run_summary.json")["champion"]; ch = ch if ch else "seed"
                cv, ct = ("seed@val", "seed@train") if ch == "seed" else (ch + "@val", ch + "@train")
                v, t = ledger_arm(arm, s, "seed@val", cv, "seed@train", ct)
            elif arm == "meta_harness":
                ch = j(run + "/run_summary.json")["champion"]; v, t = ledger_arm(arm, s, "seed", ch, "seed", ch)
            elif arm == "evoskill":
                ch = j(run + "/run_summary.json")["champion_candidate"]; v, t = ledger_arm(arm, s, "seed", ch, "seed", ch)
            elif arm in ("gepa", "miprov2", "wikiskill"):
                ch = str(j(run + "/run_summary.json")["champion"]); v, t = ledger_arm(arm, s, "seed", ch, "seed", ch)
            elif arm in ("gepa_full", "ace"):
                ch = str(j(run + "/run_summary.json")["champion"]); rows = ledger(arm, s)
                first = {}
                for r in rows: first.setdefault(r["candidate_id"], r["t_start"])
                seedc = "seed" if "seed" in first else min(first, key=first.get)
                ch = seedc if ch == "seed" else ch
                v, t = ledger_arm(arm, s, seedc, ch, seedc, ch)
            else: v = t = None
        except Exception as e:
            v = t = None; print("ERR", arm, s, repr(e)[:120], file=sys.stderr)
        res[(arm, s)] = (v, t, x)
json.dump({f"{a}|{s}": [v, t, {k: x[k] for k in ("seed_test_mean", "champion_test_mean", "paired_delta", "paired_se_cr1", "ci95", "n_tasks_paired", "inert_champion")}]
           for (a, s), (v, t, x) in res.items()}, open("runs/.watch/full_table.json", "w"), indent=1)
f = lambda z: "n/a" if not z else f"{z[0]:.3f}->{z[1]:.3f} ({z[1]-z[0]:+.3f}, n={z[2]})"
for (a, s), (v, t, x) in sorted(res.items()):
    print(f"{a:13} s{s} | TRAIN {f(t):30} | VAL {f(v):30} | TEST {x['seed_test_mean']:.3f}->{x['champion_test_mean']:.3f} ({x['paired_delta']:+.3f}) n={x['n_tasks_paired']}")
print(len(res), "finished seeds")
