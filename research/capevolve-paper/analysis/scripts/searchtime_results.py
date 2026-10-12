#!/usr/bin/env python3
"""searchtime_results.py: latest SEARCH-TIME results from the run artifacts (read-only, never a final set).

Reads campaign-scratch/runs/{E10,E10B,E10C,E12A,E12C} (candidates.jsonl, events.jsonl, state.json,
run_summary.json, rollout_counter.json, candidate artifact dirs) and analysis/out/metrics/*.csv, and writes
  analysis/out/searchtime/{runs.csv, anytime.csv, edits_by_candidate.csv, edits_by_arm.csv, gate_by_run.csv,
                           gate_compare.csv, infra_by_arm.csv, searchtime.json, summary.md}
  paper/tables/searchtime_*.tex   paper/figures/searchtime_*.pdf   (plotting style of paper/scripts/plots/common.py)
Re-runnable at any time (idempotent); refresh at the 2026-10-13 06:00 UTC cutoff by running it again:
  /home/dev/projects2/campaign-scratch/venv-paper/bin/python -I analysis/scripts/searchtime_results.py

Every number is a search-time number on a search/selection split.  Selection-split scores are optimistic and are NOT
comparable across methods (each method selects on a different split and with a different rule), so no cross-method
ranking may be drawn from them.  Fields that could leak a final set (test_reward etc.) are never read: events are
parsed through explicit field whitelists and any path under final_eval/ or named *test* is refused.
Python 3.9 compatible; matplotlib is only needed for the figures.
"""
import csv
import difflib
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2]
SCRATCH = Path(os.environ.get("CAMPAIGN_SCRATCH", "/home/dev/projects2/campaign-scratch"))
RUNS = SCRATCH / "runs"
METRICS = PAPER / "analysis" / "out" / "metrics"
OUT = PAPER / "analysis" / "out" / "searchtime"
TABLES = PAPER / "paper" / "tables"
FIGS = PAPER / "paper" / "figures"
sys.path.insert(0, str(PAPER / "paper" / "scripts" / "plots"))

SEEDS = ("s0", "s1", "s2")
# suite key -> (root dir, base suite letter, {run dir name: paper arm key}, metrics suite label)
SUITES = {
    "A": (RUNS / "E10", "A", {"hill-climb": "hc", "agent-optimize": "ao", "gepa": "gepa", "skillopt": "skillopt",
                              "metaharness": "metaharness", "evoskill": "evoskill", "wikiskill": "wikiskill",
                              "trace2skill": "trace2skill", "ace": "ace", "mipro": "mipro"}),
    "B": (RUNS / "E10B", "B", {"hc": "hc", "ao": "ao", "gepa": "gepa", "harnesslens": "harnesslens",
                               "ctl-oneshot": "oneshot", "ctl-seed": "seed"}),
    "C": (RUNS / "E10C", "C", {"hc": "hc", "ao": "ao", "gepa": "gepa", "ctl-oneshot": "oneshot", "ctl-seed": "seed"}),
    "A-E12": (RUNS / "E12A", "A", {"hcstock": "hcstock"}),
    "C-E12": (RUNS / "E12C", "C", {"hcstock": "hcstock", "bestofk": "bestofk"}),
}
METRIC_ARM = {"oneshot": "ctl-oneshot", "seed": "ctl-seed"}  # paper arm key -> arm name in the metrics CSVs
SHARE_SURFACES = ["system_prompt", "task_template", "tool_code", "mcp", "skill_files", "other"]  # process_docs/reference excluded from shares
CAPEVOLVE = ("hc", "ao", "hcstock")
OPT_ROLES = {"optimizer", "reflection", "proposer", "reflector", "curator", "optimizer-aux", "debugger"}
CAVEAT = ("search-time, on the search/selection split each method selects on, not held-out; selection-split scores are "
          "optimistic and not comparable across methods (different splits, selection rules and visible feedback)")
EXCL_FILE = PAPER / "protocol" / "infra_exclusions.json"
FORBIDDEN = re.compile(r"(final_eval|/test|test_|eval_test)")


# ----------------------------------------------------------------------------- safe readers
def _ok(p):
    return not FORBIDDEN.search(str(p).replace(str(SCRATCH), ""))


def jl(p):
    p = Path(p)
    if not _ok(p) or not p.exists():
        return []
    rows = []
    try:
        for line in p.open(errors="replace"):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows


def js(p):
    p = Path(p)
    if not _ok(p) or not p.exists():
        return None
    try:
        return json.loads(p.read_text(errors="replace"))
    except (OSError, ValueError):
        return None


def num(x):
    try:
        return None if x in (None, "") else float(x)
    except (TypeError, ValueError):
        return None


def read_csv(p):
    try:
        return list(csv.DictReader(open(p)))
    except OSError:
        return []


# ----------------------------------------------------------------------------- recorded infrastructure exclusions
def _epoch(iso):
    import datetime as dt
    s = str(iso).replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def exclusions(suite, arm, seed):
    """{candidate: before_epoch}: that candidate's evaluation records earlier than before_epoch are infrastructure-missing."""
    j = js(EXCL_FILE) or {}
    return {e["candidate"]: _epoch(e["before_utc"]) for e in j.get("entries", [])
            if e["suite"] == suite and e["arm"] == arm and str(e["seed"]) == str(seed)}


def is_excluded(excl, cid, t):
    """t: epoch seconds, ISO string or None; a record with unknown time is excluded when the candidate is listed."""
    if not excl or cid not in excl:
        return False
    te = t if isinstance(t, (int, float)) else (_epoch(t) if t else None)
    return te is None or te < excl[cid]


# ----------------------------------------------------------------------------- run discovery
def capevolve_dir(sd):
    """Latest .capevolve/run_* under a seed dir that has a candidates.jsonl or state.json."""
    cands = sorted(Path(sd).glob(".capevolve/run_*"))
    cands = [c for c in cands if (c / "candidates.jsonl").exists() or (c / "state.json").exists()]
    return cands[-1] if cands else None


def discover():
    runs = []
    for suite, (root, base, arms) in SUITES.items():
        for dname, arm in arms.items():
            for s in SEEDS:
                sd = root / dname / s
                if not sd.exists():
                    continue
                runs.append({"suite": suite, "base": base, "arm": arm, "dir_name": dname, "seed": s[1:], "sd": sd,
                             "cap": capevolve_dir(sd) if arm in ("hc", "ao", "hcstock", "oneshot") else None})
    return runs


