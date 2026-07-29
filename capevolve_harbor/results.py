"""Parse Harbor job directories and map results to cap-evolve types."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrialResult:
    """One Harbor trial's outcome, parsed from the job directory."""

    task_id: str
    reward: float = 0.0
    reward_json: dict = field(default_factory=dict)
    trajectory: Any = None
    cost_usd: float = 0.0
    tokens: int = 0
    verifier_stdout: str = ""
    verifier_stderr: str = ""
    error: str | None = None


def parse_job_dir(
    job_dir: Path,
    task_ids: list[str] | None = None,
) -> dict[str, list[TrialResult]]:
    """Walk a Harbor job directory and extract per-trial results.

    Harbor job directory structure::

        <job-dir>/
            config.json
            result.json
            <trial-name>/
                config.json
                result.json
                agent/
                    trajectory.json
                    recording.cast
                verifier/
                    reward.txt
                    reward.json  (optional)
                    test-stdout.txt
                    test-stderr.txt

    Returns ``{task_id: [TrialResult, ...]}``.
    """
    results: dict[str, list[TrialResult]] = {}
    job_dir = Path(job_dir)

    if not job_dir.is_dir():
        return results

    for trial_dir in sorted(job_dir.iterdir()):
        if not trial_dir.is_dir():
            continue

        task_id = _extract_task_id(trial_dir)
        if task_ids and task_id not in task_ids:
            continue

        tr = _parse_trial(trial_dir, task_id)
        results.setdefault(task_id, []).append(tr)

    return results


def _extract_task_id(trial_dir: Path) -> str:
    """Extract the task ID from a trial directory.

    Tries trial config.json first, falls back to the directory name.
    """
    config_path = trial_dir / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            task_name = cfg.get("task", {}).get("name") or cfg.get("task_name")
            if task_name:
                return str(task_name)
        except (json.JSONDecodeError, KeyError):
            pass
    return trial_dir.name


def _parse_trial(trial_dir: Path, task_id: str) -> TrialResult:
    """Parse a single trial directory into a TrialResult."""
    tr = TrialResult(task_id=task_id)

    verifier_dir = trial_dir / "verifier"
    if verifier_dir.is_dir():
        tr.reward, tr.reward_json = _read_reward(verifier_dir)
        tr.verifier_stdout = _read_text(verifier_dir / "test-stdout.txt")
        tr.verifier_stderr = _read_text(verifier_dir / "test-stderr.txt")

    agent_dir = trial_dir / "agent"
    if agent_dir.is_dir():
        tr.trajectory = _read_trajectory(agent_dir)

    result_path = trial_dir / "result.json"
    if result_path.exists():
        tr.cost_usd, tr.tokens = _extract_cost_tokens(result_path)

    return tr


def _read_reward(verifier_dir: Path) -> tuple[float, dict]:
    """Read reward from verifier output.

    Tries reward.json first (``"reward"`` key). Falls back to reward.txt
    only when reward.json is absent or unparseable — a legitimate 0.0 in
    reward.json is honoured as-is.
    """
    reward_json: dict = {}

    rj_path = verifier_dir / "reward.json"
    if rj_path.exists():
        try:
            reward_json = json.loads(rj_path.read_text(encoding="utf-8"))
            if "reward" in reward_json:
                return float(reward_json["reward"]), reward_json
        except (json.JSONDecodeError, ValueError):
            pass

    rt_path = verifier_dir / "reward.txt"
    if rt_path.exists():
        try:
            return float(rt_path.read_text(encoding="utf-8").strip()), reward_json
        except ValueError:
            pass

    return 0.0, reward_json


def _read_trajectory(agent_dir: Path) -> Any:
    """Read the agent trajectory from the agent directory."""
    traj_path = agent_dir / "trajectory.json"
    if traj_path.exists():
        try:
            return json.loads(traj_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return None


def _extract_cost_tokens(result_path: Path) -> tuple[float, int]:
    """Extract cost and token count from a trial result.json."""
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        cost = float(data.get("cost_usd", 0) or data.get("cost", 0) or 0)
        tokens = int(
            data.get("tokens", 0)
            or data.get("total_tokens", 0)
            or data.get("input_tokens", 0) + data.get("output_tokens", 0)
            or 0
        )
        return cost, tokens
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0.0, 0


def _read_text(path: Path, max_chars: int = 5000) -> str:
    """Read a text file, truncating to max_chars."""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:] if len(text) > max_chars else text
    except OSError:
        return ""


def build_feedback(tr: TrialResult) -> str:
    """Build gold-safe feedback from a TrialResult."""
    parts: list[str] = []

    if tr.reward >= 1.0:
        parts.append("Task fully solved (reward 1.0).")
    elif tr.reward > 0.0:
        parts.append(f"Partial success (reward {tr.reward:.3f}).")
    else:
        parts.append("Task not solved (reward 0.0).")

    if tr.reward_json:
        metrics = {k: v for k, v in tr.reward_json.items() if k != "reward"}
        if metrics:
            metric_strs = [f"{k}={v}" for k, v in metrics.items()]
            parts.append(f"Metrics: {', '.join(metric_strs)}.")

    stdout = tr.verifier_stdout.strip()
    if stdout and len(stdout) < 500:
        parts.append(f"Verifier: {stdout}")

    if tr.error:
        parts.append(f"Error: {tr.error}")

    return " ".join(parts)
