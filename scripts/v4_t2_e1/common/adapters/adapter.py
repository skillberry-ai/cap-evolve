#!/usr/bin/env python3
"""Harbor adapter for v4_t2_e1 — single-task, system-prompt-only cap-evolve
optimization of parsec v4.

Shared by all 21 per-task projects via a symlink chain
(project/adapters -> .capevolve/v4_t2_e1_common/adapters -> this file's own
directory). Since load_adapter() (core/cap_evolve/check.py) instantiates
Adapter() with zero constructor arguments, this adapter reads a required
TASK_ID environment variable — set by scripts/v4_t2_e1/run_one_task.py
immediately before each `cap-evolve run` invocation — to know which of the
21 tasks it is running.

Candidate delivery: system_prompt.py's get_agent_prompt() re-reads
config/prompts/*.md from disk on every request, keyed by mtime (see the
design doc) — so apply() just overwrites those files in the live
parsec-live clone. No process restart, no Harbor injection flag needed.
Because that clone is shared and long-lived, live() is overridden to
snapshot those files on entry and restore them in a finally, so a crash
mid-evaluation cannot leave a candidate's prompts serving indefinitely.

Note on PARSEC_LIVE_PROMPTS_DIR: this is read into an INSTANCE attribute
(self.live_prompts_dir) inside __init__, evaluated fresh every time an
Adapter is constructed — NOT a module-level constant computed once at
import time. A module-level constant would freeze the default path in at
first import, so a test (or a caller) that patches the env var AFTER this
module has already been imported would silently miss it — apply() would
keep writing to the real default directory instead of the caller's chosen
one. Reading it per-instance is what makes the env var actually override
the default at every construction, which is exactly what
TestAdapterApply relies on.

Cost/token telemetry: Harbor's own result.json never carries real cost data
for ParsecAgent (its agent_result.cost_usd is a hard null — the agent's real
LLM calls happen inside the external, already-running parsec-live process,
entirely outside Harbor's own metering loop). run_target() instead reads
parsec-live's own MetricsCollector log (one "usage runtime=..." line per
conversation turn, written unconditionally regardless of MLflow reachability)
and attributes lines to a trial by timestamp window. PARSEC_LIVE_LOG follows
the exact same per-instance, env-overridable pattern as PARSEC_LIVE_PROMPTS_DIR
above, for the same testability reason (self.live_log_path).
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

# This file is reached through a chain of symlinks (project/adapters ->
# v4_t2_e1_common/adapters -> scripts/v4_t2_e1/common/adapters). .resolve()
# fully follows every hop, landing on the real physical path regardless —
# so this always finds the actual repo root, not wherever the caller's
# --project happened to point.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from capevolve_harbor.results import build_feedback, parse_job_dir  # noqa: E402
from cap_evolve import CapabilityAdapter, Rollout, Score, Task  # noqa: E402

V4N = Path(os.environ.get("PARSEC_V4N", "/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16"))
TASKS_DIR = V4N / "_run" / "tasks"
JOBS_ROOT = V4N / "_run" / "jobs" / "v4_t2_e1"
TRIAL_TIMEOUT_SEC = 20 * 60

PROMPT_FILES = [
    "orchestrator.md",
    "shared_context.md",
    "aap2_agent.md",
    "babylon_agent.md",
    "cost_agent.md",
    "icinga_agent.md",
    "ocpv_agent.md",
    "security_agent.md",
]

#: Plausibility floor for a candidate's orchestrator.md. The real prompt is
#: ~11.7KB; the corrupted fixture that once reached the live clone (and was
#: then frozen into all 21 seed snapshots) was 21 bytes. Anything under this
#: is truncated or placeholder content, not a prompt worth serving.
MIN_ORCHESTRATOR_BYTES = 500

MCP_PORTS = {
    "PLATFORM_MCP_URL": 8086,
    "GITHUB_MCP_URL": 8087,
    "ICINGA_MCP_URL": 8088,
    "COST_MCP_URL": 8089,
    "CLOUD_MCP_URL": 8090,
}


_SEED_SEGMENT_RE = re.compile(r"^seed-(\d+)$")


def _path_sort_key(path: Path, root: Path) -> list[tuple[int, int, str]]:
    """Order ``path`` under ``root`` by segment, numerically where it is a number.

    Needed because run_target()'s layout is ``seed-<N>/<millis>/<harbor-ts>`` and
    plain string ordering gets the numeric segments wrong: ``"seed-10" <
    "seed-2"`` and ``"1789740999999" < "989740746891"``. Each segment becomes
    ``(0, <int>, "")`` when it is (or wraps) an integer and ``(1, 0, <text>)``
    otherwise, so numbers order numerically and sort before free text.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    key: list[tuple[int, int, str]] = []
    for part in parts:
        match = _SEED_SEGMENT_RE.match(part)
        if match:
            key.append((0, int(match.group(1)), ""))
        elif part.isdigit():
            key.append((0, int(part), ""))
        else:
            key.append((1, 0, part))
    return key


