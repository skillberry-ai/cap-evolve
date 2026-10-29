#!/usr/bin/env python3
"""Family 1 POST HOC descriptive contrasts (team-lead's request after the primary was read; erratum 152). Uses the registered fam1_analysis.py machinery
(same per-task cell means, infra rule, one-sample t(19) over 20 tasks). code - prose on reward, decision steps, pass^5 (per task C(c,5)/C(10,5)),
seed-tool calls and prompt tokens per rollout; per champion and pooled (mean of the two champions). Raw p, no family, labelled post hoc.
    python3 -I fam1_posthoc.py OUTDIR RESULTS_ROOT"""
import csv, json, math, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb
OUT, ROOT = sys.argv[1:3]
SEEDP = ("book_reservation", "calculate", "cancel_reservation", "get_reservation_details", "get_user_details", "list_all_airports", "search_direct_flight", "search_onestop_flight", "send_certificate", "transfer_to_human_agents", "update_reservation_baggages", "update_reservation_flights", "update_reservation_passengers", "get_flight_status")
rows = list(csv.DictReader(open(os.path.join(ROOT, "results_trials.csv")))); dirs = {}; llm = {}
for l in open(os.path.join(ROOT, "raw", "rollouts.jsonl")):
    j = json.loads(l); dirs[j["job_id"]] = j["attempt_dir"]; llm[j["job_id"]] = j["n_llm_calls"]
Q = defaultdict(lambda: defaultdict(list))
for x in rows:
    a, t = x["arm"], str(x["task"]); r = float(x["reward"]); Q[(a, "reward")][t].append(r); Q[(a, "succ")][t].append(1.0 if r == 1.0 else 0.0)
    Q[(a, "steps")][t].append(llm[x["job_id"]] - 1)
    tr = json.load(open(os.path.join(dirs[x["job_id"]], "trace.json"))); asst = [m for m in tr if m.get("role") == "assistant"]
    Q[(a, "seedp")][t].append(sum(1 for m in asst for c in (m.get("tool_calls") or []) if c.get("name") in SEEDP))
    Q[(a, "ptok")][t].append(sum(((m.get("usage") or {}).get("prompt_tokens") or 0) for m in asst if m.get("usage")))
tasks = sorted({t for k in Q for t in Q[k]}, key=lambda s: (len(s), s)); mean = lambda v: sum(v) / len(v)
def Y(a, q): return [mean(Q[(a, q)][t]) for t in tasks]
def pk(a, k): return [math.comb(sum(1 for r in Q[(a, "succ")][t] if r == 1.0), k) / math.comb(len(Q[(a, "succ")][t]), k) for t in tasks]
def one(v):
    n = len(v); m = mean(v); sd = math.sqrt(sum((a - m) ** 2 for a in v) / (n - 1)); se = sd / math.sqrt(n); c = pcb.t_ppf(0.975, n - 1)
    return dict(est=m, lo=m - c * se, hi=m + c * se, p=2 * (1 - pcb._t_cdf(abs(m / se), n - 1)) if se > 0 else 1.0)
res = {}; L = ["# Family 1 POST HOC descriptive: code - prose (E1X); one-sample t(19) over 20 tasks; raw p; labelled post hoc", ""]
for name, getter in (("reward", lambda a: Y(a, "reward")), ("decision steps", lambda a: Y(a, "steps")), ("pass^5", lambda a: pk(a, 5)), ("pass^10", lambda a: pk(a, 10)),
                     ("seed-tool calls", lambda a: Y(a, "seedp")), ("prompt tokens", lambda a: Y(a, "ptok"))):
    per = {c: [x - y for x, y in zip(getter(f"E1X-{c}-code"), getter(f"E1X-{c}-prose"))] for c in ("s0", "s3")}
    pooled = [mean([per["s0"][i], per["s3"][i]]) for i in range(len(tasks))]
    res[name] = dict(pooled=one(pooled), s0=one(per["s0"]), s3=one(per["s3"]))
    f = (lambda v: f"{v:+.0f}") if name == "prompt tokens" else (lambda v: f"{v:+.3f}")
    L.append(f"{name}: pooled {f(res[name]['pooled']['est'])} [{f(res[name]['pooled']['lo'])}, {f(res[name]['pooled']['hi'])}] raw p {res[name]['pooled']['p']:.4f}; "
             f"s0 {f(res[name]['s0']['est'])} [{f(res[name]['s0']['lo'])}, {f(res[name]['s0']['hi'])}] p {res[name]['s0']['p']:.4f}; s3 {f(res[name]['s3']['est'])} [{f(res[name]['s3']['lo'])}, {f(res[name]['s3']['hi'])}] p {res[name]['s3']['p']:.4f}")
os.makedirs(OUT, exist_ok=True); json.dump(res, open(os.path.join(OUT, "fam1_posthoc.json"), "w"), indent=1); open(os.path.join(OUT, "fam1_posthoc.md"), "w").write("\n".join(L)); print("\n".join(L))
