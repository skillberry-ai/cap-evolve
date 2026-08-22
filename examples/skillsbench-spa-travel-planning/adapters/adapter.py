"""Project adapter — optimize travel-planning skills via SPA.

Wires cap-evolve to SkillsBench (https://github.com/benchflow-ai/skillsbench)
with Skillberry Proxy-Agent (SPA) as the LLM backend for the OpenHands agent.

Architecture:
  OpenHands (Docker sandbox) → SPA (host:7000) → Skillberry Store (host:8000) + real LLM

  * ``tasks``        -> ["travel-planning"] (single task, no network).
  * ``run_target``   -> one ``bench eval create``: an OpenHands agent in a Docker
                        sandbox, with LLM_BASE_URL pointing to SPA on the host
                        (via Docker bridge IP). The CANDIDATE'S 6 travel skills are
                        injected via ``--skill-mode with-skill --skills-dir <ctx>``.
  * ``score``        -> SkillsBench's binary verifier reward in {0,1}; gold-SAFE,
                        SPECIFIC feedback from the CTRF report.
                        DETERMINISTIC: reads the recorded reward, never re-runs.
  * ``materialize``  -> writes ``{component: text}`` edits into the candidate dir,
                        namespaced per sub-skill ("<skill>/SKILL.md", ...). PURE.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import spa_env

# --- benchmark constants ----------------------------------------------------
SOURCE_REPO = "benchflow-ai/skillsbench"
SOURCE_PATH = "tasks"
SOURCE_REF = "main"
AGENT = "openhands"
SANDBOX = "docker"

BENCH_BIN = os.environ.get("SKILLSBENCH_BENCH_BIN") or str(
    Path(os.environ.get("SKILLSBENCH_REPO", "")).resolve() / ".venv" / "bin" / "bench"
    if os.environ.get("SKILLSBENCH_REPO")
    else Path.home() / ".local" / "bin" / "bench"
)

TASK_IDS = [
    "travel-planning",
]

_BENCH_CWD = Path(
    os.environ.get("SKILLSBENCH_BENCH_CWD")
    or (Path(__file__).resolve().parents[2] / ".bench_cwd")
)


_SPA_PORT = os.environ.get("SKILLBERRY_AGENT_PORT", "7000")
_STORE_PORT = os.environ.get("SKILLBERRY_STORE_PORT", "8000")
_STORE_DIR = os.environ.get("SKILLBERRY_STORE_DIR", "")
_AGENT_DIR = os.environ.get("SKILLBERRY_AGENT_DIR", "")


def _kill_port(port: str) -> None:
    """Kill any process listening on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            if pid:
                os.kill(int(pid), 9)
    except Exception:
        pass


def _stop_service(service_dir: str, port: str) -> None:
    """Stop a skillberry service: try make stop, then kill the port."""
    if service_dir and Path(service_dir).is_dir():
        try:
            subprocess.run(
                ["make", "stop"], cwd=service_dir,
                capture_output=True, text=True, timeout=15,
            )
        except Exception:
            pass
    _kill_port(port)