def _resolve_docker_host() -> str:
    out = subprocess.run(
        ["podman", "machine", "inspect", "podman-machine-default"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    data = json.loads(out.stdout)
    path = data[0]["ConnectionInfo"]["PodmanSocket"]["Path"]
    return f"unix://{path}"


# ParsecAgent's real LLM calls happen entirely inside the already-running,
# external parsec-live process (one POST /api/query per trial) — completely
# outside Harbor's own agent-invocation/metering loop. Harbor's result.json
# therefore never carries real cost/token data for this agent (its
# agent_result.cost_usd is a hard null, not a fallback zero). The real,
# authoritative numbers are already computed by parsec-live's own
# MetricsCollector (_run/parsec-live/src/metrics/collector.py) and logged —
# one line per conversation turn — regardless of whether MLflow is reachable.
# So run_target() reads that log directly instead of trusting
# TrialResult.cost_usd/.tokens (see the module docstring's testability note —
# same reasoning applies to self.live_log_path below).
_USAGE_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*"
    r"usage runtime=\S+ agent=\S+ "
    r"in=(?P<in_tok>\d+) out=(?P<out_tok>\d+) "
    r"cache_read=(?P<cache_read>\d+) cache_write=(?P<cache_write>\d+) "
    r"cache_hit=[\d.]+% tools=\d+ errors=\d+ "
    r"cost_usd=(?P<cost>[\d.]+) latency_ms=[\d.]+"
)

# Trials never overlap on the shared parsec-live process (harbor run
# --n-concurrent 1, plus live()'s own advisory lock), so a timestamp-window
# match against this adapter's own harbor subprocess is unambiguous. This
# buffer only absorbs clock-skew between when the line was logged and when
# this process's own before/after datetime.now() calls landed.
_USAGE_MATCH_BUFFER_SEC = 5.0


def _parse_usage_line(line: str) -> tuple[datetime, float, int] | None:
    """Parse one parsec-live MetricsCollector "usage runtime=..." log line.

    Returns ``(timestamp_utc, cost_usd, total_tokens)``, or None if ``line``
    doesn't match. The logged timestamp has no timezone — it is parsed as
    naive local time and converted to UTC using the CURRENT local UTC
    offset. A DST transition mid-sweep would make that offset wrong for
    lines logged on the other side of the transition, causing a false
    non-match (safe: falls back to 0 cost/tokens for that trial, loudly
    absent) rather than silently attributing cost to the wrong trial.
    """
    match = _USAGE_LINE_RE.match(line)
    if not match:
        return None
    naive_local = datetime.strptime(match["ts"], "%Y-%m-%d %H:%M:%S,%f")
    local_tz = datetime.now().astimezone().tzinfo
    ts_utc = naive_local.replace(tzinfo=local_tz).astimezone(timezone.utc)
    tokens = (
        int(match["in_tok"]) + int(match["out_tok"])
        + int(match["cache_read"]) + int(match["cache_write"])
    )
    return ts_utc, float(match["cost"]), tokens


def _read_parsec_usage_cost(
    log_path: Path, window_start: datetime, window_end: datetime,
) -> tuple[float, int]:
    """Sum real cost_usd/tokens for every usage line logged within
    ``[window_start, window_end]`` (plus _USAGE_MATCH_BUFFER_SEC on each
    side). Summing rather than taking a single match is deliberately
    defensive: today one Harbor trial produces exactly one usage line, but
    summing stays correct even if that 1:1 assumption ever breaks (e.g. a
    future retry-on-error inside one trial). Returns (0.0, 0) if the log
    doesn't exist — a missing log is infra noise, not a reason to fail the
    trial itself.
    """
    if not log_path.exists():
        return 0.0, 0
    lo = window_start - timedelta(seconds=_USAGE_MATCH_BUFFER_SEC)
    hi = window_end + timedelta(seconds=_USAGE_MATCH_BUFFER_SEC)
    total_cost = 0.0
    total_tokens = 0
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = _parse_usage_line(line)
        if parsed is None:
            continue
        ts_utc, cost_usd, tokens = parsed
        if lo <= ts_utc <= hi:
            total_cost += cost_usd
            total_tokens += tokens
    return total_cost, total_tokens


class Adapter(CapabilityAdapter):
    def __init__(self) -> None:
        task_id = os.environ.get("TASK_ID", "").strip()
        if not task_id:
            raise RuntimeError(
                "TASK_ID environment variable is required — this adapter is shared by "
                "all 21 v4_t2_e1 projects via a symlink and has no other way to know "
                "which task it is running. Set it before invoking `cap-evolve run`."
            )
        task_dir = TASKS_DIR / f"bench-v4-{task_id}"
        if not task_dir.exists():
            raise FileNotFoundError(f"no such bench-v4 task directory: {task_dir}")
        self.task_id = task_id
        self.task_dir = task_dir
        # Read fresh on every construction (see module docstring) so a caller —
        # e.g. a test — that sets PARSEC_LIVE_PROMPTS_DIR before constructing an
        # Adapter always gets it; a module-level constant would not.
        self.live_prompts_dir = Path(
            os.environ.get(
                "PARSEC_LIVE_PROMPTS_DIR",
                str(V4N / "_run" / "parsec-live" / "config" / "prompts"),
            )
        )
        # Same per-instance, env-overridable pattern as live_prompts_dir above,
        # and for the same reason: PARSEC_LIVE_LOG must be re-read fresh on
        # every construction so a test (or caller) that sets it before
        # constructing an Adapter always gets it.
        self.live_log_path = Path(
            os.environ.get("PARSEC_LIVE_LOG", str(V4N / "_run" / "logs" / "parsec-live.log"))
        )

    # ------------------------------------------------------------------
    # tasks() ignores the split argument: train == val == test == the one
    # task pinned via split_ids.json (see Task 2's capevolve.yaml).
    # ------------------------------------------------------------------
    def tasks(self, split: str) -> list[Task]:
        return [Task(id=self.task_id, metadata={"task_dir": str(self.task_dir)})]

    # ------------------------------------------------------------------
    # Candidate delivery: overwrite whichever *.md files the candidate
    # snapshot contains. The framework always hands apply() a FULL
    # directory snapshot (harness.py's run_dir.snapshot("seed", seed_dir)
    # copies the whole seed_capability tree as the run's first candidate),
    # so there is no partial-edit case to special-case here.
    # ------------------------------------------------------------------
    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        # Refuse before writing anything: a partial apply is worse than none,
        # because the live clone would then serve a mix of the candidate and
        # the previous occupant.
        orch = Path(candidate_dir) / "orchestrator.md"
        if orch.exists():
            size = orch.stat().st_size
            if size < MIN_ORCHESTRATOR_BYTES:
                raise ValueError(
                    f"refusing to apply candidate: orchestrator.md is {size} bytes "
                    f"(< {MIN_ORCHESTRATOR_BYTES}) — looks like truncated/placeholder "
                    f"content, not a real prompt ({orch})"
                )
        for name in PROMPT_FILES:
            src = Path(candidate_dir) / name
            if src.exists():
                (self.live_prompts_dir / name).write_text(
                    src.read_text(encoding="utf-8"), encoding="utf-8"
                )

    # ------------------------------------------------------------------
    # live() teardown. apply() mutates a SHARED, long-lived resource — the one
    # parsec-live clone every task's trials talk to — and the base
    # CapabilityAdapter.live() has an empty `finally`. So a crash anywhere
    # between apply() and the end of an evaluation (a VPN drop, a machine
    # sleep, a KeyboardInterrupt) left that candidate's prompts serving
    # indefinitely, and the NEXT run's "baseline" would silently be the
    # previous run's mutant. Snapshotting the 8 PROMPT_FILES on entry and
    # restoring them in a finally makes the mutation strictly scoped to the
    # one evaluation, which is exactly the contract the base class documents.
    #
    # Signature and yield value match the base class deliberately:
    # harness.py's _live() does `with adapter.live(candidate_dir) as ctx:` and
    # hands that ctx straight to run_target/run_trials.
    # ------------------------------------------------------------------
    @contextmanager
    def live(self, candidate_dir: Path):
        snapshot: dict[str, str | None] = {}
        for name in PROMPT_FILES:
            p = self.live_prompts_dir / name
            snapshot[name] = p.read_text(encoding="utf-8") if p.exists() else None
        try:
            self.apply(candidate_dir)
            yield candidate_dir
        finally:
            for name, content in snapshot.items():
                p = self.live_prompts_dir / name
                if content is None:
                    # Restore means restore: a prompt the candidate ADDED is not
                    # part of the pre-entry state and must not survive the run.
                    p.unlink(missing_ok=True)
                else:
                    p.write_text(content, encoding="utf-8")

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        task_dir = task.metadata["task_dir"]
        trial_dir = JOBS_ROOT / self.task_id / f"seed-{seed}" / str(int(time.time() * 1000))
        trial_dir.mkdir(parents=True, exist_ok=True)

        # The 5 MCP harness services are SHARED by all 21 tasks and keep serving
        # whatever dataset was PUT into them last. Per install_seeds.py's own
        # docstring, a reachable-but-unseeded service "serves whatever the
        # previous task left behind, which produces a plausible reward for the
        # wrong dataset" — so every trial re-installs its own task's seeds
        # first, exactly as the reference driver (run_full34.py's run_seed())
        # does. A seeding failure returns Rollout(error=...) rather than a 0.0
        # reward so the harness counts it as infra noise (missing data), not a
        # capability regression.
        try:
            seed_proc = subprocess.run(
                [sys.executable, "install_seeds.py", str(task_dir)],
                cwd=str(V4N), capture_output=True, text=True, timeout=120,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            # A hang past the timeout, or install_seeds.py/V4N not being there at
            # all, is the same class of event as a non-zero exit: infra, not
            # capability. Reported the same way rather than escaping as an
            # exception the caller would have to interpret.
            return Rollout(
                task_id=task.id,
                error=f"install_seeds could not be run: {type(exc).__name__}: {exc}",
                metadata={"trial_dir": str(trial_dir)},
            )
        if seed_proc.returncode != 0:
            return Rollout(
                task_id=task.id,
                error=f"install_seeds failed rc={seed_proc.returncode}: {seed_proc.stderr[-500:]}",
                metadata={"trial_dir": str(trial_dir)},
            )

        try:
            docker_host = _resolve_docker_host()
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, KeyError, IndexError) as exc:
            return Rollout(task_id=task.id, error=f"could not resolve docker host: {exc}")

        cfg_path = trial_dir / "harbor_config.json"
        cfg = {
            "jobs_dir": str(trial_dir),
            "agents": [{"name": "parsec_harbor_agent:ParsecAgent"}],
            "tasks": [{"path": task_dir}],
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        env = dict(os.environ)
        # `harbor run` (cwd=V4N) needs "." to import parsec_harbor_agent — but
        # PREPEND it, don't clobber: assigning outright discards whatever the
        # caller's environment, or the parent `cap-evolve run` process, already
        # put on PYTHONPATH.
        _existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            "." + os.pathsep + _existing_pythonpath if _existing_pythonpath else "."
        )
        env["PARSEC_URL"] = "http://127.0.0.1:8000"
        env["PARSEC_SIM_TRACE"] = str(V4N / "_run" / "logs" / "parsec-trace" / "trace.jsonl")
        env["DOCKER_HOST"] = docker_host
        for var, port in MCP_PORTS.items():
            env[var] = f"http://localhost:{port}/mcp/sse"

        log_path = trial_dir / "harbor_run.log"
        # Window bracketing this trial's one harbor subprocess invocation —
        # used below to attribute parsec-live's own usage-log line(s) to this
        # trial (see _read_parsec_usage_cost). Captured around the
        # subprocess.run call itself, not the whole method, so it stays tight
        # even though install_seeds.py and _resolve_docker_host() ran earlier.
        usage_window_start = datetime.now(timezone.utc)
        try:
            with open(log_path, "w", encoding="utf-8") as logf:
                proc = subprocess.run(
                    ["harbor", "run", "--config", str(cfg_path), "--n-concurrent", "1"],
                    cwd=str(V4N), env=env, stdout=logf, stderr=subprocess.STDOUT,
                    timeout=TRIAL_TIMEOUT_SEC,
                )
        except subprocess.TimeoutExpired:
            return Rollout(task_id=task.id, error=f"harbor run timed out after {TRIAL_TIMEOUT_SEC}s",
                           metadata={"trial_dir": str(trial_dir)})
        usage_window_end = datetime.now(timezone.utc)

        if proc.returncode != 0:
            return Rollout(task_id=task.id, error=f"harbor run exited {proc.returncode}",
                           metadata={"trial_dir": str(trial_dir)})

        # `harbor run -o <jobs_dir>` (here, trial_dir) writes its actual
        # output one level deeper, into a timestamp-named subdirectory it
        # creates itself (mirrors capevolve_harbor.run.harbor_run()'s own
        # `job_dirs = sorted(jobs_dir.iterdir()); job_dir = job_dirs[-1]`
        # resolution) — trial_dir itself only ever holds harbor_config.json/
        # harbor_run.log plus that one subdirectory, so filter to dirs.
        job_dirs = sorted(p for p in trial_dir.iterdir() if p.is_dir())
        if not job_dirs:
            return Rollout(task_id=task.id, error="harbor produced no job directory",
                           metadata={"trial_dir": str(trial_dir)})
        job_dir = job_dirs[-1]

        results = parse_job_dir(job_dir)
        if not results:
            return Rollout(task_id=task.id, error="harbor produced no parseable result",
                           metadata={"trial_dir": str(trial_dir)})
        trial_result = next(iter(results.values()))[0]

        # TrialResult (capevolve_harbor.results) has no .feedback attribute —
        # build_feedback() is the module's own accessor for a gold-safe summary.
        # Store it alongside the raw trial_result dict so score() need not
        # reconstruct a TrialResult from a plain dict to recompute it.
        feedback = build_feedback(trial_result)

        # trial_result.cost_usd/.tokens come from Harbor's own result.json and
        # are always null/zero for ParsecAgent — its real LLM calls happen
        # inside the external parsec-live process, entirely outside Harbor's
        # metering. The real numbers come from parsec-live's own usage log
        # instead (see _read_parsec_usage_cost's docstring).
        real_cost_usd, real_tokens = _read_parsec_usage_cost(
            self.live_log_path, usage_window_start, usage_window_end,
        )

        # trial_result.error is set only when the trial produced NO score at all
        # (image build failure, agent-setup timeout, agent timeout). That is
        # missing data, not a reward of 0.0 — propagating it is what lets the
        # harness exclude the trial from the mean instead of handing the
        # optimizer a phantom capability regression to "fix".
        return Rollout(
            task_id=task.id,
            output=feedback,
            error=trial_result.error,
            cost_usd=real_cost_usd,
            tokens=real_tokens,
            metadata={
                "trial_dir": str(trial_dir),
                "trial_result": trial_result.__dict__,
                "feedback": feedback,
                "parsec_usage_window": {
                    "start": usage_window_start.isoformat(),
                    "end": usage_window_end.isoformat(),
                },
            },
        )

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
            return Score(task_id=task.id, reward=0.0, feedback=rollout.error, n=1)
        meta = rollout.metadata or {}
        tr = meta.get("trial_result") or {}
        reward = float(tr.get("reward") or 0.0)
        feedback = str(meta.get("feedback") or tr.get("feedback") or "")
        return Score(task_id=task.id, reward=reward, feedback=feedback, n=1)

    def trajectories(self, split: str, ctx=None) -> Path | None:
        """The newest trial's harbor JOB directory, copied verbatim by cap-evolve
        into the optimizer's ./trajectories/.

        Returns the job dir — the one parse_job_dir() consumes, whose children
        are trial dirs carrying BOTH agent/ and verifier/ — not a single trial's
        agent/ subdirectory, which withholds the verifier output that explains
        the reward.

        "Newest" is resolved with a NUMERIC key, not a lexicographic one:
        run_target() lays trials out as <task>/seed-<N>/<millis>/<harbor-ts>/,
        and sorted() on those strings puts "seed-10" before "seed-2", so the
        tenth trial's trajectories would be silently dropped the moment
        num_trials exceeded 10.
        """
        task_root = JOBS_ROOT / self.task_id
        job_dirs = {
            Path(p).parents[1]  # .../agent -> trial dir -> job dir
            for p in glob.glob(str(task_root / "**" / "agent"), recursive=True)
        }
        if not job_dirs:
            return None
        return max(job_dirs, key=lambda d: _path_sort_key(d, task_root))
