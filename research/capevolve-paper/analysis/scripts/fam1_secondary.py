#!/usr/bin/env python3
"""Family 1 SECONDARY outcomes (addendum 28; descriptive, no p-values, no family): pass^k, tool calls by group, prompt/completion tokens, tool-output size, cost.
Written after the primary (fam1_analysis.py) was run on E1X, before the secondary numbers were looked at; registered by hash before it is run.
Per rollout (agent side), from raw/rollouts.jsonl -> attempt_dir/trace.json:
  decision steps = assistant messages with usage not null; tool calls = sum of len(tool_calls) of assistant messages, split into the removed tool
  (list_user_reservations), the 14 seed tools (SEEDP below) and others (other champion-added tools);
  prompt_tokens / completion_tokens = sums of usage over assistant messages; tool_output_chars = sum of len(content) of role=tool messages (characters, same for all arms;
  NOT tokens); agent cost = sum of the assistant messages' `cost` field (the adapter's own figure, not the gateway ledger).
pass^k per cell: mean over the 20 tasks of C(c,k)/C(10,k), c = successes of the task's 10 trials (reward is 0/1; success = reward == 1.0).
Per cell means, plus the 2x2 interaction of each quantity (both - prose - code + base) per champion and mean, with a t(19) interval over tasks, DESCRIPTIVE only.
    python3 -I fam1_secondary.py OUTDIR RESULTS_ROOT
"""
import csv, json, math, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paired_cluster_bootstrap as pcb
OUT, ROOT = sys.argv[1:3]
REMOVED = "list_user_reservations"
SEEDP = ("book_reservation", "calculate", "cancel_reservation", "get_reservation_details", "get_user_details", "list_all_airports", "search_direct_flight", "search_onestop_flight", "send_certificate", "transfer_to_human_agents", "update_reservation_baggages", "update_reservation_flights", "update_reservation_passengers", "get_flight_status")   # the 14 public tools of the seed capability (tools/tools.py of the seed artifact)
rows = list(csv.DictReader(open(os.path.join(ROOT, "results_trials.csv"))))
dirs = {}
for l in open(os.path.join(ROOT, "raw", "rollouts.jsonl")):
    j = json.loads(l); dirs[j["job_id"]] = j["attempt_dir"]
def meas(d):
    t = json.load(open(os.path.join(d, "trace.json"))); a = [m for m in t if m.get("role") == "assistant"]
    dec = [m for m in a if m.get("usage")]
    calls = [c.get("name") for m in a for c in (m.get("tool_calls") or [])]
    return dict(steps=len(dec), calls=len(calls), removed=sum(1 for c in calls if c == REMOVED), seedp=sum(1 for c in calls if c in SEEDP),
                other=sum(1 for c in calls if c != REMOVED and c not in SEEDP),
                ptok=sum((m["usage"] or {}).get("prompt_tokens", 0) for m in dec), ctok=sum((m["usage"] or {}).get("completion_tokens", 0) for m in dec),
                toolchars=sum(len(m.get("content") or "") for m in t if m.get("role") == "tool"), cost=sum(m.get("cost") or 0 for m in a))
M = defaultdict(lambda: defaultdict(list)); R = defaultdict(lambda: defaultdict(list)); allnames = set()
for x in rows:
    arm, tk = x["arm"], str(x["task"]); R[arm][tk].append(float(x["reward"])); m = meas(dirs[x["job_id"]])
    for k, v in m.items(): M[(arm, k)][tk].append(v)
    allnames |= {c for c in []}
tasks = sorted({t for a in R for t in R[a]}, key=lambda s: (len(s), s))
mean = lambda v: sum(v) / len(v)
def one(v):
    n = len(v); m = mean(v); sd = math.sqrt(sum((a - m) ** 2 for a in v) / (n - 1)); se = sd / math.sqrt(n); c = pcb.t_ppf(0.975, n - 1)
    return dict(est=m, lo=m - c * se, hi=m + c * se)
lines = ["# Family 1 secondary outcomes (descriptive; E1X)", ""]; res = {}
cells = sorted(R, key=lambda a: (a.startswith("seed"), a))
lines.append("## pass^k (mean over tasks of C(c,k)/C(10,k))"); lines.append("cell | " + " | ".join(f"k={k}" for k in (1, 2, 3, 5, 10)))
for a in cells:
    pk = {}
    for k in (1, 2, 3, 5, 10):
        pk[k] = mean([math.comb(sum(1 for r in R[a][t] if r == 1.0), k) / math.comb(len(R[a][t]), k) for t in tasks])
    res.setdefault("passk", {})[a] = pk; lines.append(f"{a} | " + " | ".join(f"{pk[k]:.3f}" for k in (1, 2, 3, 5, 10)))
lines.append("")
qs = ["steps", "calls", "removed", "seedp", "other", "ptok", "ctok", "toolchars", "cost"]
lines.append("## per-rollout means by cell (mean over tasks of the task mean)"); lines.append("cell | " + " | ".join(qs))
for a in cells:
    lines.append(f"{a} | " + " | ".join(f"{mean([mean(M[(a, q)][t]) for t in tasks]):.3f}" if q != "cost" else f"{mean([mean(M[(a, q)][t]) for t in tasks]):.5f}" for q in qs))
lines.append("")
lines.append("## interaction (both - prose - code + base) per quantity: mean over champions [t(19) interval over tasks]; per champion beside; main effects both-base and both-prose")
def Y(a, q): return [mean(M[(a, q)][t]) for t in tasks]
for q in qs:
    per = {}
    for c in ("s0", "s3"):
        b, co, pr, ba = [Y(f"E1X-{c}-{k}", q) for k in ("both", "code", "prose", "base")]
        per[c] = [b[i] - pr[i] - co[i] + ba[i] for i in range(len(tasks))]
    I = one([mean([per[c][i] for c in per]) for i in range(len(tasks))])
    fmt = (lambda v: f"{v:+.5f}") if q == "cost" else (lambda v: f"{v:+.3f}")
    lines.append(f"{q}: I {fmt(I['est'])} [{fmt(I['lo'])}, {fmt(I['hi'])}]; s0 {fmt(mean(per['s0']))}; s3 {fmt(mean(per['s3']))}")
os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "fam1_secondary.md"), "w").write("\n".join(lines)); json.dump(res, open(os.path.join(OUT, "fam1_secondary.json"), "w"), indent=1)
print("\n".join(lines))