# ----------------------------------------------------------------------------- score extraction
def sel_score(ev):
    """(score, split, n, kind) of a full selection-split evaluation event, or None for minibatch/train/unscored."""
    s = ev.get("score")
    if not isinstance(s, dict):
        return None
    split = str(s.get("split") or "val")
    if "train" in split or s.get("kind") in ("minibatch", "mini"):
        return None
    v = None
    for k in ("value", "reward", "mean", "val"):
        if num(s.get(k)) is not None:
            v = num(s[k])
            break
    if v is None and num(s.get("value_pct")) is not None:
        v = num(s["value_pct"]) / 100.0
    if v is None:
        return None
    n = ev.get("n_tasks")
    if n is not None and n < 8:
        return None
    return v, re.sub(r"\(.*\)", "", split), n, s.get("stage")


def analyse_candidates(rows, excl=None):
    """Created/evaluated bookkeeping shared by every method's candidates.jsonl."""
    created, parent, sha, adir = {}, {}, {}, {}
    evals = []   # (rollout_index, id, score, split, n, stage)
    accepted, selected, rejected, missing = [], [], set(), set()
    for r in rows:
        cid = r.get("candidate_id")
        if cid is None:
            continue
        ev = r.get("event")
        if ev != "created" and is_excluded(excl, cid, r.get("t")):
            missing.add(cid)
            continue
        if ev == "created":
            if cid not in created:
                created[cid] = r.get("rollout_index") or 0
                parent[cid] = r.get("parent_id")
                sha[cid] = r.get("sha256")
                adir[cid] = r.get("artifact_dir")
        elif ev == "evaluated":
            sc = sel_score(r)
            if sc:
                evals.append((r.get("rollout_index") or 0, cid, sc[0], sc[1], sc[2], sc[3]))
            sha.setdefault(cid, r.get("sha256"))
            adir.setdefault(cid, r.get("artifact_dir"))
        elif ev == "accepted":
            accepted.append((r.get("rollout_index") or 0, cid, sel_score(r)))
        elif ev == "selected":
            selected.append((r.get("rollout_index") or 0, cid, sel_score(r)))
        elif ev == "rejected":
            rejected.add(cid)
    return dict(created=created, parent=parent, sha=sha, adir=adir, evals=sorted(evals, key=lambda e: e[0]),
                accepted=accepted, selected=selected, rejected=rejected, infra_missing=missing)


def seed_id(info):
    roots = [c for c in info["created"] if info["parent"].get(c) is None]
    for pref in ("seed", "base", "c0", "S0", "cand_0000"):
        if pref in info["created"]:
            return pref
    return min(roots, key=lambda c: info["created"][c]) if roots else None


def anytime(info, sid, champion_events):
    """best-so-far over scored candidates (best_seen) and the incumbent chain (champion), against counted rollouts."""
    pts, best, champ = [], None, None
    champ_at = {}
    for ri, cid, sc in champion_events:
        if sc is not None:
            champ_at.setdefault((ri, cid), sc[0])
    for ri, cid, v, split, n, stage in info["evals"]:
        best = v if best is None else max(best, v)
        if cid == sid and champ is None:
            champ = v
        elif (ri, cid) in champ_at:
            champ = champ_at[(ri, cid)]
        pts.append((ri, cid, v, best, champ))
    return pts


# ----------------------------------------------------------------------------- surfaces / diffs
def surface(rel):
    r = rel.replace("\\", "/")
    b = os.path.basename(r).lower()
    if b == "task_template.md":
        return "task_template"
    if r.startswith(("skills/", ".claude/skills/")) or b in ("skill.md", "skill_text.md", "packed_skill.md") or "/skills/" in r:
        return "skill_files"
    if "mcp" in r.lower():
        return "mcp"
    if r.endswith(".py") or r.startswith("tools/") or b.endswith((".sh", ".js", ".ts")):
        return "tool_code"
    if b in ("prompt.md", "policy.md", "system_prompt.md") or r.startswith("policy/"):
        return "system_prompt"
    if b in ("instructions.md", "process.md"):
        return "process_docs"
    if r.startswith("reference/"):
        return "reference"
    return "other"


SURFACES = ["system_prompt", "task_template", "tool_code", "mcp", "skill_files", "process_docs", "reference", "other"]


def tree(d):
    out = {}
    d = Path(d)
    if not d.is_dir():
        return None
    for dp, dn, fn in os.walk(d, onerror=lambda e: None):
        dn[:] = [x for x in dn if not x.startswith(".") and x not in ("__pycache__", "wiki", "node_modules")]
        for f in fn:
            if f in ("sha256.txt",) or f.startswith("."):
                continue
            p = Path(dp) / f
            try:
                if p.stat().st_size > 2_000_000:
                    continue
                out[str(p.relative_to(d))] = p.read_text(errors="replace").splitlines()
            except OSError:
                pass
    return out


def diff_surfaces(seed_dir, cand_dir):
    """Files and lines (added+removed) changed vs the seed, per surface.  Files absent from the candidate dir are ignored
    (frozen candidate dirs hold only the mutable surface); files new in the candidate count as all-added."""
    a, b = tree(seed_dir), tree(cand_dir)
    if a is None or b is None:
        return None
    files, lines = Counter(), Counter()
    for rel, new in b.items():
        old = a.get(rel)
        if old == new:
            continue
        sf = surface(rel)
        old = old or []
        d = [x for x in difflib.unified_diff(old, new, lineterm="", n=0) if x[:1] in "+-" and x[:3] not in ("+++", "---")]
        files[sf] += 1
        lines[sf] += len(d)
    return files, lines


