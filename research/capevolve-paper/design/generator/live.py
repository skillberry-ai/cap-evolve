"""Live data for the status board and estimates. Read-only. python3.12 -I."""
import datetime as dt
import glob
import json
import os
import re
import subprocess

ROOT = "/home/dev/projects2/campaign-scratch"
NOW = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def jload(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def ps_lines():
    out = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True).stdout.splitlines()[1:]
    rows = []
    for l in out:
        parts = l.split(None, 2)
        if len(parts) < 3:
            continue
        if "conmon" in parts[2] or "cost_summary" in parts[2] or "grep" in parts[2]:
            continue
        rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


PS = ps_lines()


def pids_for(*needles):
    """PIDs whose args contain ALL needles in any one of the needle groups (each needle is a str)."""
    got = []
    for pid, et, args in PS:
        if all(n in args for n in needles):
            got.append((pid, et))
    return sorted(got)


def counter(path):
    for f in ("rollout_counter.json", "global_counter.json"):
        d = jload(os.path.join(path, f))
        if d and "total" in d:
            return d["total"]
    return None


def hhmm(t):
    return t.strftime("%H:%M")


def fmt_eta(remaining, rate_per_h):
    if rate_per_h is None or rate_per_h <= 0:
        return "n/a"
    h = remaining / rate_per_h
    eta = NOW + dt.timedelta(hours=h)
    return f"{h:.0f} h ({eta.strftime('%m-%d %H:%M')} UTC)" if h >= 1 else f"{h*60:.0f} min ({eta.strftime('%H:%M')})"


# ---- Suite A board -------------------------------------------------------
# (label, dir, seed, tier, budget cap, planned use, launch time 'HH:MM' UTC 2026-10-11, pid needles)
A_ROWS = [
    ("CapEvolve hill-climb", "hill-climb", 0, "Tier 1", 600, 600, "10:04", ["run_hc.sh hill-climb 0 "]),
    ("CapEvolve hill-climb", "hill-climb", 1, "Tier 1", 600, 600, None, None),
    ("CapEvolve hill-climb", "hill-climb", 2, "Tier 1", 600, 600, None, None),
    ("CapEvolve agent-optimize", "agent-optimize", 0, "Tier 1", 600, 600, "10:04", ["run_ao.sh agent-optimize 0 "]),
    ("CapEvolve agent-optimize", "agent-optimize", 1, "Tier 1", 600, 600, None, None),
    ("CapEvolve agent-optimize", "agent-optimize", 2, "Tier 1", 600, 600, None, None),
    ("GEPA (gepa 0.1.4)", "gepa", 0, "Tier 1", 600, 555, "08:21", ["launch_e10.sh gepa 0"]),
    ("GEPA (gepa 0.1.4)", "gepa", 1, "Tier 1", 600, 555, "08:21", ["launch_e10.sh gepa 1"]),
    ("GEPA (gepa 0.1.4)", "gepa", 2, "Tier 1", 600, 555, "08:21", ["launch_e10.sh gepa 2"]),
    ("SkillOpt @79124b37", "skillopt", 0, "Tier 1", 600, 600, "08:21", ["launch_e10.sh skillopt 0"]),
    ("SkillOpt @79124b37", "skillopt", 1, "Tier 1", 600, 600, "08:21", ["launch_e10.sh skillopt 1"]),
    ("SkillOpt @79124b37", "skillopt", 2, "Tier 1", 600, 600, "08:21", ["launch_e10.sh skillopt 2"]),
    ("Meta-Harness @8123cca", "metaharness", 0, "Tier 1", 600, 600, "09:42", ["metaharness/s0"]),
    ("Meta-Harness @8123cca", "metaharness", 1, "Tier 1", 600, 600, "09:42", ["metaharness/s1"]),
    ("Meta-Harness @8123cca", "metaharness", 2, "Tier 1", 600, 600, "09:42", ["metaharness/s2"]),
    ("EvoSkill (official loop)", "evoskill", 0, "Tier 1", 600, 568, "10:11", ["runs/E10/evoskill/s0"]),
    ("EvoSkill (official loop)", "evoskill", 1, "Tier 1", 600, 568, "10:11", ["runs/E10/evoskill/s1"]),
    ("EvoSkill (official loop)", "evoskill", 2, "Tier 1", 600, 568, "10:11", ["runs/E10/evoskill/s2"]),
    ("Trace2Skill @3d0b52a", "trace2skill", 0, "Tier 1-cheap", 600, 200, "08:50", ["launch_e10_competitors.sh trace2skill 0"]),
    ("Trace2Skill @3d0b52a", "trace2skill", 1, "Tier 1-cheap", 600, 200, "08:50", ["launch_e10_competitors.sh trace2skill 1"]),
    ("Trace2Skill @3d0b52a", "trace2skill", 2, "Tier 1-cheap", 600, 200, "08:50", ["launch_e10_competitors.sh trace2skill 2"]),
    ("GraphSkillEvo", "graphskillevo", 0, "Tier 2 (exploratory)", 600, 600, "08:56", ["launch_e10_competitors.sh graphskillevo 0"]),
    ("GraphSkillEvo", "graphskillevo", 1, "Tier 2", 600, 600, "08:56", None),
    ("GraphSkillEvo", "graphskillevo", 2, "Tier 2", 600, 600, "08:56", None),
    ("MCE", "mce", 0, "Tier 2 (exploratory)", 600, 560, "09:37", ["mce_sb_run.py --seed 0"]),
    ("MCE", "mce", 1, "Tier 2", 600, 560, "09:37", None),
    ("MCE", "mce", 2, "Tier 2", 600, 560, "09:37", None),
    ("Memento-Skills", "memento", 0, "Tier 2 (exploratory)", 600, 600, "09:52", ["memento_run.py"]),
    ("Memento-Skills", "memento", 1, "Tier 2", 600, 600, "09:52", None),
    ("Memento-Skills", "memento", 2, "Tier 2", 600, 600, "09:52", None),
]
A_NOT_LAUNCHED = [
    ("WikiSkill (community Stahl-G/wikiskill)", "Tier 1", "3 seeds, 600", "smoke only: baseline val 1.0, early stop at iteration 0, 3 rollouts"),
    ("ACE", "Tier 1-cheap", "3 seeds, cap 600", "smoke only: 6 rollouts (3 train, 3 val)"),
    ("MIPROv2 (DSPy 3.4.0)", "Tier 1-cheap", "3 seeds, cap 600", "smoke running (PID shown below), counter 12/12"),
    ("RHO", "Tier 2", "1 seed, hard cap 600 (plan about 300)", "smoke running, 12-rollout hard cap; no seed run"),
    ("AHE", "Tier 2", "1 seed, cap 600", "no adapter; clone only"),
]


