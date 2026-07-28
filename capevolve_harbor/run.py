"""Subprocess wrapper for ``harbor run`` with signal forwarding and timeout."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HarborRunResult:
    """Outcome of a ``harbor run`` invocation."""

    job_dir: Path | None = None
    returncode: int = -1
    stderr_tail: str = ""
    elapsed_seconds: float = 0.0
    error: str | None = None


def find_harbor_bin() -> str:
    """Locate the ``harbor`` CLI binary.

    Checks ``HARBOR_BIN`` env var first, then falls back to PATH lookup.
    """
    from_env = os.environ.get("HARBOR_BIN")
    if from_env:
        return from_env
    found = shutil.which("harbor")
    if found:
        return found
    raise FileNotFoundError(
        "harbor CLI not found. Install it with: uv tool install harbor"
    )


def harbor_run(
    dataset_path: Path | None = None,
    *,
    dataset: str | None = None,
    agent: str = "claude-code",
    model: str,
    parallel: int = 1,
    timeout: int = 3600,
    harbor_bin: str | None = None,
    extra_flags: list[str] | None = None,
    jobs_dir: Path | None = None,
    env: dict[str, str] | None = None,
    include_tasks: list[str] | None = None,
    agent_env: dict[str, str] | None = None,
) -> HarborRunResult:
    """Run a Harbor job against a local or registry dataset.

    Use ``dataset_path`` (``-p``) for a local dataset directory, or
    ``dataset`` (``-d``) for a Harbor registry dataset name (e.g.
    ``swe-bench/swe-bench-verified``). Exactly one must be provided.

    ``include_tasks`` filters to specific task names (``-i`` flags).
    ``agent_env`` passes env vars to the agent (``--ae KEY=VALUE`` flags).
    """
    bin_path = harbor_bin or find_harbor_bin()

    cmd = [bin_path, "run"]

    if dataset_path:
        cmd += ["-p", str(dataset_path)]
    elif dataset:
        cmd += ["-d", str(dataset)]
    else:
        raise ValueError("Either dataset_path (-p) or dataset (-d) is required")

    cmd += ["-a", str(agent), "-m", str(model)]

    if parallel > 1:
        cmd += ["-n", str(parallel)]

    if jobs_dir:
        cmd += ["-o", str(jobs_dir)]

    if include_tasks:
        for task_name in include_tasks:
            cmd += ["-i", task_name]

    if agent_env:
        for key, value in agent_env.items():
            cmd += ["--ae", f"{key}={value}"]

    cmd += ["-y"]

    if extra_flags:
        cmd += extra_flags

    run_env = {**os.environ, **(env or {})}

    t0 = time.monotonic()
    result = HarborRunResult()

    try:
        proc = subprocess.Popen(
            cmd,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        _forward_signals(proc)

        stdout, stderr = proc.communicate(timeout=timeout)
        result.returncode = proc.returncode
        result.elapsed_seconds = time.monotonic() - t0
        result.stderr_tail = (stderr or b"").decode("utf-8", errors="replace")[-2000:]

        if proc.returncode != 0:
            result.error = (
                f"harbor run exited with code {proc.returncode}: "
                f"{result.stderr_tail[:500]}"
            )

    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        result.elapsed_seconds = time.monotonic() - t0
        result.error = f"harbor run timed out after {timeout}s"
        result.returncode = -9

    except FileNotFoundError:
        result.error = f"harbor binary not found at {bin_path}"
        result.elapsed_seconds = time.monotonic() - t0

    except Exception as e:
        result.elapsed_seconds = time.monotonic() - t0
        result.error = f"harbor run failed: {e}"

    if jobs_dir and jobs_dir.is_dir():
        job_dirs = sorted(jobs_dir.iterdir())
        if job_dirs:
            result.job_dir = job_dirs[-1]

    return result


def _forward_signals(proc: subprocess.Popen) -> None:
    """Set up signal forwarding so SIGINT/SIGTERM reach the subprocess."""
    original_handlers = {}

    def _handler(sig, _frame):
        try:
            proc.send_signal(sig)
        except ProcessLookupError:
            pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            original_handlers[sig] = signal.signal(sig, _handler)
        except (OSError, ValueError):
            pass
