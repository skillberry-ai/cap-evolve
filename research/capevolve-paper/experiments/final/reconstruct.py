#!/usr/bin/env python3
"""reconstruct.py: the artifact each arm's OWN native selection rule returns (a) at the matched budget B* and (b) at the cutoff.

Read-only on run directories.  Inputs: <run>/candidates.jsonl (matched-checkpoint protocol, CHECKPOINT_PROTOCOL.txt; written
natively or by the owners' converters baselines/code/to_candidates.py, E10B/cand_logger.py, ...) plus the few arm-specific native
logs named below.  Outputs, per suite:
  <FINAL_ROOT>/<S>/artifacts/{seed,B,END}/[<arm>/s<k>/]...   frozen copies (read-only) of the canonical artifact files
  manifests/artifacts_<S>.json                                   manifest with content hashes, status, evidence, rule + source line

    reconstruct.py --suite A --bstar-file manifests/bstar_A.json [--mode B,END] [--out-root DIR] [--no-copy]

Rule vocabulary (one function per arm, see RULES).  Every rule consumes only events whose rollout_index <= limit (limit = B*,
or infinity for the end-of-run artifact) and drops a candidate whose evaluation straddles the limit (an `evaluated` event is
written at the END of the evaluation, so rollout_index <= limit already implies the whole evaluation lies inside the first
`limit` counted rollouts; events that also carry start_rollout_index are checked explicitly).

Status per cell:  ok         rule replayed exactly from logged events;
                  partial    rule replayed, but a documented approximation applies (see `caveats`: reconstructed rollout
                             indexes, budget-coupled schedule not replayable, tie-break unverified, ...);
                  impossible the logs cannot support the rule at this limit; no artifact is emitted (never a guess).
A cell with nothing qualifying falls back to the arm's own seed candidate and says so (`fallback_seed`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402

INF = float("inf")
_BSTAR_RUNS = []          # runs list of the bstar file in use (own counters for the comparison point)


# ----------------------------------------------------------------------------------------------------------- events
class Ev(dict):
    pass


def event_time(e):
    t = e.get("t")
    if not isinstance(t, str):
        return None
    import datetime as dt
    try:
        x = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=dt.timezone.utc)
        return x
    except Exception:
        return None


def sval(e):
    """selection score of an event as a float in [0,1], or None"""
    s = e.get("score")
    if not isinstance(s, dict):
        return None
    for k in ("value", "mean", "reward"):
        if isinstance(s.get(k), (int, float)) and not isinstance(s.get(k), bool):
            return float(s[k])
    if isinstance(s.get("value_pct"), (int, float)):
        return float(s["value_pct"]) / 100.0
    return None


def exclusions(suite, arm, seed):
    """protocol/infra_exclusions.json: candidate evaluations lost to infrastructure are MISSING (not rejections): events of that candidate before before_utc are dropped"""
    d = C.jload(C.PAPER / "protocol/infra_exclusions.json") or {}
    out = {}
    for x in d.get("entries", []):
        if x.get("suite") == suite and x.get("arm") == arm and str(x.get("seed")) == str(seed):
            out[x["candidate"]] = x.get("before_utc") or "9999-01-01T00:00:00Z"
    return out


def apply_exclusions(events, excl):
    if not excl:
        return events, 0
    import datetime as _dt
    keep, n = [], 0
    for e in events:
        b = excl.get(e.get("candidate_id"))
        if b:
            t = event_time(e)
            lim = _dt.datetime.fromisoformat(b.replace("Z", "+00:00"))
            if t is None or t < lim:
                n += 1
                continue
        keep.append(e)
    return keep, n


def load_events(run_dir, extra_paths=()):
    """candidates.jsonl events of a run, file order.  CapEvolve runs keep it under .capevolve/run_*/ (last run dir wins)."""
    rd = Path(run_dir)
    paths = [rd / "candidates.jsonl"]
    runs = sorted((rd / ".capevolve").glob("run_*")) if (rd / ".capevolve").is_dir() else []
    # main run dir name is run_main (B/C) or run_<ts> (A); take the newest that has a candidates.jsonl
    for r in reversed(runs):
        if (r / "candidates.jsonl").exists():
            paths = [r / "candidates.jsonl"]
            break
    paths += list(extra_paths)
    out = []
    for p in paths:
        for e in C.jsonl(p):
            if e.get("event") and e.get("event") != "_check":
                out.append(e)
    return out, [str(p) for p in paths if Path(p).exists()]


def in_limit(e, limit):
    r = e.get("rollout_index")
    if not isinstance(r, (int, float)):
        return False
    if r > limit:
        return False
    s = e.get("start_rollout_index")
    return not (isinstance(s, (int, float)) and s > limit)


def first_created(events):
    for e in events:
        if e["event"] == "created":
            return e
    return events[0] if events else None


def seed_candidate(events):
    e = first_created(events)
    return e["candidate_id"] if e else None


def last_artifact_event(events, cid):
    for e in reversed(events):
        if e.get("candidate_id") == cid and e.get("artifact_dir"):
            return e
    return None


class Sel(dict):
    """selection result"""


def sel(status, cid=None, ev=None, **kw):
    d = Sel(status=status, candidate_id=cid, caveats=kw.pop("caveats", []), **kw)
    if ev is not None:
        d["artifact_dir"] = ev.get("artifact_dir")
        d["logged_sha256"] = ev.get("sha256")
        d["rollout_index"] = ev.get("rollout_index")
        d["selection_value"] = sval(ev)
        d["selection_split"] = ((ev.get("score") or {}).get("split") if isinstance(ev.get("score"), dict) else None) or ev.get("split")
        d["selection_n_tasks"] = ev.get("n_tasks")
    return d


def _exact_caveat(evs):
    if any(e.get("exact") is False for e in evs):
        return ["rollout_index of at least one used event is reconstructed (exact=false in candidates.jsonl): arithmetic from phase sizes"]
    return []


def _fallback_seed(events, reason, status="ok", caveats=None):
    cid = seed_candidate(events)
    e = last_artifact_event(events, cid) if cid else None
    if e is None:
        return sel("impossible", None, None, reason="no seed candidate in log (%s)" % reason)
    d = sel(status, cid, e, caveats=list(caveats or []))
    d["fallback_seed"] = True
    d["reason"] = reason
    return d


# ----------------------------------------------------------------------------------------------------------- rules
def argmax_eval(events, limit, splits, full_n=None, kinds=None, tie="earliest"):
    """argmax of the selection score over `evaluated` events (full-val ones) inside the limit.  tie: earliest event wins."""
    best = None
    used = []
    for e in events:
        if e["event"] != "evaluated" or not in_limit(e, limit):
            continue
        sc = e.get("score") or {}
        if splits and sc.get("split") not in splits:
            continue
        if kinds and sc.get("kind") not in kinds:
            continue
        if full_n and e.get("n_tasks") != full_n:
            continue
        if e.get("incomplete"):
            continue
        v = sval(e)
        if v is None:
            continue
        used.append(e)
        if best is None or v > sval(best):
            best = e
    return best, used


def rule_gepa(rd, events, limit, ctx):
    """GEPA 0.1.4 result.py:76-78: best_idx = max(range(len(scores)), key=scores[i]) over val_aggregate_scores -> highest mean val,
    first (earliest discovered) wins ties.  Candidates fully val-evaluated inside the limit only."""
    splits = {"val", "sel"}
    full_n = ctx["full_n"]
    best, used = argmax_eval(events, limit, splits, full_n=full_n)
    if best is None:
        return _fallback_seed(events, "no full-val evaluation inside the limit")
    return sel("ok", best["candidate_id"], best, caveats=_exact_caveat(used), n_candidates_considered=len({e["candidate_id"] for e in used}))


def rule_skillopt(rd, events, limit, ctx):
    """SkillOpt@79124b37 trainer.py:1598-1599,1706-1707: best_skill = last `accept_new_best` of the gate (candidate must strictly beat both the
    current skill and the best, evaluate_gate gate.py ~176-224); best_skill.md is the deployed file.  The converter (to_candidates.py)
    emits a `selected` event at every best change; take the last one inside the limit.  slow_update candidates are never eligible."""
    cur = None
    used = []
    for e in events:
        if e["event"] == "selected" and in_limit(e, limit):
            cur = e
            used.append(e)
    if cur is None:
        return _fallback_seed(events, "no selected event inside the limit")
    cav = _exact_caveat(used)
    cav.append("decisions.md says 'current accepted skill at B*'; the native deployed artifact is best_skill (last accept_new_best) and that is what is used; "
               "the two differ when the current skill drifted below the best")
    cav.append("end-of-run final promotion (trainer.py:2194-2240, one extra val rollout) is not replayable at a B* inside the run")
    return sel("partial" if ctx["limit_is_finite"] else "ok", cur["candidate_id"], cur, caveats=cav)


def rule_evoskill(rd, events, limit, ctx):
    """EvoSkill src/registry/manager.py:325-344,366-376,378-427 + loop/runner.py:353: frontier of size 3 (LoopConfig.frontier_size, evoskill_run.py:167),
    program admitted if the frontier has room or score > worst; best = frontier[0] after sort(key=(score, index), reverse=True), where index is the
    position in the (alphabetical) git-tag list.  Replayed over the full-val `evaluated` events inside the limit."""
    frontier = {}
    used = []
    for e in events:
        if e["event"] != "evaluated" or not in_limit(e, limit):
            continue
        v = sval(e)
        if v is None or (e.get("score") or {}).get("split") not in (None, "val"):
            continue
        used.append(e)
        name = e["candidate_id"]
        # update_frontier: score recorded first, then membership
        def ranked():
            names = sorted(frontier)                       # git tag --list order
            sc = [(n, frontier[n][0], i) for i, n in enumerate(names)]
            sc.sort(key=lambda x: (x[1], x[2]), reverse=True)
            return sc
        scored = ranked()
        if len(scored) < 3:
            frontier[name] = (v, e)
        else:
            worst_name, worst_score = scored[-1][0], scored[-1][1]
            if v > worst_score:
                del frontier[worst_name]
                frontier[name] = (v, e)
    if not frontier:
        return _fallback_seed(events, "no val evaluation inside the limit")
    top = None
    names = sorted(frontier)
    ranked = sorted([(n, frontier[n][0], i) for i, n in enumerate(names)], key=lambda x: (x[1], x[2]), reverse=True)
    top = ranked[0][0]
    ties = [r[0] for r in ranked if r[1] == ranked[0][1]]
    cav = _exact_caveat(used)
    status = "ok"
    if len(ties) > 1:
        status = "partial"
        cav.append("tie at the top of the frontier %s resolved by alphabetical git-tag index (manager.py:343); name ordering must match the real tag list" % ties)
    return sel(status, top, frontier[top][1], caveats=cav)


def rule_metaharness(rd, events, limit, ctx):
    """Meta-Harness campaign wrapper sb/mh_sb_run.py:152-166 (refresh_frontier: max over completed candidates by (val_score, -index), ties -> earliest),
    final pick :281-293.  The official repo's terminal_bench_2 reference (meta_harness.py:373-393, `if avg > current_best_avg`) is a strict-greater
    running best (also earliest on ties).  Candidates flagged incomplete are excluded."""
    best, used = argmax_eval(events, limit, {"val"})
    if best is None:
        return _fallback_seed(events, "no completed val evaluation inside the limit")
    return sel("ok", best["candidate_id"], best, caveats=_exact_caveat(used))


def rule_wikiskill(rd, events, limit, ctx):
    """WikiSkill (Stahl-G/wikiskill@da6984c) src/wikiskill/officeqa/loop.py:94-96 eq4_accepted (a candidate is accepted iff it STRICTLY beats the
    incumbent r_best, tie = reject) and engine.py:64-80/269-272 (state replays the gate events; the last accepted skill is the deployed one).
    Replayed from the `evaluated` val events in order, S0 = incumbent."""
    inc = None
    used = []
    for e in events:
        if e["event"] != "evaluated" or not in_limit(e, limit) or (e.get("score") or {}).get("split") != "val":
            continue
        v = sval(e)
        if v is None:
            continue
        used.append(e)
        if inc is None or v > sval(inc):
            inc = e
    if inc is None:
        return _fallback_seed(events, "S0 val evaluation not inside the limit")
    return sel("ok", inc["candidate_id"], inc, caveats=_exact_caveat(used))


def rule_mipro(rd, events, limit, ctx):
    """dspy MIPROv2 teleprompt/mipro_optimizer_v2.py:548-549 (best_score = default program's full-val score), :592-595 and :858-860
    (`if not minibatch and score > best_score` -> best_program) : running STRICT max over FULL-valset evaluations only; minibatch trial scores never
    update the best.  Wrapper code/mipro_run.py:132-141 tags each evaluation score.kind = full|minibatch."""
    inc = None
    used = []
    for e in events:
        if e["event"] != "evaluated" or not in_limit(e, limit):
            continue
        sc = e.get("score") or {}
        if sc.get("kind") != "full":
            continue
        v = sval(e)
        if v is None:
            continue
        used.append(e)
        if inc is None or v > sval(inc):
            inc = e
    if inc is None:
        return _fallback_seed(events, "no full-valset evaluation inside the limit", status="partial",
                              caveats=["MIPROv2 starts with a full eval of the default program; none finished inside the limit"])
    return sel("ok", inc["candidate_id"], inc, caveats=_exact_caveat(used))


def rule_ace(rd, events, limit, ctx):
    """ACE (dl_new/ace_src/ace/ace.py:781-783): deployed playbook = best_playbook, updated on `acc > best_accuracy` at each val evaluation
    (strict, earliest wins); wrapper code/ace_run.py:199-205 evaluates val at each epoch end and at final stop and takes
    max(cands, key=(val, -index)).  Replayed over `evaluated` val events inside the limit."""
    best, used = argmax_eval(events, limit, {"val"}, kinds={"full"})
    if best is None:
        d = sel("impossible", None, None)
        d["reason"] = ("no val-evaluated playbook inside the limit: ACE's native fallback (empty playbook, ace_run.py 'no_eval') would apply, but a run "
                       "with budget B* would have reserved budget for a final_stop evaluation (ace_run.py stopping()), which the log of the longer "
                       "run cannot show; playbook_current.txt snapshots are not frozen")
        return d
    cav = _exact_caveat(used)
    if ctx["limit_is_finite"]:
        cav.append("budget-coupled schedule: a run with budget B* would stop training earlier and run its final_stop val evaluation (ace_run.py stopping()/final_stop); "
                   "only val evaluations that actually occurred in the longer run are used")
    return sel("partial" if ctx["limit_is_finite"] else "ok", best["candidate_id"], best, caveats=cav)


def rule_trace2skill(rd, events, limit, ctx):
    """Trace2Skill campaign wrapper trace2skill/t2s_run.py:150-162: seed and every evolved variant (error, combined) are scored ONCE on val; best = seed,
    then `for v: if s > sel[best]: best = v` (strict, seed wins ties).  Selection happens once, after ALL variant evaluations.  A variant counts only if
    all val evaluations finished inside the limit (decisions.md: 'its selected variant if completed by B* else seed').  Completion index = position of
    the last val row in rollouts_metrics.jsonl (file order == counted order)."""
    sj = C.jload(Path(rd) / "selection_scores.json")
    rows = C.jsonl(Path(rd) / "rollouts_metrics.jsonl")
    seed_e = last_artifact_event(events, "seed")
    if seed_e is None:
        return sel("impossible", None, None, reason="no seed candidate in candidates.jsonl")
    last_val = max([i + 1 for i, r in enumerate(rows) if r.get("split") == "val"] or [0])
    cav = ["selection is a single end-of-run step; completion index derived from rollouts_metrics.jsonl row order (no timestamps)"]
    if not sj:
        d = sel("ok" if limit != INF else "ok", "seed", seed_e, caveats=cav)
        d["fallback_seed"] = True
        d["reason"] = "selection_scores.json absent: variant val evaluations not completed -> seed (native end-of-run state at the cutoff as well)"
        return d
    if last_val > limit:
        d = sel("ok", "seed", seed_e, caveats=cav)
        d["fallback_seed"] = True
        d["reason"] = "variant val evaluations completed at counted rollout %d > limit %s -> seed" % (last_val, limit)
        return d
    chosen = sj.get("selected") or "seed"
    ev = last_artifact_event(events, chosen) or seed_e
    if chosen != "seed" and not ev.get("artifact_dir"):
        return sel("impossible", chosen, None, reason="selected variant has no frozen artifact event")
    if chosen != "seed":
        cands = Path(rd) / "candidates" / chosen
        ev = Sel(candidate_id=chosen, artifact_dir=str(cands), sha256=None, rollout_index=last_val)
    return sel("ok", chosen, ev, caveats=cav, val_scores=sj.get("val_scores"))


def rule_harnesslens(rd, events, limit, ctx):
    """HarnessLens controller.py:578-603,1050-1066,1079-1088: champion = last version accepted by a confirmed paired review (cumulative chain), else v0;
    selection signal is the TRAIN split paired rollouts.  Needs the accepted-version chain with counted-rollout totals."""
    acc = [e for e in events if e["event"] == "accepted" and in_limit(e, limit)]
    if acc:
        return sel("ok", acc[-1]["candidate_id"], acc[-1], caveats=_exact_caveat(acc))
    if events:
        return _fallback_seed(events, "no accepted version inside the limit")
    d = sel("impossible", None, None)
    d["reason"] = "no candidates.jsonl for HarnessLens and its creation ledger (creation_budget.json) carries no per-version acceptance index: format pending from bl-harness"
    return d


def _capevolve_events(rd, events):
    """hc/ao fallback when no candidates.jsonl exists (suite A before the sidecar): promotions from events.jsonl kind=step accept flags."""
    out = []
    runs = sorted((Path(rd) / ".capevolve").glob("run_*"))
    for r in runs[-1:]:
        idx = C.jsonl(r / "eval_index.jsonl")
        stamps = sorted(x.get("ts") for x in idx if isinstance(x.get("ts"), (int, float)))
        import bisect
        for e in C.jsonl(r / "events.jsonl"):
            if e.get("kind") != "step" or not e.get("candidate"):
                continue
            n = bisect.bisect_right(stamps, e.get("t", 0)) if isinstance(e.get("t"), (int, float)) else None
            out.append({"event": "accepted" if e.get("accept") else "rejected", "candidate_id": e["candidate"], "parent_id": e.get("parent"),
                        "rollout_index": n, "score": {"split": "val", "mean": e.get("val")},
                        "artifact_dir": str(r / "candidates" / e["candidate"]), "sha256": None, "exact": False, "_from": "events.jsonl+eval_index.jsonl"})
    return out


def rule_capevolve(rd, events, limit, ctx):
    """CapEvolve hill-climb / agent-optimize under rule P (analysis_plan section 8, decisions.md): deployed = LAST PROMOTED candidate
    (event `accepted` = step accept flag after screen + fresh-trial confirmation) with rollout_index <= limit; else the seed.  A promotion whose
    confirmation straddles the limit is not yet logged as accepted at that index, hence excluded.  End-of-run: run_main/final.json best_id,
    else state.json best_id (the champion at the cutoff)."""
    cav = []
    evs = events
    if not [e for e in events if e["event"] in ("accepted", "rejected", "evaluated", "selected")]:
        fb = _capevolve_events(rd, events)
        if fb:
            evs = events + fb
            cav.append("promotions reconstructed from events.jsonl kind=step + eval_index.jsonl timestamps (no candidates.jsonl step events): rollout index = completed rollouts at the step time")
    if not ctx["limit_is_finite"]:
        run = sorted((Path(rd) / ".capevolve").glob("run_*"))
        if run:
            fin = C.jload(run[-1] / "final.json") or {}
            st = C.jload(run[-1] / "state.json") or {}
            bid = fin.get("best_id") or st.get("best_id")
            if bid:
                d = Path(run[-1]) / "candidates" / bid
                e = last_artifact_event(evs, bid)
                if d.is_dir() or e:
                    ev = Sel(artifact_dir=str(e["artifact_dir"] if e else d), sha256=(e or {}).get("sha256"), rollout_index=None)
                    return sel("ok", bid, ev, caveats=cav + ["end-of-run = %s best_id" % ("final.json" if fin.get("best_id") else "state.json")])
    if not first_created(evs):          # no log at all yet: the seed is the unmodified candidates/seed (A) or frozen/seed (B/C)
        for cand in [Path(rd) / "frozen" / "seed"] + [r / "candidates" / "seed" for r in sorted((Path(rd) / ".capevolve").glob("run_*"))]:
            if cand.is_dir():
                evs = evs + [{"event": "created", "candidate_id": "seed", "artifact_dir": str(cand), "sha256": None, "rollout_index": 0}]
                cav.append("no candidates.jsonl created event: seed taken from %s" % cand)
                break
    acc = [e for e in evs if e["event"] == "accepted" and in_limit(e, limit)]
    if acc and any("state.json best_id changed" in str(e.get("reason", "")) for e in acc):
        cav.append("AO promotion detected from a state.json best_id change: its rollout_index is an upper bound (<= 2 min late); a promotion just under N* may be excluded")
    if acc:
        status = "partial" if any(e.get("exact") is False for e in acc) or cav else "ok"
        return sel(status, acc[-1]["candidate_id"], acc[-1], caveats=cav + _exact_caveat(acc))
    d = _fallback_seed(evs, "no promotion (accepted event) inside the limit: the seed is the method's own deployed artifact at this budget", caveats=cav)
    return d


def rule_oneshot(rd, events, limit, ctx):
    """ctl-oneshot control: one optimizer step, no selection.  Artifact = its single revision cand_0001 (collect_cap.py best='cand_0001'),
    independent of B*; it spends well under B* counted rollouts on search."""
    e = last_artifact_event(events, "cand_0001")
    if e is None:
        d = sel("impossible", None, None)
        d["reason"] = "cand_0001 not present in candidates.jsonl"
        return d
    return sel("ok", "cand_0001", e, caveats=["no selection rule: the one-shot revision is the artifact; B*-independent"])


RULES = {
    "gepa": rule_gepa, "skillopt": rule_skillopt, "evoskill": rule_evoskill, "metaharness": rule_metaharness,
    "wikiskill": rule_wikiskill, "mipro": rule_mipro, "ace": rule_ace, "trace2skill": rule_trace2skill,
    "harnesslens": rule_harnesslens, "hc": rule_capevolve, "ao": rule_capevolve, "oneshot": rule_oneshot, "hcstock": rule_capevolve, "hlext": rule_harnesslens,
    "pt": rule_capevolve, "rulep": rule_capevolve, "p": rule_capevolve, "t": rule_capevolve, "1s": rule_capevolve, "nohist": rule_capevolve, "td": rule_capevolve,
    "nodigest": rule_capevolve, "rulep2x": rule_capevolve, "ctl": rule_oneshot,
}

FULL_N = {"A": 40, "B": 25, "C": 10, "D": 25}      # val / selection set size per suite (full-evaluation marker for GEPA)


# ----------------------------------------------------------------------------------------------------------- artifacts
def logged_sha_check(art_dir, logged, kind):
    """True/False if one of the known hash conventions reproduces `logged`; None if it can't be checked."""
    if not logged:
        return None
    d = Path(art_dir)
    cands = set()
    files = C.tree_files(d, kind)
    cands.add(hashlib.sha256(b"".join((d / f).read_bytes() for f in sorted(files))).hexdigest())   # to_candidates.freeze
    h = hashlib.sha256()                                                                             # tau_lib.sha_dir / cand_logger.sha (all files)
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(d)).encode())
            h.update(p.read_bytes())
    cands.add(h.hexdigest())
    return logged in cands


