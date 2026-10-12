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
import re
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
PY = {"D": BENCH / "venv-tau2-8ebb749" / "bin" / "python", "A": BENCH / "venv" / "bin" / "python", "B": BENCH / "venv-tau2-8ebb749" / "bin" / "python", "C": BENCH / "venv-tau2-8ebb749" / "bin" / "python"}
TAU = {"B": dict(domain="retail", example="tau2_retail", splits="tau_retail_splits.json", jmodel_default="openai/azure/gpt-5.5"),
       "D": dict(domain="retail", example="tau2_retail", splits="tau_retail_splits.json", jmodel_default="openai/azoai/gpt-4.1-2025-04-14"),
       "C": dict(domain="airline", example="tau2_airline_c", splits="tau_airline_splits.json", jmodel_default="openai/azure/gpt-5.5")}
GATEWAY = "http://127.0.0.1:4111/v1"
RAW_TOOL_TEXT = "<|tool_call>"
SB_TARGET = "rits/google/gemma-4-31B-it"
SB_API_PY = C.REPO / "third_party/spreadsheetbench/code_exec_docker/api.py"
SB_API_SHA = (HERE / "manifests/expected_api_sha256.txt").read_text().split()[0]     # patched api.py: idle-kernel timeout 10800 s + exec500 logging (2026-10-12)
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


def _empty_completion(trace, termination):
    """descriptive flag (coordinator decision): conversation not ended by USER_STOP and the last turn has no text and no tool call
    (ends on a tool result or an empty assistant message).  Scored as a normal failure; recorded only."""
    if "USER_STOP" in str(termination) or not trace:
        return False
    last = trace[-1]
    if not isinstance(last, dict):
        return False
    if last.get("role") == "tool":
        return True
    if last.get("role") == "assistant":
        c = last.get("content")
        return not (c if isinstance(c, str) else json.dumps(c or "")).strip().strip('"[]') and not last.get("tool_calls")
    return False


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
    env["KERNEL_TIMEOUT_S"] = "10800"
    env["SB_DRAIN_ERROR"] = "1"                       # fixed jupyter.py: keep reading the websocket after an error message (final evaluation only)
    import tempfile                                   # the sandbox server's runtime dir (server.log, exec500.jsonl) lands inside the attempt dir for the diagnostics
    (Path(attempt_dir) / "tmp").mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(Path(attempt_dir) / "tmp")
    tempfile.tempdir = env["TMPDIR"]
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
    if job.get("user_model"):
        env["TAU_USER_MODEL"] = job["user_model"]
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
           "empty_completion": _empty_completion(ro.trace, meta.get("termination_reason")),
           "judge_model": (meta.get("judge") or {}).get("model"), "feedback": (sc.feedback or "")[:1000]}
    ri = meta.get("tau2_reward_info") or {}
    res["tau2_reward_breakdown"] = ri.get("reward_breakdown")
    try:
        (work / "trace.json").write_text(json.dumps(ro.trace)[:2_000_000])
    except Exception:
        pass
    return res


