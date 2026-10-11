#!/usr/bin/env python3
"""One SpreadsheetBench task, seed capability, agent-only (NO optimizer): CodeAct loop in a podman
container -> output workbook -> adapter.score(). Costs only the agent model's tokens (<= --max-turns calls).

  source local/env_local.sh
  export MODEL=litellm_proxy/aws/gpt-oss-120b LITELLM_PROXY_API_BASE=... LITELLM_PROXY_API_KEY=...   # provider env (caller supplies)
  $BENCH/venv/bin/python local/sb_single_task.py --task <id> [--variant verified_400] [--isolated|--historical]

--isolated   (default) patched adapter, DATA_DIR = gold-free agent view, GOLD_DIR = pristine tree.
--historical unpatched repo adapter, gold inside the mounted DATA_DIR (CapEvolve as shipped).
Prints rewards under all four recorded metrics (soft/hard x restriction(recalc)/no_recalc)."""
import argparse, json, os, shutil, subprocess, sys, tempfile, importlib.util
from pathlib import Path
BENCH = Path(os.environ.get("BENCH", "/home/dev/projects2/campaign-scratch/bench"))
REPO = Path(os.environ.get("REPO", "/home/dev/projects2/cap-evolve-campaign"))
ap = argparse.ArgumentParser()
ap.add_argument("--task", required=True)
ap.add_argument("--variant", default="verified_400", choices=["verified_400", "full_912", "sample_200"])
ap.add_argument("--max-turns", type=int, default=30)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--historical", action="store_true")
ap.add_argument("--soffice", default=os.environ.get("SPREADSHEETBENCH_LIBREOFFICE_BIN", ""))
ap.add_argument("--out", default=str(BENCH / "out" / "sb_single"))
a = ap.parse_args()
inner = {"verified_400": "spreadsheetbench_verified_400", "full_912": "all_data_912_v0.1", "sample_200": "sample_data_200"}[a.variant]
gold = BENCH / "data" / "extracted" / inner
work = Path(tempfile.mkdtemp(prefix="sb_single_", dir=a.out if Path(a.out).is_dir() else None))
cand = work / "candidate"; shutil.copytree(REPO / "templates/adapters/spreadsheetbench/seed_capability", cand)
env = os.environ
env["SPREADSHEETBENCH_HARNESS_DIR"] = str(REPO / "third_party/spreadsheetbench")
env["SPREADSHEETBENCH_TASK_IDS"] = a.task
env["SPREADSHEETBENCH_MAX_TURNS"] = str(a.max_turns)
env["SPREADSHEETBENCH_CONCURRENCY"] = "1"
env["SPREADSHEETBENCH_SCORING"] = "hard"
env["SPREADSHEETBENCH_REWARD_RECALC"] = "0"
env["SPREADSHEETBENCH_KEEP_OUTPUTS"] = "1"
env.setdefault("TEMPERATURE", "0.0"); env.setdefault("MAX_TOKENS", "8000")
if a.soffice: env["SPREADSHEETBENCH_LIBREOFFICE_BIN"] = a.soffice
if a.historical:
    adapter = REPO / "templates/adapters/spreadsheetbench/adapter.py"; env["SPREADSHEETBENCH_DATA_DIR"] = str(gold)
else:
    adapter = BENCH / "patches/new/adapter.py"
    view = work / "agent_view"
    subprocess.run([sys.executable, str(BENCH / "local/make_agent_view.py"), str(gold), str(view)], check=True)
    env["SPREADSHEETBENCH_DATA_DIR"] = str(view); env["SPREADSHEETBENCH_GOLD_DIR"] = str(gold)
sys.path.insert(0, str(adapter.parent)); sys.path.insert(0, str(REPO / "templates/adapters")); sys.path.insert(0, str(REPO / "core"))
spec = importlib.util.spec_from_file_location("sb_adapter_single", adapter); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
A = ad.Adapter()
task = [t for t in A.tasks("test") if t.id == a.task]
assert task, f"task {a.task} not in {a.variant}"
ctx = cand
with A.live(ctx):
    r = A.run_target(task[0], ctx, seed=a.seed)
    print("rollout error:", r.error, "| turns/cost:", getattr(r, "metadata", {}).get("turns"), r.cost_usd, r.tokens, file=sys.stderr)
    s = A.score(task[0], r)
res = {"task": a.task, "variant": a.variant, "mode": "historical" if a.historical else "isolated", "reward": s.reward,
       "metrics": {m["name"]: m["value"] for m in (s.metrics or [])}, "error": r.error, "cost_usd": r.cost_usd, "tokens": r.tokens,
       "feedback": s.feedback, "soffice": ad._libreoffice_bin(), "workdir": str(work)}
print(json.dumps(res, indent=1))