def freeze_copy(src_dir, dst_dir, kind, extra_files=None):
    files = C.tree_files(src_dir, kind) if kind != "all" else [str(p.relative_to(src_dir)) for p in sorted(Path(src_dir).rglob("*")) if p.is_file()]
    if dst_dir.exists():
        os.chmod(dst_dir, 0o755)
        for p in dst_dir.rglob("*"):                      # re-run: make writable before replacing
            os.chmod(p, 0o755 if p.is_dir() else 0o644)
        shutil.rmtree(dst_dir)
    for f in files:
        t = dst_dir / f
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(src_dir) / f, t)
    for p in sorted(dst_dir.rglob("*"), reverse=True):
        os.chmod(p, (stat.S_IMODE(p.stat().st_mode) & ~0o222))
    os.chmod(dst_dir, stat.S_IMODE(dst_dir.stat().st_mode) & ~0o222)
    return files


def seed_selection_score(rd, events):
    """the seed artifact's score on the arm's own selection split, from the search record (evaluated event of the seed candidate, else CapEvolve baseline.json)"""
    cid = seed_candidate(events)
    for e in events:
        if e["event"] == "evaluated" and e.get("candidate_id") == cid and sval(e) is not None and not (e.get("score") or {}).get("kind") == "minibatch" \
                and ((e.get("score") or {}).get("split") or e.get("split")) in (None, "val", "sel", "opt(val)"):
            return {"seed_score": sval(e), "seed_split": (e.get("score") or {}).get("split") or e.get("split"), "seed_n_tasks": e.get("n_tasks"), "seed_source": "candidates.jsonl evaluated"}
    for run in sorted((Path(rd) / ".capevolve").glob("run_*"), reverse=True):
        b = C.jload(run / "baseline.json") or {}
        v = (b.get("val") or {}).get("reward")
        if isinstance(v, (int, float)):
            return {"seed_score": float(v), "seed_split": "val", "seed_n_tasks": (b.get("val") or {}).get("n_tasks"), "seed_source": "baseline.json"}
    return {"seed_score": None, "seed_source": "not found"}


