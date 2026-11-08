#!/usr/bin/env python3
"""Regression gate for the AppWorld one-task integration test (scripts/itest.sh).

Given a finished cap-evolve run dir, assert what benchmarks/tau2/examples/airline/assert_itest.py asserts:
  1. the pipeline COMPLETED   — baseline.json + final.json + report.md exist;
  2. ONE iteration ran        — state.json spent.iterations >= 1;
  3. NON-REGRESSION           — final test reward >= baseline val reward;
and what is specific to this example:
  4. EPISODES RAN             — no rollout is an infrastructure error or a lint reject (a broken
                                agent model, key or AppWorld install shows up here, not as 0.0);
  5. GOLD-FREE               — no rollout record names a gold file, and AppWorld's failure ``trace``
                                is absent from the evaluation fields (metadata, score).

With 1 iteration x 1 trial the paired gate will often REJECT the single edit (final == baseline);
that is a legitimate PASS. Prints a JSON verdict; exits non-zero on fail.

Usage:  python assert_itest.py <run_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Gold-file names that no rollout record should contain anywhere.
GOLD_FILES = ("ground_truth", "answer.json", "private_data")
# AppWorld's TestTracker failure entries carry a gold-bearing ``trace``; evaluation_fields() drops it.
# cap-evolve's own Rollout.trace (the agent's steps) is a different, legitimate field, so the key
# is looked for only where AppWorld's evaluation output would land: the rollout metadata and the score.


def _reward(path: Path, split: str) -> float | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    node = data.get(split) or data
    r = node.get("reward")
    return float(r) if r is not None else None


def _rollouts(run: Path) -> list[dict]:
    out = []
    for p in sorted((run / "rollouts").rglob("*.json")) if (run / "rollouts").is_dir() else []:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(d, dict) and ("rollout" in d or "score" in d):
            d["_path"] = str(p)
            out.append(d)
    return out


def _text(d: dict) -> str:
    """Every string in the record, plus its JSON form, so markers in nested strings are visible."""
    parts = [json.dumps({k: v for k, v in d.items() if k != "_path"})]
    stack = [d]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            stack.extend(v for k, v in x.items() if k != "_path")
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, str):
            parts.append(x)
    return "\n".join(parts)


def _has_key(x, key: str) -> bool:
    if isinstance(x, dict):
        return key in x or any(_has_key(v, key) for v in x.values())
    if isinstance(x, list):
        return any(_has_key(v, key) for v in x)
    return False


def _gold_leak(d: dict) -> bool:
    if any(m in _text(d) for m in GOLD_FILES):
        return True
    eval_part = {"metadata": (d.get("rollout") or {}).get("metadata"), "score": d.get("score")}
    return _has_key(eval_part, "trace") or '"trace":' in _text(eval_part)


def check(run: Path) -> dict:
    checks: dict[str, object] = {}
    baseline_json, final_json, report_md = run / "baseline.json", run / "final.json", run / "report.md"
    checks["completed"] = baseline_json.exists() and final_json.exists() and report_md.exists()

    iterations = None
    state = run / "state.json"
    if state.exists():
        iterations = int((json.loads(state.read_text(encoding="utf-8")).get("spent") or {}).get("iterations") or 0)
    checks["iterations"] = iterations
    checks["iteration_ran"] = bool(iterations and iterations >= 1)

    base_val = _reward(baseline_json, "val")
    final_test = _reward(final_json, "test")
    checks["baseline_val_reward"] = base_val
    checks["final_test_reward"] = final_test
    checks["no_regression"] = (base_val is not None and final_test is not None
                               and final_test + 1e-9 >= base_val)

    rolls = _rollouts(run)
    bad = []
    for d in rolls:
        r = d.get("rollout") or {}
        meta = r.get("metadata") or {}
        if r.get("error") or meta.get("infra_error") or meta.get("lint_reject"):
            bad.append({"file": d["_path"], "error": (r.get("error") or meta.get("infra_error") or "lint_reject")[:200]})
    checks["rollouts"] = len(rolls)
    checks["episode_failures"] = bad[:5]
    checks["episodes_ran"] = bool(rolls) and not bad

    leaks = [d["_path"] for d in rolls if _gold_leak(d)]
    checks["gold_markers_in_rollouts"] = leaks[:5]
    checks["gold_free"] = not leaks

    ok = bool(checks["completed"] and checks["iteration_ran"] and checks["no_regression"]
              and checks["episodes_ran"] and checks["gold_free"])
    return {"ok": ok, "suite": "appworld-1task", "run_dir": str(run), "checks": checks}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: assert_itest.py <run_dir>", file=sys.stderr)
        return 2
    verdict = check(Path(sys.argv[1]))
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
