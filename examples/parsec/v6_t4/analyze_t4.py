import json, statistics as st, collections, sys
from pathlib import Path
sys.path.insert(0, "examples/parsec/v5"); import collect as v5c
G = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/parsec-intake_v6/.capevolve/v6_g2_e1/run_g2_e1")
splits = json.loads((G/"splits.json").read_text())
def g_scores(split, pred):
    d = collections.defaultdict(list)
    for f in (G/"rollouts"/split).glob("*.json"):
        parts = f.name.split("__")
        if not pred(parts): continue
        rec = json.loads(f.read_text())
        if (rec.get("rollout") or {}).get("error"): continue
        d[parts[0]].append(float(rec["score"]["reward"]))
    return d
seedF = g_scores("feedback", lambda p: p[1]=="seed")
g5F = g_scores("feedback", lambda p: len(p)>2 and p[2]=="cand_0005")
seedT = g_scores("test", lambda p: p[1]=="FINAL_seed")
gT = g_scores("test", lambda p: p[1]=="FINAL")
def merged(base):
    d = collections.defaultdict(list)
    for s in (base, base+"x"):
        for td in Path(f"results/v5_{s}").iterdir():
            b = td/"run"/"baseline.json"
            if not b.is_file(): continue
            r = v5c.read_task_result(b, td.name)
            if r: d[td.name].extend(float(x) for x in (r.get("trial_rewards") or []))
    return d
arms = {"G": (g5F, gT)}
for m in ("m1","m3","m2"):
    d = merged(f"v6t4_{m}")
    arms[m] = ({t:v for t,v in d.items() if t in splits["feedback"]}, {t:v for t,v in d.items() if t in splits["test"]})
t2 = json.loads(Path("results/v6_t2_e1/report/results.json").read_text())
opt = {r["task"] for r in t2["tasks"] if r["class"]=="optimized"}
cls = {r["task"]: r["class"] for r in t2["tasks"]}
out = {}
def summ(arm, sd, seed, tasks):
    d = [st.fmean(arm[t]) - st.fmean(seed[t]) for t in tasks if arm.get(t) and seed.get(t)]
    n = len(d)
    return dict(n=n, delta=st.fmean(d), se=st.stdev(d)/n**.5 if n>1 else None,
                up=sum(x>0.1 for x in d), down=sum(x<-0.1 for x in d))
for a,(F,T) in arms.items():
    out[a] = {"F": summ(F,None,seedF,splits["feedback"]),
              "F_opt34": summ(F,None,seedF,sorted(opt)),
              "F_other33": summ(F,None,seedF,[t for t in splits["feedback"] if t not in opt]),
              "test": summ(T,None,seedT,splits["test"]),
              "F_trials": collections.Counter(len(v) for v in F.values()),
              "T_trials": collections.Counter(len(v) for v in T.values())}
    out[a]["F_trials"]=dict(out[a]["F_trials"]); out[a]["T_trials"]=dict(out[a]["T_trials"])
# pairwise on test: m vs G
for m in ("m1","m3","m2"):
    for sp,idx,seed in (("F",0,seedF),("test",1,seedT)):
        A, B = arms[m][idx], arms["G"][idx]
        d = [st.fmean(A[t])-st.fmean(B[t]) for t in A if A[t] and B.get(t)]
        out[m][f"{sp}_vs_G"] = dict(n=len(d), delta=st.fmean(d), se=st.stdev(d)/len(d)**.5)
# m1 vs m3
for sp,idx in (("F",0),("test",1)):
    A,B = arms["m1"][idx], arms["m3"][idx]
    d=[st.fmean(A[t])-st.fmean(B[t]) for t in A if A[t] and B.get(t)]
    out[f"m1_vs_m3_{sp}"]=dict(n=len(d),delta=st.fmean(d),se=st.stdev(d)/len(d)**.5)
# per-task test regressions and gains for each arm
for a in arms:
    T = arms[a][1]
    rows = sorted(((st.fmean(T[t])-st.fmean(seedT[t]), t) for t in T if T[t] and seedT.get(t)))
    out[a]["test_worst"] = [(t, round(x,3)) for x,t in rows[:5]]
    out[a]["test_best"] = [(t, round(x,3)) for x,t in rows[-5:]]
# short-trial tasks
for m in ("m1","m3","m2"):
    out[m]["short"] = {sp: sorted((t,len(v)) for t,v in arms[m][i].items() if len(v)<5) for i,sp in ((0,"F"),(1,"test"))}
# split-half check for 3t vs 2t consistency: mean delta of first 3 trials vs last 2
for m in ("m1","m3","m2"):
    for sp,idx,seed in (("F",0,seedF),("test",1,seedT)):
        A=arms[m][idx]
        a3=[st.fmean(v[:3])-st.fmean(seed[t]) for t,v in A.items() if len(v)>=5]
        a2=[st.fmean(v[3:5])-st.fmean(seed[t]) for t,v in A.items() if len(v)>=5]
        out[m][f"{sp}_first3_vs_last2"]=(round(st.fmean(a3),4), round(st.fmean(a2),4), len(a3))
print(json.dumps(out, indent=1, default=str))
json.dump(out, open("results/v6_t4_e1/eval/analysis.json","w"), indent=1, default=str)

import random
gap = set(json.load(open("results/v6_t4_e1/eval/test_routing_gap.json")))
ext = {}
for a in arms:
    T = arms[a][1]
    d = {t: st.fmean(T[t]) - st.fmean(seedT[t]) for t in T if T[t] and seedT.get(t)}
    vals = list(d.values()); rng = random.Random(0)
    bs = sorted(st.fmean(rng.choices(vals, k=len(vals))) for _ in range(10000))
    ext[a] = {"test_mean": st.fmean(st.fmean(T[t]) for t in d),
              "ci95": (round(bs[250],4), round(bs[9750],4)),
              "gap9": round(st.fmean(d[t] for t in d if t in gap),4),
              "routed57": round(st.fmean(d[t] for t in d if t not in gap),4),
              "up05": sum(x>0.05 for x in vals), "down05": sum(x<-0.05 for x in vals),
              "p131": round(d.get("platform-131-deployment-first-resource-blind-spot",float("nan")),3),
              "p141": round(d.get("platform-141-nested-loop-item-collision",float("nan")),3)}
# F full-mean (absolute)
for a in arms:
    F = arms[a][0]; ext[a]["F_mean"] = round(st.fmean(st.fmean(v) for v in F.values() if v),4)
ext["seed"] = {"F_mean": round(st.fmean(st.fmean(seedF[t]) for t in splits["feedback"]),4),
               "test_mean": round(st.fmean(st.fmean(seedT[t]) for t in splits["test"]),4),
               "gap9_seed": round(st.fmean(st.fmean(seedT[t]) for t in gap),4)}
print(json.dumps(ext, indent=1))
json.dump(ext, open("results/v6_t4_e1/eval/analysis_ext.json","w"), indent=1)
