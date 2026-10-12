#!/usr/bin/env python3
"""tokens_at_bstar.py: optimizer non-cache-read tokens per arm and seed (gateway ledger, collect_metrics' shared definition: uncached input + output + cache-write for Anthropic usage,
prompt + completion for OpenAI usage; roles in OPT_ROLES) (a) up to the moment the N*/final-state artifact was produced and (b) at the end of the run, and the 4M-guard check.

    tokens_at_bstar.py --suite A --bstar-file manifests/bstar_A.json [--cap 4000000] [--out FILE]

Artifact time = start time of the rollout whose index is the selected event's rollout_index (logs/rollout_starts.jsonl for CapEvolve, else rollouts_metrics*.jsonl t_end order).
Flag = the artifact was produced after the cumulative optimizer tokens passed the cap.  For flagged cells the artifact the arm's own rule would have returned at the rollout where the
cap was crossed is written as a labelled sensitivity (sensitivity_at_cap)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402
import reconstruct as R  # noqa: E402


def load_ledger(cm, wanted):
    """{(suite, arm, seed): [(t, noncache), ...]} for optimizer-role calls of main-run tags (any restart: the 4M guards meter by tag)"""
    out = {}
    path = cm.GATEWAY_LOG
    with open(path, "rb") as f:
        for line in f:
            if b'"tag": "tag:E' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            suite, arm, seed, kind, role = cm.classify_tag(d.get("tag"))
            if kind != "run" or role not in cm.OPT_ROLES or (suite, arm, seed) not in wanted:
                continue
            t = cm.epoch(d.get("t")) or 0
            out.setdefault((suite, arm, seed), []).append((t, cm.norm_usage(d)["noncache"]))
    for v in out.values():
        v.sort()
    return out


def rollout_times(rd):
    """sorted list of rollout start/end epoch seconds, index i-1 = i-th rollout"""
    ts = [r["t"] for r in C.jsonl(Path(rd) / "logs" / "rollout_starts.jsonl") if isinstance(r.get("t"), (int, float))]
    if ts:
        return sorted(ts)
    for name in ("rollouts_metrics.jsonl", "rollouts_metrics_converted.jsonl"):
        out = []
        for r in C.jsonl(Path(rd) / name):
            x = r.get("t_end") or r.get("t_start")
            if isinstance(x, str):
                try:
                    out.append(dt.datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp())
                except Exception:
                    pass
        if out:
            return sorted(out)
    return []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=sorted(C.SUITES))
    ap.add_argument("--bstar-file", default=None)
    ap.add_argument("--cap", type=int, default=4_000_000)
    ap.add_argument("--out", default=None)
    ap.add_argument("--end", action="store_true", help="evaluate the native end-of-run (5D) artifacts instead of the N* ones")
    a = ap.parse_args(argv)
    suite = a.suite
    cm = C.collect_metrics()
    bj = C.jload(a.bstar_file) if a.bstar_file else None
    final_state = bool(C.SUITES[suite].get("final_state"))
    limit = R.INF if (final_state or a.end) else float((bj or {}).get("bstar") or R.INF)
    arms = C.suite_arms(suite)
    wanted = {(suite, arm, seed) for arm in arms for seed in C.SEEDS}
    wanted_cm = {(suite if suite in "ABC" else suite, cm.canon_arm(arm) if hasattr(cm, "canon_arm") else arm, seed) for (suite, arm, seed) in wanted}
    led = load_ledger(cm, wanted_cm)
    rows = []
    for arm in arms:
        for seed in C.SEEDS:
            rd = C.run_dir(suite, arm, seed)
            if not rd.exists():
                continue
            events, _ = R.load_events(rd)
            excl, _n = R.apply_exclusions(events, R.exclusions(suite, arm, seed))
            events = excl
            ctx = {"full_n": R.FULL_N[suite], "limit_is_finite": limit != R.INF, "suite": suite}
            fn = R.RULES.get(arm)
            sel = fn(rd, events, limit, ctx) if (fn and (events or arm in ("hc", "ao", "hcstock", "trace2skill"))) else None
            calls = led.get((suite, cm.canon_arm(arm), seed), [])
            total = sum(n for _, n in calls)
            row = {"suite": suite, "arm": arm, "seed": seed, "tokens_end_of_run": total, "n_optimizer_calls": len(calls), "artifact_candidate": (sel or {}).get("candidate_id"),
                   "artifact_rollout_index": (sel or {}).get("rollout_index"), "status": (sel or {}).get("status")}
            ridx = row["artifact_rollout_index"]
            starts = [r["t"] for r in C.jsonl(Path(rd) / "logs" / "rollout_starts.jsonl") if isinstance(r.get("t"), (int, float))]
            times = rollout_times(rd)
            ev_t = [(R.event_time(e), e) for e in events if R.event_time(e) is not None]
            distinct = len({x[0].replace(microsecond=0) for x in ev_t})
            use_events = (not starts) and distinct >= 3          # converters that stamp every event with the conversion time give 1-2 distinct values
            cum, t_cross = 0, None
            for t, n in calls:
                cum += n
                if t_cross is None and cum > a.cap:
                    t_cross = t
            row["cap_crossed_at_epoch"] = t_cross
            row["artifact_time_source"] = None
            cid = row["artifact_candidate"]
            if sel and sel.get("fallback_seed"):
                row["tokens_up_to_artifact"] = 0          # the seed artifact: produced before any optimizer spending
                row["artifact_epoch"] = None
            elif use_events and cid:
                cr = [t for t, e in ev_t if e["event"] == "created" and e.get("candidate_id") == cid]
                ex = [t for t, e in ev_t if e.get("candidate_id") == cid]
                tt = (min(cr) if cr else (min(ex) if ex else None))
                row["artifact_epoch"] = tt.timestamp() if tt else None
                row["artifact_time_source"] = "candidates.jsonl created-event time"
                row["tokens_up_to_artifact"] = sum(n for t, n in calls if t <= row["artifact_epoch"]) if tt else None
            elif isinstance(ridx, (int, float)) and ridx > 0 and (starts or times):
                tl = starts or times
                row["artifact_epoch"] = tl[min(int(ridx), len(tl)) - 1]
                row["artifact_time_source"] = "rollout_starts.jsonl" if starts else "rollouts_metrics t_end order"
                row["tokens_up_to_artifact"] = sum(n for t, n in calls if t <= row["artifact_epoch"])
            else:
                row["tokens_up_to_artifact"] = None
                row["artifact_epoch"] = None
            row["artifact_after_cap"] = bool(t_cross is not None and row.get("artifact_epoch") and row["artifact_epoch"] > t_cross)
            row["end_of_run_over_cap"] = total > a.cap
            if row["artifact_after_cap"]:
                if starts:
                    idx_c = sum(1 for t in starts if t <= t_cross)
                elif use_events:
                    idx_c = max([e.get("rollout_index") or 0 for t, e in ev_t if t.timestamp() <= t_cross] or [0])
                else:
                    idx_c = sum(1 for t in times if t <= t_cross)
                s2 = fn(rd, events, float(idx_c), dict(ctx, limit_is_finite=True)) if fn else None
                row["sensitivity_at_cap"] = {"label": "artifact the arm's own rule returns at the rollout where cumulative optimizer tokens crossed %d" % a.cap,
                                             "rollout_index_at_crossing": idx_c, "candidate_id": (s2 or {}).get("candidate_id"), "status": (s2 or {}).get("status"),
                                             "selection_value": (s2 or {}).get("selection_value")}
            rows.append(row)
    out = Path(a.out) if a.out else C.MANIFESTS / ("optimizer_tokens_%s.json" % suite)
    C.write_json_atomic(out, {"suite": suite, "cap": a.cap, "limit": None if limit == R.INF else limit, "generated_utc": C.now_utc(), "rows": rows})
    print("%-12s %s %-10s %-12s %-12s %s" % ("arm", "seed", "up_to_art", "end_of_run", "after_cap", "sensitivity"))
    for r in rows:
        print("%-12s s%d %-10s %-12s %-12s %s" % (r["arm"], r["seed"], r["tokens_up_to_artifact"], r["tokens_end_of_run"], r["artifact_after_cap"] or ("OVER-AT-END" if r["end_of_run_over_cap"] else ""),
                                               (r.get("sensitivity_at_cap") or {}).get("candidate_id", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
