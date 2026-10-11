#!/usr/bin/env python3
"""collect_metrics.py: campaign-wide cost / token / latency / throughput accounting.

Reads (never writes) the gateway call log and the run directories under campaign-scratch/runs, and writes
analysis/out/metrics/{metrics_by_arm.csv, metrics_by_role.csv, rollout_metrics.csv, campaign_totals.json,
configs_by_arm.json, metrics_report.md}.  Re-runnable: `python3 collect_metrics.py` (idempotent, ~1 min).

Conventions (see analysis_plan.md section 9):
  * Only Claude models in protocol/pricing.json are priced; everything else is reported in tokens with USD = null
    (never 0); any sum that excludes unpriced spend is flagged `lower_bound`.
  * "ledger tokens" reproduce the gateway /health ledger (usage.total_tokens when present, else the API-specific sum).
  * "noncache tokens" = the optimizer-cap basis of decisions.md: uncached input + output + cache-write for Anthropic
    usage, prompt (cached or not) + completion for OpenAI usage; cache reads are excluded.
  * Categories: main | chaser_eval | restart_waste | pilot | stopped | superseded | smoke | untagged | no_run_dir.
    Main tables use main and chaser_eval; everything else is overhead/waste (it still counts toward campaign cost).
Python 3.9 compatible.
"""
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

SCRATCH = Path(os.environ.get("CAMPAIGN_SCRATCH", "/home/dev/projects2/campaign-scratch"))
GATEWAY_LOG = SCRATCH / "logs" / "gateway_calls.jsonl"
RUNS = SCRATCH / "runs"
BASELINES = SCRATCH / "baselines"
PAPER = Path(__file__).resolve().parents[2]
PRICING = PAPER / "protocol" / "pricing.json"
OUT = Path(os.environ.get("METRICS_OUT", str(PAPER / "analysis" / "out" / "metrics")))
HEALTH_URL = os.environ.get("GATEWAY_HEALTH", "http://127.0.0.1:4111/health")
OPT_CAP = 4_000_000
SUITE_OF = {"E10": "A", "E10B": "B", "E10C": "C", "E12C": "C-E12", "E12A": "A-E12"}  # E12C = stock-gate ablation on Suite C (decisions 2026-10-11 21:55)
SUITE_ROOT = {"A": RUNS / "E10", "B": RUNS / "E10B", "C": RUNS / "E10C", "C-E12": RUNS / "E12C", "A-E12": RUNS / "E12A"}
ARM_ALIAS = {"hill-climb": "hc", "agent-optimize": "ao", "ctlseed": "ctl-seed"}
OPT_ROLES = {"optimizer", "reflection", "proposer", "reflector", "curator", "optimizer-aux", "debugger"}
TARGET_ROLES = {"target"}
USER_ROLES = {"user", "usersim"}
JUDGE_ROLES = {"judge"}
CAPS = SCRATCH / "logs" / "caps.json"
LOWPRI_FIX_T = epoch_const = None  # set below (needs epoch())
LOWPRI_EXTRA_BEFORE_FIX = ["E10-evoskill", "E10-harnesslens", "probe"]  # decisions.md 2026-10-11 18:40: were still listed until the fix
NON_OPT_ROLES = TARGET_ROLES | USER_ROLES | JUDGE_ROLES | {"probe", ""}
MAIN_CATS = ("main", "chaser_eval")
# Restart cutoffs that cannot be derived from file birth times (source: run-dir notes).
MANUAL_CUTOFFS = {
    ("B", "*"): ("2026-10-11T12:38:38Z", "runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44)"),
}
TIERS_A = {
    "hc": "Tier 1", "ao": "Tier 1", "gepa": "Tier 1", "skillopt": "Tier 1", "metaharness": "Tier 1",
    "wikiskill": "Tier 1", "evoskill": "Tier 1 (promoted from Tier 2 before any result, decisions.md 09:55)",
    "trace2skill": "Tier 1-cheap", "ace": "Tier 1-cheap", "mipro": "Tier 1-cheap",
    "ahe": "Tier 2 (exploratory)", "mce": "Tier 2 (exploratory)", "graphskillevo": "Tier 2 (exploratory)",
    "memento": "Tier 2 (exploratory)", "rho": "Tier 2 (exploratory)", "harnesslens": "Tier 2 (exploratory)",
}
NOW = dt.datetime.now(dt.timezone.utc)


# ----------------------------------------------------------------------------------------------- helpers
def epoch(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.replace("Z", "").split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    except Exception:
        return None


def iso(ts):
    return None if ts is None else dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 3)


