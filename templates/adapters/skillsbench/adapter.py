"""SkillsBench adapter template — optimize SHARED office-document Agent Skills.

Ready-to-use cap-evolve adapter for SkillsBench (https://github.com/benchflow-ai/skillsbench).
Supports Anthropic-compatible gateways for the in-sandbox Claude agent.

SETUP:
  1. Install the `bench` CLI (BenchFlow):
       See https://github.com/benchflow-ai/bench for installation.

  2. Copy this directory to .capevolve/project/adapters/

  3. Set env vars (in .env or shell):
       ANTHROPIC_BASE_URL=https://your-anthropic-gateway.example.com
       ANTHROPIC_AUTH_TOKEN=sk-ant-…

     Or for direct Anthropic API:
       ANTHROPIC_BASE_URL=https://api.anthropic.com
       ANTHROPIC_AUTH_TOKEN=sk-ant-…

  4. Optional env vars:
       SKILLSBENCH_MODEL=claude-sonnet-4-6        # the in-sandbox agent model (as your gateway names it)
       SKILLSBENCH_AGENT=claude                   # agent kind bench runs
       SKILLSBENCH_SANDBOX=docker                 # docker | modal
       SKILLSBENCH_BENCH_BIN=/path/to/bench       # default: ~/.local/bin/bench
       SKILLSBENCH_CONCURRENCY=7                   # parallel tasks (default: 7)
       SKILLSBENCH_TASK_TIMEOUT=1800               # per-task timeout in seconds

  5. Run: cap-evolve check && cap-evolve run

WHAT THIS OPTIMIZES:
  - Four shared office-document Agent Skills (docx, pptx, xlsx, pdf)
  - Each skill is a sub-package with a SKILL.md

HOW IT WORKS:
  - tasks()      → the 10 SkillsBench task ids (no network; ids only).
  - run_batch()  → one `bench eval run` call with candidate skills injected.
  - score()      → binary verifier reward + gold-SAFE CTRF-based feedback.
  - materialize() → writes edits namespaced per sub-skill.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

# --- benchmark constants ----------------------------------------------------
SOURCE_REPO = "benchflow-ai/skillsbench"
SOURCE_PATH = "tasks"
SOURCE_REF = "main"
# Optional LOCAL tasks dir (a checkout of skillsbench). When set, bench reads tasks
# from here (--tasks-dir) instead of resolving/cloning the remote repo — this avoids
# bench's remote source-SHA resolution (which can fail on newer git) and works offline.
TASKS_DIR = os.environ.get("SKILLSBENCH_TASKS_DIR", "")
AGENT = os.environ.get("SKILLSBENCH_AGENT", "claude")
MODEL = os.environ.get("SKILLSBENCH_MODEL", "claude-sonnet-4-6")
SANDBOX = os.environ.get("SKILLSBENCH_SANDBOX", "docker")
BENCH_BIN = os.environ.get("SKILLSBENCH_BENCH_BIN") or str(
    Path.home() / ".local" / "bin" / "bench"
)

TASK_IDS = [
    "offer-letter-generator",
    "exceltable-in-ppt",
    "xlsx-recover-data",
    "sales-pivot-analysis",
    "invoice-fraud-detection",
    "weighted-gdp-calc",
    "financial-modeling-qa",
    "pdf-excel-diff",
    "pptx-reference-formatting",
    "reserves-at-risk-calc",
]

_BENCH_CWD = Path(
    os.environ.get("SKILLSBENCH_BENCH_CWD")
    or (Path(__file__).resolve().parents[2] / ".bench_cwd")
)


# --- credential helper (lazy — no network at import time) -------------------


def _load_env() -> None:
    """Load the repo-root .env into os.environ (walk parents), without overwrite."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        env = parent / ".env"
        if env.exists():
            try:
                for raw in env.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key:
                        os.environ.setdefault(key, val)
            except Exception as exc:  # non-fatal: env vars may already be set
                print(f"skillsbench: could not read {env}: {exc}", file=sys.stderr)
            break


def _gateway_env() -> dict[str, str]:
    """Return the gateway env for the sandboxed agent.

    Always includes the Anthropic-compatible vars (Claude models). Also mirrors them
    onto OpenAI-compatible vars so an OpenAI-family model (e.g. aws/gpt-oss-120b)
    served by the same gateway can run — bench routes such models via OPENAI_API_KEY.
    """
    _load_env()
    base = os.environ.get("ANTHROPIC_BASE_URL")
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    missing = [
        v
        for v, x in (("ANTHROPIC_BASE_URL", base), ("ANTHROPIC_AUTH_TOKEN", token))
        if not x
    ]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not set. Put them in the repo-root .env."
        )
    env = {"ANTHROPIC_BASE_URL": base, "ANTHROPIC_AUTH_TOKEN": token}
    # OpenAI-compatible mirror (same gateway) for OpenAI-family agent models.
    env["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", token)
    env["OPENAI_BASE_URL"] = os.environ.get("OPENAI_BASE_URL", base.rstrip("/") + "/v1")
    return env