def worker_hl(job, attempt_dir):
    """HarnessLens / hl-v0 (Suite B): bl-harness's sealed-test entrypoint hl_final_eval.py runs ONE (task, trial) in its sandboxed OpenCode tree.
    Its trial index sets the seed, so a retry uses trial + 10 x attempt (a new seed)."""
    hl = job["hl"]
    out = Path(attempt_dir) / "hl_out"
    trial = int(job["trial"]) + 10 * int(job.get("attempt", 0))
    cmd = [sys.executable, "-I", str(BASELINES / "harnesslens/tau/hl_final_eval.py"), "--out", str(out), "--tag-prefix", job["tag"].split(":")[1],
           "--version", hl["version"], "--tasks", "%s:%d" % (job["task"], trial), "--workers", "1"]
    cmd += ["--judge-model", job.get("judge_model") or "openai/azure/gpt-5.5"]     # every Suite B cell is judged by azure/gpt-5.5 (shared evaluator); only the OpenCode target harness is HarnessLens's
    if hl.get("src_run_dir"):
        cmd += ["--src-run-dir", hl["src_run_dir"]]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    t1 = time.time()
    rows = C.jsonl(out / "fe_results.jsonl")
    row = next((x for x in rows if str(x.get("task_id")) == str(job["task"]) and int(x.get("trial", -1)) == trial), None)
    if row is None:
        return {"t_start": t0, "t_end": t1, "error": "hl_final_eval produced no result (exit %d): %s" % (r.returncode, (r.stdout + r.stderr)[-500:]),
                "error_kind_adapter": "infra", "force_infra": True, "force_rule": "hl_wrapper_error", "reward": 0.0, "reward_as_saved": 0.0, "tokens": 0, "n_llm_calls": 0, "empty_output": False}
    err = row.get("error")
    tc = row.get("target_calls")
    trunc = bool(row.get("truncated_stream"))
    exit_like = bool(re.search(r"exit[_ ]?(code[_ ]?)?\d|worker exit", str(err or ""), re.I))
    if tc is not None:         # real rule: exit with 0 target calls, or a truncated stream, is infra; exit after target calls is a candidate fault
        force, frule = bool(err and (trunc or int(tc) == 0)), "hl_exit_zero_target_calls_or_truncated_stream"
    else:                      # fe_results rows without target_calls: assume an exit made no target calls
        force, frule = bool(err and exit_like), "hl_worker_exit_no_target_calls_assumed"
    flags = {}
    try:                       # bl-harness's per-trial descriptive flags (empty_completion, truncated_stream, worker_error)
        fo = Path(attempt_dir) / "hl_flags.jsonl"
        subprocess.run([sys.executable, "-I", str(BASELINES / "harnesslens/tau/hl_trial_flags.py"), str(out / "tree"), str(fo)], capture_output=True, text=True, timeout=300)
        for x in C.jsonl(fo):
            if str(x.get("task_id")) == str(job["task"]) and int(x.get("trial", -1)) == trial:
                flags = x
    except Exception:
        pass
    return {"t_start": t0, "t_end": t1, "error": err, "error_kind_adapter": "infra" if err else None, "force_infra": force, "force_rule": frule,
            "n_llm_calls": tc, "reward": float(row.get("reward") or 0.0), "reward_as_saved": float(row.get("reward") or 0.0), "tokens": 0, "empty_output": False,
            "empty_completion": bool(flags.get("empty_completion")), "hl_run_id": row.get("run_id"), "hl_flags": flags or None}


def cmd_worker(a):
    job = json.loads(Path(a.job).read_text())
    ad = Path(job["attempt_dir"])
    ad.mkdir(parents=True, exist_ok=True)
    try:
        if job.get("hl"):
            res = worker_hl(job, ad)
            res["worker_ok"] = True
            tmp = ad / "result.json.tmp"
            tmp.write_text(json.dumps(res))
            os.replace(tmp, ad / "result.json")
            return 0
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
    if res.get("force_infra"):
        return "infra", res.get("force_rule") or "hl_worker_error"
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


def sandbox_diag(ad):
    """Suite A sandbox-server diagnostics of one attempt (baseline-eng 2026-10-12): execs, HTTP 500s (exec500.jsonl: conversation, kernel id, idle seconds since the last exec),
    idle-cleanup closures and silent kernel re-creations (a conversation whose kernel was created more than once)."""
    d = {"sandbox_execs": 0, "sandbox_500": 0, "kernel_recreations": 0, "idle_closures": 0}
    created = {}
    for sl in Path(ad).glob("tmp/capevolve_sb_sandbox_*/server.log"):
        try:
            for line in sl.read_text(errors="replace").splitlines():
                m = re.search(r"Kernel created for conversation (\S+)", line)
                if m:
                    created[m.group(1)] = created.get(m.group(1), 0) + 1
                if "Kernel closed for conversation" in line:
                    d["idle_closures"] += 1
                if "POST /execute" in line:
                    d["sandbox_execs"] += 1
        except Exception:
            pass
    d["kernel_recreations"] = sum(max(0, n - 1) for n in created.values())
    e5 = []
    for f in Path(ad).glob("tmp/capevolve_sb_sandbox_*/exec500.jsonl"):
        e5 += C.jsonl(f)
    d["sandbox_500"] = len(e5)
    d["exec500"] = e5[:5]
    return d


