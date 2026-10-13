#!/usr/bin/env python3
"""Why did a rollout end as infra?  Third descriptive column next to the two infra sensitivities.

Per suite / arm / seed (artifact): infra attempts by cause, infra_final cells (last attempt, attempt 3, final_status 'missing'),
and the share of infra_final cells whose LIVE trace holds a guard-error ToolMessage.

tau2 re-executes the agent's tool calls on a pristine environment and compares the tool results with the live ones; a mismatch is
labelled TerminationReason.INFRASTRUCTURE_ERROR.  infra_detail then holds "Tool call: ... Returned: <pristine result> ... Expected:
<live result>".  A guard error = the live (Expected) result is an `Error...` message while the pristine (Returned) result is not, i.e.
the artifact's edited tool refused an action the pristine tool performed.  Evaluation property, not network infrastructure.

usage: python3 -I infra_mechanism.py [--suites B,C,D,E] [--json out.json]
"""
import argparse
import collections
import csv
import json
import re
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_common as C

RATE = re.compile(r"429|RateLimit|rate_limit|high demand|rate limit", re.I)
TOOL = re.compile(r"name: (\w+)")


def _msg_content(s, label):
    i = s.find(label)
    if i < 0:
        return None
    j = s.find("content:", i)
    return None if j < 0 else s[j + 8:j + 8 + 200].replace("\\n", "\n").strip()


def _subtype(ret, exp):
    """live_refusal: live result is an Error, pristine is not (guard); reworded_error: both Error, texts differ; content_differs: neither is an Error."""
    re_, ee = (ret or "").startswith("Error"), (exp or "").startswith("Error")
    return "live_refusal" if ee and not re_ else ("reworded_error" if ee and re_ else ("pristine_refusal" if re_ else "content_differs"))


def classify(d):
    detail = str(d.get("infra_detail"))
    text = str(d.get("error_text") or "")
    if RATE.search(detail) or RATE.search(text) and "terminated" not in text:
        return "rate_limit", None, False, None
    if "Tool call:" in detail and "Returned:" in detail and "Expected:" in detail:
        m = TOOL.search(detail)
        ret, exp = _msg_content(detail, "Returned:"), _msg_content(detail, "Expected:")
        guard = bool(exp and exp.startswith("Error") and not (ret or "").startswith("Error"))
        return "tool_result_mismatch", (m.group(1) if m else "?"), guard, _subtype(ret, exp)
    if "user-simulator" in text:
        return "user_sim_stop", None, False, None
    return "other", None, False, None


def analyse(suite):
    root = C.SCRATCH / "final_eval" / suite / "raw" / "rollouts.jsonl"
    last = {}
    attempts = []
    for l in open(root):
        try:
            d = json.loads(l)
        except Exception:
            continue
        if d.get("type") != "attempt":
            continue
        k = d["job_id"]
        if k not in last or d["attempt"] > last[k]["attempt"]:
            last[k] = d
        if d.get("error_class") == "infra":
            attempts.append(d)
    rows = collections.defaultdict(lambda: {"infra_attempts": 0, "rate_limit": 0, "tool_result_mismatch": 0, "user_sim_stop": 0, "other": 0,
                                            "guard_error_attempts": 0, "sub_live_refusal": 0, "sub_reworded_error": 0, "sub_content_differs": 0, "sub_pristine_refusal": 0, "infra_final": 0, "infra_final_guard_error": 0, "tools": collections.Counter()})
    for d in attempts:
        r = rows[(d["arm"], d["seed"])]
        cause, tool, guard, sub = classify(d)
        if sub:
            r["sub_" + sub] += 1
        r["infra_attempts"] += 1
        r[cause] += 1
        r["guard_error_attempts"] += guard
        if tool:
            r["tools"][tool] += 1
    for d in last.values():
        if d.get("error_class") == "infra" and d.get("final_status") == "missing":
            r = rows[(d["arm"], d["seed"])]
            r["infra_final"] += 1
            if classify(d)[2]:
                r["infra_final_guard_error"] += 1
    out = []
    for (arm, seed), r in sorted(rows.items()):
        out.append(dict(suite=suite, arm=arm, seed=seed, **{k: v for k, v in r.items() if k != "tools"},
                        guard_share_of_infra_final=round(r["infra_final_guard_error"] / r["infra_final"], 3) if r["infra_final"] else None,
                        tools=dict(r["tools"].most_common(4))))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="B,C,D,E")
    ap.add_argument("--json", default=None)
    ap.add_argument("--min-attempts", type=int, default=5)
    a = ap.parse_args()
    allrows = []
    for S in a.suites.split(","):
        rows = analyse(S)
        allrows += rows
        tot = collections.Counter()
        for r in rows:
            for k in ("infra_attempts", "rate_limit", "tool_result_mismatch", "user_sim_stop", "other", "guard_error_attempts", "sub_live_refusal", "sub_reworded_error", "sub_content_differs", "sub_pristine_refusal", "infra_final", "infra_final_guard_error"):
                tot[k] += r[k]
        print("== Suite %s: %s" % (S, dict(tot)))
        for r in rows:
            if r["infra_attempts"] >= a.min_attempts:
                print("  %-12s s%d infra_att %3d mismatch %3d ratelimit %2d usersim %2d other %2d | infra_final %2d (guard-error %s) tools %s" % (
                    r["arm"], r["seed"], r["infra_attempts"], r["tool_result_mismatch"], r["rate_limit"], r["user_sim_stop"], r["other"],
                    r["infra_final"], r["guard_share_of_infra_final"], r["tools"]))
    if a.json:
        json.dump(allrows, open(a.json, "w"), indent=1)
