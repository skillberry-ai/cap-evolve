#!/usr/bin/env python3
"""Regenerate the `DATA_V1` / `DATA_V2` arrays embedded in ui/heatmap.html from results.json.

Why this exists: ui/heatmap.html has no build step and no `fetch()` — it is meant to be opened
straight from a checkout over `file://`, and CORS rules out fetching a sibling JSON file. So
its data arrays are a copy of results.json pasted into the page, and a pasted copy drifts.
On skillsbench-history that drift silently undercounted the pass rate by one task (63/87 vs
64/87) because the pasted array was missing a field. Generating the arrays removes the failure
mode entirely.

Departure from skillsbench-history's version of this script, recorded deliberately: there the
page had two data blocks and only the FIRST was generated (the second, `DATA_C4`, was
hand-maintained because it had no source-of-truth file). Here BOTH blocks are generated —
parsec's two experiments are both fully represented in results.json, so there is no reason to
leave either one hand-maintained. `--check` therefore covers the whole page's data.

Usage: python3 scripts/build_heatmap.py [--check]
  --check   exit 1 if regenerating would change the file, instead of writing it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "results.json"
HEATMAP_HTML = ROOT / "ui" / "heatmap.html"

# Field order for each entry. `seed_n` and `seed_train` are carried into the page (unlike
# skillsbench, which had a single uniform trial count) because parsec's numbers are NOT
# comparable across cells without their n: v2's headline gate compared an n=9 candidate
# against a reused n=3 seed. The page renders the n so nobody reads the row as apples-to-apples.
FIELDS = [
    "experiment", "task", "category", "subcategory", "source", "status",
    "baseline", "baseline_gate", "baseline_trajectory", "baseline_assertions",
    # Contract shape and harness reachability. Carried into the page because v1's trajectory
    # column is not a measurement of the skill on 25 of its 30 tasks: those contracts demand a
    # tool no simulator served when the sweep ran, and a `subset` match fails whole on one
    # uncallable op. A reader looking at a bare 0.000 trajectory cell cannot see that, so the
    # missing-tool list travels with the row and the page can mark it.
    "n_trajectory_ops", "trajectory_match", "n_assertions", "baseline_assertions_passed",
    "trajectory_reachable_at_baseline", "trajectory_tools_missing_at_baseline",
    "n_expected_calls", "n_required_facts", "n_derived_facts",
    "seed", "seed_n", "seed_all", "seed_train", "seed_train_n", "seed_train_all",
    "cand_0001", "cand_0001_all", "cand_0002",
    "best", "best_tag", "delta", "final_test", "trials_errored", "weights", "flags", "report",
]

BLOCKS = {"v1": "DATA_V1", "v2": "DATA_V2"}


def build_data_block(tasks: list[dict]) -> str:
    entries = [{k: t.get(k) for k in FIELDS} for t in tasks]
    lines = json.dumps(entries, indent=2).splitlines()
    assert lines[0] == "[" and lines[-1] == "]"
    return "\n".join(lines[1:-1])


def build_ladder_block(results: dict) -> str:
    """Every measurement of the *seed* skill, across every run, with its trial count.

    The seed `SKILL.md` is byte-identical in all nine runs, so each of these rows measures the
    same artifact. They disagree by up to 0.36 on v2 and 0.32 on v1. That is the branch's
    central finding and it is only visible when the measurements are put side by side with
    their `n`, so the page renders it as a table of its own rather than leaving it in prose.
    """
    rows = []
    for r in results["runs"]:
        # A reused baseline is a measurement too — from a *different* run, at that run's n.
        if r.get("baseline_reused"):
            rows.append(
                {
                    "experiment": r["experiment"], "run": r["run"], "role": r["role"],
                    "headline": r["headline"], "split": "val", "tag": "seed (reused)",
                    "n": next(
                        (t["seed_n"] for t in results["tasks"]
                         if t["experiment"] == r["experiment"] and t.get("seed_n")),
                        None,
                    ),
                    "reward": r["baseline_reused"]["val"],
                    "from_run": r["baseline_reused"]["prior_run_dir"], "convention": None,
                    "n_errored": 0,
                }
            )
        for e in r["evaluations"]:
            if e["tag"] not in ("seed", "seed_train", "FINAL_seed"):
                continue
            rec = e["reconciliation"]
            rows.append(
                {
                    "experiment": r["experiment"], "run": r["run"], "role": r["role"],
                    "headline": r["headline"], "split": e["split"], "tag": e["tag"],
                    "n": rec.get("n_trials"), "reward": e["reward"], "from_run": None,
                    "convention": rec["convention"], "n_errored": rec["n_errored_trials"],
                    "reason": rec.get("reason"),
                }
            )
    lines = json.dumps(rows, indent=2).splitlines()
    return "\n".join(lines[1:-1])


def splice(html: str, var: str, block: str) -> str:
    start_re = re.compile(r"^const " + var + r" = \[\n", re.MULTILINE)
    m = start_re.search(html)
    if not m:
        raise SystemExit(f"ERROR: could not find 'const {var} = [' in ui/heatmap.html")
    end_re = re.compile(r"^\];\n", re.MULTILINE)
    e = end_re.search(html, m.end())
    if not e:
        raise SystemExit(f"ERROR: could not find closing '];' for {var}")
    return html[: m.end()] + block + html[e.start() :]


def main() -> int:
    check_only = "--check" in sys.argv

    results = json.loads(RESULTS_JSON.read_text())
    tasks = results["tasks"]
    assert len(tasks) == results["total_tasks"], "results.json task count mismatch"

    html = new_html = HEATMAP_HTML.read_text()
    counts = {}
    for exp, var in BLOCKS.items():
        rows = [t for t in tasks if t["experiment"] == exp]
        counts[exp] = len(rows)
        new_html = splice(new_html, var, build_data_block(rows) + "\n")
    new_html = splice(new_html, "SEED_LADDER", build_ladder_block(results) + "\n")

    if new_html == html:
        print(f"ui/heatmap.html DATA blocks already up to date ({counts}).")
        return 0
    if check_only:
        print("ui/heatmap.html DATA blocks are STALE relative to results/results.json.",
              file=sys.stderr)
        return 1

    HEATMAP_HTML.write_text(new_html)
    print(f"Regenerated DATA_V1/DATA_V2 from results/results.json ({counts}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