# ----------------------------------------------------------------------------- events (CapEvolve gate behaviour)
def gate_events(cap, excl=None):
    out = dict(proposed=set(), screens=0, confirms=0, promoted=0, screen_reject=0, confirm_reject=0, gate_veto=0,
               indecisive_events=0, indecisive_cands=set(), steps=0, accepted=0, rejected=0, eval_errors=0,
               reasons=Counter(), by_cand={}, infra_missing=set())
    if not cap:
        return out
    last_step, last_prom = {}, {}
    for e in jl(cap / "events.jsonl"):
        k = e.get("kind")
        c_ = e.get("candidate") or e.get("tag") or e.get("id")
        if k in ("step", "promotion", "step_indecisive", "evaluate_error", "evaluate", "eval_start") and is_excluded(excl, c_, e.get("t")):
            out["infra_missing"].add(c_)
            continue
        if k == "step":
            last_step[e.get("candidate")] = e
        elif k == "promotion":
            last_prom[e.get("candidate")] = e
        elif k == "step_indecisive":
            out["indecisive_events"] += 1
            out["indecisive_cands"].add(e.get("candidate"))
            m = re.search(r"only (\d+)% of val tasks produced a valid score", e.get("reason") or "")
            out["reasons"]["coverage<0.95 (%s%%)" % m.group(1) if m else (e.get("reason") or "")[:60]] += 1
        elif k == "evaluate_error":
            out["eval_errors"] += 1
        elif k == "candidate_proposed":
            out["proposed"].add(e.get("id"))
    for c, e in last_prom.items():
        out["screens"] += 1 if e.get("screen") else 0
        out["confirms"] += 1 if e.get("confirm") else 0
        st = e.get("stage")
        if e.get("promote"):
            out["promoted"] += 1
            out["by_cand"][c] = "promoted"
        elif st in ("screen_reject", "confirm_reject", "gate_veto"):
            out[st] += 1
            out["by_cand"][c] = st
            if "INDECISIVE" in (e.get("reason") or ""):
                out["indecisive_cands"].add(c)
    for c, e in last_step.items():
        out["steps"] += 1
        if e.get("accept"):
            out["accepted"] += 1
        else:
            out["rejected"] += 1
        if c not in last_prom:   # no Rule P record: stock gate or agent-optimize accept/reject
            out["by_cand"][c] = "accepted" if e.get("accept") else "rejected"
            out["screens"] += 1 if e.get("val") is not None else 0
    return out


# ----------------------------------------------------------------------------- metrics join
def load_metrics():
    arm_rows = {}
    for r in read_csv(METRICS / "metrics_by_arm.csv"):
        if r["category"] in ("main",):
            arm_rows[(r["suite"], r["arm"], r["seed"])] = r
    role = defaultdict(lambda: Counter())
    for r in read_csv(METRICS / "metrics_by_role.csv"):
        if r["category"] not in ("main", "chaser_eval") or r["role"] not in OPT_ROLES:
            continue
        k = (r["suite"], r["arm"], r["seed"])
        iu, cr, o = int(r["in_uncached"] or 0), int(r["cache_read"] or 0), int(r["output"] or 0)
        cw = int(r["cache_write_5m"] or 0) + int(r["cache_write_1h"] or 0)
        role[k]["noncache"] += iu + o + cw
        role[k]["cache_read"] += cr
        role[k]["cache_write"] += cw
        role[k]["calls"] += int(r["calls"] or 0)
        if r["priced"] == "True":
            role[k]["usd"] += float(r["usd_total"] or 0)
        else:
            role[k]["unpriced_noncache"] += iu + o + cw
    return arm_rows, role


def pid_alive(p):
    try:
        pid = int(Path(p).read_text().split()[0])
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, IndexError):
        return False


def status_of(r, mrow, cap, info):
    sd = r["sd"]
    if mrow and mrow.get("active") == "True":
        return "running"
    if not mrow:
        for pf in list(sd.glob("*.pid")) + list(sd.glob("logs/*.pid")):
            if pid_alive(pf):
                return "running"
    if list(sd.glob("run_summary.crash*")):
        return "crash"
    for lg in list(sd.glob("logs/*.err")) + [sd / "hc.err"]:
        if lg.exists() and re.search(r"Traceback|RuntimeError", "".join(lg.read_text(errors="replace").splitlines(True)[-40:])):
            return "crash"
    g = sd / "guard.log"
    if g.exists() and re.search(r"(stop|kill|abort|exceed|cap)", g.read_text(errors="replace"), re.I):
        return "guard stop"
    for lg in (sd / "run.log", sd / "launcher.log"):
        if lg.exists():
            tail = "".join(lg.read_text(errors="replace").splitlines(True)[-60:])
            if re.search(r"Traceback|FATAL|CRASH", tail):
                return "crash"
    if cap and js(cap / "state.json"):
        st = js(cap / "state.json")
        b, sp = st.get("budget", {}), st.get("spent", {})
        if b.get("max_metric_calls") and sp.get("metric_calls", 0) >= b["max_metric_calls"]:
            return "native finish (budget)"
        if b.get("max_iterations") and sp.get("iterations", 0) >= b["max_iterations"]:
            return "native finish (iterations)"
    if r["arm"] in ("oneshot", "seed"):
        return "native finish"
    if cap and any(e.get("kind") == "finalize" for e in jl(cap / "events.jsonl")):
        return "native finish"
    if (sd / "run_summary.json").exists() or (sd / "final").is_dir() and any((sd / "final").iterdir()):
        return "native finish"
    if mrow and mrow.get("counted_rollouts"):
        return "stopped (unclassified)"
    return "unknown"