def run_attempt(job, attempt, store_root, cm, py, hang_s=HANG_S):
    jid = job["job_id"]
    h = hashlib.sha256(jid.encode()).hexdigest()[:16]
    ad = Path(store_root) / "raw" / "attempts" / h / ("a%d" % attempt)
    ad.mkdir(parents=True, exist_ok=True)
    ts = job["trial_seed"] + 7919 * attempt
    spec = dict(job, attempt=attempt, trial_seed=ts, attempt_dir=str(ad))
    pidf, rp0 = ad / "pid", ad / "result.json"
    resumed = False
    if rp0.exists() or pidf.exists():
        # resume: this attempt was spawned by an earlier orchestrator.  Ingest a finished result, or wait for the live worker (bounded by the
        # hang rule counted from its spawn time); a dead worker without a result is an aborted attempt and is respawned in place.
        try:
            wpid = int(pidf.read_text())
        except Exception:
            wpid = -1
        t_spawn = pidf.stat().st_mtime if pidf.exists() else time.time()
        alive = False
        try:
            os.kill(wpid, 0)
            alive = wpid > 0
        except Exception:
            alive = False
        if rp0.exists() or alive:
            resumed = True
            while alive and not rp0.exists() and time.time() - t_spawn < hang_s:
                time.sleep(5)
                try:
                    os.kill(wpid, 0)
                except Exception:
                    alive = False
            proc = None
            hang = alive and not rp0.exists()
            if hang:
                try:
                    os.killpg(wpid, signal.SIGKILL)
                except Exception:
                    pass
    if not resumed:
        for stale in ("result.json", "pid"):
            try:
                (ad / stale).unlink()
            except FileNotFoundError:
                pass
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
        res = {"worker_ok": False, "worker_exception": "worker exited %s without result.json: %s" % (proc.returncode if proc else "?", tail), "t_start": t_spawn, "t_end": t_end}
    cls, rule = classify(res, cm)
    diag = sandbox_diag(ad) if job["suite"] == "A" else {}
    rec = {"type": "attempt", **{k: v for k, v in diag.items() if k != "exec500"}, "job_id": jid, "attempt": attempt, "suite": job["suite"], "arm": job["arm_label"], "seed": job["seed"], "task": job["task"], "family": job.get("family"),
           "trial": job["trial"], "mode": job["mode"], "trial_seed": ts, "t_spawn": t_spawn, "t_start": res.get("t_start"), "t_end": res.get("t_end"),
           "reward": res.get("reward"), "reward_as_saved": res.get("reward_as_saved"), "error_class": cls, "error_rule": rule,
           "error_text": (res.get("error") or res.get("worker_exception") or ""), "hang": hang, "worker_ok": res.get("worker_ok"),
           "tokens": res.get("tokens"), "raw_tool_text_last": res.get("raw_tool_text_last"), "raw_tool_text_any": res.get("raw_tool_text_any"),
           "empty_output": res.get("empty_output"), "empty_completion": res.get("empty_completion"), "n_llm_calls": res.get("n_llm_calls"), "termination": res.get("termination"),
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
            if not rec["hang"]:       # 429-aware backoff before the retry (Azure-direct suites); depends on the error class only
                time.sleep(min(60, 10 * infra_n) if re.search(r"\b429\b|rate ?limit", rec.get("error_text") or "", re.I) else 0)
            hang_n += 1 if rec["hang"] else 0
            exhausted = (rec["hang"] and hang_n > MAX_HANG_RETRIES) or infra_n > MAX_INFRA_RETRIES
            rec["terminal"] = bool(exhausted)
            rec["final_status"] = "missing" if exhausted else None
            # amendment 5O: an infra error still infra after the retries is `infra_final` (scored 0 in the primary results, missing only in the
            # sensitivity file); a 3 h hang that exhausted its one retry stays a missing cell in both.
            rec["missing_kind"] = ("hang" if (rec["hang"] or hang_n > MAX_HANG_RETRIES) else "infra_final") if exhausted else None
        else:
            rec["terminal"] = True
            rec["final_status"] = "done"
        store.add(rec)
        log("%s a%d reward=%s class=%s%s%s" % (jid, attempt, rec["reward"], cls or "-", " HANG" if rec["hang"] else "", " -> %s" % rec["final_status"] if rec["terminal"] else " (retry)"))
        if rec["terminal"]:
            return
        attempt += 1


def job_final_state(t, allr):
    """per-cell final status (amendment 5O): ok / retry_k_ok / infra_final / hang_retried / hang_missing / artifact_fail / pending"""
    if not t:
        return "pending"
    if t["final_status"] == "missing":
        return "hang_missing" if t.get("missing_kind") == "hang" else "infra_final"
    if t["error_class"] in ("candidate", "unverifiable"):
        return "artifact_fail"
    prior = allr[:-1]
    if not prior:
        return "ok"
    if any(x.get("hang") for x in prior):
        return "hang_retried"
    return "retry_%d_ok" % len(prior)


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(c - h, 4), round(c + h, 4)]


