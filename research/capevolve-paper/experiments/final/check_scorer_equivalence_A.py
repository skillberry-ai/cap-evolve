#!/usr/bin/env python3
"""Suite A score-equivalence check: v1 final scorer (bench/patches/new/adapter.py, sha b128a098) vs the v2 scorer (main's adapter at a3f5eeb6d), on SEARCH-split tasks only.

One target rollout per task is run through the v1 adapter with SPREADSHEETBENCH_KEEP_OUTPUTS=1; the SAME recorded output workbook is then scored by the v1 and by the v2 adapter
(hard_restriction = LibreOffice-recalculated, hard_no_recalc, feedback, per-case result lists).  Compares reward and feedback; no held-out data (val-split ids, tags FE-smoke-...).
The target is Azure gpt-5-mini (dry path; the check is about scoring, not about the model).

usage: python3 -I check_scorer_equivalence_A.py --ids ID1,ID2,... --out shard.json     (run under the bench venv, env as run_final.worker_A)
"""
import argparse
import importlib.util
import json
import shutil
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fe_common as C  # noqa: E402

BENCH = C.SCRATCH / "bench"
V2_ROOT = Path("/home/dev/projects2/wt-v2run")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="FE-smoke-A-equiv")
    a = ap.parse_args()
    env = os.environ
    uid = os.getuid()
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % uid)
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=%s/bus" % env["XDG_RUNTIME_DIR"])
    env.setdefault("DOCKER_HOST", "unix://%s/podman/podman.sock" % env["XDG_RUNTIME_DIR"])
    env.update({
        "MODEL": "litellm_proxy/azoai/gpt-5-mini-2025-08-07", "LITELLM_PROXY_API_BASE": "http://127.0.0.1:4112/v1", "LITELLM_PROXY_API_KEY": "tag:%s-s0:equiv:target" % a.tag,
        "TEMPERATURE": "1.0", "MAX_TOKENS": "8000", "SPREADSHEETBENCH_HARNESS_DIR": str(C.REPO / "third_party/spreadsheetbench"),
        "SPREADSHEETBENCH_DATA_DIR": str(C.SCRATCH / "baselines/work/agent_view_verified400"),
        "SPREADSHEETBENCH_GOLD_DIR": str(C.SCRATCH / "bench/data/extracted/spreadsheetbench_verified_400"),
        "SPREADSHEETBENCH_MAX_TURNS": "30", "SPREADSHEETBENCH_CONCURRENCY": "1", "SPREADSHEETBENCH_SCORING": "hard", "SPREADSHEETBENCH_REWARD_RECALC": "0",
        "SPREADSHEETBENCH_KEEP_OUTPUTS": "1", "SPREADSHEETBENCH_LIBREOFFICE_BIN": str(BENCH / "lo258/root/opt/libreoffice25.8/program/soffice"),
        "KERNEL_TIMEOUT_S": "10800", "SB_DRAIN_ERROR": "1", "PYTHONDONTWRITEBYTECODE": "1", "CAPEVOLVE_HELPERS": "1"})
    tmp = Path(tempfile.mkdtemp(prefix="eqcheck_"))
    env["TMPDIR"] = str(tmp)
    tempfile.tempdir = str(tmp)
    sys.path[:0] = [str(BENCH / "patches/new"), str(V2_ROOT / "templates/adapters"), str(V2_ROOT / "core")]
    ids = a.ids.split(",")
    rows = []
    for tid in ids:
        env["SPREADSHEETBENCH_TASK_IDS"] = tid
        # fresh modules per task: both adapters cache the task table / data dir from the environment at first use
        v1 = load("sb_v1_%s" % tid.replace("-", "_"), str(BENCH / "patches/new/adapter.py"))
        v2 = load("sb_v2_%s" % tid.replace("-", "_"), str(V2_ROOT / "templates/adapters/spreadsheetbench/adapter.py"))
        ctx = tmp / ("ctx_" + tid)
        ctx.mkdir(parents=True, exist_ok=True)
        art = C.SCRATCH / "final_eval/A/artifacts/seed"
        for f in ("prompt.md", "task_template.md"):
            (ctx / f).write_bytes((art / f).read_bytes())
        row = {"task": tid}
        snap = tmp / "nosnap"
        try:
            ad1, ad2 = v1.Adapter(), v2.Adapter()
            task = [t for t in ad1.tasks("val") if t.id == tid]
            if not task:
                task = [t for t in ad1.tasks("test") if t.id == tid]
            task = task[0]
            with ad1.live(ctx):
                r = ad1.run_target(task, ctx, seed=7)
                # the LibreOffice recalculation rewrites the output workbook IN PLACE: score both adapters on the same PRISTINE bytes (snapshot, then restore)
                out_dir = Path(env["SPREADSHEETBENCH_DATA_DIR"]) / "outputs" / str((r.metadata or {}).get("run_tag"))
                snap = tmp / ("snap_" + tid)
                if out_dir.is_dir():
                    shutil.copytree(out_dir, snap)
                s1 = ad1.score(task, r)
            if snap.is_dir():
                shutil.rmtree(out_dir, ignore_errors=True)
                shutil.copytree(snap, out_dir)
            s2 = ad2.score(task, r)
            m1 = {m["name"]: m["value"] for m in (s1.metrics or [])} if s1.metrics else {}
            m2 = {m["name"]: m["value"] for m in (s2.metrics or [])} if s2.metrics else {}
            row.update(error=r.error, r1=s1.reward, r2=s2.reward, m1=m1, m2=m2, f1=(s1.feedback or "")[:600], f2=(s2.feedback or "")[:600],
                       run_tag=(r.metadata or {}).get("run_tag"), same_reward=s1.reward == s2.reward, same_metrics=m1 == m2, same_feedback=(s1.feedback == s2.feedback))
        except Exception as exc:
            row["exception"] = repr(exc)[:400]
        rows.append(row)
        json.dump(rows, open(a.out, "w"), indent=1)
    print("done", len(rows))


if __name__ == "__main__":
    main()