def jload(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def jsonl(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def birth(paths):
    """Birth times (statx) for existing paths; returns {path: epoch}."""
    paths = [str(p) for p in paths if Path(p).exists()]
    if not paths:
        return {}
    try:
        out = subprocess.run(["stat", "-c", "%W\t%n"] + paths, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return {}
    res = {}
    for line in out.splitlines():
        w, _, n = line.partition("\t")
        if w.isdigit() and int(w) > 0:
            res[n] = int(w)
    return res


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def canon_arm(a):
    return ARM_ALIAS.get(a, a)


# ----------------------------------------------------------------------------------------------- pricing
def load_pricing():
    p = jload(PRICING, {})
    return p.get("usd_per_mtok", {}), p.get("unknown", [])


PRICES, UNPRICED_LIST = load_pricing()
LOWPRI_FIX_T = epoch("2026-10-11T18:40:00Z")
LOWPRI_NOW = (jload(CAPS, {}) or {}).get("low_priority_tags", [])


LOWPRI_START = epoch("2026-10-11T13:11:00Z")  # priority feature live with the gateway swap (decisions.md 13:11)
LOWPRI_COMMON = ["smoke", "Smoke", "E10-memento", "E10-ahe", "E10-mce", "E10-rho", "E10-verse", "E10-graphskillevo", "E10-coevo"]
LOWPRI_BEFORE_FIX = LOWPRI_COMMON + ["probe", "E10-evoskill", "E10-harnesslens"]  # 13:11-18:40 (team-lead, exact)


def low_priority(tag, t):
    """Tag matched the gateway low_priority_tags list in effect: none before 13:11 UTC, the list incl. probe/E10-evoskill/
    E10-harnesslens from 13:11 to 18:40, the common list after 18:40 (2026-10-11)."""
    if t < LOWPRI_START:
        return False
    tags = LOWPRI_BEFORE_FIX if t < LOWPRI_FIX_T else LOWPRI_COMMON
    return any(x in (tag or "") for x in tags)


def price_row(model, tok):
    """tok: dict in_unc, cache_read, cw5, cw1, out. Returns dict of USD components or None values (unpriced)."""
    pr = PRICES.get(model)
    if not pr:
        return {"usd_input": None, "usd_output": None, "usd_cache_read": None, "usd_cache_write": None, "usd_total": None, "priced": False}
    M = 1e6
    cw = None if tok["cw1"] else tok["cw5"] * pr["cache_write_5m"] / M  # no 1h price in pricing.json
    d = {"usd_input": tok["in_unc"] * pr["input"] / M, "usd_output": tok["out"] * pr["output"] / M,
         "usd_cache_read": tok["cache_read"] * pr["cache_read"] / M, "usd_cache_write": cw, "priced": True}
    d["usd_total"] = None if cw is None else d["usd_input"] + d["usd_output"] + d["usd_cache_read"] + cw
    return d


# ----------------------------------------------------------------------------------------------- run registry
def discover_runs():
    """Return (main, others). main[(suite, arm, seed)] = info; others = list of non-main dirs (waste evidence)."""
    main, others = {}, []
    for suite, root in SUITE_ROOT.items():
        if not root.is_dir():
            continue
        for armdir in sorted(root.iterdir()):
            n = armdir.name
            if not armdir.is_dir() or n.startswith("_"):
                continue
            if n == "superseded" or n.startswith("superseded_"):
                for sub in sorted(armdir.iterdir()):
                    if sub.is_dir():
                        for sd in sorted(sub.glob("s[0-9]*")):
                            others.append({"suite": suite, "arm": canon_arm(sub.name.replace("pilot_", "")), "dir": str(sd),
                                           "kind": "superseded", "via": str(armdir.name)})
                    elif sub.is_file():
                        pass
                continue
            if n.startswith("pilot-"):
                for sd in sorted(armdir.glob("s[0-9]*")):
                    others.append({"suite": suite, "arm": canon_arm(n[6:]), "dir": str(sd), "kind": "pilot", "via": n})
                continue
            if n == "smoke" or "smoke" in n:
                others.append({"suite": suite, "arm": n, "dir": str(armdir), "kind": "smoke", "via": n})
                continue
            for sd in sorted(armdir.iterdir()):
                if not sd.is_dir():
                    continue
                m = re.fullmatch(r"s(\d+)", sd.name)
                if m:
                    key = (suite, canon_arm(n), int(m.group(1)))
                    stopped = jload(sd / "STOPPED.json")
                    sup = (sd / "SUPERSEDED.txt").read_text()[:400] if (sd / "SUPERSEDED.txt").exists() else None
                    main[key] = {"suite": suite, "arm": canon_arm(n), "arm_dir": n, "seed": int(m.group(1)), "dir": str(sd),
                                 "stopped": stopped, "superseded_note": sup, "restart_dirs": []}
                    continue
                m = re.fullmatch(r"s(\d+)_(.+)", sd.name)
                if m:
                    others.append({"suite": suite, "arm": canon_arm(n), "seed": int(m.group(1)), "dir": str(sd),
                                   "kind": "stopped" if "stopped" in m.group(2) else "restart", "via": m.group(2)})
    arms_by_suite = defaultdict(set)
    for k in main:
        arms_by_suite[k[0]].add(k[1])
    for o in others:  # superseded dir names carry suffixes (e.g. metaharness-gold-readable-...): match by longest arm prefix
        if o["kind"] in ("superseded", "pilot") and o["arm"] not in arms_by_suite[o["suite"]]:
            cands = [a for a in arms_by_suite[o["suite"]] if o["arm"].startswith(a)]
            if cands:
                o["arm"] = max(cands, key=len)
    for o in others:
        if o["kind"] in ("restart", "stopped") and (o["suite"], o["arm"], o["seed"]) in main:
            main[(o["suite"], o["arm"], o["seed"])]["restart_dirs"].append(o["dir"])
    # attach pilot/superseded dirs to arms (seed-agnostic evidence)
    for o in others:
        if o["kind"] in ("pilot", "superseded"):
            for k, v in main.items():
                if k[0] == o["suite"] and k[1] == o["arm"] and Path(o["dir"]).name == "s%d" % k[2]:
                    v["restart_dirs"].append(o["dir"])
    return main, others


CUTOFF_MARKERS = ["manifest/negtest.txt", "logs/baseline.json", "negtest_before_launch.txt", "isolation_negtest.txt",
                  "launcher.log", "candidates.jsonl", "events.jsonl", "rollout_counter.json", "manifest.json"]


def derive_cutoffs(main):
    """Per run: time before which gateway calls with the run's tag belong to a superseded attempt."""
    for key, info in main.items():
        info["cutoff"] = None
        info["cutoff_source"] = None
        if not info["restart_dirs"]:
            continue
        manual = MANUAL_CUTOFFS.get((key[0], "*"))
        if manual and key[0] == "B":
            info["cutoff"], info["cutoff_source"] = epoch(manual[0]), manual[1]
            continue
        d = Path(info["dir"])
        b = birth([d / m for m in CUTOFF_MARKERS])
        if b:
            p, t = min(b.items(), key=lambda kv: kv[1])
            info["cutoff"], info["cutoff_source"] = float(t), "derived: birth time of " + os.path.relpath(p, d)


# ----------------------------------------------------------------------------------------------- gateway pass
RUN_RE = re.compile(r"^(E10[BC]?|E12[AC])-(.+)-s(\d+)$")
SMOKE_WORDS = ("smoke", "probe", "negtest", "mock", "test", "wd")


def classify_tag(tag):
    """-> (suite, arm, seed, kind, role).  kind: run | pilot | chaser | smoke | pre | untagged"""
    if not tag or tag == "untagged":
        return (None, "untagged", None, "untagged", "")
    parts = tag.split(":")
    run_id = parts[1] if len(parts) > 1 else tag
    role = parts[3] if len(parts) > 3 else (parts[2] if len(parts) > 2 else "")
    m = RUN_RE.match(run_id)
    if not m:
        if run_id.startswith(("E10", "E12")):
            exp = run_id.split("-")[0]
            return (SUITE_OF.get(exp), run_id, None, "smoke", role)
        return (None, run_id, None, "pre", role)
    exp, arm, seed = m.group(1), m.group(2), int(m.group(3))
    suite = SUITE_OF[exp]
    if seed >= 90 or any(w in arm for w in SMOKE_WORDS):
        return (suite, canon_arm(arm), seed, "smoke", role)
    if arm.startswith("pilot-"):
        return (suite, canon_arm(arm[6:]), seed, "pilot", role)
    if arm.startswith("chaser-"):
        return (suite, "chaser-" + canon_arm(arm[7:]), seed, "chaser", role)
    return (suite, canon_arm(arm), seed, "run", role)


def norm_usage(d):
    u = d.get("usage") or {}
    if d.get("api") == "openai":
        p = u.get("prompt_tokens") or 0
        c = u.get("completion_tokens") or 0
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        reas = (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        return {"in_unc": max(p - cached, 0), "cache_read": cached, "cw5": 0, "cw1": 0, "out": c, "reas": reas,
                "ledger": (u.get("total_tokens") or (p + c)), "noncache": p + c}
    i = u.get("input_tokens") or 0
    o = u.get("output_tokens") or 0
    cr = u.get("cache_read_input_tokens") or 0
    cw = u.get("cache_creation_input_tokens") or 0
    cc = u.get("cache_creation") or {}
    cw1 = cc.get("ephemeral_1h_input_tokens") or 0
    cw5 = cw - cw1
    reas = (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0
    return {"in_unc": i, "cache_read": cr, "cw5": cw5, "cw1": cw1, "out": o, "reas": reas,
            "ledger": (u.get("total_tokens") or (i + o + cw)), "noncache": i + o + cw}


class Acc:
    __slots__ = ("calls", "status", "retried", "extra", "tok", "lat", "que", "first", "last", "ledger", "noncache", "nousage")

    def __init__(self):
        self.calls = 0
        self.status = Counter()
        self.retried = 0
        self.extra = 0
        self.tok = Counter()
        self.lat = []
        self.que = []
        self.first = None
        self.last = None
        self.ledger = 0
        self.noncache = 0
        self.nousage = 0


def read_gateway(main):
    lines = []
    with open(GATEWAY_LOG) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                try:
                    lines.append(json.loads(ln))
                except Exception:
                    pass
    acc = defaultdict(Acc)
    run_span = {}
    last_t = 0
    for d in lines:
        t = epoch(d.get("t")) or 0
        last_t = max(last_t, t)
        suite, arm, seed, kind, role = classify_tag(d.get("tag"))
        if kind == "run":
            info = main.get((suite, arm, seed))
            if info is None:
                cat = "no_run_dir"
            elif info["stopped"]:
                cat = "stopped"
            elif info["superseded_note"]:
                cat = "superseded"
            elif info["cutoff"] and t < info["cutoff"]:
                cat = "restart_waste"
            else:
                cat = "main"
        elif kind == "chaser":
            cat = "chaser_eval"
        else:
            cat = {"pilot": "pilot", "smoke": "smoke", "pre": "smoke", "untagged": "untagged"}[kind]
        model = d.get("model") or ""
        lp = low_priority(d.get("tag"), t)
        a = acc[(suite or "-", arm, seed if seed is not None else -1, cat, role, model, d.get("api"), lp)]
        n = norm_usage(d)
        a.calls += 1
        a.status[d.get("status")] += 1
        att = d.get("attempts")
        if isinstance(att, int) and att > 1:
            a.retried += 1
            a.extra += att - 1
        for k in ("in_unc", "cache_read", "cw5", "cw1", "out", "reas"):
            a.tok[k] += n[k]
        a.ledger += n["ledger"]
        a.noncache += n["noncache"]
        if not d.get("usage"):
            a.nousage += 1
        if isinstance(d.get("latency_s"), (int, float)):
            a.lat.append(d["latency_s"])
        if isinstance(d.get("queue_s"), (int, float)):
            a.que.append(d["queue_s"])
        a.first = t if a.first is None else min(a.first, t)
        a.last = t if a.last is None else max(a.last, t)
        sp = run_span.setdefault((suite or "-", arm, seed if seed is not None else -1, cat), [t, t])
        sp[0] = min(sp[0], t)
        sp[1] = max(sp[1], t)
    return lines, acc, run_span, last_t


def fetch_health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ----------------------------------------------------------------------------------------------- rollout adapters
def _tok_from_approx(r):
    a = r.get("approx") or {}
    m = re.search(r"total only:\s*(\d+)", str(a.get("tokens", "")))
    return int(m.group(1)) if m else None


EXTRA_COLS = ["n_target_calls", "n_usersim_calls", "n_judge_calls", "usersim_prompt_tokens", "usersim_completion_tokens"]


def adapter_unified(rd):
    files = sorted(list(rd.glob("rollouts_metrics*.jsonl")) + list(rd.glob(".capevolve/run_*/rollouts_metrics*.jsonl")),
                   key=lambda p: ("converted" in p.name, p.name))
    if not files:
        return None
    # prefer the exact (non-converted) file unless it is shorter than the converter output
    parsed = [(f, jsonl(f)) for f in files]
    best = max(parsed, key=lambda fr: (len(fr[1]) > 0, "converted" not in fr[0].name, len(fr[1]))) if len(parsed) == 1 else None
    if best is None:
        exact = [fr for fr in parsed if "converted" not in fr[0].name]
        conv = [fr for fr in parsed if "converted" in fr[0].name]
        best = exact[0] if exact and (not conv or len(exact[0][1]) >= len(conv[0][1])) else (conv[0] if conv else exact[0])
    files = [best[0]]
    rows = []
    for r in best[1]:
        tt = r.get("target_total_tokens") or r.get("target_tokens_total") or _tok_from_approx(r)
        rows.append({"task_id": r.get("task_id"), "split": r.get("split"), "trial_seed": r.get("trial_seed"),
                     "candidate_id": r.get("candidate_id"), "t_start": r.get("t_start"), "t_end": r.get("t_end"),
                     "wall_s": r.get("wall_s"), "turns": r.get("turns"), "n_llm_calls": r.get("n_llm_calls"),
                     "target_prompt_tokens": r.get("target_prompt_tokens"), "target_completion_tokens": r.get("target_completion_tokens"),
                     "target_total_tokens": tt, "reward": r.get("reward"), "reward_as_saved": r.get("reward_as_saved"),
                     "error_kind": r.get("error_kind"), "error_text": r.get("error") or r.get("error_text"), "_source": r.get("source"),
                     "retried": r.get("retried"), "counted": True,
                     **{k: r.get(k) for k in EXTRA_COLS}})
    return "unified:" + files[0].name, rows


_RCACHE = {}
_RCACHE_PATH = OUT / ".rollout_cache.json"


def _parse_ts(s):
    try:
        return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()
    except Exception:
        return None


def _capevolve_rollout_row(path):
    st = path.stat()
    k = str(path)
    c = _RCACHE.get(k)
    if c and c[0] == st.st_mtime_ns and c[1] == st.st_size:
        return c[2]
    try:
        d = json.load(open(path))
    except Exception:
        return None
    r, s = d.get("rollout") or {}, d.get("score") or {}
    md = r.get("metadata") or {}
    tr = r.get("trace") or []
    ts = [_parse_ts(x.get("timestamp")) for x in tr if isinstance(x, dict) and x.get("timestamp")]
    ts = [x for x in ts if x]
    mets = {x.get("name"): x.get("value") for x in (s.get("metrics") or []) if isinstance(x, dict)}
    row = {"turns": sum(1 for x in tr if isinstance(x, dict) and x.get("role") == "assistant"),
           "wall_s": round(max(ts) - min(ts), 1) if len(ts) > 1 else None,
           "t_end": max(ts) if ts else None, "tokens": r.get("tokens"), "reward": s.get("reward"),
           "reward_as_saved": mets.get("hard_no_recalc"), "error": r.get("error"),
           "error_kind": md.get("error_kind") or ("infra" if r.get("error") else None), "seed": md.get("seed")}
    _RCACHE[k] = [st.st_mtime_ns, st.st_size, row]
    return row


def adapter_capevolve(rd):
    runs = sorted(list((rd / ".capevolve").glob("run_*")))
    if not runs:
        return None
    rows = []
    for run in runs:
        ev = jsonl(run / "eval_index.jsonl")
        jsons = {}
        for sp in ("train", "val", "test"):
            for p in sorted((run / "rollouts" / sp).glob("*__*__t*.json")) if (run / "rollouts" / sp).exists() else []:
                task, cand, trial = p.name[:-5].split("__")
                jsons[(sp, task, cand, int(trial[1:]))] = p
        used = set()
        for e in ev:
            sp = e.get("split")
            key = (sp, str(e.get("task")), e.get("tag"), e.get("trial_idx"))
            j = _capevolve_rollout_row(jsons[key]) if key in jsons else None
            used.add(key)
            rows.append({"task_id": e.get("task"), "split": sp, "trial_seed": e.get("trial_idx"), "candidate_id": e.get("tag"),
                         "t_start": None, "t_end": e.get("ts"), "wall_s": j and j["wall_s"], "turns": j and j["turns"],
                         "n_llm_calls": j and j["turns"], "target_prompt_tokens": None, "target_completion_tokens": None,
                         "target_total_tokens": e.get("tokens"), "reward": e.get("reward"),
                         "reward_as_saved": j and j["reward_as_saved"], "error_kind": j and j["error_kind"], "error_text": j and j.get("error"),
                         "retried": None, "counted": True})
        for key, p in jsons.items():
            if key in used:
                continue
            j = _capevolve_rollout_row(p)
            if j:
                rows.append({"task_id": key[1], "split": key[0], "trial_seed": key[3], "candidate_id": key[2], "t_start": None,
                             "t_end": j["t_end"], "wall_s": j["wall_s"], "turns": j["turns"], "n_llm_calls": j["turns"],
                             "target_prompt_tokens": None, "target_completion_tokens": None, "target_total_tokens": j["tokens"],
                             "reward": j["reward"], "reward_as_saved": j["reward_as_saved"], "error_kind": j["error_kind"], "error_text": j.get("error"),
                             "retried": None, "counted": True})
    if not rows:  # Suite A daemon meter (rollouts.jsonl) when per-rollout JSONs are not yet written
        for m in jsonl(rd / "logs" / "rollouts.jsonl"):
            rows.append({"task_id": m.get("task"), "split": m.get("split"), "trial_seed": m.get("seed"),
                         "candidate_id": str(m.get("cand", "")).rstrip("/").split("/")[-1], "t_start": (m["t"] - m["secs"]) if m.get("secs") else None,
                         "t_end": m.get("t"), "wall_s": m.get("secs"), "turns": None, "n_llm_calls": None,
                         "target_prompt_tokens": None, "target_completion_tokens": None, "target_total_tokens": m.get("tokens"),
                         "reward": None, "reward_as_saved": None, "error_kind": "infra" if m.get("error") else None,
                         "retried": None, "counted": True})
        return "capevolve-daemon-meter(no reward until rollouts JSON written)", rows
    return "capevolve:.capevolve/run_*", rows


def adapter_events(rd):
    p = rd / "events.jsonl"
    ev = [e for e in jsonl(p) if e.get("ev") == "rollout"]
    if not ev:
        return None
    rows = []
    for e in ev:
        rows.append({"task_id": e.get("id"), "split": e.get("who"), "trial_seed": None, "candidate_id": e.get("cand"),
                     "t_start": None, "t_end": e.get("t"), "wall_s": None, "turns": None, "n_llm_calls": None,
                     "target_prompt_tokens": None, "target_completion_tokens": None, "target_total_tokens": None,
                     "reward": e.get("reward"), "reward_as_saved": e.get("as_saved"),
                     "error_kind": "infra" if e.get("err") else None, "error_text": e.get("err"), "retried": None, "counted": e.get("counted", True)})
    return "events.jsonl(ev=rollout)", rows


def adapter_memento(rd):
    ro = jsonl(rd / "rollouts.jsonl")
    if not ro:
        return None
    rows = [{"task_id": r.get("id"), "split": r.get("phase"), "trial_seed": None, "candidate_id": r.get("lib"),
             "t_start": (r["t"] - r["wall_s"]) if r.get("t") and r.get("wall_s") else None, "t_end": r.get("t"),
             "wall_s": r.get("wall_s"), "turns": None, "n_llm_calls": None, "target_prompt_tokens": None,
             "target_completion_tokens": None, "target_total_tokens": r.get("tokens"), "reward": r.get("reward"),
             "reward_as_saved": r.get("as_saved"), "error_kind": "infra" if r.get("error") else None, "error_text": r.get("error"),
             "retried": None, "counted": r.get("counted", True)} for r in ro]
    return "rollouts.jsonl", rows


def adapter_gepa_evals(rd):
    ev = jsonl(rd / "evals.jsonl")
    if not ev:
        return None
    rows = [{"task_id": e.get("id"), "split": "val", "trial_seed": None, "candidate_id": "call%s" % e.get("call"), "t_start": None,
             "t_end": None, "wall_s": None, "turns": None, "n_llm_calls": None, "target_prompt_tokens": None,
             "target_completion_tokens": None, "target_total_tokens": None, "reward": e.get("reward"), "reward_as_saved": None,
             "error_kind": "infra" if e.get("error") else None, "error_text": e.get("error"), "retried": None, "counted": True} for e in ev]
    return "evals.jsonl", rows


def adapter_eval_opt(rd):
    rows = []
    for fn, sp in (("eval_opt.json", "opt"), ("eval_sel.json", "sel")):
        d = jload(rd / fn)
        if d and "rows" in d:
            rows += [dict(r, _split=sp) for r in d["rows"]]
    if not rows:
        return None
    rows = [{"task_id": r.get("id"), "split": r["_split"], "trial_seed": r.get("trial"), "candidate_id": "seed", "t_start": None,
             "t_end": None, "wall_s": None, "turns": None, "n_llm_calls": None, "target_prompt_tokens": None,
             "target_completion_tokens": None, "target_total_tokens": r.get("tokens"), "reward": r.get("reward"),
             "reward_as_saved": None, "error_kind": "infra" if r.get("error") else None, "error_text": r.get("error"),
             "retried": (r.get("attempts") or 1) > 1, "counted": r["_split"] == "opt"} for r in rows]
    return "eval_opt.json+eval_sel.json", rows


ADAPTERS = [adapter_unified, adapter_capevolve, adapter_events, adapter_memento, adapter_gepa_evals, adapter_eval_opt]


def rollout_rows(rd):
    """Run every adapter; keep the one with the most rows (ties: adapter order). Partial converter output never hides a fuller source."""
    best = ("none (no per-rollout record in run dir)", [])
    for ad in ADAPTERS:
        try:
            r = ad(rd)
        except Exception as e:  # keep the pipeline alive; report the failure
            r = ("adapter-error:%s:%s" % (ad.__name__, e), [])
        if r and len(r[1]) > len(best[1]):
            best = r
    return best


# ----------------------------------------------------------------------------------------------- uniform error classifier
# ONE rule for every arm (analysis_plan.md section 6, R14).  The adapter's own label is kept in `error_kind_adapter`.
#   infra     = a transport / timeout / sandbox-HTTP error string, OR zero target-LLM calls together with an error
#   candidate = any other failure or error (reward < 1 without an infra cause)
#   unverifiable = the adapter said "infra" but no string survives and the call count is not zero: neither confirmed nor refuted.
#                  Reported per arm; pessimistic bound counts it as a failure, optimistic bound drops it (analysis_plan section 6.5).
#   ""        = no error and reward >= 1
# "zero calls" is only used when the call count is known (n_target_calls, else n_llm_calls); None never counts as zero.
INFRA_RE = re.compile(
    r"timed? ?out|timeout|connection ?(error|reset|refused|aborted)|connecterror|apiconnection|remoteprotocol|read ?error|broken pipe|"
    r"infrastructure|sandbox exec failed|server error|internal ?server|service ?unavailable|bad gateway|gateway time|rate ?limit|"
    r"\b(429|500|502|503|504)\b|container (pull|start)|oom|out of memory|ratelimit|upstream", re.I)

USERSIM_RE = re.compile(r"user.?simulator", re.I)


def _calls(r):
    for k in ("n_target_calls", "n_llm_calls"):
        v = r.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
    return None


def uniform_class(r):
    """returns (class, rule) with class in {"", "infra", "candidate", "unverifiable"}"""
    txt = str(r.get("error_text") or "")
    adapter = r.get("error_kind_adapter")
    has_err = bool(adapter or txt)
    if has_err:
        if txt and USERSIM_RE.search(txt):
            # simulated-user malfunction: environment, shared by all arms, but a candidate's messages could provoke it;
            # own subclass so a sensitivity analysis can flip these to candidate
            return "infra", "env_user_simulator"
        if txt and INFRA_RE.search(txt):
            return "infra", "error_string"
        # a recorded non-infra string (e.g. "task_template.md broke the placeholder contract") is candidate-induced even with 0 calls;
        # the zero-call rule only decides label-only errors whose text the adapter did not keep
        if not txt and _calls(r) == 0:
            return "infra", "zero_target_calls_with_error"
        if adapter == "infra" and not txt:
            return "unverifiable", "adapter_infra_unverifiable"
        return "candidate", "error_other"
    rw = r.get("reward")
    if isinstance(rw, (int, float)) and rw >= 1.0:
        return "", ""
    return "candidate", "failure_no_error"


def attach_pool_error_text(rd, rows):
    """Trace2Skill stores the error string only in pool.jsonl; give it to the metric rows that carry an adapter label but no text.
    Matching is by task id, consumed one-to-one in file order."""
    cache = {}
    for r in rows:  # SkillOpt: the converter dropped the string, the per-step results.jsonl has it
        src = r.get("_source")
        if r.get("error_kind") and not r.get("error_text") and src and str(src).endswith("results.jsonl"):
            if src not in cache:
                cache[src] = {str(e.get("id")): e.get("error") for e in jsonl(rd / src) if e.get("error")}
            r["error_text"] = cache[src].get(str(r.get("task_id"))) or r.get("error_text")
    pool = [e for e in jsonl(rd / "pool.jsonl") if e.get("error")]
    if not pool:
        return
    by = defaultdict(list)
    for e in pool:
        by[str(e.get("id"))].append(e["error"])
    for r in rows:
        if r.get("error_kind") and not r.get("error_text") and by.get(str(r.get("task_id"))):
            r["error_text"] = by[str(r["task_id"])].pop(0)


def attach_raw_error_text(rd, rows):
    """Last-resort string recovery for rows that carry an adapter label but no text: tau2 rollout JSONs (CapEvolve B/C arms),
    Meta-Harness train/val result files, GEPA best-output files.  Search-time rows only; the final evaluation records every string."""
    need = [r for r in rows if r.get("error_kind") and not r.get("error_text")]
    if not need:
        return
    # (a) CapEvolve rollout JSONs: .capevolve/run_*/rollouts/*/<task>__<cand>__t<trial>.json
    idx = {}
    for f in rd.glob(".capevolve/run_*/rollouts/*/*__*__t*.json"):
        idx[f.stem] = f
    for r in need:
        stem = "%s__%s__t%s" % (r.get("task_id"), r.get("candidate_id"), r.get("trial_seed") if r.get("trial_seed") is not None else 0)
        f = idx.get(stem)
        if f:
            d = jload(f) or {}
            r["error_text"] = ((d.get("rollout") or {}).get("error") or (d.get("score") or {}).get("feedback") or r.get("error_text"))
    # (b) Meta-Harness: workspace/logs/<cand>/train_results.json and private/<split>/<cand>.json (lists of {id, error})
    mh = defaultdict(list)
    for f in list(rd.glob("workspace/logs/*/*results*.json")) + list(rd.glob("private/*/*.json")):
        d = jload(f)
        if isinstance(d, list):
            cand = f.parent.name if f.name.endswith("results.json") else f.stem
            for x in d:
                if isinstance(x, dict) and x.get("error") not in (None, "None", ""):
                    mh[(str(x.get("id")), cand)].append(x["error"])
    # (c) GEPA: gepa_run/generated_best_outputs_valset/task_*/iter_*.json ({id, reward, error})
    ge = defaultdict(list)
    for f in rd.glob("gepa_run/generated_best_outputs_valset/*/*.json"):
        x = jload(f)
        if isinstance(x, dict) and x.get("error") not in (None, "None", ""):
            ge[str(x.get("id"))].append(x["error"])
    for r in need:
        if r.get("error_text"):
            continue
        k = (str(r.get("task_id")), str(r.get("candidate_id")))
        if mh.get(k):
            r["error_text"] = mh[k][0]
        elif ge.get(str(r.get("task_id"))) and str(r.get("candidate_id", "")).startswith("best-at-conversion"):
            r["error_text"] = ge[str(r["task_id"])][0]


# ----------------------------------------------------------------------------------------------- run-level facts
def counted_rollouts(rd):
    for rel, keys in (("rollout_counter.json", ("total", "rollouts")), ("logs/rollout_counter.json", ("total",))):
        d = jload(rd / rel)
        if isinstance(d, dict):
            for k in keys:
                if num(d.get(k)) is not None:
                    return d[k], rel + ":" + k
    for run in sorted((rd / ".capevolve").glob("run_*")):
        st = jload(run / "state.json")
        if st and num((st.get("spent") or {}).get("metric_calls")) is not None:
            return st["spent"]["metric_calls"], "%s/state.json:spent.metric_calls" % run.name
    d = jload(rd / "eval_opt.json")
    if d and num(d.get("rollout_attempts_counted")) is not None:
        return d["rollout_attempts_counted"], "eval_opt.json:rollout_attempts_counted"
    d = jload(rd / "global_counter.json")
    if d and num(d.get("total")) is not None:
        return d["total"], "global_counter.json:total"
    return None, None


def infra_retries(rd):
    d = jload(rd / "rollout_counter.json") or jload(rd / "logs" / "rollout_counter.json") or {}
    r = d.get("infra_retries", d.get("retries"))
    d2 = jload(rd / "infra_retries.json")
    return r, d2


def candidate_counts(rd):
    paths = [rd / "candidates.jsonl"] + sorted((rd / ".capevolve").glob("run_*/candidates.jsonl"))
    ev = []
    for p in paths:
        ev += jsonl(p)
    c = defaultdict(set)
    for e in ev:
        c[e.get("event")].add(e.get("candidate_id"))
    return {"created": len(c["created"]), "evaluated": len(c["evaluated"]), "accepted": len(c["accepted"]),
            "rejected": len(c["rejected"]), "selected": len(c["selected"]), "events": len(ev),
            "log_present": any(p.exists() for p in paths)}


def capevolve_state(rd):
    out = {}
    for run in sorted((rd / ".capevolve").glob("run_*")):
        st = jload(run / "state.json")
        if st:
            sp = st.get("spent") or {}
            out = {"state_optimizer_tokens": sp.get("optimizer_tokens"), "state_metric_calls": sp.get("metric_calls"),
                   "state_iterations": sp.get("iterations"), "state_optimizer_usd": sp.get("optimizer_usd"),
                   "state_runner_tokens": sp.get("runner_tokens"), "state_best_val": sp.get("best_val")}
    cs = jload(rd / "cost_summary.json")
    if cs and isinstance(cs.get("optimizer"), dict):
        out["cost_summary_optimizer_noncache"] = cs["optimizer"].get("non_cache_read_tokens")
    return out


# ----------------------------------------------------------------------------------------------- configs
SECRET = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|AUTH)[A-Z_]*=\S+|sk-[A-Za-z0-9_\-]{8,}", re.I)


def scrub(s):
    return SECRET.sub("<redacted>", s)


def read_text(p, n=4000):
    try:
        return scrub(Path(p).read_text()[:n])
    except Exception:
        return None


def parse_simple_yaml(path):
    try:
        import yaml
        return yaml.safe_load(open(path))
    except Exception:
        pass
    out = {}
    try:
        for line in open(path):
            m = re.match(r"^([A-Za-z_][\w\-]*):\s*(.*?)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2).strip('"')
    except Exception:
        return None
    return out


def live_cmdlines():
    try:
        out = subprocess.run(["ps", "-eo", "pid,lstart,args"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return []
    return [scrub(l.strip()) for l in out.splitlines() if "--out" in l or "driver.sh" in l or "run_hc.sh" in l or "run_ao.sh" in l]


def load_deviations(arm, rd):
    devs = []
    for p in (BASELINES / ("deviations_%s.json" % arm), BASELINES / ("deviations_%s.json" % arm.replace("metaharness", "metaharness")),
              rd / "deviations.json", rd.parent / "deviations.json", RUNS / "E10B" / ("deviations_%s_tau.json" % arm)):
        d = jload(p)
        if d is not None:
            devs.append({"file": str(p), "content": d})
    return devs


def isolation_info(rd, manifest):
    info = {}
    if isinstance(manifest, dict) and manifest.get("optimizer_isolation"):
        info["manifest.optimizer_isolation"] = manifest["optimizer_isolation"]
    for rel in ("manifest/negtest.txt", "isolation_negtest.txt", "negtest_before_launch.txt", "isolation_tests.json", "negtest_output.txt"):
        t = read_text(rd / rel, 3000)
        if t:
            verdicts = [l for l in t.splitlines() if re.search(r"verdict|PASS|FAIL", l)]
            info[rel] = {"verdict_lines": verdicts[-3:], "n_denied": sum(1 for l in t.splitlines() if l.startswith("denied"))}
    return info or "not recorded"


def build_config(info, role_models, state, ctx):
    rd = Path(info["dir"])
    suite, arm, seed = info["suite"], info["arm"], info["seed"]
    manifests = {}
    for p in [rd / "manifest.json", rd / "manifest" / "manifest.json"] + sorted(rd.glob("manifest*.json")):
        d = jload(p)
        if d is not None:
            manifests[str(p.relative_to(rd))] = d
    sha = {}
    for rel in ("manifest/integration_sha.txt",):
        t = read_text(rd / rel, 100)
        if t:
            sha["integration_sha"] = t.strip()
    t = read_text(RUNS / "E10B" / "WT_SHA.txt", 200)
    if suite == "B" and t:
        sha["E10B/WT_SHA.txt"] = t.strip()
    for m in manifests.values():
        if isinstance(m, dict):
            for k in ("worktree_sha", "tau2_pin", "campaign_head_base"):
                if m.get(k):
                    sha[k] = m[k]
    prov = jload(BASELINES / "PROVENANCE.json", {})
    runbook = jload(BASELINES / "RUNBOOK.json", {})
    method_ver = None
    key = {"hc": None, "ao": None}.get(arm, arm)
    if key and isinstance(prov.get("clones"), dict) or key:
        for pk in (key, {"metaharness": "meta-harness"}.get(arm)):
            if pk and pk in prov:
                method_ver = prov[pk]
    pins = (runbook.get("pins") or {}).get(arm)
    cfgs = {}
    for rel in ("project/capevolve.yaml", ".capevolve/project/capevolve.yaml", "config.yaml", "skillopt_out/config.json",
                "gse_out/config.json", "study/manifest.json"):
        p = rd / rel
        if p.exists():
            cfgs[rel] = jload(p) if rel.endswith(".json") else parse_simple_yaml(p)
    scripts = {}
    for rel in ("driver.sh", "env.sh", "restart_note.txt", "negtest_before_launch.txt"):
        t = read_text(rd / rel, 2500)
        if t and rel != "negtest_before_launch.txt":
            scripts[rel] = t
    for s in ("launch_e10_competitors.sh", "launch_e10_new.sh", "launch_e10.sh", "launch_e10_evoskill.sh"):
        t = read_text(BASELINES / "code" / s, 2500) or read_text(BASELINES / s, 2500)
        if t and arm in "\n".join(t.splitlines()[:3]):
            scripts["baselines/" + s] = t
    if suite == "A" and arm in ("hc", "ao"):
        t = read_text(RUNS / "E10" / "_tools" / ("run_%s.sh" % arm), 3500)
        if t:
            scripts["E10/_tools/run_%s.sh" % arm] = t
    live = [c for c in ctx["cmdlines"] if info["dir"] in c]
    cmd_args = {}
    for c in live:
        for m in re.finditer(r"--([\w-]+)(?:[ =]([^\s-][^\s]*))?", c):
            cmd_args[m.group(1)] = m.group(2) if m.group(2) is not None else True
    if cmd_args:
        cfgs["live_cmdline_args"] = cmd_args
    fails = jload(rd / "llm_failure_counts.json")
    ir, ir2 = infra_retries(rd)
    cfg = {
        "suite": suite, "arm": arm, "seed": seed, "run_dir": info["dir"],
        "status": "stopped" if info["stopped"] else ("superseded" if info["superseded_note"] else "active_or_finished"),
        "stopped_record": info["stopped"], "superseded_note": info["superseded_note"],
        "tier_track": TIERS_A.get(arm, "not recorded") if suite == "A" else
        ("Suite B/C control (E10B manifest)" if arm.startswith("ctl") else ("Suite B/C search arm (E10B manifest)" if arm in ("hc", "ao", "gepa") else "not recorded")),
        "tier_track_source": "decisions.md 2026-10-11 09:00 capacity-driven scope decision (+09:55 EvoSkill promotion)" if suite == "A" else "run manifest",
        "method_version_or_sha": {"shas_from_manifests": sha or "not recorded", "provenance_entry": method_ver or "not recorded",
                                  "runbook_pin": pins or "not recorded"},
        "hyperparameters_and_specs": cfgs or "not recorded",
        "launch_scripts": scripts or "not recorded",
        "live_process_cmdlines_snapshot": live or "not recorded (no live process matched at collection time)",
        "models_by_role_observed_in_gateway": role_models or "not recorded",
        "budget": {"counted_rollouts_cap_per_search": "600 (decisions.md frozen E10 parameters; manifest/launch may differ per arm)",
                   "optimizer_noncache_token_cap": OPT_CAP, "rollout_counter": counted_rollouts(rd)[0]},
        "concurrency": {k: v.get("concurrency_per_search") for k, v in manifests.items() if isinstance(v, dict) and v.get("concurrency_per_search")} or
        "see launch_scripts/live cmdlines (E10_CONC / TAU2_MAX_CONCURRENCY env) else not recorded",
        "isolation": isolation_info(rd, next((v for v in manifests.values() if isinstance(v, dict) and "optimizer_isolation" in v), None)),
        "manifests": manifests or "not recorded",
        "deviations": load_deviations(arm, rd) or "not recorded",
        "restart_siblings_and_superseded_dirs": info["restart_dirs"],
        "restart_cutoff": {"utc": iso(info.get("cutoff")), "source": info.get("cutoff_source")} if info.get("cutoff") else None,
        "infra": {"infra_retries_in_counter": ir, "infra_retries_json": ir2, "llm_failure_counts": fails},
        "capevolve_state": state or None,
    }
    return cfg


# ----------------------------------------------------------------------------------------------- main
def fmt(x, nd=2):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return ("%." + str(nd) + "f") % x
    return str(x)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    global _RCACHE
    _RCACHE = jload(_RCACHE_PATH, {}) or {}
    health1 = fetch_health()
    main_runs, others = discover_runs()
    derive_cutoffs(main_runs)
    lines, acc, run_span, last_t = read_gateway(main_runs)
    health2 = fetch_health()
    newest = last_t

    # ---- by role / model
    role_rows = []
    for (suite, arm, seed, cat, role, model, api, lp), a in sorted(acc.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        tok = {k: a.tok[k] for k in ("in_unc", "cache_read", "cw5", "cw1", "out", "reas")}
        usd = price_row(model, tok)
        lat, que = sorted(a.lat), sorted(a.que)
        errs = {str(k): v for k, v in a.status.items() if k != 200}
        role_rows.append({
            "suite": suite, "arm": arm, "seed": seed if seed >= 0 else "", "category": cat, "role": role, "model": model, "api": api,
            "rits": model.startswith("rits/"), "low_priority": lp, "calls": a.calls, "ok_200": a.status.get(200, 0), "errors": sum(errs.values()),
            "errors_by_status": json.dumps(errs, sort_keys=True), "retried_calls": a.retried, "extra_attempts": a.extra,
            "calls_without_usage": a.nousage, "in_uncached": tok["in_unc"], "cache_read": tok["cache_read"],
            "cache_write_5m": tok["cw5"], "cache_write_1h": tok["cw1"], "output": tok["out"], "reasoning": tok["reas"],
            "ledger_tokens": a.ledger, "noncache_tokens": a.noncache,
            "usd_input": usd["usd_input"], "usd_output": usd["usd_output"], "usd_cache_read": usd["usd_cache_read"],
            "usd_cache_write": usd["usd_cache_write"], "usd_total": usd["usd_total"], "priced": usd["priced"],
            "latency_p50": pct(lat, 50), "latency_p95": pct(lat, 95), "latency_max": lat[-1] if lat else None,
            "queue_p50": pct(que, 50), "queue_p95": pct(que, 95), "first_call": iso(a.first), "last_call": iso(a.last)})
    write_csv(OUT / "metrics_by_role.csv", role_rows)

    # ---- per-rollout and run facts
    rollout_out, run_facts = [], {}
    for key, info in sorted(main_runs.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        rd = Path(info["dir"])
        src, rows = rollout_rows(rd)
        counted, csrc = counted_rollouts(rd)
        cand = candidate_counts(rd)
        ir, _ = infra_retries(rd)
        st = capevolve_state(rd)
        cat = "stopped" if info["stopped"] else ("superseded" if info["superseded_note"] else "main")
        attach_pool_error_text(rd, rows)
        attach_raw_error_text(rd, rows)
        for r in rows:
            r2 = dict(r)
            r2["error_kind_adapter"] = r2.get("error_kind")
            r2["error_class_uniform"], r2["error_rule_uniform"] = uniform_class(r2)
            r2["error_kind"] = r2["error_class_uniform"] if r2["error_kind_adapter"] or r2["error_text"] else r2["error_kind_adapter"]
            r2.update({"suite": key[0], "arm": key[1], "seed": key[2], "category": cat, "source_adapter": src})
            for tk in ("t_start", "t_end"):
                if isinstance(r2.get(tk), (int, float)):
                    r2[tk] = iso(r2[tk])
            rollout_out.append(r2)
        run_facts[key] = {"counted": counted, "counted_source": csrc, "cand": cand, "infra_retries": ir, "rollout_source": src,
                          "n_rollout_rows": len(rows), "state": st, "category": cat}
    write_csv(OUT / "rollout_metrics.csv", rollout_out, cols=[
        "suite", "arm", "seed", "category", "source_adapter", "task_id", "split", "trial_seed", "candidate_id", "t_start", "t_end", "wall_s",
        "turns", "n_llm_calls", "target_prompt_tokens", "target_completion_tokens", "target_total_tokens", "reward", "reward_as_saved",
        "error_kind", "error_kind_adapter", "error_class_uniform", "error_rule_uniform", "error_text", "retried", "counted"] + EXTRA_COLS)
    write_error_parity(rollout_out)
    try:
        json.dump(_RCACHE, open(_RCACHE_PATH, "w"))
    except Exception:
        pass

    # ---- by arm
    groups = defaultdict(list)
    for r in role_rows:
        groups[(r["suite"], r["arm"], r["seed"], r["category"])].append(r)
    arm_rows = []
    for (suite, arm, seed, cat), rs in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        row = {"suite": suite, "arm": arm, "seed": seed, "category": cat, "tier_track": TIERS_A.get(arm, "") if suite == "A" else ""}
        row["calls"] = sum(r["calls"] for r in rs)
        row["low_priority_calls"] = sum(r["calls"] for r in rs if r["low_priority"])
        row["errors"] = sum(r["errors"] for r in rs)
        eb = Counter()
        for r in rs:
            for k, v in json.loads(r["errors_by_status"]).items():
                eb[k] += v
        row["errors_by_status"] = json.dumps(dict(eb), sort_keys=True)
        row["retried_calls"] = sum(r["retried_calls"] for r in rs)
        row["extra_attempts"] = sum(r["extra_attempts"] for r in rs)
        for k in ("in_uncached", "cache_read", "cache_write_5m", "cache_write_1h", "output", "reasoning", "ledger_tokens", "noncache_tokens"):
            row[k] = sum(r[k] for r in rs)
        row["rits_ledger_tokens"] = sum(r["ledger_tokens"] for r in rs if r["rits"])
        row["nonrits_ledger_tokens"] = row["ledger_tokens"] - row["rits_ledger_tokens"]
        for cls, roles in (("target", TARGET_ROLES), ("user", USER_ROLES), ("judge", JUDGE_ROLES), ("optimizer", OPT_ROLES)):
            sel = [r for r in rs if (r["role"] in roles if cls != "optimizer" else r["role"] not in NON_OPT_ROLES)]
            row[cls + "_calls"] = sum(r["calls"] for r in sel)
            row[cls + "_noncache_tokens"] = sum(r["noncache_tokens"] for r in sel)
            pr = [r["usd_total"] for r in sel if r["usd_total"] is not None]
            unp = sum(r["noncache_tokens"] for r in sel if r["usd_total"] is None)
            row[cls + "_usd_priced"] = sum(pr) if pr else None
            row[cls + "_unpriced_noncache_tokens"] = unp
        other = [r for r in rs if r["role"] not in TARGET_ROLES | USER_ROLES | JUDGE_ROLES | OPT_ROLES]  # roles counted as optimizer if not target/user/judge/probe
        row["other_role_calls"] = sum(r["calls"] for r in other)
        for comp in ("usd_input", "usd_output", "usd_cache_read", "usd_cache_write"):
            v = [r[comp] for r in rs if r[comp] is not None]
            row[comp] = sum(v) if v else None
        pr = [r["usd_total"] for r in rs if r["usd_total"] is not None]
        row["usd_total_priced"] = sum(pr) if pr else None
        row["unpriced_noncache_tokens"] = sum(r["noncache_tokens"] for r in rs if r["usd_total"] is None)
        row["usd_lower_bound"] = bool(row["unpriced_noncache_tokens"])
        # optimizer cap (main category only is meaningful, reported for all)
        row["optimizer_cap_tokens"] = OPT_CAP
        row["optimizer_pct_of_cap"] = round(100.0 * row["optimizer_noncache_tokens"] / OPT_CAP, 1)
        row["optimizer_over_cap"] = row["optimizer_noncache_tokens"] > OPT_CAP
        span = run_span.get((suite, arm, seed if seed != "" else -1, cat))
        info = main_runs.get((suite, arm, seed if seed != "" else -1))
        row["first_call"] = iso(span[0]) if span else None
        row["last_call"] = iso(span[1]) if span else None
        if cat in MAIN_CATS and info is not None or (cat in MAIN_CATS and arm.startswith("chaser-")):
            pass
        facts = run_facts.get((suite, arm, seed if seed != "" else -1)) if cat == "main" else None
        if facts:
            start = span[0] if span else None
            end = span[1] if span else None
            if info and info["stopped"] and epoch(info["stopped"].get("stopped_utc")):
                end = epoch(info["stopped"]["stopped_utc"])
            wall_h = (end - start) / 3600.0 if start and end else None
            row.update({"counted_rollouts": facts["counted"], "counted_source": facts["counted_source"],
                        "rollout_record_source": facts["rollout_source"], "rollout_rows": facts["n_rollout_rows"],
                        "wall_clock_h_since_launch": round(wall_h, 2) if wall_h else None,
                        "rollouts_per_hour": round(facts["counted"] / wall_h, 1) if facts["counted"] and wall_h and wall_h > 0.25 else None,
                        "active": bool(end and newest - end < 1800),
                        "candidates_created": facts["cand"]["created"], "candidates_evaluated": facts["cand"]["evaluated"],
                        "candidates_accepted": facts["cand"]["accepted"], "candidates_rejected": facts["cand"]["rejected"],
                        "candidates_selected": facts["cand"]["selected"], "candidates_log_present": facts["cand"]["log_present"],
                        "infra_retries_in_counter": facts["infra_retries"]})
            row.update(facts["state"])
            c = facts["counted"]
            if c:
                row["tokens_per_counted_rollout_all_roles"] = round(row["noncache_tokens"] / c)
                row["target_tokens_per_rollout"] = round(row["target_noncache_tokens"] / c)
                row["target_plus_user_tokens_per_rollout"] = round((row["target_noncache_tokens"] + row["user_noncache_tokens"]) / c)
                row["usd_priced_per_rollout"] = round(row["usd_total_priced"] / c, 5) if row["usd_total_priced"] is not None else None
        arm_rows.append(row)
    write_csv(OUT / "metrics_by_arm.csv", arm_rows)

    # ---- waste evidence from run dirs (rollout counters of superseded/restart/pilot/smoke dirs)
    waste_dirs = []
    for o in others:
        rd = Path(o["dir"])
        c, cs = counted_rollouts(rd) if rd.is_dir() else (None, None)
        waste_dirs.append({"suite": o["suite"], "arm": o["arm"], "seed": o.get("seed", ""), "kind": o["kind"], "via": o.get("via"),
                           "dir": o["dir"], "counted_rollouts_in_dir": c, "counter_source": cs})
    write_csv(OUT / "waste_run_dirs.csv", waste_dirs)

    # ---- totals + reconciliation
    totals = build_totals(role_rows, lines, health1, health2)
    json.dump(totals, open(OUT / "campaign_totals.json", "w"), indent=1, default=str)

    # ---- configs
    ctx = {"cmdlines": live_cmdlines()}
    role_models = defaultdict(lambda: defaultdict(set))
    for r in role_rows:
        if r["category"] == "main" or r["category"] == "restart_waste":
            role_models[(r["suite"], r["arm"], r["seed"])][r["role"]].add(r["model"])
    configs = {"_generated_utc": iso(NOW.timestamp()), "_note": "values not found in manifests/specs/deviations/launch scripts are 'not recorded'; nothing is guessed",
               "runs": {}}
    for key, info in sorted(main_runs.items()):
        rm = {role: sorted(ms) for role, ms in role_models.get((key[0], key[1], key[2]), {}).items()}
        configs["runs"]["%s/%s/s%d" % key] = build_config(info, rm, run_facts[key]["state"], ctx)
    json.dump(configs, open(OUT / "configs_by_arm.json", "w"), indent=1, default=str)

    write_report(arm_rows, role_rows, totals, waste_dirs, run_facts, main_runs, newest)
    print("wrote", OUT, "gateway lines:", len(lines), "newest:", iso(newest))


def write_error_parity(rows):
    """per arm/seed: adapter label vs uniform label and how many change (error_label_parity.csv + .md)"""
    g = defaultdict(lambda: Counter())
    for r in rows:
        k = (r["suite"], r["arm"], r["seed"], r["category"])
        c = g[k]
        c["rollouts"] += 1
        a, u = r.get("error_kind_adapter") or "", r.get("error_class_uniform") or ""
        if a == "infra": c["adapter_infra"] += 1
        if a == "candidate": c["adapter_candidate"] += 1
        has = bool(a or r.get("error_text"))
        if has:
            c["errors"] += 1
            c["uniform_infra"] += u == "infra"
            c["uniform_candidate_error"] += u == "candidate"
            c["uniform_unverifiable"] += u == "unverifiable"
            if a == "candidate" and u == "infra": c["changed_candidate_to_infra"] += 1
            if a == "infra" and u == "candidate": c["changed_infra_to_candidate"] += 1
            if not a and u == "infra": c["changed_unlabelled_to_infra"] += 1
            if u == "infra" and r.get("error_rule_uniform") == "zero_target_calls_with_error" and not r.get("error_text"):
                c["infra_by_zero_calls_no_string"] += 1
            if not r.get("error_text"): c["errors_without_string"] += 1
            if r.get("error_rule_uniform") == "adapter_infra_unverifiable": c["adapter_infra_unverifiable"] += 1
        if u == "candidate" and not has: c["failures_without_error"] += 1
    cols = ["suite", "arm", "seed", "category", "rollouts", "errors", "errors_without_string", "adapter_infra", "adapter_candidate",
            "uniform_infra", "uniform_candidate_error", "uniform_unverifiable", "changed_candidate_to_infra", "changed_infra_to_candidate",
            "changed_unlabelled_to_infra", "infra_by_zero_calls_no_string", "adapter_infra_unverifiable", "failures_without_error"]
    out = [dict(zip(cols[:4], k), **{c: v[c] for c in cols[4:]}) for k, v in sorted(g.items(), key=lambda kv: tuple(str(x) for x in kv[0]))]
    write_csv(OUT / "error_label_parity.csv", out, cols=cols)
    lines = ["# Error-label parity: adapter label vs uniform classifier", "",
             "Rule (all arms): infra = transport/timeout/sandbox-HTTP error string, or zero target-LLM calls with an error; otherwise candidate. "
             "Adapter label kept in `error_kind_adapter` of rollout_metrics.csv. Only rows with an adapter label or an error string are counted in `errors`.", "",
             "| suite | arm | seed | cat | rollouts | errors | adapter infra | adapter cand. | uniform infra | uniform cand. | uniform unverifiable | cand->infra | infra->cand. | unlabelled->infra | infra by 0 calls, no string | adapter-infra unverifiable |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in out:
        if r["errors"] or r["adapter_infra"] or r["adapter_candidate"]:
            lines.append("| " + " | ".join(str(r[c]) for c in ["suite", "arm", "seed", "category", "rollouts", "errors", "adapter_infra", "adapter_candidate",
                         "uniform_infra", "uniform_candidate_error", "uniform_unverifiable", "changed_candidate_to_infra", "changed_infra_to_candidate",
                         "changed_unlabelled_to_infra", "infra_by_zero_calls_no_string", "adapter_infra_unverifiable"]) + " |")
    (OUT / "error_label_parity.md").write_text("\n".join(lines) + "\n")


def write_csv(path, rows, cols=None):
    if cols is None:
        cols = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def build_totals(role_rows, lines, h1, h2):
    def blank():
        return {"calls": 0, "errors": 0, "ledger_tokens": 0, "rits_ledger_tokens": 0, "nonrits_ledger_tokens": 0,
                "component_noncache_tokens": 0, "in_uncached": 0, "cache_read": 0, "cache_write": 0, "output": 0, "reasoning": 0,
                "usd_priced_proxy": 0.0, "usd_priced_calls_models": [], "unpriced_noncache_tokens": 0, "usd_lower_bound": False}
    T = {"by_suite_category": {}, "by_suite": {}, "overall": blank()}
    models_priced = defaultdict(set)
    for r in role_rows:
        for k in (("%s|%s" % (r["suite"], r["category"]), "by_suite_category"), (r["suite"], "by_suite"), ("overall", "overall")):
            key, grp = k
            tgt = T["overall"] if grp == "overall" else T[grp].setdefault(key, blank())
            tgt["calls"] += r["calls"]
            tgt["errors"] += r["errors"]
            tgt["ledger_tokens"] += r["ledger_tokens"]
            if r["rits"]:
                tgt["rits_ledger_tokens"] += r["ledger_tokens"]
            else:
                tgt["nonrits_ledger_tokens"] += r["ledger_tokens"]
            tgt["component_noncache_tokens"] += r["noncache_tokens"]
            tgt["in_uncached"] += r["in_uncached"]
            tgt["cache_read"] += r["cache_read"]
            tgt["cache_write"] += r["cache_write_5m"] + r["cache_write_1h"]
            tgt["output"] += r["output"]
            tgt["reasoning"] += r["reasoning"]
            if r["usd_total"] is not None:
                tgt["usd_priced_proxy"] += r["usd_total"]
            else:
                tgt["unpriced_noncache_tokens"] += r["noncache_tokens"]
                tgt["usd_lower_bound"] = True
    for grp in ("by_suite_category", "by_suite"):
        for v in T[grp].values():
            v.pop("usd_priced_calls_models", None)
    T["overall"].pop("usd_priced_calls_models", None)
    # reconciliation: first h1.calls log lines vs health at that time
    rec = {"health_before_read": h1, "health_after_read": h2, "log_lines": len(lines)}
    n = h1.get("calls") if isinstance(h1, dict) else None
    if isinstance(n, int) and n <= len(lines):
        sub = lines[:n]
        led = rits = 0
        recomputed = 0
        diff_calls = Counter()
        for d in sub:
            nu = norm_usage(d)
            led += nu["ledger"]
            if (d.get("model") or "").startswith("rits/"):
                rits += nu["ledger"]
            naive = nu["in_unc"] + nu["cache_read"] * 0 + nu["cw5"] + nu["cw1"] + nu["out"] if d.get("api") != "openai" else nu["noncache"]
            if naive != nu["ledger"]:
                diff_calls[(d.get("model"), d.get("api"), d.get("stream"))] += naive - nu["ledger"]
            recomputed += naive
        rec["prefix_calls_compared"] = n
        rec["log_ledger_total"] = led
        rec["log_ledger_rits"] = rits
        rec["log_ledger_nonrits_capped"] = led - rits
        rec["health_total_minus_log"] = h1.get("total_tokens", 0) - led
        rec["health_rits_minus_log"] = h1.get("rits_tokens", 0) - rits
        rec["health_capped_minus_log"] = h1.get("capped_tokens", 0) - (led - rits)
        rec["ledger_formula"] = "usage.total_tokens if truthy else (prompt+completion | input+output+cache_creation); rits = model startswith rits/"
        rec["naive_sum_in_out_cachewrite_minus_ledger_by_model_api_stream"] = {str(k): v for k, v in diff_calls.items()}
        rec["note"] = ("Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output "
                       "and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).")
    T["reconciliation"] = rec
    T["notes"] = ["USD is a PROXY (Anthropic list prices); IBM LiteLLM billing is not visible. Non-Claude models are unpriced: tokens only, USD null.",
                  "ledger_tokens = gateway /health basis (cache reads excluded for Anthropic; OpenAI prompt tokens incl. cached counted in full).",
                  "Categories other than main/chaser_eval are overhead/waste but still count toward campaign cost."]
    return T


def write_report(arm_rows, role_rows, totals, waste_dirs, run_facts, main_runs, newest):
    L = []
    A = L.append
    A("# Campaign metrics report")
    A("")
    A("Generated %s UTC from `%s` (newest call %s). Re-run: `refresh_metrics.sh --once`." % (iso(NOW.timestamp()), GATEWAY_LOG, iso(newest)))
    A("USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.")
    A("")
    rec = totals["reconciliation"]
    A("## Reconciliation with gateway /health")
    A("")
    if "log_ledger_total" in rec:
        h = rec["health_before_read"]
        A("| quantity | /health | recomputed from log (first %d calls) | diff |" % rec["prefix_calls_compared"])
        A("|---|---:|---:|---:|")
        A("| total_tokens | %s | %s | %s |" % (format(h["total_tokens"], ","), format(rec["log_ledger_total"], ","), format(rec["health_total_minus_log"], ",")))
        A("| rits_tokens | %s | %s | %s |" % (format(h["rits_tokens"], ","), format(rec["log_ledger_rits"], ","), format(rec["health_rits_minus_log"], ",")))
        A("| capped_tokens (non-RITS) | %s | %s | %s |" % (format(h["capped_tokens"], ","), format(rec["log_ledger_nonrits_capped"], ","), format(rec["health_capped_minus_log"], ",")))
        A("| calls | %s | %s | %s |" % (h["calls"], rec["prefix_calls_compared"], h["calls"] - rec["prefix_calls_compared"]))
        A("")
        A(rec["note"])
        A("Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `%s`" % json.dumps(rec["naive_sum_in_out_cachewrite_minus_ledger_by_model_api_stream"]))
    else:
        A("health unavailable: `%s`" % json.dumps(rec["health_before_read"]))
    A("")
    ov = totals["overall"]
    A("## Campaign totals")
    A("")
    A("| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, v in [("overall", ov)] + [("suite " + k, v) for k, v in sorted(totals["by_suite"].items())]:
        A("| %s | %s | %s | %s | %s | %s | %s | %s lb | %s |" % (name, format(v["calls"], ","), format(v["errors"], ","), format(v["component_noncache_tokens"], ","), format(v["ledger_tokens"], ","),
                                                         format(v["rits_ledger_tokens"], ","), format(v["nonrits_ledger_tokens"], ","),
                                                         "$%.2f" % v["usd_priced_proxy"], format(v["unpriced_noncache_tokens"], ",")))
    A("")
    A("By suite and category (overhead = everything except main/chaser_eval):")
    A("")
    A("| suite|category | calls | ledger tokens | RITS tokens | proxy USD |")
    A("|---|---:|---:|---:|---:|")
    for k, v in sorted(totals["by_suite_category"].items()):
        A("| %s | %s | %s | %s | $%.2f |" % (k, format(v["calls"], ","), format(v["ledger_tokens"], ","), format(v["rits_ledger_tokens"], ","), v["usd_priced_proxy"]))
    A("")
    main_rows = [r for r in arm_rows if r["category"] in MAIN_CATS]
    A("## Per arm x seed (main + chaser evaluation)")
    A("")
    A("| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |")
    A("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for r in main_rows:
        ou = r.get("optimizer_usd_priced")
        A("| %s | %s | %s | %s | %s | %s | %s | %s | %.2f | %.2f | %.0f (%.1f%%) | %s | %s/%s/%s | %s |" % (
            r["suite"], r["arm"], r["seed"], fmt(r.get("counted_rollouts")), fmt(r.get("wall_clock_h_since_launch")), fmt(r.get("rollouts_per_hour")),
            r["calls"], r["errors"], r["target_noncache_tokens"] / 1e6, r["user_noncache_tokens"] / 1e6,
            r["optimizer_noncache_tokens"] / 1e3, r["optimizer_pct_of_cap"],
            ("$%.2f" % ou + (" lb" if r["optimizer_unpriced_noncache_tokens"] else "")) if ou is not None else "n/a (unpriced)",
            fmt(r.get("candidates_created")), fmt(r.get("candidates_evaluated")), fmt(r.get("candidates_accepted")),
            fmt(r.get("tokens_per_counted_rollout_all_roles"))))
    A("")
    A("## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds")
    A("")
    A("Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.")
    A("")
    A("| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |")
    A("|---|---|---:|---:|---:|---:|---:|---:|")
    by = defaultdict(list)
    for r in main_rows:
        if r["category"] == "main" and r.get("counted_rollouts"):
            by[(r["suite"], r["arm"])].append(r)
    for (s, a), rs in sorted(by.items()):
        def mean(k):
            v = [x[k] for x in rs if x.get(k) is not None]
            return sum(v) / len(v) if v else None
        ou = [x["optimizer_usd_priced"] for x in rs if x.get("optimizer_usd_priced") is not None]
        A("| %s | %s | %d | %s | %s | %s | %s | %s |" % (s, a, len(rs), fmt(mean("target_tokens_per_rollout"), 0), fmt(mean("target_plus_user_tokens_per_rollout"), 0),
                                                         fmt(mean("tokens_per_counted_rollout_all_roles"), 0), fmt(mean("optimizer_noncache_tokens"), 0),
                                                         ("$%.2f" % (sum(ou) / len(ou))) if ou else "n/a"))
    A("")
    A("## Overhead / waste (not in main tables; included in campaign totals)")
    A("")
    A("| suite | arm | seed | category | calls | ledger tokens | RITS tokens | proxy USD |")
    A("|---|---|---|---|---:|---:|---:|---:|")
    agg = defaultdict(lambda: [0, 0, 0, 0.0])
    for r in arm_rows:
        if r["category"] in MAIN_CATS:
            continue
        a = agg[(r["suite"], r["arm"], r["category"])]
        a[0] += r["calls"]
        a[1] += r["ledger_tokens"]
        a[2] += r["rits_ledger_tokens"]
        a[3] += r["usd_total_priced"] or 0.0
    for (s, a, c), v in sorted(agg.items(), key=lambda kv: (-kv[1][1])):
        A("| %s | %s | all | %s | %s | %s | %s | $%.2f |" % (s, a, c, format(v[0], ","), format(v[1], ","), format(v[2], ","), v[3]))
    A("")
    A("Restart cutoffs used (gateway calls before this time with the run's tag are counted as restart_waste):")
    A("")
    for k, i in sorted(main_runs.items()):
        if i.get("cutoff"):
            A("- %s/%s/s%d: %s (%s)" % (k[0], k[1], k[2], iso(i["cutoff"]), i["cutoff_source"]))
    A("")
    A("## Data-quality notes")
    A("")
    noroll = [k for k, v in run_facts.items() if v["rollout_source"].startswith("none")]
    A("- Runs without a per-rollout record: %s" % (", ".join("%s/%s/s%d" % k for k in noroll) or "none"))
    A("- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.")
    A("- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.")
    open(OUT / "metrics_report.md", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