def build_entry(suite, arm, seed, mode, limit, out_root, copy, kind):
    rd = C.run_dir(suite, arm, seed)
    entry = {"suite": suite, "arm": arm, "seed": seed, "mode": mode, "limit": None if limit == INF else limit, "run_dir": str(rd)}
    if not rd.exists():
        entry.update(status="impossible", reason="run directory missing")
        return entry
    events, sources = load_events(rd)
    events, n_excl = apply_exclusions(events, exclusions(suite, arm, seed))
    entry["infra_excluded_events"] = n_excl
    entry["event_sources"] = sources
    entry["n_events"] = len(events)
    fn = RULES[arm]
    ctx = {"full_n": FULL_N[suite], "limit_is_finite": limit != INF, "suite": suite}
    if not events and arm not in ("trace2skill", "hc", "ao"):
        entry.update(status="impossible", reason="no candidates.jsonl events yet")
        return entry
    s = fn(rd, events, limit, ctx)
    entry.update({k: v for k, v in s.items()})
    if entry["status"] == "impossible":
        return entry
    src = entry.get("artifact_dir")
    k = "all" if arm == "harnesslens" else kind
    if not src or not Path(src).is_dir() or not C.tree_files(src, kind if k != "all" else "all") and k != "all":
        entry.update(status="impossible", reason="frozen artifact directory missing or empty: %s" % src)
        return entry
    h, files = C.tree_hash(src, kind) if k != "all" else (None, None)
    if k == "all":
        files = {str(p.relative_to(src)): C.sha256_file(p) for p in sorted(Path(src).rglob("*")) if p.is_file()}
        hh = hashlib.sha256()
        for f in sorted(files):
            hh.update(("%s\0%s\n" % (f, files[f])).encode())
        h = hh.hexdigest()
    sr = seed_selection_score(rd, events)
    inlim = [e for e in events if in_limit(e, limit)]
    cands_seen = {e["candidate_id"] for e in inlim if e["event"] in ("evaluated", "accepted", "rejected")}
    sv = C.jload(Path(rd) / "surface_violations.json")
    entry["n_promotions"] = len({e["candidate_id"] for e in inlim if e["event"] == "accepted"} - {seed_candidate(events)})
    entry["n_screened"] = len(cands_seen)
    if sv is not None:
        entry["surface_violations"] = sv
    def _viol(v):
        if isinstance(v, dict) and "n_violating_candidates" in v:      # tau-runner format: {"violating_candidates": {...}, "n_violating_candidates": n}; absent file = 0
            return int(v.get("n_violating_candidates") or 0) > 0      # surface_violations.json: any nonzero count / non-empty list = the champion's search edited outside its cell's lock
        if isinstance(v, dict):
            return any(_viol(x) for x in v.values())
        if isinstance(v, (list, tuple, set)):
            return len(v) > 0
        return bool(v) and v not in (0, "0")
    entry["surface_violation"] = bool(sv is not None and _viol(sv))
    entry["dagger"] = ((suite, arm) in C.DAGGER) or entry["surface_violation"]      # amendment 9H: stays in its cell (ITT), dagger + sensitivity row without it
    own = (_BSTAR_RUNS or [])
    own_n = next((r.get("counter") for r in own if r["arm"] == arm and r["seed"] == seed), None)
    entry["selection"] = {"split": entry.get("selection_split"), "n_tasks": entry.get("selection_n_tasks"),
                          "champion_score": (sr.get("seed_score") if entry.get("fallback_seed") or entry.get("candidate_id") == seed_candidate(events) else entry.get("selection_value")),
                          "comparison_count": (min(limit, own_n) if (own_n is not None and limit != INF) else own_n), "own_count": own_n, **sr}
    entry["tree_sha256"] = h
    entry["files"] = files
    entry["logged_sha_matches"] = logged_sha_check(src, entry.get("logged_sha256"), kind if k != "all" else "tau_cap")
    if copy:
        dst = out_root / "artifacts" / mode / arm / ("s%d" % seed)
        freeze_copy(src, dst, k)
        entry["frozen_dir"] = str(dst)
    return entry


