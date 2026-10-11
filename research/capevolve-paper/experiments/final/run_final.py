#!/usr/bin/env python3
"""run_final.py: executes a hashed, interleaved final-evaluation order with each arm's own evaluation harness.

    run_final.py run     --suite A --order ORDER.jsonl [--order-sha HEX] [--workers N] [--limit K] [--smoke] [--canary-every 3600]
    run_final.py prepare --suite A --order ORDER.jsonl          preflight only (hash, artifacts, gateway, agent view); no rollout
    run_final.py aggregate --suite A [--order ORDER.jsonl]      rebuild results_long*.csv / results_trials*.csv / report from raw/
    run_final.py worker  --job JOB.json                         ONE rollout in this process (spawned by `run`; stdlib + venv deps)

One rollout = one worker process (fresh interpreter): the tau adapter keeps the applied candidate in process-global state, so
different arms interleave only across processes; it also makes the 3 h hang rule exact (kill the process group, record an
infra error).  Frozen settings are those of the search: target model, temperature 0, MAX_TOKENS 8000, turn limits, gateway.
Suite A scorer: patched SpreadsheetBench adapter (gold-free agent view, LibreOffice 25.8 recalculated hard score is the reward,
as-saved logged).  Suite B/C scorer: tau2 8ebb7499 via the campaign adapters (judge azure/gpt-5.5 for B; C is DB+COMMUNICATE).

Error policy (analysis_plan section 6, HUNG_ROLLOUT_RULE.txt): every attempt's error string is recorded and classified by
collect_metrics.uniform_class.  `infra` -> retried (<= 3 further attempts, new trial seed; a 3 h hang gets one retry), then a
MISSING CELL (no row in results_long.csv, never a 0).  `candidate`/`unverifiable` -> the rollout stands with its reward.
Resumable and idempotent: raw/rollouts.jsonl is append-only; a job with a terminal record is never run again.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fe_common as C  # noqa: E402

HANG_S = 10800                 # HUNG_ROLLOUT_RULE.txt: >= 3 h wall time
MAX_INFRA_RETRIES = 3          # analysis_plan section 6.2 (R = 3 further attempts)
MAX_HANG_RETRIES = 1           # HUNG_ROLLOUT_RULE.txt: one retry, a second timeout is a missing cell
BENCH = C.SCRATCH / "bench"
BASELINES = C.SCRATCH / "baselines"
WT_TAU = Path(os.environ.get("TAU_WT", "/home/dev/projects2/wt-tau"))
PY = {"A": BENCH / "venv" / "bin" / "python", "B": BENCH / "venv-tau2-8ebb749" / "bin" / "python", "C": BENCH / "venv-tau2-8ebb749" / "bin" / "python"}
TAU = {"B": dict(domain="retail", example="tau2_retail", splits="tau_retail_splits.json", jmodel_default="openai/azure/gpt-5.5"),
       "C": dict(domain="airline", example="tau2_airline_c", splits="tau_airline_splits.json", jmodel_default="openai/azure/gpt-5.5")}
GATEWAY = "http://127.0.0.1:4111/v1"
RAW_TOOL_TEXT = "<|tool_call>"
SB_TARGET = "rits/google/gemma-4-31B-it"
SB_LO_BIN = str(BENCH / "lo258/root/opt/libreoffice25.8/program/soffice")


# ============================================================================================================= worker
def _assistant_texts(trace):
    out = []
    for m in trace or []:
        if isinstance(m, dict) and m.get("role") == "assistant":
            c = m.get("content")
            if isinstance(c, list):
                c = " ".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in c)
            out.append(c if isinstance(c, str) else ("" if c is None else str(c)))
    return out


def _tool_text_flags(trace):
    texts = _assistant_texts(trace)
    last = texts[-1] if texts else ""
    return {"raw_tool_text_last": RAW_TOOL_TEXT in last, "raw_tool_text_any": any(RAW_TOOL_TEXT in t for t in texts), "n_assistant_turns": len(texts)}


def _stage_candidate(job, dest):
    """dest/<files>: A = the two capability files; B/C = the seed capability tree with policy/ and tools/ replaced by the artifact's."""
    import shutil
    art = Path(job["artifact_dir"])
    kind = job["artifact_kind"]
    if kind == "sb_files":
        dest.mkdir(parents=True, exist_ok=True)
        for f in C.FAMILY_FILES["sb_files"]:
            shutil.copy2(art / f, dest / f)
    else:
        seed_cap = WT_TAU / "examples" / TAU[job["suite"]]["example"] / "seed_capability"
        shutil.copytree(seed_cap, dest)
        for sub in ("policy", "tools"):
            if (art / sub).is_dir():
                shutil.rmtree(dest / sub, ignore_errors=True)
                shutil.copytree(art / sub, dest / sub)
    th, _ = C.tree_hash(dest, kind)
    return th


