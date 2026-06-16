"""skills-bench adapter — optimize an Agent Skill against benchflow-ai/skillsbench.

The capability under optimization is a **skill package** (a `skill-package`
capability): a directory `<skill-name>/SKILL.md`. AgentCapTune edits the skill; the
RUNNER is the skills-bench harness running a chosen agent+model on each task WITH
the candidate skill injected (`--skills-dir <cand> --skill-mode with-skill`); the
SCORE is the task verifier's reward in [0,1].

This targets the **skills-bench v1.2 CLI** (`bench eval create`), where tasks are
`task.md` packages run in a Docker sandbox. There is no in-process API, so the
adapter shells out to `uv run bench eval create` and reads the per-rollout
`result.json` it writes under `--jobs-dir`.

Env knobs:
  ACAPO_SKILLSBENCH_ROOT   path to the skillsbench checkout (required)
  ACAPO_SKB_TASK_IDS       comma-separated task ids (default: all tasks under tasks/)
  ACAPO_SKB_AGENT          benchflow agent: oracle | opencode | openclaw | codex |
                           claude | gemini  (default: oracle — deterministic, no model)
  ACAPO_SKB_MODEL          litellm model id for the agent (e.g. openai/gpt-oss-120b);
                           ignored when agent is "oracle"
  ACAPO_SKB_SANDBOX        docker | daytona | modal (default: docker)
  ACAPO_SKB_TIMEOUT        per-task wall-clock budget in seconds (default: 1200)

Routing a model: with a non-"oracle" agent + a model, benchflow starts a host-side
LiteLLM proxy and the sandboxed agent talks OpenAI to it. Point that proxy at your
provider with the standard provider env vars (OPENAI_API_KEY / WATSONX_* / etc.) or
benchflow's BENCHFLOW_PROVIDER_BASE_URL / BENCHFLOW_PROVIDER_API_KEY. NOTE: IBM RITS
authenticates with a custom `RITS_API_KEY` header (not Bearer), which the in-sandbox
OpenAI agents do not send — use a litellm-native provider (e.g. watsonx) for the
in-sandbox RUNNER. See examples/skills_bench/README.md for the full setup.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from agent_capo import CapabilityAdapter, Rollout, Score, Task

ROOT = Path(os.environ.get("ACAPO_SKILLSBENCH_ROOT", "")).expanduser()
AGENT = os.environ.get("ACAPO_SKB_AGENT", "oracle")
MODEL = os.environ.get("ACAPO_SKB_MODEL", "openai/gpt-oss-120b")
SANDBOX = os.environ.get("ACAPO_SKB_SANDBOX", "docker")
TIMEOUT = int(os.environ.get("ACAPO_SKB_TIMEOUT", "1200"))
_TASK_IDS = os.environ.get("ACAPO_SKB_TASK_IDS", "").strip()


def _task_instruction(task_dir: Path) -> str:
    """The instruction the agent is prompted with (task.md body, after frontmatter)."""
    md = task_dir / "task.md"
    if not md.exists():
        return ""
    text = md.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("\n---", 2)
        if len(parts) >= 2:
            return parts[-1].strip()
    return text.strip()


def _latest_result(jobs: Path) -> tuple[dict, Path] | None:
    """Newest per-rollout (result.json dict, its path) under a --jobs-dir, or None."""
    results = sorted(jobs.rglob("result.json"), key=lambda p: p.stat().st_mtime)
    if not results:
        return None
    return json.loads(results[-1].read_text(encoding="utf-8")), results[-1]


def _verifier_detail(result_path: Path, limit: int = 14) -> dict:
    """Parse the task verifier's pytest output.

    Returns ``{fraction, passed, total, failures}`` where ``fraction`` is the share
    of assertions that passed (a DENSE optimization signal — far better than the
    benchmark's all-or-nothing 0/1 reward, which gives the optimizer no gradient),
    and ``failures`` is a list of ``"test_name: AssertionError msg"`` strings the
    optimizer can act on. Empty dict if no verifier output.
    """
    stdout = result_path.parent / "verifier" / "test-stdout.txt"
    if not stdout.exists():
        return {}
    txt = stdout.read_text(encoding="utf-8", errors="replace")
    # Per-test outcome lines: "::test_name FAILED [ 5%]" / "PASSED" / "ERROR".
    outcomes = re.findall(r"^::?\S*?(\S+?)\s+(PASSED|FAILED|ERROR)", txt, re.M)
    passed = sum(1 for _, o in outcomes if o == "PASSED")
    total = len(outcomes)
    if total == 0:
        # Fallback to the pytest summary line counts.
        counts = {"passed": 0, "failed": 0, "error": 0}
        for m in re.finditer(r"(\d+)\s+(passed|failed|error)", txt):
            counts[m.group(2)] += int(m.group(1))
        passed = counts["passed"]
        total = counts["passed"] + counts["failed"] + counts["error"]
    # Short failure reasons from the summary block: "FAILED ::test - AssertionError: ..."
    failures = []
    for m in re.finditer(r"^(?:FAILED|ERROR)\s+::?(\S+?)(?:\s+-\s+(.*))?$", txt, re.M):
        name, msg = m.group(1).lstrip(":"), (m.group(2) or "").strip()
        entry = f"{name}: {msg}" if msg else name
        if entry not in failures:
            failures.append(entry)
    return {"fraction": (passed / total if total else None),
            "passed": passed, "total": total, "failures": failures[:limit]}


def _reward_of(result: dict) -> float | None:
    r = result.get("rewards")
    if isinstance(r, dict) and isinstance(r.get("reward"), (int, float)):
        return float(r["reward"])
    if isinstance(r, (int, float)):
        return float(r)
    for k in ("reward", "score"):
        if isinstance(result.get(k), (int, float)):
            return float(result[k])
    return None


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        base = ROOT / "tasks"
        wanted = {i.strip() for i in _TASK_IDS.split(",") if i.strip()}
        out = []
        for md in sorted(base.glob("*/task.md")):
            tid = md.parent.name
            if wanted and tid not in wanted:
                continue
            out.append(Task(id=tid, input=_task_instruction(md.parent), target=str(md.parent)))
        return out

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        # The candidate dir IS the skills-root passed to `--skills-dir` (it holds
        # one <skill-name>/SKILL.md). Nothing global to inject; run_target uses it.
        return None

    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        # `bench` runs with cwd=ACAPO_SKILLSBENCH_ROOT, so every path handed to it
        # must be absolute (candidate_dir arrives relative to the acapo workdir).
        candidate_dir = Path(candidate_dir).resolve()
        task_dir = Path(task.target).resolve()
        # Per-candidate jobs dir, cleared each call: candidates share a parent, so a
        # shared/uncleared dir would let one candidate (or trial) read another's stale
        # result.json instead of running the model.
        jobs = (candidate_dir.parent / "skb_jobs" / f"{candidate_dir.name}__{task.id}").resolve()
        if jobs.exists():
            shutil.rmtree(jobs)
        jobs.mkdir(parents=True, exist_ok=True)

        cmd = ["uv", "run", "bench", "eval", "create",
               "--tasks-dir", str(task_dir),
               "--agent", AGENT,
               "--sandbox", SANDBOX,
               "--jobs-dir", str(jobs)]
        if AGENT != "oracle":
            # Inject the candidate skill and route the chosen model.
            cmd += ["--model", MODEL, "--skills-dir", str(candidate_dir),
                    "--skill-mode", "with-skill"]
            # Forward provider/bridge wiring to benchflow's in-sandbox agent so the
            # model call exits to the chosen OpenAI-compatible endpoint (e.g. a local
            # LiteLLM bridge → RITS). Only vars actually set in the environment.
            for var in ("BENCHFLOW_PROVIDER_BASE_URL", "BENCHFLOW_PROVIDER_API_KEY", "OPENAI_API_KEY"):
                val = os.environ.get(var)
                if val:
                    cmd += ["--agent-env", f"{var}={val}"]

        env = dict(os.environ)
        # A plain OpenAI-compatible endpoint (not RITS): mirror RITS_* only when the
        # caller has explicitly opted in by setting OPENAI_BASE_URL (RITS's custom
        # header is incompatible with the in-sandbox agents — see the module docstring).
        if env.get("OPENAI_BASE_URL") and env.get("RITS_API_KEY") and not env.get("OPENAI_API_KEY"):
            env["OPENAI_API_KEY"] = env["RITS_API_KEY"]

        try:
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                                  env=env, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return Rollout(task_id=task.id, error=f"timeout after {TIMEOUT}s")

        found = _latest_result(jobs)
        if found is None:
            return Rollout(task_id=task.id,
                           error=f"no result.json (rc={proc.returncode}): {proc.stderr[-400:]}")
        result, result_path = found

        binary = _reward_of(result)
        detail = _verifier_detail(result_path)
        # Shaped reward: fraction of assertions passed (dense gradient). Fall back to
        # the benchmark's binary reward only if the verifier output can't be parsed.
        reward = detail.get("fraction")
        if reward is None:
            reward = binary if binary is not None else 0.0
        agent_res = result.get("agent_result") or {}
        metrics = result.get("final_metrics") or {}
        cost = metrics.get("total_cost_usd") or agent_res.get("cost_usd") or 0.0
        tokens = agent_res.get("total_tokens") or 0
        return Rollout(
            task_id=task.id,
            output=str(reward),
            trace=json.dumps(result.get("trajectory_summary") or {})[:2000],
            cost_usd=float(cost or 0.0),
            tokens=int(tokens or 0),
            metadata={"reward": float(reward), "binary_pass": binary,
                      "passed": detail.get("passed"), "total": detail.get("total"),
                      "failures": detail.get("failures") or [],
                      "skill_invocations": result.get("n_skill_invocations"),
                      "error": result.get("error")},
        )

    def score(self, task: Task, rollout: Rollout) -> Score:
        meta = rollout.metadata or {}
        reward = float(meta.get("reward") or 0.0)
        passed, total = meta.get("passed"), meta.get("total")
        if reward >= 1.0:
            fb = f"passed all {total or ''} task assertions"
        else:
            head = f"{passed}/{total} assertions passed" if total else f"reward={reward:.3f}"
            fb = f"{head}. Keep the checks that already pass; fix the failing ones"
            if meta.get("error"):
                fb += f" (run error: {meta['error']})"
            failures = meta.get("failures") or []
            if failures:
                fb += ":\n- " + "\n- ".join(failures)
        return Score(task_id=task.id, reward=reward, feedback=fb, trial_rewards=[reward])