class Adapter(CapabilityAdapter):

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return the 10 SkillsBench tasks for any split (stable, no network)."""
        return [
            Task(id=tid, input=tid, metadata={"benchmark": "skillsbench"})
            for tid in TASK_IDS
        ]

    # ---- running ---------------------------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run ONE SkillsBench task — a thin wrapper over run_batch."""
        return self.run_batch([task], ctx, seed=seed).get(
            task.id, Rollout(task_id=task.id, error="no rollout produced")
        )

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run ALL tasks in ONE bench eval run call, in parallel."""
        if not tasks:
            return {}

        # Short-circuit unknown task ids WITHOUT launching bench — this keeps the
        # `cap-evolve check` stub-probe (a synthetic "__probe__" task) cheap and
        # offline, and rejects any id that is not a real SkillsBench task.
        known = set(TASK_IDS)
        results: dict[str, Rollout] = {
            t.id: Rollout(task_id=t.id, error=f"unknown SkillsBench task id: {t.id!r}")
            for t in tasks if t.id not in known
        }
        tasks = [t for t in tasks if t.id in known]
        if not tasks:
            return results

        candidate_dir = Path(ctx).resolve()
        jobs_dir = self._jobs_dir(candidate_dir, seed)
        jobs_dir.mkdir(parents=True, exist_ok=True)
        _BENCH_CWD.mkdir(parents=True, exist_ok=True)

        # Deploy only real skill sub-packages (dirs with SKILL.md).
        skills_root = Path(
            tempfile.mkdtemp(prefix="skillsbench_skills_", dir=str(_BENCH_CWD))
        )
        for sub in sorted(candidate_dir.iterdir()):
            if sub.is_dir() and (sub / "SKILL.md").exists():
                shutil.copytree(sub, skills_root / sub.name)

        try:
            env = _gateway_env()
        except Exception as e:
            shutil.rmtree(skills_root, ignore_errors=True)
            return {
                t.id: Rollout(
                    task_id=t.id, error=f"gateway credentials unavailable: {e}"
                )
                for t in tasks
            }

        concurrency = min(
            len(tasks), int(os.environ.get("SKILLSBENCH_CONCURRENCY", "7"))
        )
        cmd = [BENCH_BIN, "eval", "run"]
        # Source: a local tasks dir (robust/offline) if provided, else the remote repo.
        if TASKS_DIR and Path(TASKS_DIR).is_dir():
            cmd += ["--tasks-dir", str(Path(TASKS_DIR).resolve())]
        else:
            cmd += ["--source-repo", SOURCE_REPO, "--source-path", SOURCE_PATH,
                    "--source-ref", SOURCE_REF]
        cmd += [
            "--agent", AGENT,
            "--model", MODEL,
            "--sandbox", SANDBOX,
            "--concurrency", str(concurrency),
            "--skill-mode", "with-skill",
            "--skills-dir", str(skills_root),
            "--jobs-dir", str(jobs_dir),
        ]
        # Pass every gateway var (Anthropic + OpenAI mirror) so both Claude and
        # OpenAI-family agent models resolve against the same gateway.
        for k, v in env.items():
            cmd += ["--agent-env", f"{k}={v}"]
        for t in tasks:
            cmd += ["--include", t.id]

        per_task_s = int(os.environ.get("SKILLSBENCH_TASK_TIMEOUT", "1800"))
        waves = (len(tasks) + concurrency - 1) // max(concurrency, 1)
        timeout_s = per_task_s * max(waves, 1) + 600
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(_BENCH_CWD),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            launch_err = None
            rc = proc.returncode
            tail = (proc.stderr or proc.stdout or "")[-1500:]
        except subprocess.TimeoutExpired:
            launch_err = f"bench eval run timed out after {timeout_s}s"
            rc, tail = None, ""
        except Exception as e:  # noqa: BLE001
            launch_err = f"bench eval run failed to launch: {e}"
            rc, tail = None, ""
        finally:
            shutil.rmtree(skills_root, ignore_errors=True)

        # (results already holds any unknown-task-id errors from the guard above)
        for t in tasks:
            if launch_err is not None:
                results[t.id] = Rollout(
                    task_id=t.id,
                    error=launch_err,
                    metadata={"jobs_dir": str(jobs_dir)},
                )
                continue
            task_dir = _task_jobs_dir(jobs_dir, t.id)
            reward, ctrf, found = _read_verifier(task_dir)
            transcript = _read_transcript(task_dir)
            if not found:
                results[t.id] = Rollout(
                    task_id=t.id,
                    error=f"no verifier reward for {t.id} under {jobs_dir} (rc={rc}). tail: {tail}",
                    output=transcript,
                    metadata={"jobs_dir": str(jobs_dir), "ctrf": ctrf},
                )
            else:
                results[t.id] = Rollout(
                    task_id=t.id,
                    output=transcript,
                    trace=transcript,
                    cost_usd=0.0,
                    tokens=0,
                    error=None,
                    metadata={
                        "reward": float(reward),
                        "ctrf": ctrf,
                        "jobs_dir": str(jobs_dir),
                    },
                )
        return results

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Binary SkillsBench reward + gold-SAFE, SPECIFIC feedback."""
        meta = rollout.metadata or {}

        if rollout.error:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=(
                    "Rollout did not complete for an infrastructure reason "
                    f"({rollout.error}). Uncontrollable noise, not a skill defect; "
                    "do not optimize against it."
                ),
            )

        reward = float(meta.get("reward", 0.0) or 0.0)
        ctrf = meta.get("ctrf") or {}
        feedback = _build_feedback(reward, ctrf)
        return Score(task_id=task.id, reward=reward, feedback=feedback)

    # ---- candidate materialization ----------------------------------------

    def materialize(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """Write {component: text} edits into the candidate dir. PURE."""
        super().materialize(candidate_dir, edits)

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _jobs_root(skills_dir: Path) -> Path:
        # Non-fatal path-shape probe; any odd layout falls back to the default root.
        try:
            if skills_dir.parent.name == "candidates":
                return skills_dir.parent.parent / "bench_jobs"
        except (AttributeError, IndexError, TypeError):
            pass  # odd path shape → fall through to the default jobs root below
        return Path(__file__).resolve().parents[2] / ".bench_runs" / "default"

    @classmethod
    def _jobs_dir(cls, candidate_dir: Path, seed: int) -> Path:
        return cls._jobs_root(candidate_dir) / candidate_dir.name / f"seed{seed}"


# ---------------------------------------------------------------------------
# Verifier / transcript readers + gold-safe feedback
# ---------------------------------------------------------------------------


def _task_jobs_dir(batch_dir: Path, task_id: str) -> Path:
    if not batch_dir.is_dir():
        return batch_dir
    matches = sorted(d for d in batch_dir.rglob(f"{task_id}__*") if d.is_dir())
    return matches[-1] if matches else batch_dir


def _read_verifier(jobs_dir: Path) -> tuple[float, dict, bool]:
    """Read SkillsBench's verifier reward (0/1) and CTRF report."""
    ctrf: dict = {}
    for cf in jobs_dir.rglob("ctrf*.json"):
        try:
            ctrf = json.loads(cf.read_text(encoding="utf-8"))
            break
        except Exception:
            continue

    for rf in jobs_dir.rglob("reward.txt"):
        try:
            return float(rf.read_text(encoding="utf-8").strip() or "0"), ctrf, True
        except Exception:
            continue

    for rf in list(jobs_dir.rglob("result*.json")) + list(
        jobs_dir.rglob("*scored*.json")
    ):
        try:
            obj = json.loads(rf.read_text(encoding="utf-8"))
        except Exception:
            continue
        r = _extract_reward(obj)
        if r is not None:
            return float(r), ctrf, True

    if ctrf:
        summary = (ctrf.get("results") or {}).get("summary") or {}
        tests = summary.get("tests")
        passed = summary.get("passed")
        if isinstance(tests, int) and tests > 0 and isinstance(passed, int):
            return (1.0 if passed == tests else 0.0), ctrf, True

    return 0.0, ctrf, False


def _extract_reward(obj):
    """Recursively find a 'reward' field in a result JSON."""
    if isinstance(obj, dict):
        for k in ("reward", "score"):
            if k in obj and isinstance(obj[k], (int, float, bool)):
                return float(obj[k])
        for v in obj.values():
            r = _extract_reward(v)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _extract_reward(v)
            if r is not None:
                return r
    return None


def _read_transcript(jobs_dir: Path):
    """Best-effort: the agent's native transcript as a list of message dicts."""
    for tf in jobs_dir.rglob("*trajectory*.jsonl"):
        msgs = []
        try:
            for line in tf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        msgs.append(json.loads(line))
                    except Exception:
                        msgs.append({"raw": line})
        except Exception:
            continue
        if msgs:
            return msgs
    return None


def _build_feedback(reward: float, ctrf: dict) -> str:
    """Gold-SAFE, SPECIFIC learning signal from CTRF report."""
    if reward >= 1.0:
        return "Task fully solved (all verifier tests passed; reward 1.0)."

    tests = []
    try:
        tests = (ctrf.get("results") or {}).get("tests") or []
    except Exception:
        tests = []

    failed = [
        t
        for t in tests
        if isinstance(t, dict)
        and str(t.get("status", "")).lower() in ("failed", "error")
    ]
    if not failed:
        return (
            f"Task scored {reward:.3f} (not all verifier tests passed). No per-test "
            "CTRF breakdown was available; inspect ./trajectories/ for the agent "
            "transcript and the produced files."
        )

    lines = [f"Task reward: {reward:.3f}. {len(failed)} verifier test(s) failed:"]
    for t in failed[:12]:
        name = str(t.get("name") or t.get("test") or "<unnamed test>")
        msg = t.get("message") or t.get("failure") or ""
        if isinstance(msg, dict):
            msg = msg.get("message") or msg.get("text") or ""
        msg = str(msg).strip().replace("\n", " ")
        if len(msg) > 280:
            msg = msg[:280] + "…"
        lines.append(f"  - {name}" + (f": {msg}" if msg else ""))
    return "\n".join(lines)