def _verify_artifact(job):
    th, _ = C.tree_hash(job["artifact_dir"], job["artifact_kind"])
    if th != job["artifact_tree_sha256"]:
        raise RuntimeError("frozen artifact hash mismatch: %s != %s" % (th, job["artifact_tree_sha256"]))


def worker_A(job, attempt_dir):
    env = os.environ
    env.update(job.get("env", {}))
    uid = os.getuid()
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % uid)
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=%s/bus" % env["XDG_RUNTIME_DIR"])
    env.setdefault("DOCKER_HOST", "unix://%s/podman/podman.sock" % env["XDG_RUNTIME_DIR"])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    tgt = job.get("target_model") or SB_TARGET
    env["MODEL"] = "litellm_proxy/%s" % tgt
    env["LITELLM_PROXY_API_BASE"] = job.get("gateway") or GATEWAY
    env["LITELLM_PROXY_API_KEY"] = job["tag"] + ":target"          # metering tag, not a secret
    env["SPREADSHEETBENCH_HARNESS_DIR"] = str(C.REPO / "third_party/spreadsheetbench")
    env["SPREADSHEETBENCH_DATA_DIR"] = job["agent_view"]
    env["SPREADSHEETBENCH_GOLD_DIR"] = job["gold_dir"]
    env["SPREADSHEETBENCH_TASK_IDS"] = str(job["task"])
    env["SPREADSHEETBENCH_MAX_TURNS"] = "30"
    env["SPREADSHEETBENCH_CONCURRENCY"] = "1"
    env["SPREADSHEETBENCH_SCORING"] = "hard"
    env["SPREADSHEETBENCH_REWARD_RECALC"] = "0"
    env["SPREADSHEETBENCH_KEEP_OUTPUTS"] = "0"
    env["SPREADSHEETBENCH_LIBREOFFICE_BIN"] = SB_LO_BIN
    env.setdefault("TEMPERATURE", "0.0")
    env.setdefault("MAX_TOKENS", "8000")
    env.update(job.get("env", {}))
    import importlib.util
    sys.path.insert(0, str(BENCH / "patches/new"))
    sys.path.insert(0, str(C.REPO / "templates/adapters"))
    sys.path.insert(0, str(C.REPO / "core"))
    spec = importlib.util.spec_from_file_location("sb_adapter_final", job["adapter_path"])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ad = mod.Adapter()
    ctx = Path(attempt_dir) / "candidate"
    _stage_candidate(job, ctx)
    task = [t for t in ad.tasks("test") if t.id == str(job["task"])][0]
    t0 = time.time()
    with ad.live(ctx):
        r = ad.run_target(task, ctx, seed=int(job["trial_seed"]))
        s = ad.score(task, r)
    t1 = time.time()
    metrics = {m["name"]: m["value"] for m in (s.metrics or [])} if s.metrics else {}
    fl = _tool_text_flags(r.trace)
    out_present = bool(r.output)
    res = {"t_start": t0, "t_end": t1, "error": r.error, "tokens": int(r.tokens or 0), "feedback": (s.feedback or "")[:2000],
           "metrics": metrics, "n_llm_calls": fl["n_assistant_turns"], "empty_output": (not out_present) and not r.error, **fl}
    if r.error:
        res["reward"] = 0.0
        res["reward_as_saved"] = 0.0
        res["error_kind_adapter"] = "infra"
    else:
        if "hard_restriction" not in metrics or "hard_no_recalc" not in metrics:
            raise RuntimeError("scorer metrics missing hard_restriction/hard_no_recalc: %s" % sorted(metrics))
        res["reward"] = float(metrics["hard_restriction"])          # LibreOffice 25.8 recalculated hard score
        res["reward_as_saved"] = float(metrics["hard_no_recalc"])
        res["error_kind_adapter"] = None
    try:
        (Path(attempt_dir) / "trace.json").write_text(json.dumps(r.trace)[:2_000_000])
    except Exception:
        pass
    return res


