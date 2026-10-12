#!/usr/bin/env python3
"""Read-only scan of every campaign run dir for silent environment failures (missing binary/package, import error, sandbox permission
denial, candidate that never materialized/applied).  Writes analysis/out/metrics/silent_env_scan.json; prints one summary line per run.
Never modifies a run dir.  Usage: scan_silent_env_failures.py [RUNS_ROOT]"""
import json, os, re, sys, glob, collections
from pathlib import Path

RUNS = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/dev/projects2/campaign-scratch/runs")
OUT = Path(__file__).resolve().parents[1] / "out/metrics/silent_env_scan.json"
PAT = re.compile(r"ModuleNotFoundError|ImportError|No module named|command not found|not found in PATH|No such file or directory|Permission denied|"
                 r"PermissionError|bwrap|bubblewrap|materializ|failed to apply|apply(ing)? (failed|error)|cannot apply|FileNotFoundError|"
                 r"Operation not permitted|EACCES|sandbox (failed|error|denied)|unshare|setfacl|sudo:|executable|OSError|exec format|"
                 r"AttributeError|KeyError|Traceback|pregate|rejected: ", re.I)
SKIP_FILE = re.compile(r"(rollouts?/|/work/|/native_sims|/frozen/|/claude_cfg|/claude_config|/projects/|/proposer_sessions|/traces?/|node_modules|\.git/)")


def norm(s):
    s = str(s).strip().splitlines()[0][:170] if str(s).strip() else ""
    s = re.sub(r"0x[0-9a-f]+|\b[0-9a-f]{8,}\b", "H", s)
    s = re.sub(r"(cand|iter|step|task|prop|run)[_-]?\d+", r"\1N", s)
    s = re.sub(r"\d+", "N", s)
    return s


def jl(p):
    out = []
    try:
        for l in open(p, errors="replace"):
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def scan_run(root: Path):
    r = {"root": str(root).replace(str(RUNS) + "/", "")}
    cap_dirs = sorted(root.glob(".capevolve/run_*"))
    cids, evald = set(), set()
    err = collections.Counter()
    nroll = 0
    for cd in cap_dirs:
        g = jl(cd / "graph.jsonl")
        for x in g:
            if x.get("id") and x["id"] != "seed":
                cids.add(x["id"])
        for x in jl(cd / "candidates.jsonl"):
            if x.get("candidate_id") and x["candidate_id"] != "seed":
                cids.add(x["candidate_id"])
        if (cd / "candidates").is_dir():
            for c in (cd / "candidates").iterdir():
                if c.name != "seed":
                    cids.add(c.name)
        for x in jl(cd / "eval_index.jsonl"):
            if x.get("tag") and x["tag"] != "seed":
                evald.add(x["tag"])
        for f in glob.glob(str(cd / "rollouts/*/*.json")):
            nroll += 1
            m = re.match(r".*/([^/]+)__([^_].*?)__t\d+\.json$", f)
            if m and m.group(2) != "seed":
                evald.add(m.group(2))
            try:
                d = json.load(open(f))
            except Exception:
                continue
            e = (d.get("rollout") or {}).get("error")
            if e:
                err["rollout: " + norm(e)] += 1
        for x in jl(cd / "events.jsonl"):
            k = x.get("kind") or x.get("event")
            if k in ("infra_warning", "agent_optimize_pregate_warning", "gate_warning", "errored_trial_policy", "agent_optimize_compliance") or "error" in str(k).lower() or "fail" in str(k).lower():
                err["event %s: %s" % (k, norm(x.get("msg") or x.get("message") or x.get("detail") or x.get("reason") or json.dumps({a: b for a, b in x.items() if a not in ("t",)})[:140]))] += 1
        for x in jl(cd / "rejected.jsonl"):
            err["rejected: " + norm(x.get("reason") or x.get("why") or json.dumps(x)[:120])] += 1
        for x in jl(cd / "graph.jsonl"):
            if x.get("note"):
                err["graph note: " + norm(x["note"])] += 1
    # non-capevolve baselines: candidates.jsonl at root, rollouts_metrics*.jsonl
    for x in jl(root / "candidates.jsonl"):
        cid = x.get("candidate_id") or x.get("id")
        if cid and cid != "seed" and x.get("event", "created") == "created":
            cids.add(str(cid))
    for f in ("rollouts_metrics.jsonl", "rollouts_metrics_converted.jsonl"):
        for x in jl(root / f):
            nroll += 1
            if x.get("candidate_id") and x["candidate_id"] not in ("seed",):
                evald.add(str(x["candidate_id"]))
    # log-ish files at the root and one level down (no rollouts/traces)
    logs = [p for p in list(root.glob("*.log")) + list(root.glob("*.err")) + list(root.glob("*.out")) + list(root.glob("logs/*")) +
            list(root.glob("*/guard.log")) + list(root.glob("*/*.log")) if p.is_file() and not SKIP_FILE.search(str(p)) and p.stat().st_size < 60e6]
    for p in logs:
        try:
            with open(p, errors="replace") as fh:
                for i, line in enumerate(fh):
                    if i > 400000:
                        break
                    if PAT.search(line) and "get_response_cost" not in line and "isn't mapped" not in line:
                        err["log %s: %s" % (p.name if not p.name[:4].isdigit() else "N", norm(line))] += 1
        except OSError:
            pass
    r.update(candidates_proposed=len(cids), candidates_evaluated=len(evald & cids) if cids else len(evald), rollout_rows=nroll,
             cand_ids_never_evaluated=sorted(cids - evald)[:12], top_errors=err.most_common(8))
    return r


def roots():
    out = []
    for suite in ("E10", "E10B", "E10C", "E12A", "E12C", "E20", "E21", "E26"):
        base = RUNS / suite
        if not base.is_dir():
            continue
        for arm in sorted(base.iterdir()):
            if not arm.is_dir() or "superseded" in arm.name or arm.name.startswith(("_", "smoke", "pilot")) or arm.name.endswith("_test_k1"):
                continue
            for s in sorted(arm.glob("s[0-9]*")):
                if s.is_dir() and re.fullmatch(r"s\d", s.name):
                    out.append(s)
    return out


if __name__ == "__main__":
    res = []
    for rt in roots():
        try:
            r = scan_run(rt)
        except Exception as e:  # keep scanning
            r = {"root": str(rt), "error": repr(e)}
        res.append(r)
        print(r["root"], "proposed", r.get("candidates_proposed"), "evaluated", r.get("candidates_evaluated"), "rollouts", r.get("rollout_rows"))
    OUT.write_text(json.dumps(res, indent=1))