class Adapter(CapabilityAdapter):

    _teardown_registered = False

    def __init__(self):
        super().__init__()
        if not Adapter._teardown_registered:
            atexit.register(Adapter.teardown)
            Adapter._teardown_registered = True

    @staticmethod
    def teardown():
        """Stop skillberry-agent and skillberry-store services."""
        _stop_service(_AGENT_DIR, _SPA_PORT)
        _stop_service(_STORE_DIR, _STORE_PORT)

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return SkillsBench tasks (stable, no network)."""
        return [Task(id=tid, input=tid, metadata={"benchmark": "skillsbench-spa"}) for tid in TASK_IDS]

    # ---- running ---------------------------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run ONE SkillsBench task via OpenHands → SPA."""
        return self.run_batch([task], ctx, seed=seed).get(
            task.id, Rollout(task_id=task.id, error="no rollout produced")
        )

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run tasks via bench eval create with OpenHands agent routed through SPA.

        Each task runs in its own Docker container. The agent's LLM_BASE_URL
        points to SPA on the host (via Docker bridge IP). The CANDIDATE's 6 travel
        skills are injected via --skills-dir (BenchFlow strips the task's bundled
        skills and mounts the candidate dir at /skills instead).

        If SKILLSBENCH_SKILLS_DIR is set, that path is used as --skills-dir verbatim
        (resolved to absolute) and the candidate dir is ignored for skill injection.
        """
        if not tasks:
            return {}

        candidate_dir = Path(ctx).resolve()
        jobs_dir = self._jobs_dir(candidate_dir, seed)
        jobs_dir.mkdir(parents=True, exist_ok=True)
        _BENCH_CWD.mkdir(parents=True, exist_ok=True)

        # If a fixed skills dir is provided, use it directly; otherwise deploy a clean
        # copy of only the real skill sub-packages from the candidate dir.
        fixed_skills_dir = os.environ.get("SKILLSBENCH_SKILLS_DIR", "")
        if fixed_skills_dir:
            skills_root = Path(fixed_skills_dir).resolve()
            _tmp_skills = None
        else:
            # Deploy ONLY the real skill sub-packages (dirs with a SKILL.md): the
            # candidate dir accumulates optimizer scratch files; bench would inject those
            # as "skills" and corrupt the Dockerfile. COPY (not symlink) — bench
            # copytree's the skills dir and skips symlinked entries.
            _tmp_skills = Path(tempfile.mkdtemp(prefix="skillsbench_spa_skills_", dir=str(_BENCH_CWD)))
            skills_root = _tmp_skills
            for sub in sorted(candidate_dir.iterdir()):
                if sub.is_dir() and (sub / "SKILL.md").exists():
                    shutil.copytree(sub, skills_root / sub.name)

        try:
            env = spa_env.spa_env()
        except Exception as e:
            shutil.rmtree(skills_root, ignore_errors=True)
            return {t.id: Rollout(task_id=t.id, error=f"SPA credentials unavailable: {e}")
                    for t in tasks}

        model = env[spa_env.LLM_MODEL_VAR]
        llm_base_url = env[spa_env.LLM_BASE_URL_VAR]
        llm_api_key = env[spa_env.LLM_API_KEY_VAR]

        concurrency = min(len(tasks), int(os.environ.get("SKILLSBENCH_CONCURRENCY", "1")))

        cmd = [
            BENCH_BIN, "eval", "create",
            "--source-repo", SOURCE_REPO, "--source-path", SOURCE_PATH, "--source-ref", SOURCE_REF,
            "--agent", AGENT, "--model", model,
            "--sandbox", SANDBOX,
            "--concurrency", str(concurrency),
            "--jobs-dir", str(jobs_dir),
            "--skill-mode", "with-skill", "--skills-dir", str(skills_root),
            "--agent-env", f"LLM_API_KEY={llm_api_key}",
            "--agent-env", f"LLM_BASE_URL={llm_base_url}",
        ]

        for t in tasks:
            cmd += ["--include", t.id]

        per_task_s = int(os.environ.get("SKILLSBENCH_TASK_TIMEOUT", "1800"))
        waves = (len(tasks) + concurrency - 1) // max(concurrency, 1)
        timeout_s = per_task_s * max(waves, 1) + 600

        try:
            proc = subprocess.run(
                cmd, cwd=str(_BENCH_CWD), capture_output=True, text=True, timeout=timeout_s
            )
            launch_err = None
            rc = proc.returncode
            tail = (proc.stderr or proc.stdout or "")[-1500:]
        except subprocess.TimeoutExpired:
            launch_err = f"bench eval create timed out after {timeout_s}s"
            rc, tail = None, ""
        except Exception as e:
            launch_err = f"bench eval create failed to launch: {e}"
            rc, tail = None, ""
        finally:
            if _tmp_skills is not None:
                shutil.rmtree(_tmp_skills, ignore_errors=True)

        results: dict[str, Rollout] = {}
        for t in tasks:
            if launch_err is not None:
                results[t.id] = Rollout(task_id=t.id, error=launch_err,
                                        metadata={"jobs_dir": str(jobs_dir)})
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
                    metadata={"reward": float(reward), "ctrf": ctrf, "jobs_dir": str(jobs_dir)},
                )
        return results

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Binary SkillsBench reward + gold-SAFE feedback. Deterministic."""
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

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _jobs_root(candidate_dir: Path) -> Path:
        """Where BenchFlow jobs land for this eval.

        candidate_dir is the live candidate dir (<run>/candidates/<id>), so the run
        root is two levels up. Jobs go under <run>/bench_jobs/. Falls back to a local
        scratch dir for non-standard paths (e.g. cap-evolve check's temp copy).
        """
        try:
            if candidate_dir.parent.name == "candidates":
                return candidate_dir.parent.parent / "bench_jobs"
        except Exception:
            pass
        return Path(__file__).resolve().parents[1] / ".bench_runs" / "default"

    @classmethod
    def _jobs_dir(cls, candidate_dir: Path, seed: int) -> Path:
        """Unique jobs dir per candidate AND per seed/trial."""
        return cls._jobs_root(candidate_dir) / candidate_dir.name / f"seed{seed}"


# ---------------------------------------------------------------------------
# Verifier / transcript readers + gold-safe feedback
# ---------------------------------------------------------------------------


def _task_jobs_dir(batch_dir: Path, task_id: str) -> Path:
    """Find the per-task subtree within a batch jobs dir."""
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

    for rf in list(jobs_dir.rglob("result*.json")) + list(jobs_dir.rglob("*scored*.json")):
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
    """Best-effort: read the agent's native transcript."""
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

    failed = [t for t in tests if isinstance(t, dict) and str(t.get("status", "")).lower() in ("failed", "error")]
    if not failed:
        return (
            f"Task scored {reward:.3f} (not all verifier tests passed). No per-test "
            "CTRF breakdown available; inspect the agent transcript for details."
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
