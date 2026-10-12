"""Shared constants and helpers for the post-cutoff final-evaluation machinery (python >= 3.9, stdlib only).

Nothing here makes a model call or reads a final-set task.  Paths are overridable by environment so the dry run can
point at a scratch directory:  CAMPAIGN_SCRATCH, FINAL_EVAL_ROOT.
"""
from __future__ import annotations

import csv
import datetime as dt
import fcntl
import hashlib
import json
import re
import os
import random
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parents[1]                      # research/capevolve-paper
REPO = PAPER.parents[1]
SCRATCH = Path(os.environ.get("CAMPAIGN_SCRATCH", "/home/dev/projects2/campaign-scratch"))
RUNS = SCRATCH / "runs"
FINAL_ROOT = Path(os.environ.get("FINAL_EVAL_ROOT", str(SCRATCH / "final_eval")))
MANIFESTS = HERE / "manifests"               # committed: bstar_*.json, artifacts_*.json, order hashes
ORDER_SEED = 20261013
CUTOFF_UTC = "2026-10-13T06:00:00Z"
HARD_STOP_UTC = "2026-10-14T07:00:00Z"
BSTAR_FLOOR = 200
BSTAR_STEP = 50

# --- arm registry (keys are the real_numbers.py contract keys) -------------------------------------------------------
# run directory name per (suite, arm); CapEvolve arms live under their long names in Suite A only.
SUITES = {
    "A": {
        "exp": "E10", "label": "SpreadsheetBench (Gemma-4-31B-it)",
        "main": ["hc", "ao", "gepa", "skillopt", "metaharness", "evoskill", "wikiskill"],
        "cheap": ["trace2skill", "ace", "mipro"],
        "controls": [],
        "exploratory": ["hcstock"],       # E12A stock-gate hill climb: does not bind N*, compared at min(N*, own count)
        "dirname": {"hc": "hill-climb", "ao": "agent-optimize"},
        "artifact_kind": "sb_files",       # prompt.md + task_template.md
    },
    "B": {
        "exp": "E10B", "label": "tau2 retail (gpt-oss-120b)",
        "main": ["hc", "ao", "gepa", "harnesslens"],
        "cheap": [],
        "controls": ["oneshot"],
        "dirname": {"oneshot": "ctl-oneshot"},
        "artifact_kind": "tau_cap",        # policy/** + tools/**
    },
    "C": {
        "exp": "E10C", "label": "tau2 airline (gpt-oss-120b)",
        "main": ["hc", "ao", "gepa"],
        "cheap": [],
        "controls": ["oneshot"],
        "dirname": {"oneshot": "ctl-oneshot"},
        "artifact_kind": "tau_cap",
    },
}
SUITES["D"] = {
    "exp": "E20", "label": "tau2 retail, Azure target gpt-4.1-mini (Suite D ablation family)",
    "main": ["pt", "rulep", "p", "t", "ctl", "1s", "gepa", "nohist"],   # Tier 1 + E26-nohist (approved set; amendment 8F, m = 11)
    "cheap": [], "controls": [], "exploratory": [],                       # Tier 2 / exploratory cells are NOT approved for the final window
    "dirname": {},
    "artifact_kind": "tau_cap", "final_state": True,                      # no B*: D searches are rollout-capped, the final state is compared
}
# candidate run directories (relative to RUNS) per Suite D arm; first existing one is used.  Real names: runs/E20/{PT,P,T,CTL}, runs/E21/ruleP (tau-runner)
E_DIRS = {"pt": ["E30/PT"], "p": ["E30/P"], "t": ["E30/T"], "ctl": ["E30/CTL"], "gepa": ["E30/GEPA"], "rulep": ["E31/ruleP"], "1s": ["E31/1S"], "nohist": ["E36/NOHIST"],
          "ace": ["E32/ace"], "mipro": ["E32/mipro"], "gepafull": ["E32/gepafull"], "ao": ["E32/ao"], "harnesslens": ["E10E/harnesslens"]}
D_DIRS = {"pt": ["E20/PT"], "p": ["E20/P"], "t": ["E20/T"], "ctl": ["E20/CTL"], "gepa": ["E20/GEPA"], "rulep": ["E21/ruleP"], "1s": ["E21/1S", "E21/OneStage", "E21/1s"],
          "nohist": ["E26/NOHIST", "E26/nohist"]}
