"""Project adapter — optimize SkillsBench's SHARED office-document skills.

Wires cap-evolve to SkillsBench (https://github.com/benchflow-ai/skillsbench),
the first benchmark for how well agents USE skills. The capability under
optimization is the FOUR shared office-document Agent Skills (docx, pptx, xlsx,
pdf) that the benchmark hands its agent — improving them moves many tasks at once.

  * ``tasks``        -> the 10 SkillsBench task ids (no network; ids only).
  * ``run_target``   -> one ``bench eval run`` for ONE task: a ``claude-sonnet-4-6``
                        agent in a Docker sandbox, with the CANDIDATE'S four skills
                        injected verbatim at /skills via
                        ``--skill-mode with-skill --skills-dir <ctx>`` (BenchFlow
                        strips the task's own bundled skills). Gateway creds are
                        propagated into the sandbox with ``--agent-env``.
  * ``score``        -> SkillsBench's binary verifier reward in {0,1}; gold-SAFE,
                        SPECIFIC feedback = the FAILED test names + assertion
                        messages from the CTRF report (never the oracle/gold).
                        DETERMINISTIC: reads the recorded reward, never re-runs.
  * ``materialize``  -> writes ``{component: text}`` edits into the candidate dir,
                        namespaced per sub-skill ("<skill>/SKILL.md", ...). PURE.
  * ``live``         -> default: ``ctx`` == the candidate ``seed_capability`` dir,
                        which IS the ``--skills-dir`` deployed to every task.

The candidate dir (``seed_capability``) holds FOUR sub-packages; the skill-package
capability handlers walk every immediate sub-package (a framework extension — see
the report). ``cap-evolve check`` does NO live LLM call: ``tasks``/``score``/
``materialize`` are network-free, and the gateway env is resolved lazily (only on a
real ``run_target``).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Make sibling helper modules (anthropic_env.py) importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import anthropic_env

# --- benchmark constants ----------------------------------------------------
SOURCE_REPO = "benchflow-ai/skillsbench"
SOURCE_PATH = "tasks"
SOURCE_REF = "main"
AGENT = "claude"
# Agent-under-test model. Override with SKILLSBENCH_AGENT_MODEL (e.g. a cheaper
# claude-haiku-4-5 for the on-demand integration test); defaults to sonnet.
MODEL = os.environ.get("SKILLSBENCH_AGENT_MODEL") or "claude-sonnet-4-6"
SANDBOX = "docker"
BENCH_BIN = os.environ.get("SKILLSBENCH_BENCH_BIN") or str(Path.home() / ".local" / "bin" / "bench")

# The 10 tasks (ids = SkillsBench task names). tasks() is split-agnostic and
# network-free; the harness filters by the frozen split_ids.json.
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

# Where bench caches its dataset clone. We always invoke bench from this stable
# fixed dir so candidate evals reuse the ~1.1GB cache instead of re-cloning.
_BENCH_CWD = Path(os.environ.get("SKILLSBENCH_BENCH_CWD") or (Path(__file__).resolve().parents[2] / ".bench_cwd"))


class Adapter(CapabilityAdapter):

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return the 10 SkillsBench tasks for any split (stable, no network)."""
        return [Task(id=tid, input=tid, metadata={"benchmark": "skillsbench"}) for tid in TASK_IDS]

    # ---- running ---------------------------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run ONE SkillsBench task — a thin wrapper over ``run_batch``."""
        return self.run_batch([task], ctx, seed=seed).get(
            task.id, Rollout(task_id=task.id, error="no rollout produced")
        )

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run ALL ``tasks`` in ONE ``bench eval run`` call, in parallel.

        A sonnet agent runs each task in its own Docker container with the candidate
        skills injected at /skills; ``--concurrency`` lets bench run many at once, so a
        whole split evaluates in ~one task's wall-clock instead of the serial sum.

        Embeds each task's BenchFlow artifacts (verifier reward + CTRF + transcript)
        INTO its Rollout so the optimizer reads the full per-candidate trace from
        cap-evolve's own rollout JSON. A task with no result under the batch dir ->
        ``Rollout.error`` (infra). ``ctx`` is the live candidate dir == ``--skills-dir``.
        """
        if not tasks:
            return {}
        # bench runs from a DIFFERENT cwd (_BENCH_CWD), so every path handed to it must
        # be ABSOLUTE — the harness passes ctx as a relative candidate dir. The jobs dir
        # is UNIQUE per candidate AND per seed/trial so concurrent/repeated evals don't
        # collide and bench doesn't resume a populated dir.
        candidate_dir = Path(ctx).resolve()
        jobs_dir = self._jobs_dir(candidate_dir, seed)
        jobs_dir.mkdir(parents=True, exist_ok=True)
        _BENCH_CWD.mkdir(parents=True, exist_ok=True)

        # Deploy ONLY the real skill sub-packages ONCE (immediate child dirs with a
        # SKILL.md): the candidate dir is also the optimizer's workdir (scratch
        # INSTRUCTIONS.md/PROCESS.md/guidance/...), and bench would inject those as
        # "skills" and corrupt the Dockerfile. COPY (not symlink) — bench copytree's the
        # skills dir and SKIPS symlinked entries, so symlinks would deploy 0 files.
        skills_root = Path(tempfile.mkdtemp(prefix="skillsbench_skills_", dir=str(_BENCH_CWD)))
        for sub in sorted(candidate_dir.iterdir()):
            if sub.is_dir() and (sub / "SKILL.md").exists():
                shutil.copytree(sub, skills_root / sub.name)

        try:
            env = anthropic_env.gateway_env()
        except Exception as e:  # creds missing — infra error for every task
            shutil.rmtree(skills_root, ignore_errors=True)
            return {t.id: Rollout(task_id=t.id, error=f"gateway credentials unavailable: {e}")
                    for t in tasks}

        concurrency = min(len(tasks), int(os.environ.get("SKILLSBENCH_CONCURRENCY", "7")))
        cmd = [
            BENCH_BIN, "eval", "run",
            "--source-repo", SOURCE_REPO, "--source-path", SOURCE_PATH, "--source-ref", SOURCE_REF,
            "--agent", AGENT, "--model", MODEL,
            "--sandbox", SANDBOX,
            "--concurrency", str(concurrency),
            "--skill-mode", "with-skill", "--skills-dir", str(skills_root),
            "--jobs-dir", str(jobs_dir),
            "--agent-env", f"ANTHROPIC_BASE_URL={env['ANTHROPIC_BASE_URL']}",
            "--agent-env", f"ANTHROPIC_AUTH_TOKEN={env['ANTHROPIC_AUTH_TOKEN']}",
        ]
        for t in tasks:
            cmd += ["--include", t.id]

        # bench is verbose on stdout; the cap-evolve skills' stdout is a JSON contract,
        # so capture bench output. Scale the timeout with the batch size (a parallel
        # batch is ~one task long, but allow headroom when concurrency < len(tasks)).
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
            launch_err = f"bench eval run timed out after {timeout_s}s"
            rc, tail = None, ""
        except Exception as e:  # noqa: BLE001
            launch_err = f"bench eval run failed to launch: {e}"
            rc, tail = None, ""
        finally:
            shutil.rmtree(skills_root, ignore_errors=True)

        # Map EACH task's result out of the single batch jobs dir, keyed by task name.
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
                    cost_usd=0.0,  # gateway spend not metered here (honest: not double-counted)
                    tokens=0,
                    error=None,
                    metadata={"reward": float(reward), "ctrf": ctrf, "jobs_dir": str(jobs_dir)},
                )
        return results

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Binary SkillsBench reward + gold-SAFE, SPECIFIC feedback. Deterministic:
        reads the recorded reward/CTRF from ``rollout.metadata`` (never re-runs)."""
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

    # ---- candidate materialization (FOUR-skill-package aware) ------------

    def materialize(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """Write ``{component: text}`` edits into the candidate dir. PURE.

        Components are namespaced per sub-skill ("docx/SKILL.md",
        "pdf/references/forms.md", ...) since the candidate holds FOUR sub-packages.
        The default base behavior (write each component as a file under the candidate
        dir) already does exactly this, so we just delegate.
        """
        super().materialize(candidate_dir, edits)

    # ---- native trajectories (supplementary fallback) --------------------

    def trajectories(self, split: str, ctx=None):
        """The BenchFlow jobs dir for the most recent eval of ``split``.

        cap-evolve prefers its own per-candidate rollout JSON (which already embeds
        the transcript + CTRF we stashed in the Rollout); this is the verbatim
        full-artifact fallback (llm_trajectory.jsonl, verifier logs). Best-effort:
        without ``ctx`` we cannot locate the per-candidate run root, so return None
        and let cap-evolve fall back to its own rollout JSON (which has the trace)."""
        if ctx is None:
            return None
        ctx = Path(ctx)
        d = self._jobs_root(ctx) / ctx.name
        return d if d.is_dir() else None

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _jobs_root(skills_dir: Path) -> Path:
        """Where BenchFlow jobs land for this eval.

        ``ctx``/``skills_dir`` is the live candidate dir (``<run>/candidates/<id>``),
        so the run root is two levels up. Jobs go under ``<run>/bench_jobs/`` (a
        sibling of cap-evolve's own ``trajectories/`` so nothing collides). When the
        candidate isn't under a recognizable run root (e.g. ``cap-evolve check``'s
        temp copy), fall back to a local scratch dir."""
        try:
            if skills_dir.parent.name == "candidates":
                return skills_dir.parent.parent / "bench_jobs"
        except Exception:
            # Deliberate best-effort fallback: a nonstandard/temporary candidate path
            # (e.g. `cap-evolve check`'s temp copy) has no recognizable run root, so we
            # use the local scratch dir below rather than failing the eval.
            pass
        return Path(__file__).resolve().parents[2] / ".bench_runs" / "default"

    @classmethod
    def _jobs_dir(cls, candidate_dir: Path, seed: int) -> Path:
        """The batch jobs dir — UNIQUE per candidate AND per seed/trial.

        ``candidate_dir.name`` is the candidate id (``seed``, ``cand_0001``, …). bench
        treats a ``--jobs-dir`` that already holds a completed result as DONE and skips
        re-running; keying by candidate id (and seed) forces a fresh run per candidate
        and prevents concurrent/repeated evals from colliding. bench writes its own
        per-task subdirs under this batch dir."""
        return cls._jobs_root(candidate_dir) / candidate_dir.name / f"seed{seed}"


# ---------------------------------------------------------------------------
# Verifier / transcript readers + gold-safe feedback (module-level, pure)
# ---------------------------------------------------------------------------


def _task_jobs_dir(batch_dir: Path, task_id: str) -> Path:
    """The per-task subtree for ``task_id`` within a batch jobs dir.

    bench writes ``<batch>/<timestamp>/<task_id>__<hash>/...`` per task; scoping the
    verifier/transcript read to that leaf isolates one task's result from its
    batch-mates. Falls back to the whole batch dir if no leaf is found yet (the read
    helpers then report "no reward" -> infra error, as for a task bench never ran)."""
    if not batch_dir.is_dir():
        return batch_dir
    matches = sorted(d for d in batch_dir.rglob(f"{task_id}__*") if d.is_dir())
    # Most recent match wins (a retried task can have multiple); deterministic by name.
    return matches[-1] if matches else batch_dir


def _read_verifier(jobs_dir: Path) -> tuple[float, dict, bool]:
    """Read SkillsBench's verifier reward (0/1) and CTRF report from a jobs dir.

    BenchFlow writes the verifier reward to ``/logs/verifier/reward.txt`` and a CTRF
    JSON to ``/logs/verifier/ctrf.json`` per rollout; it also collects the reward into
    the per-task ``result.json`` / scored-trajectory under ``--jobs-dir``. We glob for
    these (layout varies by sandbox), preferring an explicit reward file/result.
    Returns (reward, ctrf_dict, found)."""
    ctrf: dict = {}
    for cf in jobs_dir.rglob("ctrf*.json"):
        try:
            ctrf = json.loads(cf.read_text(encoding="utf-8"))
            break
        except Exception:
            continue

    # 1) explicit reward.txt
    for rf in jobs_dir.rglob("reward.txt"):
        try:
            return float(rf.read_text(encoding="utf-8").strip() or "0"), ctrf, True
        except Exception:
            continue

    # 2) reward inside a result/scored-trajectory JSON
    for rf in list(jobs_dir.rglob("result*.json")) + list(jobs_dir.rglob("*scored*.json")):
        try:
            obj = json.loads(rf.read_text(encoding="utf-8"))
        except Exception:
            continue
        r = _extract_reward(obj)
        if r is not None:
            return float(r), ctrf, True

    # 3) derive from CTRF summary if present
    if ctrf:
        summary = (ctrf.get("results") or {}).get("summary") or {}
        tests = summary.get("tests")
        passed = summary.get("passed")
        if isinstance(tests, int) and tests > 0 and isinstance(passed, int):
            return (1.0 if passed == tests else 0.0), ctrf, True

    return 0.0, ctrf, False


def _extract_reward(obj):
    """Recursively find a 'reward' field (or score in {0,1}) in a result JSON."""
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
    """Best-effort: the agent's native transcript (llm_trajectory.jsonl), as a list
    of message dicts. Returns None when absent."""
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
    """Gold-SAFE, SPECIFIC learning signal.

    For a FAILING task, surface the FAILED test names + their assertion messages from
    the CTRF report (the agent's OWN output defect named by the test). Gold-SAFE: we
    never read the oracle/solve.sh/gold output — only the failing test name + its
    message. If a message is not safely usable we fall back to the test name alone.
    Deterministic on a fixed CTRF."""
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
            "CTRF breakdown was available; inspect ./trajectories/ for the agent transcript "
            "and the produced files to see which skill behavior was missing."
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
