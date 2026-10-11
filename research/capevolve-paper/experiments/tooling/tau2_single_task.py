#!/usr/bin/env python3
"""One tau2 airline task, seed capability (policy + tools), agent + user-simulator only (NO optimizer).

  source local/env_local.sh
  export MODEL=litellm_proxy/aws/gpt-oss-120b LITELLM_PROXY_API_BASE=... LITELLM_PROXY_API_KEY=...   # provider env (caller supplies)
  # optional: TAU2_USER_MODEL=litellm_proxy/<other>   (default: the same MODEL as the agent -- CI behaviour)
  $BENCH/venv-tau2-8ebb749/bin/python local/tau2_single_task.py --task 9 [--seed 0]

Uses templates/adapters/tau2_bench/adapter.py (the CI `tau2` leg). Reward is tau2's own deterministic DB+COMMUNICATE
check (no LLM judge for airline: reward_basis is [DB, COMMUNICATE] on all 50 tasks)."""
import argparse, importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path
REPO = Path(os.environ.get("REPO", "/home/dev/projects2/cap-evolve-campaign"))
ap = argparse.ArgumentParser(); ap.add_argument("--task", default="9"); ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--capability", default=str(REPO / "examples/tau2_airline/seed_capability"))
a = ap.parse_args()
os.environ.setdefault("TEMPERATURE", "0.0"); os.environ.setdefault("MAX_TOKENS", "8000")
os.environ.setdefault("TAU2_MAX_CONCURRENCY", "1"); os.environ.setdefault("CAPEVOLVE_NATIVE_SIMS", "0")
sys.path.insert(0, str(REPO / "templates/adapters/tau2_bench")); sys.path.insert(0, str(REPO / "templates/adapters")); sys.path.insert(0, str(REPO / "core"))
spec = importlib.util.spec_from_file_location("tau2_adapter_single", REPO / "templates/adapters/tau2_bench/adapter.py")
ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
cand = Path(tempfile.mkdtemp(prefix="tau2_single_")) / "candidate"; shutil.copytree(a.capability, cand)
A = ad.Adapter(); tasks = [t for t in A.tasks("test") if t.id == a.task]; assert tasks, f"airline task {a.task} not found"
A.apply(cand)
r = A.run_batch(tasks, cand, seed=a.seed)[a.task]
s = A.score(tasks[0], r)
print(json.dumps({"task": a.task, "seed": a.seed, "reward": s.reward, "error": r.error, "cost_usd": r.cost_usd, "tokens": r.tokens,
                  "agent_model": ad.model_config.MODEL, "user_model": ad._user_model(), "feedback": (s.feedback or "")[:1500]}, indent=1))