def a_state(label, d, seed):
    p = os.path.join(ROOT, "runs/E10", d, f"s{seed}")
    if not os.path.isdir(p):
        return "pending", None, None
    stopped = os.path.exists(os.path.join(p, "STOPPED.json"))
    n = counter(p)
    if d in ("hill-climb", "agent-optimize"):
        rj = os.path.join(p, "logs", "rollouts.jsonl")
        if os.path.exists(rj):
            n = sum(1 for _ in open(rj))
    return ("stopped" if stopped else "running"), n, stopped


def board_a():
    out = []
    for label, d, seed, tier, cap, plan, launch, needles in A_ROWS:
        status, n, stopped = a_state(label, d, seed)
        pid = "-"
        if needles:
            got = pids_for(*needles)
            if got:
                pid = ", ".join(str(g[0]) for g in got[:2])
            elif status == "running":
                pid = "not found in ps"
        if status == "pending":
            out.append([label, f"s{seed}", tier, "[[pending|pending]]", "-", "-", "-", "-", "-", "-"])
            continue
        # launch time
        rate = None
        if launch and n is not None:
            h, m = map(int, launch.split(":"))
            t0 = NOW.replace(hour=h, minute=m, second=0, microsecond=0)
            hrs = max((NOW - t0).total_seconds() / 3600, 0.05)
            rate = n / hrs
        if status != "running":
            rate = None
        chipk = "running" if status == "running" else "planned"
        lab = "running" if status == "running" else "stopped"
        pct = f"{100*n/cap:.1f}%" if n is not None else "n/a"
        eta = "-" if status != "running" else fmt_eta(max(plan - (n or 0), 0), rate)
        out.append([
            label, f"s{seed}", tier, f"[[{chipk}|{lab}]]", pid,
            f"{n}" if n is not None else "not recorded", str(cap), pct,
            f"{rate:.0f}" if rate else "-", eta,
        ])
    return out


# ---- Suite B board -------------------------------------------------------
# arm label, dir, budget, launch, kind
B_ARMS = [
    ("CapEvolve hill-climb", "hc", 550, "09:40"),
    ("CapEvolve agent-optimize", "ao", 550, "09:43"),
    ("GEPA (gepa 0.1.4, policy only)", "gepa", 600, "09:41"),
    ("ctl-oneshot (one-shot repair)", "ctl-oneshot", 200, "09:43"),
    ("ctl-seed (seed, 2 trials)", "ctl-seed", 148, "09:43"),
]