def infra_diagnostic(jstat):
    """per (mode, arm, seed) and per arm: counts of cells by final status, first-attempt infra rate, infra_final rate (Wilson 95% CI), next to the seed artifact's
    rates in the same window (amendment 5O descriptive diagnostic)."""
    def summarize(rows):
        done = [r for r in rows if r[5]]
        n = len(done)
        st = {}
        for r in done:
            st[r[3]] = st.get(r[3], 0) + 1
        fi = sum(1 for r in done if r[4])
        ff = st.get("infra_final", 0)
        return {"cells": n, "status_counts": st, "first_attempt_infra": fi, "first_attempt_infra_rate": round(fi / n, 4) if n else None,
                "first_attempt_infra_ci95": wilson(fi, n), "infra_final": ff, "infra_final_rate": round(ff / n, 4) if n else None, "infra_final_ci95": wilson(ff, n)}
    out = {"per_artifact": {}, "per_arm": {}, "seed_artifact": summarize([r for r in jstat if r[1] == "seed"])}
    groups = {}
    for r in jstat:
        groups.setdefault(("%s|%s|s%d" % (r[0], r[1], r[2])), []).append(r)
        groups.setdefault(("arm|%s|%s" % (r[0], r[1])), []).append(r)
    for k, rows in sorted(groups.items()):
        out["per_arm" if k.startswith("arm|") else "per_artifact"][k] = summarize(rows)
    return out


