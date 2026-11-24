#!/usr/bin/env python3
"""Assemble a benchmark run's standard folder: what one run produced, in a fixed layout.

    run_folder.py <out_dir> <dest> [--project <dir>] [--run-dir <dir>] [--tier-dir <dir>]
                  [--name <run_id>__<tier>-<bench>] [--repo <skillberry-runs repo>] [--has-ui]

  out_dir   the leg's output dir (CI: ci/benchmarks/.work/suite_<tier>_<bench>): runmeta.json,
            metrics.jsonl, steps.jsonl, report.md, optimized/
  dest      the folder to create, e.g. <stage>/ci_runs/<run_id>__<tier>-<bench>
  --project the cap-evolve project dir (.capevolve/project): capevolve.yaml, inputs/split_ids.json
  --run-dir the run dir (.capevolve/run_suite): final.json
  --tier-dir ci/benchmarks/<bench>/<tier>: its overrides.env, if any, goes into recipe/
  --repo    the skillberry-runs repo the folder is published in (for the README's links)
  --has-ui  the run's Open UI data is published next to it (ci_ui/<name>/)
  --provenance  how the folder came to be (default: published by its CI job)

Layout (published to skillberry-runs/<repo>/ci_runs/<name>/ by publish_results.sh; a run
published by hand uses the same layout, see ci/benchmarks/PUBLISHING.md):

  README.md                 generated: the run's settings, results, links, files, how to re-run
  report.md                 the run's metrics report (the same text as its PR comment)
  runmeta.json              how the run was launched (models, tier, iterations, trials, commit, ...)
  metrics.jsonl             one row per task: baseline vs optimized reward
  steps.jsonl               one row per iteration: cost and time
  final.json                the sealed test result (when the run got that far)
  capability.diff           the optimized capability vs the seed
  optimized_capability/     the optimized capability itself (no __pycache__)
  recipe/                   capevolve.yaml, split_ids.json, the tier's overrides.env
  backup.json               where the raw run data is: its staging area, or the runner (when backup_run.sh kept it)

SkillsBench skills are Anthropic-licensed, so for skillsbench only a diffstat is kept
(capability.diffstat.txt), as run_suite.sh already does. Anything over MAX_BYTES is left out,
and the README says so. Raw run data (traces, candidates, logs) is NOT here: the run's
"Open UI" data covers browsing it. When the dispatch asked for it, the full run dir is kept, packed,
in a staging area (or on the runner, when staging failed) as a capture source for
docs/FULL_BACKUP.md (backup_run.sh; backup.json and the README say where).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record import rollup  # noqa: E402  (the same rollup as the dashboard row)

MAX_BYTES = 20 * 1024 * 1024
DASHBOARD = "https://skillberry-runs.github.io/dashboard"
CAP_EVOLVE = "https://github.com/skillberry-ai/cap-evolve"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
PROVENANCE_CI = "published automatically by its CI job (`ci/benchmarks/lib/publish_results.sh`)"

FILES = [  # (path, description); listed in the README only if present
    ("report.md", "the run's metrics report (also its PR comment)"),
    ("runmeta.json", "how the run was launched: models, tier, iterations, trials, commit"),
    ("metrics.jsonl", "one row per task: baseline vs optimized reward"),
    ("steps.jsonl", "one row per iteration: cost and time"),
    ("final.json", "the sealed test result"),
    ("capability.diff", "the optimized capability vs the seed"),
    ("capability.diffstat.txt", "which files of the capability changed (content not published: licensed)"),
    ("optimized_capability/", "the optimized capability"),
    ("recipe/capevolve.yaml", "the run's cap-evolve spec"),
    ("recipe/split_ids.json", "the train / val / test task ids"),
    ("recipe/overrides.env", "the tier's committed overrides"),
    ("backup.json", "where the run's raw data archive is (backup_run.sh)"),
]


def _size(p: Path) -> int:
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _put(src: Path, dst: Path, skipped: list[str], rel: str) -> None:
    if not src.exists():
        return
    if _size(src) > MAX_BYTES:
        skipped.append(f"{rel} ({_size(src) / 1e6:.0f} MB, over the {MAX_BYTES // 2**20} MB limit)")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=IGNORE)
    else:
        shutil.copy2(src, dst)


def _jsonl(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fmt(x, d=3) -> str:
    return f"{x:.{d}f}" if isinstance(x, (int, float)) and not isinstance(x, bool) else "—"


def readme(meta: dict, dest: Path, name: str, repo: str | None, has_ui: bool, skipped: list[str],
           provenance: str = PROVENANCE_CI) -> str:
    bench, tier, run_id = meta.get("bench", "?"), meta.get("tier", "?"), meta.get("run_id", "?")
    sha = meta.get("sha") or ""
    L = [f"# {tier} / {bench} — run {run_id}", ""]
    L.append(f"A cap-evolve benchmark run, {provenance}. Its row is on the "
             f"[benchmark-runs dashboard]({DASHBOARD}/).")
    L.append("")
    if tier == "canary":
        L += ["> **Pipeline check only.** A `canary` run exists to exercise the CI path (1 task, 1 trial, "
              "1 iteration); its numbers mean nothing.", ""]
    elif tier == "pilot":
        L += ["> **Pilot run:** a cost/runtime measurement rig; its rewards are not comparable to anything.", ""]

    links = []
    if meta.get("run_url"):
        links.append(f"[Actions run]({meta['run_url']})")
    if meta.get("pr"):
        links.append(f"[PR #{meta['pr']}]({CAP_EVOLVE}/pull/{meta['pr']})")
    if sha:
        links.append(f"[commit `{sha[:9]}`]({CAP_EVOLVE}/tree/{sha})")
    if has_ui and repo:
        data = f"{DASHBOARD}/{repo}/ci_ui/{name}"
        links.append(f"[Open UI]({DASHBOARD}/viewer/index.html?dataBase={urllib.parse.quote(data, safe='')}#/runs/run_suite)")
    if links:
        L += [" · ".join(links), ""]

    L += ["## Run", "", "| | |", "|---|---|"]
    rows = [
        ("Benchmark / tier", f"`{bench}` / `{tier}`"),
        ("Source", meta.get("source")),
        ("Date (UTC)", meta.get("date")),
        ("Conclusion", meta.get("conclusion")),
        ("Agent model", f"`{meta['agent_model']}`" if meta.get("agent_model") else None),
        ("Optimizer model", f"`{meta['optimizer_model']}`" if meta.get("optimizer_model") else None),
        ("Algorithm", f"`{meta['algorithm']}`" if meta.get("algorithm") else None),
        ("Iterations / trials", f"{meta.get('iterations', '—')} / {meta.get('trials', '—')}"),
        ("Gate (k·SE)", meta.get("gate_k_se")),
        ("Warm-started seed", "yes" if meta.get("warm_seed") else None),
        ("Reward metric", meta.get("reward_metric") or None),
    ]
    L += [f"| {k} | {v} |" for k, v in rows if v not in (None, "")]
    L.append("")

    suite = rollup(_jsonl(dest / "metrics.jsonl"), _jsonl(dest / "steps.jsonl")) \
        if meta.get("conclusion") == "success" else None
    final = json.loads((dest / "final.json").read_text(encoding="utf-8")) if (dest / "final.json").is_file() else None
    L += ["## Results", ""]
    if suite:
        tasks = f"{suite['n']} task" + ("" if suite["n"] == 1 else "s")
        cov = f" ({suite['n_scored']} of {tasks} scored)" if suite["n_scored"] != suite["n"] else f" ({tasks})"
        L.append(f"- **Reward:** {_fmt(suite['reward_base'])} → {_fmt(suite['reward_opt'])}{cov}, "
                 "each measured in this run against its own baseline.")
        L.append(f"- **Cost:** eval ${_fmt(suite['eval_usd'], 4)}, optimizer ${_fmt(suite['optimizer_usd'], 4)}.")
    else:
        L.append("- No suite result: the run did not finish successfully (see `report.md` and the Actions run).")
    if final and isinstance(final.get("test"), dict):
        base = (final.get("test_baseline") or {}).get("reward")
        L.append(f"- **Sealed test:** {_fmt(base)} → {_fmt(final['test'].get('reward'))} "
                 f"(best candidate `{final.get('best_id', '?')}`, Δ {_fmt(final.get('test_delta'))}).")
        if final.get("train_equals_val"):
            L.append("- **No held-out split:** train = val = test for this tier, so this is a fit to the "
                     "tier's tasks, not a measure of generalisation.")
    L += ["", "Details per task are in `report.md`.", ""]

    L += ["## Files", ""]
    for rel, desc in FILES:
        if (dest / rel.rstrip("/")).exists():
            L.append(f"- [`{rel}`]({rel}) — {desc}")
    for s in skipped:
        L.append(f"- not included: {s}")
    if (dest / "backup.json").is_file():
        b = json.loads((dest / "backup.json").read_text(encoding="utf-8"))
        where = (f"staged at `{b['staged']}`" if b.get("staged")
                 else f"kept on runner `{b.get('runner', '?')}` in `{b.get('capture_dir', '?')}/`")
        L.append(f"- **Raw run data** (run dir with candidates, traces and rollouts, {b.get('bytes', 0) / 1e6:.0f} MB "
                 f"compressed): {where} "
                 "(sha256 of every file in `members.sha256`), as a capture source for the full backup "
                 "([docs/FULL_BACKUP.md](https://github.com/skillberry-ai/cap-evolve/blob/main/docs/FULL_BACKUP.md)).")
    if not (dest / "recipe" / "capevolve.yaml").exists():
        L.append("- `recipe/` was not available for this run (published from its CI artifact); the tier's "
                 f"definition is `ci/benchmarks/{bench}/{tier}/` at the commit above.")
    L.append("")

    L += ["## Re-running it", "",
          f"The tier's tasks, split and overrides are committed in cap-evolve under `ci/benchmarks/{bench}/{tier}/`. "
          "To run the same configuration again, dispatch the Benchmarks workflow on a branch at the commit above:", "",
          "```bash",
          f"gh workflow run benchmarks.yml -R skillberry-ai/cap-evolve --ref <branch> -f tier={tier} -f bench={bench} \\",
          f"  -f iterations={meta.get('iterations', '')} -f trials={meta.get('trials', '')} "
          f"-f agent_model={meta.get('agent_model_requested') or meta.get('agent_model', '')} \\",
          f"  -f optimizer_model={meta.get('optimizer_model_requested') or meta.get('optimizer_model', '')} "
          f"-f algorithm={meta.get('algorithm', '')}",
          "```", "",
          "Model calls are sampled, so a re-run gives a new measurement, not the same numbers.", ""]
    return "\n".join(L)


def build(out: Path, dest: Path, project: Path | None, run_dir: Path | None, tier_dir: Path | None,
          name: str | None, repo: str | None, has_ui: bool, provenance: str = PROVENANCE_CI) -> Path:
    meta = json.loads((out / "runmeta.json").read_text(encoding="utf-8"))
    name = name or f"{meta['run_id']}__{meta.get('tier', 'smoke')}-{meta['bench']}"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    skipped: list[str] = []
    for f in ("report.md", "runmeta.json", "metrics.jsonl", "steps.jsonl", "backup.json"):
        _put(out / f, dest / f, skipped, f)
    if run_dir:
        _put(run_dir / "final.json", dest / "final.json", skipped, "final.json")
    opt = out / "optimized"
    _put(opt / "capability.diff", dest / "capability.diff", skipped, "capability.diff")
    _put(opt / "capability.diffstat.txt", dest / "capability.diffstat.txt", skipped, "capability.diffstat.txt")
    if meta.get("bench") != "skillsbench":
        _put(opt / "optimized_capability", dest / "optimized_capability", skipped, "optimized_capability/")
    if project:
        _put(project / "capevolve.yaml", dest / "recipe" / "capevolve.yaml", skipped, "recipe/capevolve.yaml")
        _put(project / "inputs" / "split_ids.json", dest / "recipe" / "split_ids.json", skipped, "recipe/split_ids.json")
    if tier_dir:
        _put(tier_dir / "overrides.env", dest / "recipe" / "overrides.env", skipped, "recipe/overrides.env")
    (dest / "README.md").write_text(readme(meta, dest, name, repo, has_ui, skipped, provenance), encoding="utf-8")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("dest", type=Path)
    ap.add_argument("--project", type=Path)
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument("--tier-dir", type=Path)
    ap.add_argument("--name")
    ap.add_argument("--repo")
    ap.add_argument("--has-ui", action="store_true")
    ap.add_argument("--provenance", default=PROVENANCE_CI,
                    help="how the folder came to be, completing 'A cap-evolve benchmark run, ...' "
                         "(default: published by its CI job; e.g. 'published by hand by <who>')")
    a = ap.parse_args()
    if not (a.out / "runmeta.json").is_file():
        print(f"run_folder: no runmeta.json in {a.out}", file=sys.stderr)
        return 1
    d = build(a.out, a.dest, a.project, a.run_dir, a.tier_dir, a.name, a.repo, a.has_ui, a.provenance)
    print(f"run_folder: wrote {d} ({sum(1 for f in d.rglob('*') if f.is_file())} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
