#!/usr/bin/env python3
"""check_kernel_idle.py: behavioural check of the patched sandbox api.py: a kernel left idle for IDLE_S (default 700 s > the old 600 s timeout) must keep its state.
Run in the Suite A venv:  bench/venv/bin/python -I check_kernel_idle.py [--idle-s 700] [--kernel-timeout-s 10800]   exit 0 = ok.
Starts the same sandbox server the adapter starts (patched adapter _Sandbox), runs x=41, idles, then expects x+1 == 42 and no 'Kernel closed' line in server.log."""
import argparse, importlib.util, os, sys, time
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--idle-s", type=int, default=700); ap.add_argument("--kernel-timeout-s", default="10800")
ap.add_argument("--adapter", default="/home/dev/projects2/campaign-scratch/bench/patches/new/adapter.py")
ap.add_argument("--view", default="/home/dev/projects2/campaign-scratch/baselines/work/agent_view_verified400")
a = ap.parse_args()
uid = os.getuid(); env = os.environ
env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % uid); env.setdefault("DOCKER_HOST", "unix://%s/podman/podman.sock" % env["XDG_RUNTIME_DIR"])
env["KERNEL_TIMEOUT_S"] = str(a.kernel_timeout_s); env["CLEANUP_TIMEOUT_MS"] = "5000"
repo = Path(__file__).resolve().parents[4]
env["SPREADSHEETBENCH_HARNESS_DIR"] = str(repo / "third_party/spreadsheetbench"); env["SPREADSHEETBENCH_DATA_DIR"] = a.view
sys.path[:0] = [str(repo / "templates/adapters"), str(repo / "core"), str(Path(a.adapter).parent)]
spec = importlib.util.spec_from_file_location("sb_idle_check", a.adapter); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
sb = m._Sandbox(); cid = "idlecheck-%d" % os.getpid()
try:
    sb.execute(cid, "x = 41")
    time.sleep(a.idle_s)
    out = sb.execute(cid, "print(x + 1)")
    log = (sb.runtime_dir / "server.log").read_text(errors="replace")
    ok = "42" in str(out) and "Kernel closed for conversation %s" % cid not in log
    print("IDLE-KERNEL OK" if ok else "IDLE-KERNEL FAILED", "idle_s=%d timeout=%s out=%r closed_in_log=%s" % (a.idle_s, a.kernel_timeout_s, str(out)[:60], "Kernel closed" in log))
    sys.exit(0 if ok else 1)
except Exception as exc:
    print("IDLE-KERNEL FAILED (exception)", repr(exc)[:300]); sys.exit(1)
finally:
    try: sb.release(cid)
    except Exception: pass
