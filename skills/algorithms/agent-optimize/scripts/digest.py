"""digest -- the optimizer's one-screen state (<= 1.5k tokens) for the DAG engine (#712).

    python digest.py --run-dir $R [--project $P] [--format md|json] [--max-tokens 1500]

Reads the run (graph, evidence ledger, hypotheses, clusters, budget) and prints:

* ``budget``    remaining USD, eval / optimizer / user-sim spend, rollouts, wall minutes
* ``noise``     ``sd_est`` of one full-val mean, from REPEAT CELLS of identical bytes in the
                ledger (no null controls); ``stale`` says when to buy a seed duplicate
* ``clusters``  failure clusters (``$R/clusters.json`` = ``diagnose/run.py --cluster v2`` output)
                with hypothesis status open|attempted|fixed|stuck
* ``tips``      branch tips: posterior mean/se, coverage, P(beat parent), P(beat champion)
* ``merge_opps``  tip pairs with complementary wins (needs merge_n.py; absent => warning)
* ``pregate``   pre-gate warnings recorded on tips;  ``suggested``  every item cites its numbers

Also the single optimizer-spend sink: ``meter()`` harvests the Claude Code session log
(``optimizer_cost``) into ``state.json`` idempotently; every ``act.py`` verb and this CLI call it.
Switch: ``optimizer.ablation.context_digest`` / ``CAPEVOLVE_CONTEXT_DIGEST`` (off => the legacy
raw numbers only, no suggestions). Infra errors never kill the digest: they become ``warnings``
(loud on stderr); ``--strict`` makes them fatal.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

from cap_evolve import (RunDir, eval_index, hypotheses, lineage, optimizer_config, optimizer_cost,
                        posterior, sched, schema_v2)
from cap_evolve.candidate_graph import CandidateGraph
from cap_evolve.rundir import _file_lock
from cap_evolve.specfile import spec_for_run

MIN_REPEAT_CELLS = 6        # fewer repeat cells than this and sd_est is called stale
STALE_S = 3 * 3600          # newest repeat evidence older than this => stale
MAX_TOKENS = 1500
CHARS_PER_TOKEN = 4         # rough: the budget is checked on the rendered text
PROBE_AT = 0.3              # successive halving: widen only tips with P(beat parent) above this
COMPLEMENTARY = 0.5         # merge opportunity bar (design: complementarity > 0.5)
STUCK_ATTEMPTS = 3


def warn(msg: str) -> None:
    print(f"digest WARNING: {msg}", file=sys.stderr)


# ---- optimizer spend: the single sink --------------------------------------------------------

def _run_start(run_dir) -> float:
    try:
        with run_dir.events_path.open(encoding="utf-8") as f:
            return float(json.loads(f.readline()).get("t") or 0.0)
    except (OSError, ValueError):
        return 0.0


def infra(run_dir, msg: str) -> None:
    """Fail-open infra error: loud on stderr AND recorded, so the digest shows it prominently."""
    warn(msg)
    try:
        run_dir.log_event("infra_warning", msg=msg[:300])
    except OSError:
        pass


def meter(run_dir, strict: bool = False) -> dict | None:
    """Add optimizer spend not yet counted (session-log messages deduped by id, so repeated
    calls are idempotent) to ``state.json``. The read-seen / price / write-seen / update_spent
    sequence runs under one lock, so concurrent verbs charge each message exactly once.
    Fail-open: an unreadable log warns (and shows in the digest), ``strict`` raises."""
    if optimizer_cost.mode() == "off":
        return None
    try:
        with _file_lock(Path(run_dir.root) / ".meter.lock"):
            h = optimizer_cost.harvest(run_dir, [run_dir.root.parent.parent, Path.cwd()], _run_start(run_dir))
            if h and (h["usd"] or h["tokens"]):
                run_dir.update_spent(optimizer_usd=h["usd"], optimizer_tokens=h["tokens"])
        if h and (h["usd"] or h["tokens"]):
            schema_v2.emit(run_dir, "optimizer_spend", role="agent", usd=h["usd"], tokens=h["tokens"],
                           model=",".join(sorted(h.get("models") or {})) or None, node=None)
            if h.get("unpriced_tokens"):
                warn(f"{h['unpriced_tokens']} optimizer tokens have no price (model unknown): spend is a lower bound")
        return h
    except Exception as e:  # noqa: BLE001 - metering is advisory
        if strict:
            raise
        infra(run_dir, f"optimizer metering failed ({type(e).__name__}: {e}); spend NOT updated")
        return None


def recent_infra(run_dir, n: int = 3) -> list[str]:
    try:
        lines = Path(run_dir.events_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if e.get("kind") == "infra_warning":
            out.append(str(e.get("msg")))
    return out[-n:]


# ---- noise -----------------------------------------------------------------------------------

def noise(run_dir, val_ids, now: float | None = None) -> dict:
    """sd of ONE full-val mean (one trial per task) from repeat cells = (cap_hash, task) with
    n >= 2 trials. Per task the unbiased within-cell variance is pooled over cells (weights n-1);
    tasks without a repeat cell get the average; sd = sqrt(sum_t var_t) / T. ``min_detectable``
    = 2 sd (the issue's convention: sd .048 -> .10). ``stale``: fewer than MIN_REPEAT_CELLS repeat
    cells, or the newest repeat evidence older than STALE_S."""
    now = time.time() if now is None else now
    fp = eval_index.env_fp()
    cells: dict = {}
    for r in eval_index.rows(run_dir):
        if r["split"] == "val" and r["env_fp"] == fp:
            cells.setdefault((r["cap_hash"], r["task"]), []).append(r)
    acc: dict = {}
    n_cells, newest = 0, 0.0
    for xs in cells.values():
        n = len(xs)
        if n < 2:
            continue
        m = sum(x["reward"] for x in xs) / n
        v = sum((x["reward"] - m) ** 2 for x in xs) / (n - 1)
        w = acc.setdefault(xs[0]["task"], [0.0, 0.0])
        w[0] += (n - 1) * v
        w[1] += n - 1
        n_cells += 1
        newest = max(newest, max(float(x.get("ts") or 0.0) for x in xs))
    if not acc:
        return {"sd_est": None, "min_detectable": None, "repeat_cells": 0, "stale": True,
                "why": "no repeat cells yet"}
    var_t = {t: s / w for t, (s, w) in acc.items()}
    avg = sum(var_t.values()) / len(var_t)
    ids = [str(t) for t in val_ids] or list(var_t)
    sd = math.sqrt(sum(var_t.get(t, avg) for t in ids)) / len(ids)
    why = ("only %d repeat cells (< %d)" % (n_cells, MIN_REPEAT_CELLS) if n_cells < MIN_REPEAT_CELLS else
           "newest repeat evidence %.0f min old" % ((now - newest) / 60) if now - newest > STALE_S else "")
    return {"sd_est": round(sd, 4), "min_detectable": round(2 * sd, 3), "repeat_cells": n_cells,
            "stale": bool(why), "why": why}


# ---- posteriors ------------------------------------------------------------------------------

def cand_dir(run_dir, tag: str) -> Path:
    """The COMMITTED snapshot when one exists (finalize seals ``candidates/<best_id>``, so every
    coverage / confirm figure must describe those bytes); the work dir only for an uncommitted tag."""
    snap = run_dir.candidate_dir(tag)
    w = Path(run_dir.root) / "work" / tag
    return snap if snap.is_dir() or not w.is_dir() else w


def pair(run_dir, cand: str, ref: str, val_ids):
    """posterior.Pair of ``cand`` vs ``ref`` from the ledger (pooled by content hash)."""
    h = [eval_index.cap_hash(cand_dir(run_dir, t)) for t in (cand, ref)]
    return posterior.from_ledger(run_dir, h[0], h[1], val_ids)


def stats(P) -> dict:
    """Candidate posterior read-out: mean of per-task Beta posteriors (tasks the candidate has
    not run shrink to the reference's rate), se, coverage = tasks with >=1 candidate trial."""
    means, var = [], 0.0
    for i in range(P.T):
        p = (P.sp[i] + .5) / (P.np_[i] + 1)
        a, b = P.k[i] * p + P.sc[i], P.k[i] * (1 - p) + P.nc[i] - P.sc[i]
        means.append(a / (a + b))
        var += a * b / ((a + b) ** 2 * (a + b + 1))
    return {"mean": round(sum(means) / P.T, 4), "se": round(math.sqrt(var) / P.T, 4),
            "cov": sum(1 for n in P.nc if n > 0), "T": P.T, "trials": int(sum(P.nc)), "task_means": means}


def p_beat(P, seed: int = 0) -> float:
    return round(P.verdict(random.Random(seed), int(sum(P.nc)))["p_beat"], 3)


def _own(run_dir, tag, val_ids) -> dict:
    c = eval_index.counts(run_dir, eval_index.cap_hash(cand_dir(run_dir, tag)), "val")
    ms = [((c.get(t, (0.0, 0))[0] + .5) / (c.get(t, (0.0, 0))[1] + 1)) for t in val_ids]
    return {"mean": round(sum(ms) / len(ms), 4) if ms else None,
            "cov": sum(1 for t in val_ids if c.get(t, (0, 0))[1] > 0), "T": len(val_ids)}


# ---- clusters / hypotheses -------------------------------------------------------------------

def load_clusters(run_dir) -> list[dict] | None:
    f = Path(run_dir.root) / "clusters.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d.get("clusters", []) if isinstance(d, dict) else d


def hyp_latest(run_dir) -> list[dict]:
    """hypotheses.jsonl, last record per id wins (status updates are appended records)."""
    out: dict = {}
    for h in hypotheses.load(run_dir):
        out[h.get("id")] = {**out.get(h.get("id"), {}), **h}
    return list(out.values())


def cluster_rows(clusters, hyps, per_task: bool, own_task_means=None, T: int = 1) -> list[dict]:
    rows = []
    for c in clusters:
        cid = c.get("cluster_id") or c.get("signature") or c.get("tag") or "?"
        tasks = [str(t) for t in c.get("tasks") or []]
        if per_task:  # failure_clustering off: one row per task, no grouping
            for t in tasks:
                m = (own_task_means or {}).get(t, 0.0)
                rows.append({"id": f"task {t}", "tasks": [t], "headroom": round((1 - m) / T, 3),
                             "status": "open", "attempts": 0})
            continue
        hs = [h for h in hyps if cid in (h.get("cluster_ids") or [])]
        attempts = len(hs)
        live = [h for h in hs if h.get("status") != "pruned"]
        status = ("fixed" if any(h.get("status") == "fixed" for h in hs) else
                  "stuck" if attempts >= STUCK_ATTEMPTS and not live else
                  "attempted" if attempts else "open")
        rows.append({"id": cid, "label": str(c.get("label") or c.get("signature") or "")[:28],
                     "tasks": tasks[:8], "headroom": round(float(c.get("headroom") or 0.0), 3),
                     "status": status, "attempts": attempts,
                     "best_cand": next((h.get("candidate") for h in reversed(hs) if h.get("candidate")), None)})
    rows.sort(key=lambda r: (-r["headroom"], r["id"]))
    return rows


# ---- merge opportunities (adapter over merge_n.py, PR #727) ----------------------------------

def complementarity(wa, wb) -> float:
    u = set(wa) | set(wb)
    return round(len(set(wa) ^ set(wb)) / len(u), 3) if u else 0.0


def merge_opps(run_dir, g, tips, champion, warnings, limit: int = 3) -> list[dict]:
    import merge_n as mn
    cand = [t for t in tips if t != champion][:5] + ([champion] if champion in tips else [])
    wins = mn.wins_from_run(run_dir, cand, champion or "seed") or {}
    out = []
    for i, a in enumerate(cand):
        for b in cand[i + 1:]:
            if g.is_descendant(a, b) or g.is_descendant(b, a):
                continue
            if any({a, b} <= set(g.parents_of(n)) for n in g._nodes):  # already merged
                continue
            wa, wb = wins.get(a), wins.get(b)
            if wa is None or wb is None:
                continue
            comp = complementarity(wa, wb)
            if comp <= COMPLEMENTARY:
                continue
            row = {"a": a, "b": b, "complementarity": comp,
                   "est_gain_tasks": len(set(wa) ^ set(wb)) // 2}
            try:
                base = lineage.merge_base(g, a, b)
                f = [mn.features(cand_dir(run_dir, base), cand_dir(run_dir, t), (), w)
                     for t, w in ((a, wa), (b, wb))]
                it = mn.interaction(*f)
                row.update(I=it["I"], unknown=it["unknown"])
            except Exception as e:  # noqa: BLE001
                warnings.append(f"interaction({a},{b}) failed: {type(e).__name__}: {e}")
            out.append(row)
    return sorted(out, key=lambda r: -r["complementarity"])[:limit]


# ---- the digest ------------------------------------------------------------------------------

ENGINE_FIX = ("set optimizer.ablation.dag_parallel/active_eval/... = true in capevolve.yaml "
              "(references/ablation.md) or run with CAPEVOLVE_ACTIVE_EVAL=1")


def config_warning(cfg: dict) -> str | None:
    """Loud first-line warning when the run is not on the full new engine (switches off)."""
    off = sorted(k for k, v in cfg.items() if not v)
    if not off:
        return None
    full = " probe --auto runs FULL val (no posterior allocator)." if "active_eval" in off else ""
    return f"CONFIG: mixed/legacy engine, switches off: {', '.join(off)}.{full} Fix: {ENGINE_FIX}"


def build(run_dir, project: Path | None = None, spec: dict | None = None, strict: bool = False) -> dict:
    spec = spec if spec is not None else spec_for_run(run_dir, project)
    cfg = optimizer_config.resolve(spec)
    meter(run_dir, strict)
    b, s = run_dir.budget, run_dir.spent
    warnings: list[str] = []
    out: dict = {"budget": {
        "remaining_usd": round(b.max_usd - s.total_usd, 2) if b.max_usd else None,
        "remaining_opt_usd": round(b.max_optimizer_usd - s.optimizer_usd, 2) if b.max_optimizer_usd else None,
        "eval_usd": round(s.usd, 2), "opt_usd": round(s.optimizer_usd, 2),
        "usersim_usd": round(s.usersim_usd, 2), "rollouts": s.metric_calls,
        "wall_min": round(max(0.0, time.time() - _run_start(run_dir)) / 60, 1)}}
    stop, why = run_dir.budget_exhausted()
    if stop:
        out["budget"]["exhausted"] = why
    cw = config_warning(cfg)
    if cw:
        out["config_warning"] = cw
    if not cfg["context_digest"]:  # legacy: raw numbers, no summaries/suggestions
        out["context_digest"] = False
        out["best_id"] = run_dir.best_id
        out["note"] = "context_digest off: use spend.py / round.py tables"
        return out
    try:
        val_ids = [str(t) for t in run_dir.read_splits().ids("val")]
    except Exception as e:  # noqa: BLE001
        val_ids = []
        warnings.append(f"no frozen val split ({type(e).__name__}): posteriors unavailable")
    if val_ids and not eval_index.rows(run_dir):
        try:
            n = eval_index.backfill(run_dir)
            warnings.append(f"ledger was empty: rebuilt {n} rows from rollouts")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"ledger backfill failed: {type(e).__name__}: {e}")
    out["noise"] = noise(run_dir, val_ids)
    champ = run_dir.best_id or "seed"
    g = CandidateGraph.load(run_dir)
    tips = [t for t in lineage.tips(g) if t != "seed"]
    rows = []
    for t in tips:
        try:
            par = (g.parents_of(t) or ["seed"])[0]
            P = pair(run_dir, t, par, val_ids) if val_ids else None
            if P is None or not sum(P.nc):
                rows.append({"id": t, "parent": par, "cov": f"0/{len(val_ids)}", "n": 0,
                             "p_beat_parent": None, "p_beat_champ": None})
                continue
            st = stats(P)
            row = {"id": t, "parent": par, "mean": st["mean"], "se": st["se"],
                   "cov": f"{st['cov']}/{st['T']}", "n": st["trials"], "p_beat_parent": p_beat(P),
                   "p_beat_champ": None if t == champ else p_beat(pair(run_dir, t, champ, val_ids)),
                   "decision": P.verdict(random.Random(0), st["trials"])["decision"]}
            wins = [val_ids[i] for i in range(P.T) if P.nc[i] and st["task_means"][i] > (P.sp[i] + .5) / (P.np_[i] + 1) + .2]
            row["wins"] = wins[:6]
            picks = sched.pick(P, [max(0.0, 1 - n) for n in P.nc], [0.0] * P.T, 4)  # uncovered cells, most informative first
            row["next"] = sorted({val_ids[i] for _, i in picks})
            rows.append(row)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"posterior for {t} failed: {type(e).__name__}: {e}")
    rows.sort(key=lambda r: -(r.get("mean") or 0))
    out["champion"] = {"id": champ, **_own(run_dir, champ, val_ids)} if val_ids else {"id": champ}
    out["tips"] = [r for r in rows if r["id"] != champ]   # the champion is never a prune/promote target
    infra_w = recent_infra(run_dir)
    if infra_w:
        out["infra_warnings"] = infra_w
    cl = load_clusters(run_dir)
    if cl is None:
        warnings.append("no clusters.json: run diagnose/scripts/run.py --cluster v2 > $R/clusters.json")
    hyps = hyp_latest(run_dir)
    own_means = None
    if cl and not cfg["failure_clustering"] and val_ids:
        c = eval_index.counts(run_dir, eval_index.cap_hash(cand_dir(run_dir, champ)), "val")
        own_means = {t: (c.get(t, (0.0, 0))[0] + .5) / (c.get(t, (0.0, 0))[1] + 1) for t in val_ids}
    out["clusters"] = cluster_rows(cl or [], hyps, not cfg["failure_clustering"], own_means, max(1, len(val_ids)))
    out["merge_opps"] = merge_opps(run_dir, g, [r["id"] for r in rows], champ, warnings) \
        if cfg["smart_merge"] and len(rows) > 1 else []
    out["pregate"] = [f"{n}: {w}"[:120] for n in tips for w in
                      ((g.node(n) or {}).get("pregate") or {}).get("warnings", [])[:2]][:4]
    out["suggested"] = suggest(out, hyps, cfg)
    if warnings:
        out["warnings"] = warnings[:5]
        for w in warnings:
            warn(w)
    return out


def suggest(d: dict, hyps: list[dict], cfg: dict) -> list[dict]:
    """Structured suggestions, each citing the numbers behind it (``why``)."""
    out = []
    for t in d["tips"]:
        n, pp = t.get("n", 0), t.get("p_beat_parent")
        if pp is None:
            out.append({"verb": "probe", "target": t["id"], "why": f"no ledger cells yet (cov {t['cov']})"})
        elif t.get("decision") == "prune":
            out.append({"verb": "prune", "target": t["id"],
                        "why": f"P(beat parent) {pp} after {n} trials (posterior rule says prune)"})
        elif t.get("decision") == "accept" and (t.get("p_beat_champ") or 0) >= 0.5:
            out.append({"verb": "promote", "target": t["id"],
                        "why": f"P(beat parent) {pp}, P(beat champion) {t['p_beat_champ']}, cov {t['cov']}"})
        elif pp > PROBE_AT:
            full = t["cov"].split("/")[0] == t["cov"].split("/")[1]
            out.append({"verb": "probe", "target": t["id"],
                        "why": f"P(beat parent) {pp} > {PROBE_AT}, cov {t['cov']}: "
                        + ("add a trial per cell" if full else "widen coverage")
                        + (f" on {{{','.join(t['next'])}}}" if t.get("next") else "")})
    for m in d.get("merge_opps", []):
        out.append({"verb": "merge", "target": f"{m['a']} {m['b']}",
                    "why": f"complementarity {m['complementarity']}, I={m.get('I', '?')}"})
    md = (d.get("noise") or {}).get("min_detectable")
    attempts = len(hyps)
    p_succ = (sum(1 for h in hyps if h.get("status") == "fixed") + 1) / (attempts + 2)
    openc = [c for c in d["clusters"] if c["status"] in ("open", "attempted")]
    if openc:
        c = openc[0]
        ev = round(c["headroom"] * p_succ, 3)
        if md is not None and ev < md:
            out.append({"verb": "finalize", "target": "",
                        "why": f"best open cluster {c['id']} headroom {c['headroom']} x P(success) {round(p_succ, 2)} = {ev} < min detectable {md}"})
        elif c["status"] == "open":
            out.append({"verb": "propose", "target": c["id"],
                        "why": f"headroom {c['headroom']} on tasks {','.join(c['tasks'][:5])}, no attempts"})
    nz = d.get("noise") or {}
    if nz.get("stale") and d["tips"]:
        out.append({"verb": "probe", "target": d["champion"]["id"],
                    "why": f"sd_est stale ({nz.get('why')}): repeat 6+ champion cells to refresh the noise estimate"})
    if d["budget"].get("exhausted"):
        out.insert(0, {"verb": "finalize", "target": "", "why": d["budget"]["exhausted"]})
    return out[:6]


# ---- rendering -------------------------------------------------------------------------------

def tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def render(d: dict) -> str:
    b = d["budget"]
    left = f"${b['remaining_usd']} left | " if b.get("remaining_usd") is not None else ""
    if b.get("remaining_opt_usd") is not None:
        left += f"${b['remaining_opt_usd']} optimizer left | "
    L = (["!! INFRA (fail-open, result may be incomplete): " + " | ".join(d["infra_warnings"])]
         if d.get("infra_warnings") else []) + (["!! " + d["config_warning"]] if d.get("config_warning") else []) + [f"budget: {left}eval ${b['eval_usd']} opt ${b['opt_usd']} usersim ${b['usersim_usd']} | "
         f"{b['rollouts']} rollouts | {b['wall_min']} min" + (f" | EXHAUSTED: {b['exhausted']}" if b.get("exhausted") else "")]
    if d.get("context_digest") is False:
        return "\n".join(L + [f"best: {d.get('best_id')}", d["note"]])
    n = d["noise"]
    L.append("noise: " + ("sd_est %s -> min detectable %s (%d repeat cells%s)" % (
        n["sd_est"], n["min_detectable"], n["repeat_cells"], ", STALE: " + n["why"] if n["stale"] else "")
        if n["sd_est"] is not None else "unknown (%s)" % n["why"]))
    c = d["champion"]
    L.append(f"champion: {c['id']}" + (f" mean {c.get('mean')} cov {c.get('cov')}/{c.get('T')}" if "mean" in c else ""))
    L.append("clusters: " + (" | ".join(
        f"{x['id']} {x.get('label', '')} (tasks {','.join(x['tasks'][:4])}) headroom {x['headroom']} {x['status']}"
        + (f" x{x['attempts']}" if x["attempts"] else "") for x in d["clusters"]) or "none"))
    L.append("tips: " + (" | ".join(
        f"{t['id']} mean {t.get('mean', '-')} se {t.get('se', '-')} cov {t['cov']} p_beat_parent {t['p_beat_parent']}"
        + (f" p_beat_champ {t['p_beat_champ']}" if t.get("p_beat_champ") is not None else "")
        for t in d["tips"]) or "none"))
    if d["merge_opps"]:
        L.append("merge_opps: " + " | ".join(
            f"{m['a']}+{m['b']} I={m.get('I', '?')} complementarity {m['complementarity']}" for m in d["merge_opps"]))
    if d["pregate"]:
        L.append("pregate: " + " | ".join(d["pregate"]))
    L.append("suggested: " + ("; ".join(f"{s['verb']} {s['target']} [{s['why']}]".replace("  ", " ")
                                       for s in d["suggested"]) or "none"))
    if d.get("warnings"):
        L.append("warnings: " + " | ".join(d["warnings"]))
    return "\n".join(L)


def fit(d: dict, max_tokens: int = MAX_TOKENS) -> tuple[dict, str]:
    """Drop the least valuable list tails until the rendering fits the token budget."""
    d = json.loads(json.dumps(d))
    for key, floor in (("clusters", 2), ("tips", 3), ("suggested", 3), ("merge_opps", 1), ("pregate", 0)) * 4:
        text = render(d)
        if tokens(text) <= max_tokens:
            return d, text
        if d.get(key) and len(d[key]) > floor:
            d[key] = d[key][:-1]
    d.pop("warnings", None)
    return d, render(d)[: max_tokens * CHARS_PER_TOKEN]


def save_suggestions(run_dir, d: dict) -> None:
    """``$R/digest_last.json``: what was suggested, so act.py can log whether it was followed."""
    try:
        p = Path(run_dir.root) / "digest_last.json"
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"t": time.time(), "suggested": d.get("suggested", [])}), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="digest", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", default=None)
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    p.add_argument("--strict", action="store_true", help="infra errors (metering, ledger) are fatal, not warnings")
    a = p.parse_args(argv)
    run_dir = RunDir.open(Path(a.run_dir).resolve())  # absolute: metering locates the session log from it
    try:
        d, text = fit(build(run_dir, Path(a.project) if a.project else None, strict=a.strict), a.max_tokens)
    except ValueError as e:  # e.g. an unknown ablation key
        print(json.dumps({"error": str(e)}))
        return 2
    save_suggestions(run_dir, d)
    print(json.dumps(d, indent=1) if a.format == "json" else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