# ----------------------------------------------------------------------------- per-run record
def run_record(r, arm_rows, role):
    suite, arm, s, sd, cap = r["suite"], r["arm"], r["seed"], r["sd"], r["cap"]
    mkey = (suite, METRIC_ARM.get(arm, arm), s)
    mrow = arm_rows.get(mkey)
    rec = {"suite": suite, "base_suite": r["base"], "arm": arm, "seed": s, "run_dir": str(sd.relative_to(SCRATCH))}
    crows = jl((cap or sd) / "candidates.jsonl") if arm != "seed" else []
    if arm == "bestofk":
        crows = jl(sd / "candidates.jsonl")
    excl = exclusions(suite, arm, s)
    info = analyse_candidates(crows, excl)
    sid = seed_id(info)
    state = js(cap / "state.json") if cap else None
    rec["counted_rollouts"] = int(float(mrow["counted_rollouts"])) if mrow and mrow.get("counted_rollouts") else None
    rec["counted_source"] = mrow.get("counted_source") if mrow else None
    if rec["counted_rollouts"] is None and arm == "bestofk":
        pr = js(sd / "progress.json")
        rec["counted_rollouts"] = pr.get("counted") if pr else None
        rec["counted_source"] = "progress.json:counted"
    evs = info["evals"]
    rec["split"] = None
    if evs:
        sp = Counter((e[3], e[4]) for e in evs if e[4])
        sname, n = (sp.most_common(1)[0][0] if sp else (evs[0][3], None))
        rec["split"] = "%s-%s" % (sname, n) if n else sname
    if not rec["split"] or rec["split"] in ("val", "opt", "sel"):
        ve = ((state or {}).get("screening_economics") or {}).get("val_n")
        if ve:
            rec["split"] = "%s-%s" % (rec["split"] or ("opt" if r["base"] in ("B", "C") else "val"), ve)
    seed_score = None
    if arm == "seed":
        for nm, key in (("eval_opt.json", "opt"), ("eval_sel.json", "sel")):
            j = js(sd / nm)
            if j and j.get("mean_reward") is not None:
                rec["seed_" + key] = j["mean_reward"]
                rec["split_" + key] = "%s-%s" % (key, j.get("n_tasks"))
        rec["rollouts_note"] = "seed re-scored on opt and sel (2 trials), no search"
    if sid:
        se = [e for e in evs if e[1] == sid]
        seed_score = se[0][2] if se else None
    if seed_score is None and state and state.get("spent", {}).get("best_val") is not None and state.get("best_id") == "seed":
        seed_score = state["spent"]["best_val"]
    if seed_score is None and cap:
        for e in jl(cap / "events.jsonl"):
            if e.get("kind") == "baseline" and e.get("val") is not None:
                seed_score = e["val"]
                break
    if seed_score is None and arm == "bestofk":
        sib = [x for x in (RUNS / "E12C" / "hcstock" / ("s" + s)).glob(".capevolve/run_*/events.jsonl")]
        for p in sib:
            for e in jl(p):
                if e.get("kind") == "baseline" and e.get("val") is not None:
                    seed_score = e["val"]
                    rec["seed_note"] = "seed split score taken from the paired hcstock run (same opt split)"
                    break
    rec["seed_score"] = seed_score
    # champion = the artifact the method itself would return
    champ_id, champ_score = None, None
    if arm in CAPEVOLVE or arm == "oneshot":
        if state:
            champ_id, champ_score = state.get("best_id"), state.get("spent", {}).get("best_val")
    elif arm == "bestofk":
        pr = js(sd / "progress.json") or {}
        res = pr.get("results", {})
        if res:
            k = max(res, key=lambda x: res[x].get("opt_score", -1))
            champ_id, champ_score = "prop_%02d" % int(k), res[k]["opt_score"]
            for x in res:
                info["evals"].append((0, "prop_%02d" % int(x), res[x]["opt_score"], "opt", None, None))
            info["evals"].sort(key=lambda e: e[0])
    else:
        sel = [x for x in info["selected"] if x[2]]
        if sel:
            champ_id, champ_score = sel[-1][1], sel[-1][2][0]
        elif evs:
            b = max(evs, key=lambda e: (e[2], -e[0]))
            champ_id, champ_score = b[1], b[2]
    rec["champion_id"], rec["champion_score"] = champ_id, champ_score
    rec["champion_gain_vs_seed"] = (champ_score - seed_score) if champ_score is not None and seed_score is not None else None
    csha = info["sha"].get(champ_id)
    ssha = info["sha"].get(sid) if sid else None
    rec["returned_equals_seed"] = (None if champ_id is None else (champ_id == sid or (csha is not None and csha == ssha)))
    rec["final_dir_present"] = (sd / "final").is_dir() and any((sd / "final").iterdir()) if (sd / "final").is_dir() else False
    gen = [c for c in info["created"] if c != sid]
    scr = {e[1] for e in evs if e[1] != sid}
    rec["candidates_generated"] = len(gen) if gen else (len(prop_dirs(sd)) if arm == "bestofk" else 0)
    rec["candidates_screened"] = len(scr)
    if arm in CAPEVOLVE or arm == "oneshot":
        ge = gate_events(cap, excl)
        info["infra_missing"] |= ge["infra_missing"]
        rec["candidates_promoted"] = ge["promoted"] if (ge["promoted"] or ge["screens"] and ge["by_cand"] and
                                                         any(v == "promoted" for v in ge["by_cand"].values())) else ge["accepted"]
        if arm in ("ao", "oneshot"):
            rec["candidates_promoted"] = ge["accepted"]
    else:
        acc = {c for _, c, _ in info["accepted"] if c != sid}
        rec["candidates_promoted"] = len(acc or {c for _, c, _ in info["selected"] if c != sid})
    rec["infra_lost_attempts"] = len(info["infra_missing"])   # attempts lost to infrastructure (a retried candidate counts once here)
    rec["infra_missing_ids"] = ",".join(sorted(info["infra_missing"]))
    info["infra_full"] = {c for c, t in excl.items() if t and t > 4e9}   # candidates with no valid record at all
    rec["infra_lost_candidates"] = len(info["infra_full"])
    rec["optimizer_noncache_tokens"] = role[mkey]["noncache"] if mkey in role else None
    rec["optimizer_cache_read_tokens"] = role[mkey]["cache_read"] if mkey in role else None
    rec["optimizer_cache_write_tokens"] = role[mkey]["cache_write"] if mkey in role else None
    rec["optimizer_usd"] = round(role[mkey]["usd"], 4) if mkey in role else None
    rec["optimizer_unpriced_noncache_tokens"] = role[mkey]["unpriced_noncache"] if mkey in role else None
    rec["wall_clock_h"] = num(mrow.get("wall_clock_h_since_launch")) if mrow else None
    rec["status"] = status_of(r, mrow, cap, info)
    rec["last_gateway_call"] = mrow.get("last_call") if mrow else None
    if arm in ("ace", "harnesslens"):
        rec["note"] = "no candidate/selection step recorded (online playbook / pre-search trace phase): no champion score"
    cs = []
    if arm in CAPEVOLVE or arm == "oneshot":
        cs = [(a, b, c) for a, b, c in info["accepted"]]
    return rec, info, sid, cs


def prop_dirs(sd):
    return sorted(p for p in Path(sd).glob("prop_*") if p.is_dir())