def worker_tau(job, attempt_dir):
    env = os.environ
    cfg = TAU[job["suite"]]
    env.update({"TAU_TAG_PREFIX": job["tag"], "TAU2_MAX_CONCURRENCY": "1", "TAU2_SIM_TIMEOUT": str(HANG_S),
                "CAPEVOLVE_NATIVE_SIMS": "1" if job.get("save_sims", True) else "0",
                "TAU_SPLITS_JSON": str(WT_TAU / "protocol" / cfg["splits"]), "MAX_TOKENS": "8000", "PYTHONDONTWRITEBYTECODE": "1",
                "TAU_GATEWAY": job.get("gateway") or GATEWAY})
    if job.get("target_model"):
        env["TAU_AGENT_MODEL"] = job["target_model"]
    if job.get("judge_model"):
        env["TAU_JUDGE_MODEL"] = job["judge_model"]
    if job.get("final_split"):
        env["TAU_ALLOW_SEALED_TEST"] = "final-eval-only"
    env.update(job.get("env", {}))
    sys.path.insert(0, str(WT_TAU / "core"))
    sys.path.insert(0, str(WT_TAU / "examples" / cfg["example"] / "adapters"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("tau_adapter_final", WT_TAU / "examples" / cfg["example"] / "adapters" / "adapter.py")
    ad = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ad)
    tid = str(job["task"])
    final_split = bool(job.get("final_split"))

    class FinalAdapter(ad.Adapter):
        def _tau2_tasks_by_id(self):
            # the stock adapter only knows opt+sel ids; the final evaluation adds exactly the ids of this job
            if not final_split:
                return super()._tau2_tasks_by_id()
            import importlib
            get_tasks = importlib.import_module("tau2.domains.%s.environment" % cfg["domain"]).get_tasks
            return {str(t.id): t for t in get_tasks(None) if str(t.id) == tid}

    A = FinalAdapter()
    work = Path(attempt_dir)
    ctx = work / "candidates" / "cand"                     # layout read by the adapter's native-sim saver
    _stage_candidate(job, ctx)
    A.apply(ctx)
    task = ad.Task(id=tid, input=tid, metadata={"domain": cfg["domain"]})
    t0 = time.time()
    res_t = A.run_trials([task], ctx, n_trials=1, base_seed=int(job["trial_seed"]))
    ro = res_t[tid][0]
    sc = A.score(task, ro)
    t1 = time.time()
    meta = ro.metadata or {}
    fl = _tool_text_flags(ro.trace)
    res = {"t_start": t0, "t_end": t1, "error": ro.error, "tokens": int(ro.tokens or 0), "reward": float(sc.reward), "reward_as_saved": float(sc.reward),
           "error_kind_adapter": meta.get("error_kind") if ro.error else None, "termination": meta.get("termination_reason"),
           "n_llm_calls": fl["n_assistant_turns"], "empty_output": False, **fl,
           "judge_model": (meta.get("judge") or {}).get("model"), "feedback": (sc.feedback or "")[:1000]}
    ri = meta.get("tau2_reward_info") or {}
    res["tau2_reward_breakdown"] = ri.get("reward_breakdown")
    try:
        (work / "trace.json").write_text(json.dumps(ro.trace)[:2_000_000])
    except Exception:
        pass
    return res


def cmd_worker(a):
    job = json.loads(Path(a.job).read_text())
    ad = Path(job["attempt_dir"])
    ad.mkdir(parents=True, exist_ok=True)
    try:
        _verify_artifact(job)
        if job["suite"] == "A":
            res = worker_A(job, ad)
        else:
            res = worker_tau(job, ad)
        res["worker_ok"] = True
    except BaseException as exc:                       # noqa: BLE001
        import traceback
        res = {"worker_ok": False, "worker_exception": "%s: %s" % (type(exc).__name__, exc), "traceback": traceback.format_exc()[-3000:],
               "t_start": None, "t_end": time.time()}
    tmp = ad / "result.json.tmp"
    tmp.write_text(json.dumps(res))
    os.replace(tmp, ad / "result.json")
    return 0


# ======================================================================================================= orchestrator
def load_order(path):
    rows = C.jsonl(path)
    meta = [r for r in rows if r.get("type") == "meta"]
    jobs = [r for r in rows if r.get("type") == "job"]
    return (meta[0] if meta else {}), jobs


def sha_of_file(path):
    return C.sha256_file(path)


class Store:
    """append-only rollouts.jsonl (+ in-memory index).  Terminal record per job id = done | missing."""

    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / "raw" / "rollouts.jsonl"
        self.lock = threading.Lock()
        self.by_job = {}
        for r in C.jsonl(self.path):
            self.by_job.setdefault(r["job_id"], []).append(r)

    def records(self, jid):
        return self.by_job.get(jid, [])

    def terminal(self, jid):
        for r in self.by_job.get(jid, []):
            if r.get("terminal"):
                return r
        return None

    def add(self, rec):
        with self.lock:
            C.append_jsonl(self.path, rec)
            self.by_job.setdefault(rec["job_id"], []).append(rec)


def classify(res, cm):
    """returns (class, rule).  class in '', infra, candidate, unverifiable"""
    if res.get("hang"):
        return "infra", "hang_rule_3h"                # HUNG_ROLLOUT_RULE.txt: a watchdog timeout is an infra error, never a 0
    if not res.get("worker_ok"):
        return "infra", "worker_exception"            # a harness failure is never a score
    rec = {"error_text": res.get("error"), "error_kind_adapter": res.get("error_kind_adapter"), "reward": res.get("reward"),
           "n_llm_calls": res.get("n_llm_calls")}
    cls, rule = cm.uniform_class(rec)
    if not (rec["error_text"] or rec["error_kind_adapter"]):
        return "", ""                                  # no error: a plain 0 is a task failure, not an error class
    return cls, rule


def run_attempt(job, attempt, store_root, cm, py, hang_s=HANG_S):
    jid = job["job_id"]
    h = hashlib.sha256(jid.encode()).hexdigest()[:16]
    ad = Path(store_root) / "raw" / "attempts" / h / ("a%d" % attempt)
    ad.mkdir(parents=True, exist_ok=True)
    ts = job["trial_seed"] + 7919 * attempt
    spec = dict(job, attempt=attempt, trial_seed=ts, attempt_dir=str(ad))
    (ad / "job.json").write_text(json.dumps(spec))
    t_spawn = time.time()
    out = open(ad / "worker.log", "ab")
    proc = subprocess.Popen([str(py), "-I", str(HERE / "run_final.py"), "worker", "--job", str(ad / "job.json")],
                            stdout=out, stderr=subprocess.STDOUT, start_new_session=True, cwd=str(ad))
    (ad / "pid").write_text(str(proc.pid))
    hang = False
    try:
        proc.wait(timeout=hang_s)
    except subprocess.TimeoutExpired:
        hang = True
        for sig, grace in ((signal.SIGTERM, 60), (signal.SIGKILL, 10)):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                break
            try:
                proc.wait(timeout=grace)
                break
            except subprocess.TimeoutExpired:
                continue
    out.close()
    t_end = time.time()
    rp = ad / "result.json"
    res = C.jload(rp) if (rp.exists() and not hang) else None
    if hang:
        res = {"worker_ok": True, "hang": True, "error": "watchdog timeout: rollout exceeded %d s wall time (hang rule); process group killed" % hang_s, "error_kind_adapter": "infra",
               "reward": 0.0, "reward_as_saved": 0.0, "t_start": t_spawn, "t_end": t_end, "n_llm_calls": 0}
    elif res is None:
        tail = ""
        try:
            tail = (ad / "worker.log").read_text(errors="replace")[-1500:]
        except Exception:
            pass
        res = {"worker_ok": False, "worker_exception": "worker exited %s without result.json: %s" % (proc.returncode, tail), "t_start": t_spawn, "t_end": t_end}
    cls, rule = classify(res, cm)
    rec = {"type": "attempt", "job_id": jid, "attempt": attempt, "suite": job["suite"], "arm": job["arm_label"], "seed": job["seed"], "task": job["task"], "family": job.get("family"),
           "trial": job["trial"], "mode": job["mode"], "trial_seed": ts, "t_spawn": t_spawn, "t_start": res.get("t_start"), "t_end": res.get("t_end"),
           "reward": res.get("reward"), "reward_as_saved": res.get("reward_as_saved"), "error_class": cls, "error_rule": rule,
           "error_text": (res.get("error") or res.get("worker_exception") or ""), "hang": hang, "worker_ok": res.get("worker_ok"),
           "tokens": res.get("tokens"), "raw_tool_text_last": res.get("raw_tool_text_last"), "raw_tool_text_any": res.get("raw_tool_text_any"),
           "empty_output": res.get("empty_output"), "n_llm_calls": res.get("n_llm_calls"), "termination": res.get("termination"),
           "tag": job["tag"], "attempt_dir": str(ad), "extra_set": job.get("extra_set")}
    return rec


def execute_job(job, store, cm, py, hang_s=HANG_S, log=print):
    jid = job["job_id"]
    prior = store.records(jid)
    if store.terminal(jid):
        return
    infra_n = sum(1 for r in prior if r["error_class"] == "infra" and not r.get("aborted"))
    hang_n = sum(1 for r in prior if r.get("hang"))
    attempt = len(prior)
    while True:
        rec = run_attempt(job, attempt, store.root, cm, py, hang_s)
        cls = rec["error_class"]
        if cls == "infra":
            infra_n += 1
            hang_n += 1 if rec["hang"] else 0
            exhausted = (rec["hang"] and hang_n > MAX_HANG_RETRIES) or infra_n > MAX_INFRA_RETRIES
            rec["terminal"] = bool(exhausted)
            rec["final_status"] = "missing" if exhausted else None
        else:
            rec["terminal"] = True
            rec["final_status"] = "done"
        store.add(rec)
        log("%s a%d reward=%s class=%s%s%s" % (jid, attempt, rec["reward"], cls or "-", " HANG" if rec["hang"] else "", " -> %s" % rec["final_status"] if rec["terminal"] else " (retry)"))
        if rec["terminal"]:
            return
        attempt += 1


def aggregate(suite, root, meta, jobs):
    """results_long.csv (contract) + results_trials.csv + END variants + per-arm report, from raw/rollouts.jsonl"""
    root = Path(root)
    store = Store(root)
    fam = {}
    trial_rows = {"B": [], "END": []}
    attempts_by_arm = {}
    for j in jobs:
        t = store.terminal(j["job_id"])
        allr = store.records(j["job_id"])
        arm = j["arm_label"]
        rep = attempts_by_arm.setdefault((j["mode"], arm), {"jobs": 0, "attempts": 0, "retried_jobs": 0, "done": 0, "missing": 0, "pending": 0, "infra_attempts": 0,
                                                            "hangs": 0, "candidate_errors": 0, "empty_output": 0, "raw_tool_text_last": 0})
        r = rep
        r["jobs"] += 1
        r["attempts"] += len(allr)
        r["retried_jobs"] += 1 if len(allr) > 1 else 0
        r["infra_attempts"] += sum(1 for x in allr if x["error_class"] == "infra")
        r["hangs"] += sum(1 for x in allr if x.get("hang"))
        if not t:
            r["pending"] += 1
            continue
        if t["final_status"] == "missing":
            r["missing"] += 1
            continue
        r["done"] += 1
        r["candidate_errors"] += 1 if t["error_class"] in ("candidate", "unverifiable") else 0
        r["empty_output"] += 1 if t.get("empty_output") else 0
        r["raw_tool_text_last"] += 1 if t.get("raw_tool_text_last") else 0
        for _m in (["B", "END"] if j.get("also_end") else [j["mode"]]):
          trial_rows[_m].append(dict(arm=j.get("arm"), seed=j["seed"], task=j["task"], trial=j["trial"], reward=t["reward"], family=j.get("family"),
                                            reward_as_saved=t["reward_as_saved"], t_start=_iso(t["t_start"]), t_end=_iso(t["t_end"]), error_class=t["error_class"],
                                            error_text=(t["error_text"] or "").replace("\n", " ")[:500], attempts=len(allr), empty_output=int(bool(t.get("empty_output"))),
                                            raw_tool_text_last=int(bool(t.get("raw_tool_text_last"))), tag=t["tag"], job_id=j["job_id"]))
    out = {}
    for mode, suffix in (("B", ""), ("END", "_end")):
        rows = trial_rows[mode]
        _write_csv(root / ("results_trials%s.csv" % suffix), rows,
                   ["arm", "seed", "task", "trial", "reward", "family", "reward_as_saved", "t_start", "t_end", "error_class", "error_text", "attempts", "empty_output",
                    "raw_tool_text_last", "tag", "job_id"])
        agg = {}
        for x in rows:
            agg.setdefault((x["arm"], x["seed"], x["task"]), []).append(x)
        long_rows = []
        for (arm, seed, task), xs in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2]))):
            long_rows.append(dict(arm=arm, seed=seed, task=task, reward=round(sum(x["reward"] for x in xs) / len(xs), 10), family=xs[0]["family"],
                                  n_trials=len(xs), reward_as_saved=round(sum(x["reward_as_saved"] for x in xs) / len(xs), 10),
                                  t_start=min(x["t_start"] for x in xs), t_end=max(x["t_end"] for x in xs),
                                  error_class="|".join(sorted({x["error_class"] for x in xs if x["error_class"]})),
                                  error_text=next((x["error_text"] for x in xs if x["error_text"]), "")))
        _write_csv(root / ("results_long%s.csv" % suffix), long_rows,
                   ["arm", "seed", "task", "reward", "family", "n_trials", "reward_as_saved", "t_start", "t_end", "error_class", "error_text"])
        out[mode] = len(long_rows)
    rep = {"%s|%s" % k: v for k, v in sorted(attempts_by_arm.items())}
    C.write_json_atomic(root / "per_arm_report.json", rep)
    return out, rep


