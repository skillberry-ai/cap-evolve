"""Optimizer subprocess plumbing — the seam between the framework and an agent CLI.

Split out of ``harness.py`` (#115). Everything about spawning the external optimizer,
reading its self-reported cost off stdout, and turning a non-zero exit into an
actionable message lives here. It knows nothing about splits, candidates or gates,
which is exactly why it is its own module: nothing else in the engine should have to
care how an agent CLI is invoked.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

# An optimizer mutates ``workdir`` in place. It MAY return a dict reporting its own
# cost, e.g. ``{"cost_usd": 0.42, "tokens": 1234}`` (or ``None`` when unknown) so the
# loop can count optimizer spend against ``max_usd``. Older optimizers returning
# ``None`` keep working — cost simply stays unmeasured for them.
OptimizerFn = Callable[[Path, str], "dict | None"]


def _parse_optimizer_cost(stdout: str) -> dict | None:
    """Pull ``{"cost_usd","tokens"}`` from a ``run-optimizer`` stdout payload.

    ``run-optimizer`` prints a single JSON object whose ``cost`` field is
    ``{"total_cost_usd": <float|None>, "tokens": <int|None>}`` (only when invoked
    with ``--json`` against a CLI that emits structured output). We read the last
    JSON line that carries a ``cost`` block. Returns ``None`` when no cost is
    present so callers can leave optimizer spend unmeasured.
    """
    if not stdout or not stdout.strip():
        return None
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict) and isinstance(obj.get("cost"), dict):
            c = obj["cost"]
            usd = c.get("total_cost_usd")
            tokens = c.get("tokens")
            if usd is None and tokens is None:
                return None
            return {"cost_usd": float(usd or 0.0), "tokens": int(tokens or 0)}
    return None


# ---- optimizer plumbing ---------------------------------------------------

def optimizer_from_command(cmd_template: list[str]) -> OptimizerFn:
    """Build an OptimizerFn that shells out to a skill's run.py.

    ``cmd_template`` is a list with ``{workdir}`` and ``{prompt}`` placeholders,
    e.g. ``["python", ".../optimizers/run-optimizer/scripts/run.py", "--name",
    "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"]``. The subprocess
    edits files in workdir.
    """
    def _run(workdir: Path, instructions: str) -> dict | None:
        prompt_path = workdir / "INSTRUCTIONS.md"
        prompt_path.write_text(instructions, encoding="utf-8")
        cmd = [c.format(workdir=str(workdir), prompt=str(prompt_path)) for c in cmd_template]
        env = dict(os.environ)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            err = RuntimeError(
                f"optimizer failed ({proc.returncode}): {_optimizer_failure_detail(proc)}")
            # run-optimizer prints its cost payload *before* returning its own exit
            # code, which mirrors the underlying CLI's (e.g. non-zero on hitting
            # --max-budget-usd though the CLI still reports real total_cost_usd) —
            # attach whatever cost it already computed so the caller can still
            # count real spend against the budget instead of discarding it.
            err.cost = _parse_optimizer_cost(proc.stdout)  # type: ignore[attr-defined]
            raise err
        # Capture optimizer spend (cost_usd/tokens) from run-optimizer's JSON payload
        # so it counts against the budget and shows in the dashboard. Returns None
        # when the agent CLI emitted no structured cost (spend stays unmeasured).
        return _parse_optimizer_cost(proc.stdout)
    return _run


def _optimizer_failure_detail(proc: "subprocess.CompletedProcess") -> str:
    """Best-effort human-readable reason a failed optimizer subprocess gives.

    The optimizer runner (``run-optimizer``) reports the underlying agent CLI's
    real output as a JSON object on **stdout** (``stderr_tail``/``stdout_tail``),
    while its own stderr is usually empty. Prefer that detail so the
    ``optimizer_error`` event (and the dashboard) explains *why* it failed
    instead of an empty ``failed (1):``.
    """
    detail = (proc.stderr or "").strip()
    out = (proc.stdout or "").strip()
    if out:
        try:
            import json as _json
            info = _json.loads(out.splitlines()[-1])
            tail = str(info.get("stderr_tail") or info.get("stdout_tail") or "").strip()
            if tail:
                detail = f"{detail} {tail}".strip() if detail else tail
            elif not detail:
                detail = out[-2000:]
        except Exception:  # noqa: BLE001 — stdout wasn't the runner's JSON
            if not detail:
                detail = out[-2000:]
    return (detail or "no output from optimizer")[:2000]