def gw_calls_by_tag():
    agg = {}
    try:
        with open(os.path.join(ROOT, "logs/gateway_calls.jsonl")) as f:
            for l in f:
                try:
                    r = json.loads(l)
                except Exception:
                    continue
                m = re.match(r"tag:(E10B?-[a-z0-9\-]+?-s\d+):([^:]+):([^:]+)", r.get("tag", ""))
                if not m:
                    continue
                us = r.get("usage") or {}
                pt = us.get("prompt_tokens", us.get("input_tokens", 0)) or 0
                ct = us.get("completion_tokens", us.get("output_tokens", 0)) or 0
                k = (m.group(1), m.group(3))
                a = agg.setdefault(k, [0, 0, 0])
                a[0] += 1
                a[1] += pt
                a[2] += ct
    except Exception:
        pass
    return agg


GW = gw_calls_by_tag()
CALLS_PER_ROLLOUT_B = 17.2


def board_b():
    out = []
    for label, d, cap, launch in B_ARMS:
        for s in range(3):
            tagname = {"hc": "hc", "ao": "ao", "gepa": "gepa", "ctl-oneshot": "ctl-oneshot", "ctl-seed": "ctlseed"}[d]
            calls = sum(GW.get((f"E10B-{tagname}-s{s}", r), [0])[0] for r in ("target", "user", "judge"))
            p = os.path.join(ROOT, "runs/E10B", d, f"s{s}")
            drv = pids_for(f"E10B/{d}/s{s}/driver.sh") if d != "ctl-seed" else pids_for(f"E10B/{d}/s{s}")
            pid = ", ".join(str(x[0]) for x in drv[:2]) or ("not found in ps" if os.path.isdir(p) else "-")
            exact = None
            lg = os.path.join(p, "run.log")
            if os.path.exists(lg):
                try:
                    txt = open(lg, errors="ignore").read()[-200000:]
                    m = re.findall(r"Status: (\d+)/(\d+) complete", txt)
                    if m:
                        exact = f"{m[-1][0]} of {m[-1][1]} in current batch"
                except Exception:
                    pass
            est = calls / CALLS_PER_ROLLOUT_B
            c = counter(p) if d == "gepa" else None
            h, m_ = map(int, launch.split(":"))
            t0 = NOW.replace(hour=h, minute=m_, second=0, microsecond=0)
            hrs = max((NOW - t0).total_seconds() / 3600, 0.05)
            rate = est / hrs
            out.append([
                label, f"s{s}", "[[running|running]]" if os.path.isdir(p) else "[[pending|pending]]", pid,
                (f"{c} started (counter)" if c is not None else "not recorded") + (f"; {exact}" if exact else ""),
                f"{est:.0f}", str(cap), f"{100*est/cap:.0f}%", f"{rate:.0f}",
                fmt_eta(max(cap - est, 0), rate),
            ])
    return out


def snapshot():
    """Numbers used in prose: gateway health, spend totals."""
    import urllib.request
    h = None
    try:
        h = json.loads(urllib.request.urlopen("http://127.0.0.1:4111/health", timeout=3).read())
    except Exception:
        pass
    return h


HEALTH = snapshot()


def gemma_rates():
    """calls/min for Gemma and gpt-oss over the last 30 and 120 min of the gateway log (by completion time t)."""
    rows = []
    with open(os.path.join(ROOT, "logs/gateway_calls.jsonl")) as f:
        for l in f:
            try:
                r = json.loads(l)
            except Exception:
                continue
            rows.append((r.get("t", ""), r.get("model", ""), r.get("latency_s", 0), r.get("queue_s", 0), r.get("status", 200)))
    last = dt.datetime.strptime(rows[-1][0][:19], "%Y-%m-%dT%H:%M:%S")
    res = {}
    for win in (30, 120):
        c = last - dt.timedelta(minutes=win)
        for key in ("google/gemma-4-31B-it", "openai/gpt-oss-120b-a100"):
            sel = [r for r in rows if r[1] == "rits/" + key and dt.datetime.strptime(r[0][:19], "%Y-%m-%dT%H:%M:%S") >= c]
            lat = sorted(x[2] for x in sel)
            q = sorted(x[3] for x in sel)
            res[(key, win)] = dict(n=len(sel), cpm=len(sel) / win, p50=lat[len(lat) // 2] if lat else 0,
                                   p95=lat[int(len(lat) * .95)] if lat else 0, qmean=sum(q) / len(q) if q else 0,
                                   err=sum(1 for x in sel if x[4] != 200))
    return last, res


def pooled_tokens_per_rollout_A():
    tot_tok = 0
    tot_roll = 0
    tot_calls = 0
    for arm in ("gepa", "skillopt", "trace2skill"):
        for s in range(3):
            p = os.path.join(ROOT, "runs/E10", arm, f"s{s}")
            n = counter(p) or 0
            v = GW.get((f"E10-{arm}-s{s}", "target"), [0, 0, 0])
            tot_roll += n
            tot_calls += v[0]
            tot_tok += v[1] + v[2]
    return tot_tok / tot_roll, tot_calls / tot_roll, tot_roll