def _iso(t):
    if t is None:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _write_csv(path, rows, cols):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, path)


# ----------------------------------------------------------------------------------------------------------- canary
def canary_loop(suite, root, meta, stop, cm, every, py, hang_s):
    """Hourly 5-task canary (seed artifact, fixed SEARCH-split tasks): raw tool-call-text rate and mean reward, to see provider-side drift."""
    cj = meta.get("canary_jobs") or []
    if not cj:
        return
    store = Store(Path(root) / "canary_store")
    n = 0
    while not stop.is_set():
        t0 = time.time()
        results = []
        thr = []

        def one(j, k=n):
            job = dict(j, job_id="canary%04d|%s" % (k, j["job_id"]), trial=k, tag=j["tag"].replace("-canary-", "-canary-"))
            execute_job(job, store, cm, py, hang_s, log=lambda s: None)
            t = store.terminal(job["job_id"])
            if t:
                results.append(t)
        for j in cj:
            th = threading.Thread(target=one, args=(j,), daemon=True)
            th.start()
            thr.append(th)
        for th in thr:
            th.join()
        rec = {"canary_round": n, "t": C.now_utc(), "n": len(results), "mean_reward": (sum(r["reward"] for r in results if r["reward"] is not None) / len(results)) if results else None,
               "raw_tool_text_last_rate": (sum(1 for r in results if r.get("raw_tool_text_last")) / len(results)) if results else None,
               "raw_tool_text_any_rate": (sum(1 for r in results if r.get("raw_tool_text_any")) / len(results)) if results else None,
               "empty_output_rate": (sum(1 for r in results if r.get("empty_output")) / len(results)) if results else None,
               "errors": [r["error_class"] for r in results if r["error_class"]], "wall_s": round(time.time() - t0, 1)}
        C.append_jsonl(Path(root) / "canary.jsonl", rec)
        n += 1
        stop.wait(max(1.0, every - (time.time() - t0)))


