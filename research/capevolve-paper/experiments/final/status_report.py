#!/usr/bin/env python3
"""status_report.py: hourly status of the running final evaluation (stdlib).  Per suite and arm: jobs done / missing / pending, attempts, first-attempt infra rate and infra attempts,
empty-output / raw-tool-text counts, the latest canary rounds, HarnessLens trace completeness (infra attempts whose text says 'no complete OpenCode trace'), capped-token counter.
    status_report.py [--suites A,B,C,D] [--json]"""
import argparse, json, os, sys, urllib.request, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C

ap = argparse.ArgumentParser(); ap.add_argument("--suites", default="A,B,C,D"); ap.add_argument("--json", action="store_true"); a = ap.parse_args()
out = {}
for S in a.suites.split(","):
    root = C.final_dir(S)
    order = [json.loads(l) for l in open(C.MANIFESTS / ("order_%s.jsonl" % S)) if l.strip()]
    jobs = [j for j in order if j.get("type") == "job"]
    recs = C.jsonl(root / "raw" / "rollouts.jsonl")
    by = collections.defaultdict(list)
    for r in recs:
        by[r["job_id"]].append(r)
    arms = collections.OrderedDict()
    for j in jobs:
        a_ = arms.setdefault(j["arm_label"], dict(jobs=0, done=0, missing=0, started=0, attempts=0, first_infra=0, infra_attempts=0, candidate_err=0, empty_out=0, raw_tool=0, hl_trace_fail=0))
        a_["jobs"] += 1
        rs = by.get(j["job_id"], [])
        if rs:
            a_["started"] += 1
            a_["attempts"] += len(rs)
            a_["first_infra"] += 1 if rs[0]["error_class"] == "infra" else 0
            a_["infra_attempts"] += sum(1 for x in rs if x["error_class"] == "infra")
            a_["hl_trace_fail"] += sum(1 for x in rs if "no complete OpenCode trace" in (x.get("error_text") or ""))
            t = next((x for x in rs if x.get("terminal")), None)
            if t:
                if t["final_status"] == "missing":
                    a_["missing"] += 1
                else:
                    a_["done"] += 1
                    a_["candidate_err"] += 1 if t["error_class"] in ("candidate", "unverifiable") else 0
                    a_["empty_out"] += 1 if t.get("empty_output") else 0
                    a_["raw_tool"] += 1 if t.get("raw_tool_text_last") else 0
    can = C.jsonl(root / "canary.jsonl")[-2:]
    tot = collections.Counter()
    for v in arms.values():
        for k, x in v.items():
            tot[k] += x
    out[S] = {"totals": dict(tot), "first_attempt_infra_rate": round(tot["first_infra"] / tot["started"], 4) if tot["started"] else None,
              "arms": arms, "canary_last": can}
try:
    h = json.loads(urllib.request.urlopen("http://127.0.0.1:4111/health", timeout=5).read()); out["capped_tokens"] = h.get("capped_tokens")
except Exception:
    out["capped_tokens"] = None
if a.json:
    print(json.dumps(out, indent=1)); sys.exit(0)
print("capped tokens:", out["capped_tokens"])
for S in a.suites.split(","):
    o = out[S]; t = o["totals"]
    print("== Suite %s: done %d / %d jobs, missing %d, started %d, attempts %d, first-attempt infra rate %s (infra attempts %d), HL trace failures %d" %
          (S, t["done"], t["jobs"], t["missing"], t["started"], t["attempts"], o["first_attempt_infra_rate"], t["infra_attempts"], t["hl_trace_fail"]))
    for arm, v in o["arms"].items():
        if v["started"]:
            print("   %-16s %4d/%-4d first_infra %-3d infra_att %-3d cand_err %-3d empty %-3d rawtool %-3d" % (arm, v["done"], v["jobs"], v["first_infra"], v["infra_attempts"], v["candidate_err"], v["empty_out"], v["raw_tool"]))
    for c in o["canary_last"]:
        print("   canary", {k: c.get(k) for k in ("canary_round", "t", "n", "mean_reward", "raw_tool_text_last_rate", "empty_output_rate")})
