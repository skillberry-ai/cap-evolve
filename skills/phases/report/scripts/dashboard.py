"""Build a single-file dashboard.html from a run dir.

Reconstructs a compact run JSON (KPIs, per-iteration scores, per-task rewards,
accept/reject status, pass^k/pass@k) from the run dir's baseline.json, final.json,
events.jsonl, and the val rollouts, then inlines it into the dashboard template
(ECharts, no fetch → opens offline from file://).
"""

from __future__ import annotations

import json
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "dashboard_template.html"


def _split_result_for_tag(run_dir: RunDir, tag: str):
    """Rebuild a candidate's val SplitResult from its persisted rollouts.

    Thin wrapper over the canonical core helper so the dashboard and the loop
    always reconstruct scores the same way.
    """
    return harness.split_result_from_rollouts(run_dir, tag, "val")


def build_run_json(run_dir: RunDir) -> dict:
    root = run_dir.root
    baseline = json.loads((root / "baseline.json").read_text()) if (root / "baseline.json").exists() else {}
    final = json.loads((root / "final.json").read_text()) if (root / "final.json").exists() else {}
    events = []
    if run_dir.events_path.exists():
        for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))

    base_val = (baseline.get("val") or {})
    tasks = [pt["task_id"] for pt in base_val.get("per_task", [])]

    def iter_entry(tag, status, iter_idx):
        sr = _split_result_for_tag(run_dir, tag)
        d = sr.to_dict() if sr else {"reward": None, "pass_k": {}, "pass_at_k": {}, "per_task": []}
        return {
            "iter": iter_idx,
            "candidate_id": tag,
            "status": status,
            "score": d["reward"],
            "pass_hat_k": (d.get("pass_k") or {}).get("2"),
            "pass_at_k": (d.get("pass_at_k") or {}).get("2"),
            "per_task_reward": {pt["task_id"]: pt["reward"] for pt in d.get("per_task", [])},
        }

    iterations = [iter_entry("seed", "baseline", 0)]
    best = base_val.get("reward") or 0.0
    i = 1
    for ev in events:
        if ev.get("kind") == "step":
            status = "accepted" if ev.get("accept") else "rejected"
            entry = iter_entry(ev.get("candidate"), status, i)
            if entry["score"] is None:
                entry["score"] = ev.get("val")
            best = max(best, entry["score"] or 0.0)
            entry["best_so_far"] = best
            # per-iteration cost/time/tokens from the step event
            entry["optimizer_seconds"] = ev.get("optimizer_seconds")
            entry["runner_seconds"] = ev.get("runner_seconds")
            entry["cost_usd"] = ev.get("cost_usd")
            entry["tokens"] = ev.get("tokens")
            iterations.append(entry)
            i += 1
    iterations[0]["best_so_far"] = base_val.get("reward") or 0.0

    best_val = max((it["score"] or 0.0) for it in iterations)
    test = (final.get("test") or {})
    try:
        sealed = run_dir.read_splits().test_used
    except Exception:
        sealed = bool(final)

    sp = run_dir.spent
    metrics = {
        "runner": {"cost_usd": round(sp.usd, 4), "tokens": sp.runner_tokens,
                   "seconds": round(sp.runner_seconds, 1)},
        "optimizer": {"seconds": round(sp.optimizer_seconds, 1)},
        "total_seconds": round(sp.runner_seconds + sp.optimizer_seconds, 1),
        "metric_calls": sp.metric_calls,
    }

    return {
        "meta": {"run_id": root.name, "test_sealed": sealed},
        "kpis": {
            "baseline": base_val.get("reward"),
            "val": best_val,
            "test": test.get("reward"),
            "best": best_val,
        },
        "metrics": metrics,
        "tasks": tasks,
        "iterations": iterations,
    }


def write_dashboard(run_dir: RunDir) -> Path:
    run_json = build_run_json(run_dir)
    tmpl = TEMPLATE.read_text(encoding="utf-8")
    # embed as a JSON data-island; escape </script> defensively
    data = json.dumps(run_json).replace("</", "<\\/")
    html = tmpl.replace("__RUN_DATA__", data)
    out = run_dir.root / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out