# --------------------------------------------------------------------------------------------------------- commands
def preflight(suite, order_path, meta, jobs, expect_sha=None):
    prob = []
    sha = sha_of_file(order_path)
    if expect_sha and sha != expect_sha:
        prob.append("order sha256 %s != expected %s" % (sha, expect_sha))
    ref = Path(order_path).with_suffix(".sha256")
    if ref.exists() and not expect_sha:
        want = ref.read_text().split()[0]
        if want != sha:
            prob.append("order sha256 %s != recorded %s" % (sha, want))
    for j in jobs:
        d = Path(j["artifact_dir"])
        if not d.is_dir():
            prob.append("artifact dir missing: %s" % d)
            break
    seen = set()
    for j in jobs:
        key = (j["artifact_dir"], j["artifact_tree_sha256"])
        if key in seen:
            continue
        seen.add(key)
        th, _ = C.tree_hash(j["artifact_dir"], j["artifact_kind"])
        if th != j["artifact_tree_sha256"]:
            prob.append("artifact hash drift: %s" % j["artifact_dir"])
    import urllib.request
    gw = (jobs[0].get("gateway") or GATEWAY) if jobs else GATEWAY
    try:
        h = json.loads(urllib.request.urlopen(gw.replace("/v1", "") + "/health", timeout=5).read())
        if not h.get("ok", True) or h.get("blocked"):
            prob.append("gateway unhealthy: %s" % h)
    except Exception as exc:
        prob.append("gateway health failed: %s" % exc)
    if suite == "A":
        for p in (SB_LO_BIN,):
            if not Path(p).exists():
                prob.append("LibreOffice missing: %s" % p)
        if jobs and not (Path(jobs[0]["agent_view"]) / "dataset.json").exists():
            prob.append("agent view missing: %s (build with make_agent_view.py)" % jobs[0]["agent_view"])
    return sha, prob