# ----------------------------------------------------------------------------- edits
def edits(runs_meta):
    cand_rows, arm_agg = [], defaultdict(lambda: dict(n=0, files=Counter(), lines=Counter(), touch=Counter()))
    for rec, info, sid, _ in runs_meta:
        if rec["arm"] in ("seed", "ace", "harnesslens") or not sid:
            continue
        seed_dir = info["adir"].get(sid)
        for c in info["created"]:
            if c == sid or c in info.get("infra_full", ()):
                continue
            cd = info["adir"].get(c)
            if not cd or not seed_dir:
                continue
            d = diff_surfaces(seed_dir, cd)
            if d is None:
                cand_rows.append(dict(suite=rec["suite"], arm=rec["arm"], seed=rec["seed"], candidate=c, available=False))
                continue
            f, l = d
            cr = dict(suite=rec["suite"], arm=rec["arm"], seed=rec["seed"], candidate=c, available=True,
                      is_champion=(c == rec["champion_id"]),
                      files_total=sum(f.values()), lines_total=sum(l.values()))
            for sf in SURFACES:
                cr["files_" + sf], cr["lines_" + sf] = f.get(sf, 0), l.get(sf, 0)
            cand_rows.append(cr)
            a = arm_agg[(rec["suite"], rec["arm"])]
            a["n"] += 1
            for sf in SURFACES:
                a["files"][sf] += f.get(sf, 0)
                a["lines"][sf] += l.get(sf, 0)
                a["touch"][sf] += 1 if f.get(sf, 0) else 0
    return cand_rows, arm_agg


# ----------------------------------------------------------------------------- writers
def wcsv(path, rows, cols=None):
    if not rows:
        return
    cols = cols or list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def tex(s):
    return (str(s).replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%").replace("_", "\\_")
            .replace("#", "\\#").replace("<", "$<$").replace(">", "$>$"))


def f2(x, d=2):
    return "--" if x is None else ("%.*f" % (d, x))


def msr(vals, d=2, pct=False):
    v = [x for x in vals if x is not None]
    if not v:
        return "--"
    m = statistics.mean(v)
    if len(v) == 1:
        return f2(m, d)
    return "%s {\\tiny[%s,%s]}" % (f2(m, d), f2(min(v), d), f2(max(v), d))


ARM_ORDER = ["seed", "oneshot", "gepa", "skillopt", "metaharness", "evoskill", "wikiskill", "trace2skill", "ace", "mipro",
             "harnesslens", "hc", "ao", "hcstock", "bestofk"]


def arm_label(a):
    try:
        import common
        return common.ARMS[a][0] if a in common.ARMS else {"bestofk": "Best-of-$k$"}.get(a, a)
    except Exception:
        return a


def build_summary_tables(recs):
    paths = []
    for base in ("A", "B", "C"):
        rs = [r for r in recs if r["base_suite"] == base and r["arm"] != "seed"]
        arms = sorted({r["arm"] for r in rs}, key=ARM_ORDER.index)
        splits = {}
        for a in arms:
            sp = Counter(r["split"] for r in rs if r["arm"] == a and r["split"])
            splits[a] = sp.most_common(1)[0][0] if sp else "--"
        lines = []
        for a in arms:
            xs = [r for r in rs if r["arm"] == a]
            nseed = len(xs)
            lines.append("%s & %s & %d & %s & %s & %s & %s & %s & %s & %s & %s & %s \\\\" % (
                arm_label(a), tex(splits[a]), nseed,
                msr([r["counted_rollouts"] for r in xs], 0),
                msr([r["seed_score"] for r in xs]),
                msr([r["champion_score"] for r in xs]),
                "%d/%d/%d" % tuple(sum((r["candidates_" + k] or 0) for r in xs) for k in ("generated", "screened", "promoted")),
                "%d/%d" % (sum(1 for r in xs if r["returned_equals_seed"]), sum(1 for r in xs if r["returned_equals_seed"] is not None)),
                msr([(r["optimizer_noncache_tokens"] or 0) / 1e6 if r["optimizer_noncache_tokens"] is not None else None for r in xs], 2),
                msr([r["optimizer_usd"] for r in xs], 2),
                msr([r["wall_clock_h"] for r in xs], 1),
                tex(Counter(r["status"] for r in xs).most_common(1)[0][0]) +
                (" (%d)" % len(set(r["status"] for r in xs)) if len({r["status"] for r in xs}) > 1 else "")))
        sname = {"A": "Suite A (SpreadsheetBench)", "B": "Suite B ($\\tau^2$ retail)", "C": "Suite C ($\\tau^2$ airline)"}[base]
        body = "\n".join(lines)
        t = r"""\begin{table*}[t]
\centering
\scriptsize
\caption{%s: latest %s. Search-time, on each method's own selection split (column Split), not held-out. Cells are the mean over seeds with [min,max]. Champion is the artifact the method itself would return, scored on its own selection split; seed is the seed artifact on the same split. Gen/scr/prom: candidates generated, scored on the selection split, promoted (summed over seeds); candidates lost to infrastructure (protocol/infra\_exclusions.json) count as generated only. Seed-eq.: returned artifact equals the seed. Opt.\ tok.: optimizer non-cache-read tokens (M). Selection-split scores are optimistic and not comparable across methods.}
\label{tab:searchtime-summary-%s}
\begin{tabular}{@{}llrrrrrrrrrl@{}}
\toprule
Arm & Split & Seeds & Rollouts & Seed & Champion & Gen/scr/prom & Seed-eq. & Opt.\ tok. & USD & Wall h & Status \\
\midrule
%s
\bottomrule
\end{tabular}
\end{table*}
""" % (sname, "run state", base.lower(), body)
        p = TABLES / ("searchtime_summary_%s.tex" % base)
        p.write_text(t)
        paths.append(p)
    return paths


