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
def idle_gap_proxy(hours=1.0):
    """Suite A idle-kernel exposure proxy: the longest non-first-turn Gemma call (queue+latency) of the FINAL-A tags in the last `hours` h; an inter-exec gap is this plus the exec time (<= 180 s).
    The idle-kernel defect needs a gap near/above ~600 s (check_kernel_idle: 700 s fails), so > 300 s here is an alert."""
    import time, datetime as dt
    cut = time.time() - hours * 3600
    mx, n, over = 0.0, 0, 0
    path = C.SCRATCH / "logs" / "gateway_calls.jsonl"
    with open(path, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 80_000_000)); f.readline()
        for line in f:
            if b'"tag": "tag:FINAL-A' not in line:
                continue
            try:
                d = json.loads(line)
                t = dt.datetime.strptime(d["t"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
            except Exception:
                continue
            if t < cut or not d["tag"].endswith(":target") or ((d.get("usage") or {}).get("prompt_tokens") or 0) < 2000:
                continue
            du = (d.get("queue_s") or 0) + (d.get("latency_s") or 0)
            n += 1; mx = max(mx, du); over += du > 300
    return {"calls": n, "max_call_s": round(mx, 1), "over_300s": over}


def print_no_output_rate(hours=1.0):
    """Suite A direct outcome check for the iopub race: share of code turns containing print( whose tool reply is the bare no-output message, over the attempts last written in the last `hours` h (pre-fix baseline ~1.9-2.2%). Pause A and tell lead above 4% in any hour."""
    import time
    cut = time.time() - hours * 3600
    n = bad = files = 0
    for p in (C.SCRATCH / "final_eval" / "A" / "raw" / "attempts").glob("*/a*/trace.json"):
        try:
            if p.stat().st_mtime < cut:
                continue
            msgs = json.loads(p.read_text())
        except Exception:
            continue
        files += 1
        for i, m in enumerate(msgs[:-1]):
            if m.get("role") == "assistant" and "print(" in str(m.get("content")) and msgs[i + 1].get("role") == "user":
                n += 1
                bad += str(msgs[i + 1].get("content")).strip() == "[Code executed successfully with no output]"
    return {"attempts": files, "print_turns": n, "no_output": bad, "rate": round(bad / n, 4) if n else None}


try:
    out["suiteA_idle_gap_proxy_last_hour"] = idle_gap_proxy()
except Exception:
    out["suiteA_idle_gap_proxy_last_hour"] = None
try:
    out["suiteA_print_no_output_last_hour"] = print_no_output_rate()
except Exception:
    out["suiteA_print_no_output_last_hour"] = None
try:
    h = json.loads(urllib.request.urlopen("http://127.0.0.1:4111/health", timeout=5).read()); out["capped_tokens"] = h.get("capped_tokens")
except Exception:
    out["capped_tokens"] = None
if a.json:
    print(json.dumps(out, indent=1)); sys.exit(0)
print("capped tokens:", out["capped_tokens"], "| Suite A idle-gap proxy (last hour):", out["suiteA_idle_gap_proxy_last_hour"])
print("Suite A print-returned-no-output rate (last hour, alert > 0.04):", out["suiteA_print_no_output_last_hour"])
for S in a.suites.split(","):
    o = out[S]; t = o["totals"]
    print("== Suite %s: done %d / %d jobs, missing %d, started %d, attempts %d, first-attempt infra rate %s (infra attempts %d), HL trace failures %d" %
          (S, t["done"], t["jobs"], t["missing"], t["started"], t["attempts"], o["first_attempt_infra_rate"], t["infra_attempts"], t["hl_trace_fail"]))
    for arm, v in o["arms"].items():
        if v["started"]:
            print("   %-16s %4d/%-4d first_infra %-3d infra_att %-3d cand_err %-3d empty %-3d rawtool %-3d" % (arm, v["done"], v["jobs"], v["first_infra"], v["infra_attempts"], v["candidate_err"], v["empty_out"], v["raw_tool"]))
    for c in o["canary_last"]:
        print("   canary", {k: c.get(k) for k in ("canary_round", "t", "n", "mean_reward", "raw_tool_text_last_rate", "empty_output_rate")})