def cmd_prepare(a):
    meta, jobs = load_order(a.order)
    sha, prob = preflight(a.suite, a.order, meta, jobs, a.order_sha)
    print(json.dumps({"order_sha256": sha, "n_jobs": len(jobs), "problems": prob}, indent=1))
    return 1 if prob else 0


def cmd_run(a):
    suite = a.suite
    meta, jobs = load_order(a.order)
    root = Path(a.root) if a.root else C.final_dir(suite)
    if a.extra:
        root = root / "extra_%s" % a.extra
    root.mkdir(parents=True, exist_ok=True)
    sha, prob = preflight(suite, a.order, meta, jobs, a.order_sha)
    if prob and not a.force:
        print("PREFLIGHT FAILED:\n  " + "\n  ".join(prob))
        return 2
    lockf = open(root / "run.lock", "w")
    import fcntl
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another run_final.py holds %s" % (root / "run.lock"))
        return 3
    cm = C.collect_metrics()
    py = PY[suite]
    store = Store(root)
    todo = [j for j in jobs if not store.terminal(j["job_id"])]
    if a.limit:
        todo = todo[:a.limit]
    C.append_jsonl(root / "interruptions.jsonl", {"event": "start", "t": C.now_utc(), "order_sha256": sha, "n_jobs": len(jobs), "n_todo": len(todo), "script_commit": C.git_head(),
                                                    "run_final_sha256": C.file_sha(__file__), "workers": a.workers})
    print("order sha256 %s; %d jobs, %d to run, %d workers" % (sha, len(jobs), len(todo), a.workers))
    stop = threading.Event()
    cl = None
    if a.canary_n:
        meta["canary_jobs"] = meta["canary_jobs"][:a.canary_n]
    if a.canary_every and meta.get("canary_jobs"):
        cl = threading.Thread(target=canary_loop, args=(suite, root, meta, stop, cm, a.canary_every, py, a.hang_s), daemon=True)
        cl.start()
    idx = [0]
    lk = threading.Lock()
    done_n = [0]

    def logf(s):
        print(time.strftime("%H:%M:%S"), s, flush=True)

    def worker_thread():
        while not stop.is_set():
            with lk:
                if idx[0] >= len(todo):
                    return
                j = todo[idx[0]]
                idx[0] += 1
            try:
                execute_job(j, store, cm, py, a.hang_s, logf)
            except Exception as exc:               # noqa: BLE001 - orchestrator bug must not lose the run
                logf("ORCHESTRATOR ERROR on %s: %r" % (j["job_id"], exc))
            with lk:
                done_n[0] += 1
                if done_n[0] % 25 == 0:
                    aggregate(suite, root, meta, jobs)

    ths = [threading.Thread(target=worker_thread, daemon=True) for _ in range(a.workers)]
    try:
        for t in ths:
            t.start()
        for t in ths:
            while t.is_alive():
                t.join(timeout=1.0)
    except KeyboardInterrupt:
        stop.set()
        logf("interrupted: in-flight workers keep running; rerun to ingest their results")
        C.append_jsonl(root / "interruptions.jsonl", {"event": "interrupt", "t": C.now_utc()})
    stop.set()
    out, rep = aggregate(suite, root, meta, jobs)
    C.append_jsonl(root / "interruptions.jsonl", {"event": "stop", "t": C.now_utc(), "rows": out})
    print("aggregated:", out)
    return 0