def build_edit_table(arm_agg):
    rows = []
    for (suite, arm), a in sorted(arm_agg.items(), key=lambda kv: (kv[0][0], ARM_ORDER.index(kv[0][1]))):
        if not a["n"]:
            continue
        tot = sum(a["lines"][x] for x in SHARE_SURFACES) or 1
        cells = " & ".join("%d (%s)" % (a["touch"][s], ("%d\\%%" % round(100.0 * a["lines"][s] / tot)) if s in SHARE_SURFACES else "--") for s in
                           ("system_prompt", "task_template", "tool_code", "mcp", "skill_files", "process_docs", "reference"))
        rows.append("%s & %s & %d & %s \\\\" % (tex(suite), arm_label(arm), a["n"], cells))
    t = r"""\begin{table*}[t]
\centering
\scriptsize
\caption{Edits by capability surface, diffed against the seed artifact (search-time, all candidates generated so far on each run's search split, not held-out). Each cell is the number of candidates whose diff touches the surface, with the share of changed capability lines in parentheses (process docs and reference files are not capability edits and are excluded from the shares; PROCESS.md and INSTRUCTIONS.md are the per-iteration explainability files CapEvolve requires). Surfaces are assigned by path: system prompt (prompt, policy), task template, tool code (tools/, *.py), MCP, skill files, process docs (PROCESS.md, INSTRUCTIONS.md), reference. Candidate counts include rejected candidates, and only candidates whose artifact directory is still on disk.}
\label{tab:searchtime-edits}
\begin{tabular}{@{}llrlllllll@{}}
\toprule
Suite & Arm & Cands & Sys.\ prompt & Task tmpl. & Tool code & MCP & Skills & Proc.\ docs & Ref. \\
\midrule
%s
\bottomrule
\end{tabular}
\end{table*}
""" % "\n".join(rows)
    # column alignment: 3 leading cols + 7 surfaces = 10
    p = TABLES / "searchtime_edits.tex"
    p.write_text(t)
    return p


def build_gate_table(gate_rows):
    rows = []
    for g in gate_rows:
        rows.append("%s & %s & %s & %d & %d & %d & %d & %d & %d & %d & %d & %d \\\\" % (
            tex(g["suite"]), arm_label(g["arm"]), g["seed"], g["candidates"], g["screens"], g["confirms"], g["promoted"],
            g["screen_reject"] + g["confirm_reject"] + g["rejected_other"], g["gate_veto"], g["indecisive"], g["infra_lost_candidates"], g["infra_lost_attempts"]))
    t = r"""\begin{table*}[t]
\centering
\scriptsize
\caption{Gate behaviour per CapEvolve search (search-time, on each run's own search split, not held-out). Rule P: screens and confirmations run, promotions, rejections (screen, confirm, or rejected outright by the driver), vetoes (indecisive at the gate), and indecisive events (valid-score coverage below 0.95). Lost cands: candidates with no valid evaluation because infrastructure failed them (protocol/infra\_exclusions.json), not counted as rejections. Lost attempts: evaluation attempts lost to infrastructure; a candidate that failed once and was retried successfully counts one lost attempt and zero lost candidates, so attempts can exceed candidates screened. Rows for the stock-gate ablation (E12, paired with Rule P on Suites A and C) have a single-stage accept/reject, so confirmations are 0.}
\label{tab:searchtime-gate}
\resizebox{\textwidth}{!}{%%
\begin{tabular}{@{}llrrrrrrrrrr@{}}
\toprule
Suite & Arm & Seed & Cands & Screens & Confirms & Promoted & Rejected & Vetoed & Indecisive & Lost cands & Lost attempts \\
\midrule
%s
\bottomrule
\end{tabular}}
\end{table*}
""" % "\n".join(rows)
    p = TABLES / "searchtime_gate.tex"
    p.write_text(t)
    return p


def build_infra_table(infra):
    rows = []
    for r in infra:
        rows.append("%s & %s & %d & %d & %d & %d & %d & %s \\\\" % (
            tex(r["suite"]), arm_label(r["arm"]), r["rollouts"], r["errors"], r["uniform_infra"], r["uniform_candidate_error"],
            r["uniform_unverifiable"], "%.1f" % (100.0 * r["uniform_infra"] / r["rollouts"]) if r["rollouts"] else "--"))
    t = r"""\begin{table*}[t]
\centering
\scriptsize
\caption{Infrastructure and error labels per arm under the uniform classifier (search-time rollouts on the search/selection splits, not held-out; main and chaser rows summed over seeds). Errors: rollouts with an error string or label; infra: transport, timeout or sandbox errors, or zero target-LLM calls with an error; cand.: candidate-caused errors; unver.: unverifiable. Infra\%% is infra errors over counted rollouts.}
\label{tab:searchtime-infra}
\begin{tabular}{@{}llrrrrrr@{}}
\toprule
Suite & Arm & Rollouts & Errors & Infra & Cand. & Unver. & Infra\%% \\
\midrule
%s
\bottomrule
\end{tabular}
\end{table*}
""" % "\n".join(rows)
    p = TABLES / "searchtime_infra.tex"
    p.write_text(t)
    return p