SUITES["E"] = {
    "exp": "E30", "label": "tau2 airline, Azure target gpt-4.1-mini (Suite E replication of D; development-exposed official test-20)",
    "main": ["pt", "rulep", "p", "t", "ctl", "1s", "gepa", "nohist"],      # the 8 ablation cells (family E, m = 11)
    "cheap": ["ace", "mipro", "gepafull", "ao"],                            # E-comp (own Holm; AO daggered); each exists only if its search finishes
    "controls": [], "exploratory": ["harnesslens"],                        # HarnessLens: 1 exploratory seed, outside Holm
    "dirname": {}, "artifact_kind": "tau_cap", "final_state": True,
}
for _s, _ex in (("B", ["hcstock", "hlext"]), ("C", ["hcstock"])):   # B: E12B stock-gate hill climb, HL-extended (exploratory)
    SUITES[_s]["exploratory"] = _ex                  # C: E12C stock-gate hill climb
RUN_ROOT_OVERRIDE = {("A", "hcstock"): RUNS / "E12A" / "hcstock", ("C", "hcstock"): RUNS / "E12C" / "hcstock", ("B", "hcstock"): RUNS / "E12B" / "hcstock",
                     ("B", "hlext"): RUNS / "E10B" / "harnesslens_ext"}
DAGGER = {("B", "ao"), ("C", "ao")}      # amendment 9G: agent-optimize on B/C had access to its own opt/sel gold actions; flagged, second family computed without them
SEEDS = [0, 1, 2]
FAMILY_FILES = {"sb_files": ["prompt.md", "task_template.md"], "tau_cap": None}   # None = policy/** tools/**


def suite_arms(suite, include_cheap=True, include_controls=True, include_exploratory=True):
    s = SUITES[suite]
    return list(s["main"]) + (list(s["cheap"]) if include_cheap else []) + (list(s["controls"]) if include_controls else []) + \
        (list(s.get("exploratory", [])) if include_exploratory else [])


def run_dir(suite, arm, seed):
    s = SUITES[suite]
    if (suite, arm) in RUN_ROOT_OVERRIDE:
        return RUN_ROOT_OVERRIDE[(suite, arm)] / ("s%d" % seed)
    if suite in ("D", "E"):
        root = Path(os.environ["FE_D_RUNROOT"]) if os.environ.get("FE_D_RUNROOT") else RUNS
        cands = (D_DIRS if suite == "D" else E_DIRS).get(arm, [])
        for cand in cands:
            if (root / cand).is_dir():
                return root / cand / ("s%d" % seed)
        return root / (cands[0] if cands else "E20/%s" % arm) / ("s%d" % seed)
    return RUNS / s["exp"] / s["dirname"].get(arm, arm) / ("s%d" % seed)