def cmd_aggregate(a):
    meta, jobs = load_order(a.order)
    root = Path(a.root) if a.root else C.final_dir(a.suite)
    if a.extra:
        root = root / "extra_%s" % a.extra
    out, rep = aggregate(a.suite, root, meta, jobs)
    print(json.dumps({"rows": out, "arms": len(rep)}))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "prepare", "aggregate"):
        p = sp.add_parser(name)
        p.add_argument("--suite", required=True, choices=sorted(C.SUITES))
        p.add_argument("--order", required=True)
        p.add_argument("--order-sha", default=None)
        p.add_argument("--root", default=None, help="output root (default FINAL_EVAL_ROOT/<suite>)")
        p.add_argument("--extra", default=None, help="name of an exploratory extra set -> root/extra_<name>")
        p.add_argument("--workers", type=int, default=16)
        p.add_argument("--limit", type=int, default=0)
        p.add_argument("--canary-every", type=int, default=3600)
        p.add_argument("--canary-n", type=int, default=0, help="dry runs: use only the first n canary tasks")
        p.add_argument("--hang-s", type=int, default=HANG_S)
        p.add_argument("--force", action="store_true")
    w = sp.add_parser("worker")
    w.add_argument("--job", required=True)
    a = ap.parse_args(argv)
    return {"worker": cmd_worker, "run": cmd_run, "prepare": cmd_prepare, "aggregate": cmd_aggregate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