# ----------------------------------------------------------------------------- figures
def figures(any_rows, arm_agg, gate_rows):
    try:
        import common
        common.style()
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print("figures skipped:", e)
        return []
    outs = []
    by = defaultdict(lambda: defaultdict(list))
    for r in any_rows:
        by[r["base_suite"]][(r["arm"], r["suite"], r["seed"])].append(r)
    fig, axes = plt.subplots(1, 3, figsize=(common.FULL_W, 2.5), sharey=False)
    for ax, base in zip(axes, "ABC"):
        for (arm, suite, seed), pts in sorted(by[base].items()):
            if arm not in common.ARMS or arm == "seed":
                continue
            pts = sorted(pts, key=lambda p: p["rollout_index"])
            lab, col, mk = common.ARMS[arm]
            xs = [0] + [p["rollout_index"] for p in pts]
            ys = [pts[0]["seed_score"] if pts[0]["seed_score"] is not None else pts[0]["best_seen"]] + [p["best_seen"] for p in pts]
            ax.step(xs, ys, where="post", color=col, lw=common.lw(arm), alpha=common.alpha(arm) * (1.0 if seed == "0" else 0.6),
                    label=lab if seed == "0" else None)
        ax.set_title(common.SUITE_NAME[base], fontsize=8)
        ax.set_xlabel("counted rollouts")
    axes[0].set_ylabel("best-so-far selection score")
    h, l = axes[0].get_legend_handles_labels()
    for ax in axes[1:]:
        hh, ll = ax.get_legend_handles_labels()
        for a, b in zip(hh, ll):
            if b not in l:
                h.append(a)
                l.append(b)
    fig.legend(h, l, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.2))
    fig.suptitle("Search-time, own selection split per method, not held-out", fontsize=7.5, y=1.02)
    p = FIGS / "searchtime_anytime.pdf"
    fig.savefig(p)
    plt.close(fig)
    outs.append(p)
    # edits by surface
    cols = {"system_prompt": "#0072B2", "task_template": "#56B4E9", "tool_code": "#D55E00", "mcp": "#CC79A7",
            "skill_files": "#009E73", "process_docs": "#E69F00", "reference": "#999999", "other": "#000000"}
    keys = [k for k in sorted(arm_agg, key=lambda k: (k[0], ARM_ORDER.index(k[1]))) if arm_agg[k]["n"]]
    fig, ax = plt.subplots(figsize=(common.FULL_W, 2.6))
    bottoms = [0.0] * len(keys)
    for sf in SHARE_SURFACES:
        vals = []
        for k in keys:
            tot = sum(arm_agg[k]["lines"][x] for x in SHARE_SURFACES) or 1
            vals.append(100.0 * arm_agg[k]["lines"][sf] / tot)
        if any(vals):
            ax.bar(range(len(keys)), vals, bottom=bottoms, color=cols[sf], label=sf.replace("_", " "), width=0.7)
            bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(["%s %s" % (k[0], common.ARMS.get(k[1], (k[1],))[0].replace("CapEvolve ", "CE ").replace(", stock gate", " stock")) for k in keys],
                       fontsize=6, rotation=90)
    ax.set_ylabel("share of changed capability lines (%)")
    ax.legend(ncol=4, frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 1.3))
    ax.grid(axis="x", visible=False)
    ax.text(0.99, 1.07, "Search-time, all candidates vs the seed, not held-out", transform=ax.transAxes, ha="right", fontsize=6.5)
    p = FIGS / "searchtime_surface.pdf"
    fig.savefig(p)
    plt.close(fig)
    outs.append(p)
    # gate outcomes
    cat = [("promoted", "#0072B2"), ("screen_reject", "#E69F00"), ("confirm_reject", "#D55E00"), ("rejected_other", "#999999"),
           ("gate_veto", "#CC79A7")]
    labs = ["%s %s s%s" % (g["suite"], g["arm"], g["seed"]) for g in gate_rows]
    fig, ax = plt.subplots(figsize=(common.FULL_W, 2.6))
    bot = [0] * len(gate_rows)
    for k, c in cat:
        v = [g[k] for g in gate_rows]
        if any(v):
            ax.bar(range(len(v)), v, bottom=bot, color=c, label=k.replace("_", " "), width=0.75)
            bot = [a + b for a, b in zip(bot, v)]
    ax.set_xticks(range(len(labs)))
    ax.set_xticklabels(labs, rotation=90, fontsize=5.5)
    ax.set_ylabel("candidates")
    ax.legend(ncol=5, frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    ax.grid(axis="x", visible=False)
    ax.text(0.99, 1.02, "Search-time, own search split, not held-out", transform=ax.transAxes, ha="right", fontsize=6.5)
    p = FIGS / "searchtime_gate.pdf"
    fig.savefig(p)
    plt.close(fig)
    outs.append(p)
    return outs


# ----------------------------------------------------------------------------- main
def st_excl(rec):
    return exclusions(rec["suite"], rec["arm"], rec["seed"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    arm_rows, role = load_metrics()
    meta, any_rows, gate_rows, compare = [], [], [], []
    for r in discover():
        rec, info, sid, cs = run_record(r, arm_rows, role)
        meta.append((rec, info, sid, cs))
        if r["arm"] in ("seed",):
            continue
        cap = r["cap"]
        if info["evals"]:
            for ri, cid, v, best, champ in anytime(info, sid, cs):
                any_rows.append(dict(suite=rec["suite"], base_suite=rec["base_suite"], arm=rec["arm"], seed=rec["seed"],
                                     rollout_index=ri, candidate=cid, score=v, best_seen=best, champion=champ,
                                     seed_score=rec["seed_score"], split=rec["split"]))
        if r["arm"] in ("hc", "hcstock", "ao"):
            ge = gate_events(cap, st_excl(rec))
            bc = ge["by_cand"]
            gate_rows.append(dict(
                suite=rec["suite"], arm=rec["arm"], seed=rec["seed"], candidates=rec["candidates_generated"],
                screens=ge["screens"], confirms=ge["confirms"],
                promoted=sum(1 for v in bc.values() if v in ("promoted", "accepted")),
                screen_reject=ge["screen_reject"], confirm_reject=ge["confirm_reject"],
                rejected_other=sum(1 for v in bc.values() if v == "rejected"), gate_veto=ge["gate_veto"],
                indecisive=len(ge["indecisive_cands"]), indecisive_events=ge["indecisive_events"],
                indecisive_reasons="; ".join("%s x%d" % kv for kv in ge["reasons"].items()),
                eval_errors=ge["eval_errors"], infra_lost_attempts=len(set(ge["infra_missing"]) | set(filter(None, rec["infra_missing_ids"].split(",")))),
                infra_lost_candidates=rec["infra_lost_candidates"], split=rec["split"], champion_score=rec["champion_score"],
                seed_score=rec["seed_score"], gate=("stock (paired dbar > 1 SE, single stage)" if rec["arm"] == "hcstock" else
                                                    "agent-optimize (driver judgement)" if rec["arm"] == "ao" else "Rule P (screen + fresh confirm)")))
    recs = [m[0] for m in meta]
    wcsv(OUT / "runs.csv", recs)
    wcsv(OUT / "anytime.csv", any_rows)
    wcsv(OUT / "gate_by_run.csv", gate_rows)
    # rule P vs stock at search time (E12): Suites A and C
    for base in ("A", "C"):
        for g in gate_rows:
            if g["suite"] in (base, base + "-E12") and g["arm"] in ("hc", "hcstock"):
                compare.append(dict(g, base_suite=base, gain_vs_seed=(g["champion_score"] - g["seed_score"])
                                    if g["champion_score"] is not None and g["seed_score"] is not None else None))
    wcsv(OUT / "gate_compare.csv", compare)
    cand_rows, arm_agg = edits(meta)
    wcsv(OUT / "edits_by_candidate.csv", cand_rows)
    agg_rows = []
    for (suite, arm), a in sorted(arm_agg.items()):
        row = dict(suite=suite, arm=arm, candidates=a["n"])
        for sf in SURFACES:
            row["cands_touching_" + sf], row["files_" + sf], row["lines_" + sf] = a["touch"][sf], a["files"][sf], a["lines"][sf]
        agg_rows.append(row)
    wcsv(OUT / "edits_by_arm.csv", agg_rows)
    # infra from error_label_parity.csv (main + chaser rows, per arm)
    inf = defaultdict(Counter)
    for r in read_csv(METRICS / "error_label_parity.csv"):
        if r["category"] not in ("main", "chaser_eval"):
            continue
        k = (r["suite"], r["arm"])
        for f in ("rollouts", "errors", "uniform_infra", "uniform_candidate_error", "uniform_unverifiable"):
            inf[k][f] += int(float(r[f] or 0))
    infra = [dict(suite=k[0], arm=k[1], **{f: v[f] for f in v}) for k, v in sorted(inf.items())
             if k[1] in ARM_ORDER or k[1] in ("ctl-oneshot", "ctl-seed")]
    for i in infra:
        i["arm"] = {"ctl-oneshot": "oneshot", "ctl-seed": "seed"}.get(i["arm"], i["arm"])
        i.setdefault("uniform_candidate_error", 0)
    infra = [i for i in infra if i["arm"] in ARM_ORDER]
    infra.sort(key=lambda i: (i["suite"], ARM_ORDER.index(i["arm"])))
    wcsv(OUT / "infra_by_arm.csv", infra)
    TABLES.mkdir(exist_ok=True)
    FIGS.mkdir(exist_ok=True)
    tpaths = build_summary_tables(recs) + [build_edit_table(arm_agg), build_gate_table(gate_rows), build_infra_table(infra)]
    fpaths = figures(any_rows, arm_agg, gate_rows)
    newest = max([r["last_gateway_call"] for r in recs if r.get("last_gateway_call")] or [""])
    (OUT / "searchtime.json").write_text(json.dumps(dict(
        caveat=CAVEAT, newest_gateway_call=newest, metrics_dir=str(METRICS.relative_to(PAPER)),
        runs=recs, gate=gate_rows, edits_by_arm=agg_rows, infra=infra), indent=1, default=str))
    write_md(recs, gate_rows, agg_rows, infra, compare, newest)
    print("wrote", OUT)
    for p in tpaths + fpaths:
        print("wrote", p)


def write_md(recs, gate_rows, agg_rows, infra, compare, newest):
    L = ["# Search-time results (latest run state)", "",
         "Data: run artifacts under campaign-scratch/runs and analysis/out/metrics, newest gateway call %s. Regenerate with "
         "`analysis/scripts/searchtime_results.py`." % newest, "",
         "**Caveat.** Every number here is search-time, on the search/selection split of its own method, not held-out. "
         "Selection-split scores are optimistic and not comparable across methods: GEPA selects the best candidate on its "
         "selection split, Meta-Harness's proposer saw val aggregates, CapEvolve screens on its own split, and Suites B and C use "
         "different split sizes per method. No cross-method ranking may be drawn from these numbers. Final results exist only after "
         "the 2026-10-13 06:00 UTC cutoff.", "", "## Per arm and seed", "",
         "| suite | arm | seed | split | rollouts | seed score | champion (id) | gain | gen/scr/prom | returned=seed | opt tok (non-cache) | cache read | USD | wall h | status |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in recs:
        L.append("| %s | %s | %s | %s | %s | %s | %s (%s) | %s | %s/%s/%s | %s | %s | %s | %s | %s | %s |" % (
            r["suite"], r["arm"], r["seed"], r.get("split") or ("opt/sel" if r["arm"] == "seed" else "--"), r["counted_rollouts"],
            (f2(r["seed_score"], 3) if r["arm"] != "seed" else "opt %s / sel %s" % (f2(r.get("seed_opt"), 3), f2(r.get("seed_sel"), 3))), f2(r["champion_score"], 3), r["champion_id"] or "--",
            f2(r["champion_gain_vs_seed"], 3), r["candidates_generated"], r["candidates_screened"], r["candidates_promoted"],
            r["returned_equals_seed"], r["optimizer_noncache_tokens"], r["optimizer_cache_read_tokens"], r["optimizer_usd"],
            f2(r["wall_clock_h"], 1), r["status"]))
    L += ["", "Notes: champion = what the method itself would return (CapEvolve: state best_id/best_val; GEPA, MIPRO, others: last selected "
          "or argmax of full selection-split evaluations). ACE and HarnessLens have no candidate/selection step yet. "
          "Optimizer USD covers priced (Claude) calls only; unpriced tokens are in runs.csv.", "", "## Gate behaviour (CapEvolve)", "",
          "| suite | arm | seed | cands | screens | confirms | promoted | rejected | vetoed | indecisive (reasons) | lost cands | lost attempts |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in gate_rows:
        L.append("| %s | %s | %s | %d | %d | %d | %d | %d | %d | %d %s | %d | %d |" % (
            g["suite"], g["arm"], g["seed"], g["candidates"], g["screens"], g["confirms"], g["promoted"],
            g["screen_reject"] + g["confirm_reject"] + g["rejected_other"], g["gate_veto"], g["indecisive"], g["indecisive_reasons"], g["infra_lost_candidates"], g["infra_lost_attempts"]))
    L += ["", "## Edits by capability surface (candidates touching surface / changed lines)", "",
          "| suite | arm | cands | " + " | ".join(SURFACES) + " |", "|---|---|---|" + "---|" * len(SURFACES)]
    for a in agg_rows:
        L.append("| %s | %s | %d | %s |" % (a["suite"], a["arm"], a["candidates"], " | ".join(
            "%d / %d" % (a["cands_touching_" + s], a["lines_" + s]) for s in SURFACES)))
    L += ["", "## Infra and errors (uniform classifier, main + chaser rows)", "",
          "| suite | arm | rollouts | errors | infra | candidate | unverifiable |", "|---|---|---|---|---|---|---|"]
    for i in infra:
        L.append("| %s | %s | %d | %d | %d | %d | %d |" % (i["suite"], i["arm"], i["rollouts"], i["errors"], i["uniform_infra"],
                                                      i["uniform_candidate_error"], i["uniform_unverifiable"]))
    (OUT / "summary.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