def aggregate(suite, root, meta, jobs):
    """results_long.csv (contract; infra_final cells enter as reward 0 with a flag, amendment 5O) + results_long_infra_missing.csv (infra_final cells absent)
    + results_trials.csv + END variants + per-arm and per-artifact infra-rate reports, from raw/rollouts.jsonl"""
    root = Path(root)
    store = Store(root)
    trial_rows = {"B": [], "END": []}
    attempts_by_arm = {}
    by_art = {}
    jlog = []
    jstat = []
    for j in jobs:
        t = store.terminal(j["job_id"])
        allr = store.records(j["job_id"])
        fs = job_final_state(t, allr)
        first_infra = bool(allr) and allr[0]["error_class"] == "infra"
        for x in allr:
            jlog.append(dict(arm=j.get("arm"), arm_label=j["arm_label"], seed=j["seed"], task=j["task"], trial=j["trial"], attempt=x["attempt"], error_class=x["error_class"],
                             error_rule=x.get("error_rule"), hang=int(bool(x.get("hang"))), final_status=fs, t_start=_iso(x["t_start"]), t_end=_iso(x["t_end"]),
                             error_text=(x["error_text"] or "").replace("\n", " ")[:500], job_id=j["job_id"], mode=j["mode"]))
        jstat.append((j["mode"], j["arm_label"], j["seed"], fs, first_infra, bool(t)))
        arm = j["arm_label"]
        rep = attempts_by_arm.setdefault((j["mode"], arm), {"jobs": 0, "attempts": 0, "retried_jobs": 0, "done": 0, "missing_hang": 0, "infra_final": 0, "pending": 0,
                                                            "infra_attempts": 0, "hangs": 0, "candidate_errors": 0, "empty_output": 0, "empty_completion": 0, "raw_tool_text_last": 0})
        art = by_art.setdefault("%s|%s|s%d" % (j["mode"], arm, j["seed"]), {"jobs": 0, "attempts": 0, "infra_attempts": 0, "infra_final": 0, "hang_missing": 0})
        r = rep
        r["jobs"] += 1
        art["jobs"] += 1
        r["attempts"] += len(allr)
        art["attempts"] += len(allr)
        for k in ("sandbox_execs", "sandbox_500", "kernel_recreations", "idle_closures"):
            art[k] = art.get(k, 0) + sum(int(x.get(k) or 0) for x in allr)
        n_inf = sum(1 for x in allr if x["error_class"] == "infra")
        r["retried_jobs"] += 1 if len(allr) > 1 else 0
        r["infra_attempts"] += n_inf
        art["infra_attempts"] += n_inf
        r["hangs"] += sum(1 for x in allr if x.get("hang"))
        if not t:
            r["pending"] += 1
            continue
        infra_final = t["final_status"] == "missing" and t.get("missing_kind") != "hang"
        if t["final_status"] == "missing" and not infra_final:
            r["missing_hang"] += 1
            art["hang_missing"] += 1
            continue
        if infra_final:
            r["infra_final"] += 1
            art["infra_final"] += 1
        else:
            r["done"] += 1
            r["candidate_errors"] += 1 if t["error_class"] in ("candidate", "unverifiable") else 0
            r["empty_output"] += 1 if t.get("empty_output") else 0
            r["empty_completion"] += 1 if t.get("empty_completion") else 0
            r["raw_tool_text_last"] += 1 if t.get("raw_tool_text_last") else 0
        for _m in (["B", "END"] if j.get("also_end") else [j["mode"]]):
            trial_rows[_m].append(dict(arm=j.get("arm"), seed=j["seed"], task=j["task"], trial=j["trial"], reward=(0.0 if infra_final else t["reward"]), family=j.get("family"), split=j.get("split") or "",
                                       reward_as_saved=(0.0 if infra_final else t["reward_as_saved"]), t_start=_iso(t["t_start"]), t_end=_iso(t["t_end"]), error_class=t["error_class"],
                                       error_text=(t["error_text"] or "").replace("\n", " ")[:500], attempts=len(allr), empty_output=int(bool(t.get("empty_output"))),
                                       empty_completion=int(bool(t.get("empty_completion"))), raw_tool_text_last=int(bool(t.get("raw_tool_text_last"))),
                                       infra_final=int(infra_final), tag=t["tag"], job_id=j["job_id"]))
    out = {}
    tcols = ["arm", "seed", "task", "trial", "reward", "family", "split", "reward_as_saved", "t_start", "t_end", "error_class", "error_text", "attempts", "empty_output",
             "empty_completion", "raw_tool_text_last", "infra_final", "tag", "job_id"]
    lcols = ["arm", "seed", "task", "reward", "family", "split", "n_trials", "n_infra_final", "reward_as_saved", "t_start", "t_end", "error_class", "error_text"]
    for mode, suffix in (("B", ""), ("END", "_end")):
        rows = trial_rows[mode]
        _write_csv(root / ("results_trials%s.csv" % suffix), rows, tcols)
        for variant, vsuffix in ((rows, ""), ([x for x in rows if not x["infra_final"]], "_infra_missing")):
            agg = {}
            for x in variant:
                agg.setdefault((x["arm"], x["seed"], x["task"]), []).append(x)
            long_rows = []
            for (arm, seed, task), xs in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2]))):
                long_rows.append(dict(arm=arm, seed=seed, task=task, reward=round(sum(x["reward"] for x in xs) / len(xs), 10), family=xs[0]["family"], split=xs[0].get("split", ""),
                                      n_trials=len(xs), n_infra_final=sum(x["infra_final"] for x in xs), reward_as_saved=round(sum(x["reward_as_saved"] for x in xs) / len(xs), 10),
                                      t_start=min(x["t_start"] for x in xs), t_end=max(x["t_end"] for x in xs),
                                      error_class="|".join(sorted({x["error_class"] for x in xs if x["error_class"]})),
                                      error_text=next((x["error_text"] for x in xs if x["error_text"]), "")))
            _write_csv(root / ("results_long%s%s.csv" % (suffix, vsuffix)), long_rows, lcols)
            if not vsuffix:
                out[mode] = len(long_rows)
    rep = {"%s|%s" % k: v for k, v in sorted(attempts_by_arm.items())}
    C.write_json_atomic(root / "per_arm_report.json", rep)
    for v in by_art.values():
        if v.get("sandbox_execs"):
            v["sandbox_500_rate"] = round(v["sandbox_500"] / v["sandbox_execs"], 5)
            v["kernel_recreations_per_job"] = round(v["kernel_recreations"] / max(1, v["jobs"]), 4)
        v["infra_attempt_rate"] = round(v["infra_attempts"] / v["attempts"], 4) if v["attempts"] else None
        v["infra_final_rate"] = round(v["infra_final"] / v["jobs"], 4) if v["jobs"] else None
    C.write_json_atomic(root / "per_artifact_infra_rates.json", by_art)
    _write_csv(root / "rollout_log.csv", jlog, ["mode", "arm", "arm_label", "seed", "task", "trial", "attempt", "error_class", "error_rule", "hang", "final_status", "t_start", "t_end", "error_text", "job_id"])
    C.write_json_atomic(root / "infra_diagnostic.json", infra_diagnostic(jstat))
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
def sealed_ids(suite):
    if suite == "A":
        d = C.jload(C.PAPER / "protocol/final_set/suiteA_final_tasks.json") or {}
        return {str(t["id"]) for t in d.get("tasks", [])}
    cfg = TAU[suite]
    return {str(x) for x in (C.jload(WT_TAU / "protocol" / cfg["splits"]) or {}).get("sealed_test", [])}


