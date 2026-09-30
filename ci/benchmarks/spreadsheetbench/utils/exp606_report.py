#!/usr/bin/env python3
"""exp #606 report: one row per downloaded run artifact, then paired comparisons between variants.

    gh run download <id> -D runs/<id>
    PYTHONPATH=core python3 exp606_report.py runs/<id> [runs/<id> ...] [--json]

Scores come from the artifact's metrics.jsonl (per-task test rewards, seed vs champion) and its
events (val, gate, optimizer cost), never from averaging rollout files. A run is marked invalid
when its optimizer was not only Claude Opus 5.5, when its reader block does not match its variant,
or when the rendered optimizer instructions do not contain that block.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
from pathlib import Path

from cap_evolve.stats import bootstrap_ci

WANT_MODEL = "claude-opus-5-5"
RESAMPLES = 2000


def _art(d: Path) -> Path:
    """`gh run download` nests the artifact one level down; accept either layout."""
    if (d / "metrics.jsonl").exists():
        return d
    subs = [s for s in d.iterdir() if s.is_dir() and (s / "metrics.jsonl").exists()]
    if len(subs) != 1:
        raise SystemExit(f"{d}: expected one artifact with metrics.jsonl, found {len(subs)}")
    return subs[0]


def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _events(d: Path) -> list[dict]:
    raw = d / "ui/data/runs_run_suite_file_path_events_jsonl.json"
    if raw.exists():
        rec = json.loads(raw.read_text(encoding="utf-8"))
        text = rec.get("text") or ""
        return [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
    return _jsonl(d / "events.jsonl")


def _variant(block: str) -> str:
    if not block.strip():
        return "C"
    if "You do not know which model" in block:
        return "R"
    if "**frontier**" in block:
        return "B"
    if "**strong**" in block:
        return "A"
    return "?"


def skill_shape(text: str) -> dict:
    low = text.lower()
    return {
        "chars": len(text),
        "numbered_rules": len(re.findall(r"(?m)^\s*\d+[.)]\s", text)),
        "bullets": len(re.findall(r"(?m)^\s*[-*]\s", text)),
        "code_examples": text.count("```") // 2,
        "worked_examples": len(re.findall(r"(?i)\bexample\b", text)),
        "grader_contract": "data_only" in low and "formula" in low and ("2 decimal" in low or "round" in low),
    }


def summarize(run: Path) -> dict:
    d = _art(Path(run))
    meta = json.loads((d / "runmeta.json").read_text()) if (d / "runmeta.json").exists() else {}
    rows = [r for r in _jsonl(d / "metrics.jsonl")
            if r.get("reward_baseline") is not None and r.get("reward_opt") is not None
            and not r.get("opt_infra")]
    per_task = {str(r.get("task") or r.get("task_id")): (float(r["reward_baseline"]), float(r["reward_opt"]))
                for r in rows}
    n = len(per_task)
    seed = sum(b for b, _ in per_task.values()) / n if n else None
    opt = sum(o for _, o in per_task.values()) / n if n else None
    deltas = [o - b for b, o in per_task.values()]

    ev = _events(d)
    val_seed = next((e.get("val") for e in ev if e.get("kind") in ("baseline_reused", "baseline")), None)
    steps = [e for e in ev if e.get("kind") == "step"]
    val_cand = [e.get("val") for e in steps]
    opt_usd = sum(float(e.get("opt_cost_usd") or 0) for e in steps)
    opt_min = sum(float(e.get("optimizer_seconds") or 0) for e in steps) / 60
    fin = next((e for e in ev if e.get("kind") == "finalize"), {})
    # the optimizer can exit non-zero (e.g. at its turn cap) after writing edits; the candidate is
    # still evaluated, so this is recorded, not treated as a failed run
    opt_errors = sum(1 for e in ev if e.get("kind") == "optimizer_error")

    block = (d / "reader_block.md").read_text(encoding="utf-8") if (d / "reader_block.md").exists() else None
    variant = _variant(block) if block is not None else "?"
    declared = meta.get("reader_variant")
    instr = sorted((d / "optimizer_instructions").glob("*.md")) if (d / "optimizer_instructions").is_dir() else []
    block_in_instructions = bool(instr) and all(
        (block.strip() in p.read_text(encoding="utf-8")) if block and block.strip()
        else ("THE READER" not in p.read_text(encoding="utf-8")) for p in instr)

    models_rec = json.loads((d / "optimizer_models.json").read_text()) if (d / "optimizer_models.json").exists() else {}
    models = sorted((models_rec.get("models") or {}).keys())

    cap = d / "optimized/optimized_capability"
    text = "".join((cap / f).read_text(encoding="utf-8") for f in ("prompt.md", "task_template.md") if (cap / f).exists())

    problems = []
    if len(models) != 1 or WANT_MODEL not in models[0]:
        problems.append(f"optimizer models {models}")
    if declared and declared != variant:
        problems.append(f"declared variant {declared} but reader block is {variant}")
    if block is None:
        problems.append("no reader_block.md")
    if not block_in_instructions:
        problems.append("reader block not found verbatim in the optimizer instructions")
    return {
        "run_id": str(meta.get("run_id") or Path(run).name), "variant": variant,
        "iterations": meta.get("iterations"), "sha": (meta.get("sha") or "")[:8],
        "n_tasks": n, "test_seed": seed, "test_opt": opt,
        "delta": (opt - seed) if n else None,
        "delta_ci": bootstrap_ci(deltas, resamples=RESAMPLES, seed=0) if n else None,
        "val_seed": val_seed, "val_cand": val_cand, "accepted": [bool(e.get("accept")) for e in steps],
        "best_id": fin.get("best_id"), "opt_usd": opt_usd, "opt_minutes": opt_min, "optimizer_errors": opt_errors,
        "models": models, "block_in_instructions": block_in_instructions,
        "skill_shape": skill_shape(text), "per_task": per_task,
        "valid": not problems, "problems": problems,
    }


def compare(a: list[dict], b: list[dict]) -> dict:
    """Mean per-task champion reward of variant a minus variant b, paired on shared tasks."""
    def mean_opt(runs):
        acc: dict[str, list[float]] = {}
        for r in runs:
            for t, (_, o) in r["per_task"].items():
                acc.setdefault(t, []).append(o)
        return {t: sum(v) / len(v) for t, v in acc.items()}
    ma, mb = mean_opt(a), mean_opt(b)
    common = sorted(set(ma) & set(mb))
    diffs = [ma[t] - mb[t] for t in common]
    return {"n_tasks": len(common), "diff": sum(diffs) / len(diffs) if diffs else None,
            "ci": bootstrap_ci(diffs, resamples=RESAMPLES, seed=0) if diffs else None,
            "runs_a": [r["run_id"] for r in a], "runs_b": [r["run_id"] for r in b]}


def _pct(x):
    return "—" if x is None else f"{100 * x:.1f}"


def _row(s: dict) -> str:
    lo, hi = s["delta_ci"] or (None, None)
    acc = "/".join("yes" if x else "no" for x in s["accepted"]) or "—"
    val = f"{_pct(s['val_seed'])} → {'/'.join(_pct(v) for v in s['val_cand']) or '—'}"
    sh = s["skill_shape"]
    delta = "—" if s["delta"] is None else f"{100 * s['delta']:+.1f}"
    return (f"| {s['variant']} | [{s['run_id']}](https://github.com/skillberry-ai/cap-evolve/actions/runs/{s['run_id']}) "
            f"| {s['iterations']} | {_pct(s['test_seed'])} | {_pct(s['test_opt'])} "
            f"| {delta} [{_pct(lo)}, {_pct(hi)}] | {val} | {acc} | {s['opt_usd']:.2f} | {s['opt_minutes']:.0f}{' (' + str(s['optimizer_errors']) + ' opt err)' if s['optimizer_errors'] else ''} "
            f"| {sh['chars']} / {sh['numbered_rules']} / {sh['code_examples']} / {'yes' if sh['grader_contract'] else 'no'} "
            f"| {','.join(s['models']) or '—'} | {'✅' if s['valid'] else '❌ ' + '; '.join(s['problems'])} |")


HEADER = ("| variant | run | iters | test seed | test opt | Δ [95% CI] | val seed → cand | accepted | opt $ | opt min "
          "| skill chars / rules / code ex. / grader contract | optimizer model | valid |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sums = [summarize(r) for r in a.runs]
    by: dict[str, list[dict]] = {}
    for s in sums:
        if s["valid"]:
            by.setdefault(s["variant"], []).append(s)
    comps = {f"{x}-{y}": compare(by[x], by[y]) for x, y in itertools.combinations(sorted(by), 2)}
    if a.json:
        print(json.dumps({"runs": [{k: v for k, v in s.items() if k != "per_task"} for s in sums],
                          "compare": comps}, indent=2))
        return
    print("Test scores are in points on the fixed 100-task subset (as saved, hard).\n")
    print(HEADER)
    for s in sums:
        print(_row(s))
    if comps:
        print("\n| comparison | runs | tasks | Δ points [95% CI, paired bootstrap] |\n|---|---|---|---|")
        for k, c in comps.items():
            lo, hi = c["ci"]
            print(f"| {k} | {len(c['runs_a'])} vs {len(c['runs_b'])} | {c['n_tasks']} "
                  f"| {100 * c['diff']:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] |")


if __name__ == "__main__":
    main()
