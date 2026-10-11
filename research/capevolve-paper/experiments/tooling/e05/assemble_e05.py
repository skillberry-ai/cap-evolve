import json, subprocess, datetime
B = "/home/dev/projects2/campaign-scratch/bench"; WT = "/home/dev/projects2/wt-e05"
rows = json.load(open(f"{B}/out/e05_sb.json"))
t2 = json.load(open(f"{B}/out/e05_tau2.json")); pg = json.load(open(f"{B}/out/e05_pregate.json")); pgs = json.load(open(f"{B}/out/e05_pregate_strict.json"))
def pgtxt(d): return "pregate ok" if d.get("ok") else "pregate REFUSED: " + d.get("failure", "")[:70]
def pgw(d): return (" (warning only: " + d["warnings"][0][:70] + ")") if d.get("warnings") else ""
T = []
def add(id, fault, expected, observed, status, evidence=""): T.append({"id": id, "area": "tau2 candidate tools.py", "fault": fault, "expected": expected, "observed": observed, "status": status, "evidence": evidence})
add("T2-1.import_raises", "candidate tools.py raises at import", "refused before evaluation, or its trials tagged candidate",
    f"default {pgtxt(pg['tools_py_raises_at_import'])}{pgw(pg['tools_py_raises_at_import'])}; strict {pgtxt(pgs['tools_py_raises_at_import'])}; at run time the exception escapes Adapter.run_batch ({t2['tools_py_raises_at_import'].get('apply_or_run_raised')}) and run_trials_pool turns it into an untagged error rollout",
    "PARTIAL", "default pregate only warns; the error rollout carries no error_kind=candidate, so with the default errored policy `drop` it is missing data, not a failure")
add("T2-2.syntax_error", "candidate tools.py has a syntax error", "refused before evaluation", f"default {pgtxt(pg['tools_py_syntax_error'])}; strict {pgtxt(pgs['tools_py_syntax_error'])}", "PASS")
add("T2-3.no_AirlineTools_class", "candidate tools.py defines no AirlineTools class", "refused, or edits visibly ignored",
    f"default {pgtxt(pg['tools_py_no_AirlineTools_class'])}; strict {pgtxt(pgs['tools_py_no_AirlineTools_class'])}; adapter silently falls back to pristine tau2 tools (`cand_cls or _PristineAirlineTools`)", "GAP",
    "the candidate is scored as if it were the seed tools: its tool edits (none usable) are silently discarded")
add("T2-4.get_tools_raises", "candidate AirlineTools.get_tools raises", "refused, or trials tagged candidate",
    f"default {pgtxt(pg['tools_py_get_tools_raises'])}; strict {pgtxt(pgs['tools_py_get_tools_raises'])}; run-time rollout error_kind={t2['tools_py_get_tools_raises'].get('error_kind')} (reads as infrastructure error)", "GAP",
    "with a dead gateway the healthy control and this candidate produce the identical INFRASTRUCTURE_ERROR rollout, so the adapter cannot tell them apart; the candidate fault is untagged")
add("T2-5.remove_all_tools", "candidate REMOVE_TOOLS removes every agent tool", "flagged before spending rollouts",
    f"default {pgtxt(pg['tools_py_removes_all_tools'])}; strict {pgtxt(pgs['tools_py_removes_all_tools'])}", "GAP", "tool_smoke calls tools by attribute and never inspects the exposed tool map; the effect on reward needs LLM calls to measure and was not run")
add("T2-6.tool_body_raises_when_called", "a candidate tool body raises when the agent calls it", "returned to the agent as a tool error, not a crash or an infra error",
    f"env returned error message: {t2['tool_body_raises_when_called'].get('env_returned_error_message')} ({t2['tool_body_raises_when_called'].get('content_head')})", "PASS")
T.append({"id": "T2-7.gold_env_built_from_candidate", "area": "tau2 evaluator integrity", "fault": "candidate no-ops cancel_reservation", "expected": "the DB check's gold environment is built from pristine tau2 tools",
          "observed": "tau2's evaluator builds the predicted and gold environments with registry.get_env_constructor(domain), which Adapter.apply() replaced; the constructed env uses the candidate class (module capevolve_candidate_tools_*) and its cancel_reservation is the no-op",
          "status": "GAP", "evidence": "gold actions are replayed through the candidate's tools; a state-weakening candidate shifts both sides of the DB comparison. Needs a code change (evaluate with the pristine constructor)."})
for r in rows:
    if r["id"] == "SB-5.harness_errored_policy": r["status"] = "PARTIAL"
allrows = rows + T
cnt = {}
for r in allrows: cnt[r["status"]] = cnt.get(r["status"], 0) + 1
head = subprocess.run(["git", "-C", WT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
out = {"experiment": "E05_injected_faults", "date": datetime.date.today().isoformat(), "llm_calls": 0, "repo_commit_under_test": head,
       "legend": {"PASS": "detected or neutralised as intended", "PARTIAL": "detected only in part/post hoc, or only under a non-default setting", "GAP": "not detected: the fault passes silently", "INFO": "context row", "FAIL": "test expectation violated"},
       "counts": cnt, "environment": {"libreoffice": "7.1.8.1 (host) for SB rows; no real model", "tau2": "8ebb7499622fc2be9b9d510d6f7a7653461f4f29, litellm 1.82.6"},
       "reproduce": "see research/capevolve-paper/experiments/tooling/e05/README.md", "results": allrows}
open(f"{WT}/research/capevolve-paper/experiments/summaries/E05_injected_faults.json", "w") if __import__("os").makedirs(f"{WT}/research/capevolve-paper/experiments/summaries", exist_ok=True) is None else None
json.dump(out, open(f"{WT}/research/capevolve-paper/experiments/summaries/E05_injected_faults.json", "w"), indent=1)
print(cnt)
for r in allrows: print(f"{r['status']:8} {r['id']}")