# --- io helpers ------------------------------------------------------------------------------------------------------
def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jload(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def jsonl(p):
    out = []
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return out


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_files(root, kind):
    """Canonical artifact file list (relative paths, sorted) of an artifact directory."""
    root = Path(root)
    if kind == "sb_files":
        return [f for f in FAMILY_FILES["sb_files"] if (root / f).is_file()]
    out = []
    for sub in ("policy", "tools"):
        for p in sorted((root / sub).rglob("*")) if (root / sub).is_dir() else []:
            if p.is_file() and "__pycache__" not in p.parts:
                out.append(str(p.relative_to(root)))
    return out


def tree_hash(root, kind):
    """sha256 over (relpath NUL file-sha256 NL) of the canonical files; also the per-file map."""
    files = {f: sha256_file(Path(root) / f) for f in tree_files(root, kind)}
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(("%s\0%s\n" % (f, files[f])).encode())
    return h.hexdigest(), files


def tree_hash_normalized(root, kind):
    """Identity of the RENDERED target-facing content.  tau suites (kind tau_cap): the adapters do `policy.md` .strip() and treat '' and '(none)' as 'no addendum'
    (wt-tau examples/tau2_retail/adapters/adapter.py:210-221, wt-airE tau2_airline_c adapter.py:210-221), so the policy file is hashed after strip with '(none)' == ''; other files
    (tools code) are right-stripped.  SpreadsheetBench (kind sb_files): prompt.md and task_template.md are used byte-for-byte (bench/patches/new/adapter.py:981-984,
    :921), so the strict tree hash applies."""
    if kind == "sb_files":
        return tree_hash(root, kind)[0]
    h = hashlib.sha256()
    for f in sorted(tree_files(root, kind)):
        raw = (Path(root) / f).read_bytes()
        if f == "policy/policy.md":
            t = raw.decode("utf-8", "replace").strip()
            raw = b"" if t in ("", "(none)") else t.encode()
        else:
            raw = raw.rstrip()
        h.update(("%s\0%s\n" % (f, sha256_bytes(raw))).encode())
    return h.hexdigest()


def file_sha(path):
    return sha256_file(path) if Path(path).exists() else None


def write_json_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp%d" % os.getpid())
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def append_jsonl(path, obj):
    """Append one JSON line under an exclusive lock (safe for the multi-thread orchestrator)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def import_by_path(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def collect_metrics():
    """The campaign's metrics module (counted_rollouts, uniform_class).  Imported, never copied, so the final runner uses
    the very classifier that is frozen and published with the analysis scripts."""
    if "collect_metrics" in sys.modules:
        return sys.modules["collect_metrics"]
    return import_by_path("collect_metrics", PAPER / "analysis" / "scripts" / "collect_metrics.py")


def git_head(path=REPO):
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def final_dir(suite):
    return FINAL_ROOT / suite


def cell_key(arm, seed):
    return "%s/s%d" % (arm, seed)


def _live(rd):
    """True if any other process has this run dir on its command line (a search still running or restarting)."""
    key = str(rd).encode()
    me = str(os.getpid())
    for d in os.listdir("/proc"):
        if d.isdigit() and d != me:
            try:
                cl = open("/proc/%s/cmdline" % d, "rb").read().replace(b"\0", b" ")
                # post-run scoring (chaser / post_sel) and shell wrappers are not the search
                if key in cl and not any(x in cl for x in (b"eval_cap.py", b"post_score", b"post_sel", b"/bin/bash -c", b"grep", b"check_sandbox")):
                    return True
            except Exception:
                pass
    return False


def native_status(rd):
    """('native_finish'|'crashed'|'running_or_unknown', evidence).  Native = the run's own stop rule ended it with exit status 0 (decisions.md N* rule);
    crashes / infra stops are not native.  Evidence, strongest first: a driver `run.log` whose last line is `exit <rc>`; a `launcher.log` line `exit=<rc>`;
    `run_summary.json` / `final.json` / `final/` written by the method itself.  Anything else counts as still running (binds N*, conservative)."""
    import re as _re
    rd = Path(rd)
    # frozen optimizer-token guard (CapEvolve): soft stop at 3.5M (budget frozen := spent) / hard SIGTERM at 3.9M; counts like a native termination (N* addendum)
    for f in [rd / "logs" / "optimizer_tokens.json.soft", rd / "logs" / "optimizer_tokens.json.killed", rd / "optimizer_tokens.json.soft", rd / "optimizer_tokens.json.killed"] \
            + list(rd.glob(".capevolve/run_*/optimizer_tokens.json.soft")):
        if f.exists():
            return "guard_stop", "token guard marker %s (%s)" % (f.name, "hard SIGTERM at 3.9M" if f.name.endswith("killed") else "soft stop at 3.5M")
    # Suite B/C (tau-runner): scripts/E10{B,C}/cost_summary.py --guard writes `GUARD: <tag> optimizer non-cache-read N > LIMIT; killing process group of P` to guard.log,
    # SIGTERMs the driver (no `exit N` line in run.log) and a watcher / the guard itself writes logs/token_guard_stop.json.  A crash leaves neither.
    tg = rd / "logs" / "token_guard_stop.json"
    if tg.exists():
        d = jload(tg) or {}
        return "guard_stop", "logs/token_guard_stop.json (%s, %s > %s)" % (d.get("kind"), d.get("optimizer_noncache_read_tokens"), d.get("limit"))
    bs = rd / "logs" / "budget_stop.json"      # HarnessLens (bl-harness, derived from its ledger + final.json by hl_stop_marker.py)
    if bs.exists():
        d = jload(bs) or {}
        if d.get("status") == "finished":
            return ("guard_stop" if d.get("stop_reason") == "token_guard" else "native_finish"), "logs/budget_stop.json finished (%s)" % d.get("stop_reason")
        if d.get("status") == "crashed":
            return "crashed", "logs/budget_stop.json crashed (%s)" % str(d.get("last_error"))[:80]
    gl = rd / "guard.log"
    if gl.exists():
        try:
            if re.search(r"GUARD: (\S+) optimizer non-cache-read (\d+) > (\d+); killing process group of (\d+)", gl.read_text(errors="replace")):
                return "guard_stop", "guard.log GUARD line"
        except Exception:
            pass
    for ev in list(rd.glob(".capevolve/run_*/events.jsonl")) + [rd / "events.jsonl"]:
        if ev.exists():
            try:
                with open(ev, errors="replace") as fh:
                    for line in fh:
                        if "token_guard_soft" in line or "token_guard_hard" in line:
                            return "guard_stop", "events.jsonl: " + ("token_guard_hard" if "token_guard_hard" in line else "token_guard_soft")
            except Exception:
                pass
    for run in sorted((rd / ".capevolve").glob("run_*")):      # Suite A CapEvolve: the post-agent seal step (eval_start on split=test) means the agent's search has ENDED
        evf2 = run / "events.jsonl"
        if evf2.exists() and (rd / "logs" / "host.out").exists():
            try:
                with open(evf2, errors="replace") as fh:
                    for line in fh:
                        if '"eval_start"' in line and '"split": "test"' in line:
                            return "native_finish", "events.jsonl: post-agent seal step started (eval_start split=test); the agent's search has ended"
            except Exception:
                pass
    if _live(rd):
        return "running_or_unknown", "a process with this run dir on its command line is alive"
    for name, pat in (("run.log", r"^exit (\d+)\s*$"), ("launcher.log", r"^exit=(\d+)\s*$")):
        p = rd / name
        if p.exists():
            try:
                tail = p.read_text(errors="replace").splitlines()[-40:]
            except Exception:
                tail = []
            for line in reversed(tail):
                m = _re.match(pat, line.strip())
                if m:
                    rc = int(m.group(1))
                    if rc != 0 and name == "launcher.log" and re.search(r"RolloutCap|hard cap of \d+ target rollouts", "\n".join(tail)):
                        # baseline-eng: exit 1 = sb_eval_lib.RolloutCap, the search used its whole hard cap (600 counted rollouts): a budget termination, not a crash
                        return "budget_cap", "launcher.log: exit %d from RolloutCap (search budget fully used)" % rc
                    if rc != 0 and any(rd.glob(".capevolve/run_*/final.json")):
                        # CapEvolve AO: the search ended on its own and the exit status comes from the finalize step failing on the test seal (superseded by the approved
                        # host-side finalize; decisions.md 02:50 UTC): a native termination, not a crash
                        return "native_finish", "%s: exit %d from the finalize step, final.json present (search ended on its own)" % (name, rc)
                    return ("native_finish" if rc == 0 else "crashed"), "%s: exit %d" % (name, rc)
    ho = rd / "logs" / "host.out"      # Suite A agent-optimize: the host appends `host-exited` on every exit; it counts as the agent's OWN end only if the agent produced its final report first
    if ho.exists() and not _live(rd):
        try:
            tail = ho.read_text(errors="replace")[-6000:]
        except Exception:
            tail = ""
        if tail.rstrip().endswith("host-exited") and "best_id" in tail:
            return "native_finish", "logs/host.out: agent's final report (best_id) followed by host-exited, no live process (exit code not logged)"
    evf = rd / "events.jsonl"      # EvoSkill: the loop writes {"event": "loop_done"} when its own stop rule ends it; must be newer than the last restart
    if evf.exists():
        rl = rd / "restart_log.json"
        restart_m = rl.stat().st_mtime if rl.exists() else 0
        try:
            with open(evf, errors="replace") as fh:
                for line in fh:
                    if '"loop_done"' in line:
                        try:
                            d = json.loads(line)
                        except Exception:
                            continue
                        if d.get("event") == "loop_done" and float(d.get("t") or 0) > restart_m:
                            return "native_finish", "events.jsonl loop_done at rollout_index %s (after the last restart)" % d.get("rollout_index")
        except Exception:
            pass
    for ev in ("run_summary.json", "final.json", "final"):
        cands = [rd / ev] + list((rd / ".capevolve").glob("run_*/" + ev))
        hit = [c for c in cands if c.exists()]
        if hit:
            # a summary left over from before a resume-restart is stale: it must be newer than the latest restart record
            rl = rd / "restart_log.json"
            restart_m = rl.stat().st_mtime if rl.exists() else 0
            if max(c.stat().st_mtime for c in hit) <= restart_m:
                continue
            return "native_finish", "%s present, newer than the last restart (no exit line)" % ev
    return "running_or_unknown", "no exit evidence"