def seed_artifact(suite, out_root, copy):
    """The seed artifact: the seed candidate of every search must hash identically; the first one found is frozen."""
    kind = C.SUITES[suite]["artifact_kind"]
    found = {}
    for arm in C.suite_arms(suite):
        for seed in C.SEEDS:
            rd = C.run_dir(suite, arm, seed)
            if not rd.exists():
                continue
            events, _ = load_events(rd)
            cid = seed_candidate(events)
            e = last_artifact_event(events, cid) if cid else None
            if e and Path(e["artifact_dir"]).is_dir():
                try:
                    h, files = C.tree_hash(e["artifact_dir"], kind)
                except Exception:
                    continue
                if files:
                    found.setdefault(h, []).append({"arm": arm, "seed": seed, "candidate_id": cid, "artifact_dir": e["artifact_dir"]})
    out = {"suite": suite, "distinct_seed_hashes": {h: len(v) for h, v in found.items()}}
    if not found:
        out.update(status="impossible", reason="no seed candidate artifact found")
        return out
    major = max(found, key=lambda h: len(found[h]))
    src = found[major][0]["artifact_dir"]
    out.update(status="ok" if len(found) == 1 else "partial", tree_sha256=major, source=found[major][0],
               files=C.tree_hash(src, kind)[1], n_runs_with_this_seed=len(found[major]),
               other_hashes={h: v for h, v in found.items() if h != major})
    if len(found) > 1:
        out["reason"] = "seed candidates do not all hash identically; the majority one is frozen, the others are listed"
    if copy:
        dst = out_root / "artifacts" / "seed"
        freeze_copy(src, dst, kind)
        out["frozen_dir"] = str(dst)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=sorted(C.SUITES))
    ap.add_argument("--bstar-file", default=None)
    ap.add_argument("--bstar", type=int, default=None, help="override (dry runs only)")
    ap.add_argument("--mode", default="B,END")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--no-copy", action="store_true")
    ap.add_argument("--arms", default=None)
    a = ap.parse_args(argv)
    suite = a.suite
    out_root = Path(a.out_root) if a.out_root else C.final_dir(suite)
    bj = C.jload(a.bstar_file) if a.bstar_file else None
    bstar = a.bstar if a.bstar is not None else (bj or {}).get("bstar")
    global _BSTAR_RUNS
    _BSTAR_RUNS = (bj or {}).get("runs") or []
    modes = [m for m in a.mode.split(",") if m]
    final_state = bool(C.SUITES[suite].get("final_state"))
    if final_state:                 # Suite D: no B*; the artifact is the final state (last promoted, else seed) filed under mode B
        modes = ["B"]
        bstar = "final-state"
    if "B" in modes and not bstar:
        sys.exit("B* needed for mode B")
    kind = C.SUITES[suite]["artifact_kind"]
    arms = a.arms.split(",") if a.arms else C.suite_arms(suite)
    man = {"suite": suite, "generated_utc": C.now_utc(), "bstar": bstar, "bstar_file": a.bstar_file,
           "bstar_file_sha256": C.file_sha(a.bstar_file) if a.bstar_file else None, "script_commit": C.git_head(),
           "reconstruct_py_sha256": C.file_sha(__file__), "cutoff_utc": C.CUTOFF_UTC,
           "rules": {k: (v.__doc__ or "").strip() for k, v in RULES.items()}, "entries": []}
    man["seed_artifact"] = seed_artifact(suite, out_root, not a.no_copy)
    for mode in modes:
        limit = INF if final_state else (float(bstar) if mode == "B" else INF)
        for arm in arms:
            for seed in C.SEEDS:
                man["entries"].append(build_entry(suite, arm, seed, mode, limit, out_root, not a.no_copy, kind))
    nf = (bj or {}).get("natively_finished") or {}
    for e in man["entries"]:
        k = "%s/s%d" % (e["arm"], e["seed"])
        if k in nf and nf[k].get("stop_kind") == "budget_cap":
            # per-seed note printed beside the numbers: the campaign's hard cap (RolloutCap at 600 counted rollouts, which also counts infra retries and restart waste) ended the search
            note = {"stop_kind": "budget_cap", "campaign_hard_cap": 600, "campaign_count_at_stop": nf[k]["count"], "evidence": nf[k]["evidence"]}
            sel = C.jload(Path(C.run_dir(suite, e["arm"], e["seed"])) / "final" / "SELECTION.json") or {}
            if sel.get("gepa_total_num_evals") is not None:
                note.update(own_budget_metric_calls=sel["gepa_total_num_evals"], own_budget=555, own_budget_shortfall=555 - sel["gepa_total_num_evals"])
            if (suite, e["arm"], e["seed"]) == ("A", "skillopt", 1):    # baseline-eng, rollout_counter.json 'by' counts (606 started - 6 refunded infra retries = 600)
                note.update(own_budget_steps_completed=6, own_budget_steps_planned=6,
                            cut_by_cap="epoch-3 slow-update rollout_curr (17 of 20 rollouts) and the epoch-3 meta-skill step; neither is scored or eligible for best_skill.md",
                            infra_retries_refunded=6, source="baseline-eng message 2026-10-12 (rollout_counter.json by-phase counts)")
            note["reason"] = "the search raised RolloutCap at the campaign's 600 counted-rollout hard cap before its own budget was exhausted" + (" (GEPA's own metric calls %s of 555)" % sel["gepa_total_num_evals"] if sel.get("gepa_total_num_evals") is not None else "")
            e["budget_note"] = note
            e.setdefault("caveats", []).append(note["reason"])
        if k in nf:
            e["native_finish"] = nf[k]
            e.setdefault("caveats", []).append("natively finished before the cutoff (%s); contributes its final returned artifact, count %s disclosed" % (nf[k]["evidence"], nf[k]["count"]))
    seed_h = man["seed_artifact"].get("tree_sha256")
    for e in man["entries"]:
        e["identical_to_seed"] = bool(seed_h and e.get("tree_sha256") == seed_h)
    inert = {}
    for e in man["entries"]:
        e["inert"] = bool(e.get("identical_to_seed"))
        inert.setdefault((e["mode"], e["arm"]), []).append(e["inert"])
    man["inert_fraction_by_arm"] = {"%s|%s" % k: {"inert": sum(v), "seeds": len(v), "fraction": round(sum(v) / len(v), 3),
                                                   "label": ("both returned the seed" if all(v) else ("not testable (inert in >=2 of 3 seeds)" if sum(v) >= 2 else ""))}
                                    for k, v in sorted(inert.items())}
    by_hash = {}
    for e in man["entries"]:
        if e.get("tree_sha256"):
            by_hash.setdefault((e["mode"], e["tree_sha256"]), []).append("%s/s%d" % (e["arm"], e["seed"]))
    man["duplicate_groups"] = {"%s:%s" % (m, h[:12]): v for (m, h), v in by_hash.items() if len(v) > 1}
    man["status_counts"] = {}
    for e in man["entries"]:
        k = "%s:%s:%s" % (e["mode"], e["arm"], e["status"])
        man["status_counts"][k] = man["status_counts"].get(k, 0) + 1
    import csv as _csv
    selp = out_root / "selection_scores.csv"
    selp.parent.mkdir(parents=True, exist_ok=True)
    with open(selp, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["mode", "arm", "seed", "status", "candidate_id", "split", "n_tasks", "champion_score", "seed_score", "seed_split", "comparison_count", "own_count", "seed_source",
                    "inert", "dagger", "n_promotions", "n_screened"])
        for e in man["entries"]:
            sx = e.get("selection") or {}
            w.writerow([e["mode"], e["arm"], e["seed"], e["status"], e.get("candidate_id"), sx.get("split"), sx.get("n_tasks"), sx.get("champion_score"), sx.get("seed_score"),
                        sx.get("seed_split"), sx.get("comparison_count"), sx.get("own_count"), sx.get("seed_source"),
                        int(bool(e.get("inert"))), int(bool(e.get("dagger"))), e.get("n_promotions"), e.get("n_screened")])
    path = Path(a.manifest) if a.manifest else C.MANIFESTS / ("artifacts_%s.json" % suite)
    C.write_json_atomic(path, man)
    for mode in modes:
        print("== suite %s mode %s (limit %s)" % (suite, mode, bstar if mode == "B" else "cutoff"))
        for arm in arms:
            row = [e for e in man["entries"] if e["mode"] == mode and e["arm"] == arm]
            print("  %-12s %s" % (arm, "  ".join("s%d:%s:%s%s" % (e["seed"], e["status"], e.get("candidate_id"), "*" if e.get("fallback_seed") else "") for e in row)))
    print("manifest ->", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
