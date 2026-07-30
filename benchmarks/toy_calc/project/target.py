"""toy_calc's target runner — the ONE piece that is code, not config.

A deterministic zero-API stand-in agent. It computes the arithmetic correctly only
when the candidate prompt contains the ``[CALC]`` marker, so optimizing the prompt
provably raises the score with no model calls. Everything else about this benchmark
(dataset, scoring mode, splits, metric direction, protected paths) is declared in
``benchmark.yaml``.
"""

from __future__ import annotations

from pathlib import Path

_ALLOWED = set("0123456789 +-*")


def _safe_eval(expr: str) -> int:
    if not set(expr) <= _ALLOWED:  # arithmetic only
        raise ValueError(f"unsafe expr: {expr!r}")
    return int(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 (sandboxed)


def run(task, ctx, *, seed: int = 0):
    """Run the stand-in agent. ``seed`` is accepted per contract but unused: exact."""
    prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
    has_calc = "[CALC]" in prompt
    if not has_calc:
        # without the instruction the stand-in rambles and gets it wrong
        return {"output": f"I think {task.input} is roughly some number.",
                "trace": "prompt_had_calc=False"}
    try:
        out = str(_safe_eval(str(task.input)))
    except Exception as e:  # noqa: BLE001
        out = f"error: {e}"
    return {"output": out, "trace": "prompt_had_calc=True"}