def tag_guard(suite, jobs):
    """real final runs carry FINAL-<suite> tags; dry runs (FE-*) must never touch final-set ids (ids are never printed)."""
    prob = []
    sealed = sealed_ids(suite)
    for j in jobs:
        tag = j["tag"].split(":")[1] if ":" in j["tag"] else j["tag"]
        if j.get("final_split"):
            if not tag.startswith("FINAL-%s" % suite):
                prob.append("final-set job without FINAL-%s tag: %s" % (suite, j["job_id"]))
                break
        else:
            if tag.startswith("FINAL-") and not (suite == "D" and j.get("split") == "sel"):     # Suite D scores sel-25 inside the final window (H65)
                prob.append("search-split job carries a FINAL tag: %s" % j["job_id"])
                break
            if str(j["task"]) in sealed:
                prob.append("dry/search job touches a final-set id (job %s)" % j["job_id"])
                break
    return prob


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
    for j in [x for x in jobs if not x.get("hl")]:
        d = Path(j["artifact_dir"])
        if not d.is_dir():
            prob.append("artifact dir missing: %s" % d)
            break
    prob += tag_guard(suite, jobs)
    seen = set()
    for j in [x for x in jobs if not x.get("hl")]:
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
        try:    # baseline-eng: sandbox must have no internet; check over the podman socket exactly as the adapter creates containers
            chk = BASELINES / "code" / "check_sandbox_egress.py"
            r = subprocess.run(["bash", "-c", "source %s/local/env_local.sh; %s -I %s" % (BENCH, PY["A"], chk)], capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                prob.append("sandbox egress check failed (exit %d): %s" % (r.returncode, (r.stdout + r.stderr)[-300:].replace("\n", " ")))
        except Exception as exc:
            prob.append("egress check failed: %r" % exc)
        if not SB_API_PY.exists() or C.sha256_file(SB_API_PY) != SB_API_SHA:
            prob.append("sandbox api.py sha256 %s != expected %s (idle-kernel timeout 10800 s patch)" % (C.file_sha(SB_API_PY), SB_API_SHA))
        jx = HERE / "manifests/expected_jupyter_sha256.txt"
        jp = C.REPO / "third_party/spreadsheetbench/code_exec_docker/jupyter.py"
        if jx.exists():
            if C.file_sha(jp) != jx.read_text().split()[0]:
                prob.append("sandbox jupyter.py sha256 %s != expected %s (SB_DRAIN_ERROR fix)" % (C.file_sha(jp), jx.read_text().split()[0]))
        else:
            print("NOTE: manifests/expected_jupyter_sha256.txt not recorded yet (waiting for baseline-eng's committed sha)")
        for p in (SB_LO_BIN,):
            if not Path(p).exists():
                prob.append("LibreOffice missing: %s" % p)
        if jobs and not (Path(jobs[0]["agent_view"]) / "dataset.json").exists():
            prob.append("agent view missing: %s (build with make_agent_view.py)" % jobs[0]["agent_view"])
    return sha, prob


def cmd_prepare(a):
    meta, jobs = load_order(a.order)
    sha, prob = preflight(a.suite, a.order, meta, jobs, a.order_sha)
    if getattr(a, "check_kernel_idle", False) and a.suite == "A":      # opt-in, ~12 min: an idle kernel (700 s > the old 600 s timeout) must keep its state
        r = subprocess.run(["bash", "-c", "source %s/local/env_local.sh; %s -I %s --idle-s 700" % (BENCH, PY["A"], HERE / "check_kernel_idle.py")], capture_output=True, text=True)
        print(r.stdout.strip()[-300:])
        if r.returncode != 0:
            prob.append("idle-kernel check failed: %s" % (r.stdout + r.stderr)[-300:].replace("\n", " "))
    if getattr(a, "check_error_drain", False) and a.suite == "A":      # opt-in regression: error exec, 95 s idle, next exec must succeed
        r = subprocess.run(["bash", "-c", "source %s/local/env_local.sh; SB_DRAIN_ERROR=1 %s -I %s --mode error-drain" % (BENCH, PY["A"], HERE / "check_kernel_idle.py")], capture_output=True, text=True)
        print(r.stdout.strip()[-300:])
        if r.returncode != 0:
            prob.append("error-drain regression failed: %s" % (r.stdout + r.stderr)[-300:].replace("\n", " "))
    print(json.dumps({"order_sha256": sha, "n_jobs": len(jobs), "problems": prob}, indent=1))
    return 1 if prob else 0


def cmd_run(a):
    suite = a.suite
    meta, jobs = load_order(a.order)
    root = Path(a.root) if a.root else C.final_dir(suite)
    if a.extra:
        root = root / ("extra_%s" % a.extra)
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

    def caps_watch():          # capped-token guard (coordinator): stop dispatching and page if the gateway's capped counter passes the limit
        import urllib.request
        while not stop.wait(60):
            try:
                capped = int(json.loads(urllib.request.urlopen("http://127.0.0.1:4111/health", timeout=10).read()).get("capped_tokens") or 0)
            except Exception:
                continue
            if capped > a.capped_stop:
                msg = "PAGE: capped tokens %d > %d: run_final stops dispatching" % (capped, a.capped_stop)
                print(msg, flush=True)
                (root / "PAGE_CAPPED_TOKENS").write_text(msg + "\n")
                C.append_jsonl(root / "interruptions.jsonl", {"event": "capped_token_stop", "t": C.now_utc(), "capped": capped})
                stop.set()
                return
    threading.Thread(target=caps_watch, daemon=True).start()
    cl = None
    if a.canary_n:
        meta["canary_jobs"] = meta["canary_jobs"][:a.canary_n]
    if a.canary_every and meta.get("canary_jobs"):
        cl = threading.Thread(target=canary_loop, args=(suite, root, meta, stop, cm, a.canary_every, py, a.hang_s), daemon=True)
        cl.start()
    lk = threading.Lock()
    done_n = [0]
    # one interleaved stream per suite; worker pools per arm class (e.g. hl=24,default=12) so slow HarnessLens cells do not starve the tau-agent cells
    caps = {"default": a.workers}
    if not a.class_caps and suite == "B":
        a.class_caps = "hl=24,default=12"          # decision 2026-10-12 (hl=32 withdrawn: gateway gpt-oss in-flight cap is 24)
    if a.class_caps:
        caps = {k: int(v) for k, v in (x.split("=") for x in a.class_caps.split(","))}
        caps.setdefault("default", a.workers)
    klass = lambda j: "hl" if (j.get("hl") and "hl" in caps) else "default"
    queues = {k: [j for j in todo if klass(j) == k] for k in caps}
    qidx = {k: 0 for k in caps}

    def logf(s):
        print(time.strftime("%H:%M:%S"), s, flush=True)

    def worker_thread(k):
        while not stop.is_set():
            with lk:
                if qidx[k] >= len(queues[k]):
                    return
                j = queues[k][qidx[k]]
                qidx[k] += 1
            try:
                execute_job(j, store, cm, py, a.hang_s, logf)
            except Exception as exc:               # noqa: BLE001 - orchestrator bug must not lose the run
                logf("ORCHESTRATOR ERROR on %s: %r" % (j["job_id"], exc))
            with lk:
                done_n[0] += 1
                if done_n[0] % 25 == 0:
                    aggregate(suite, root, meta, jobs)

    ths = [threading.Thread(target=worker_thread, args=(k,), daemon=True) for k, n in caps.items() for _ in range(n)]
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
        root = root / ("extra_%s" % a.extra)
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
        p.add_argument("--class-caps", default=None, help="per arm-class worker pools, e.g. hl=24,default=12 (HarnessLens cells vs everything else)")
        p.add_argument("--canary-every", type=int, default=3600)
        p.add_argument("--canary-n", type=int, default=0, help="dry runs: use only the first n canary tasks")
        p.add_argument("--hang-s", type=int, default=HANG_S)
        p.add_argument("--force", action="store_true")
        p.add_argument("--capped-stop", type=int, default=198_000_000, help="stop dispatching and write PAGE_CAPPED_TOKENS if the gateway's capped counter passes this")
        p.add_argument("--check-error-drain", action="store_true", help="prepare, Suite A: error exec, 95 s idle, next exec must succeed (needs the SB_DRAIN_ERROR jupyter.py)")
        p.add_argument("--check-kernel-idle", action="store_true", help="prepare, Suite A: also run the ~12 min idle-kernel behavioural check")
    w = sp.add_parser("worker")
    w.add_argument("--job", required=True)
    a = ap.parse_args(argv)
    return {"worker": cmd_worker, "run": cmd_run, "prepare": cmd_prepare, "aggregate": cmd_aggregate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
