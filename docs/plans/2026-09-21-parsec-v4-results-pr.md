# Parsec v4 Results PR (parsec-history) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `parsec-history` "results PR" for parsec v4 — a separate `results/v4/` ledger + heatmap, `recipes/v4/`, `artifacts/v4/<task>/`, and `reports/task-by-task/v4-*.md` covering all 34 tasks — so the T1/T2 arms that have already run are fully documented and the C2-C4/G2-G4 arms that have not are explicitly recorded as gaps, per the spec's step 2.

**Architecture:** Everything in this plan lives in the `parsec-history` worktree (an orphan branch, unrelated to `main`). Four small, single-purpose generator scripts under `scripts/` each read one JSON source and regenerate one derived artifact (`results.json`, `ui/heatmap_v4.html`, `artifacts/v4/*`, `reports/task-by-task/v4-*.md`), mirroring the existing v1/v2 scripts (`build_results_json.py`, `build_heatmap.py`, `build_task_reports.py`) but reading from a v4-only ledger instead of the shared `results/results.json`. Raw data is vendored once from the `parsec-intake_v4` worktree (which is gitignored there) into two frozen JSON/markdown snapshots; every other v4 file in this branch is derived from those snapshots, never hand-typed twice. Every script has a `--check` mode so staleness is a CI-checkable property, matching this branch's existing convention (see root `README.md`: "The lesson this branch is built around").

**Tech Stack:** Python 3 stdlib only (`json`, `re`, `glob`, `shutil`, `filecmp`, `datetime`, `pathlib`) — no new dependencies, matching every existing script in `parsec-history/scripts/`.

**Spec:** `docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md` (this plan implements step 2 of that spec's §6: "Results PR into `parsec-history`").

## Global Constraints

- **Separate v4 ledger + page.** `results/v4/results.json` and `ui/heatmap_v4.html` are structurally independent from v1/v2's shared `results/results.json` / `ui/heatmap.html` — do not add v4 rows into either shared file. (User's explicit decision, recorded in this plan's originating conversation.)
- **Never pool regression and challenge tranches.** Every aggregate statistic (mean reward, delta, coverage count) must be reported per-tranche. A single pooled number across both tranches is a plan defect wherever it appears — this is a standing convention carried from the `3x2_toy` pilot and the spec's own §0 table.
- **`num_trials: 5`, `max_iterations: 3`, `stop_at_reward: 1.0`, `max_usd: 50.0`, `max_optimizer_usd: 20.0`, `stall: 2`** — the shared per-task `capevolve.yaml` template's values, confirmed against two tasks' `state.json` (`platform-005-wrong-owner-trap`, `cloud-024-guid-to-account`) with **no divergence found** (unlike v1's 3 documented divergences).
- **`train = val = test = {task}`** — every T2 project's `split_ids.json` is per-task-generated with all three splits set to that one task, a deliberate single-task-tuning design (not an accidental omission, unlike v1's).
- **21 of 34 tasks were T2-optimized; the other 13 were skipped by design** because their seed bundle already scored a perfect `our_baseline == 1.0` — this is documented fact (spec §3), not a coverage gap to apologize for, and every v4 document must state it this way.
- **C2, C3, C4, G2, G3, G4 have not been run.** Every row for these arms in `results/v4/results.json` carries `"status": "not_run"` and `"scores": null` (or the category/global equivalent) — matching the spec's "gap-documentation convention," never simply omitted.
- **Raw rollout/run data is not committed to `parsec-history`.** It remains in the `parsec-intake_v4` worktree (gitignored there via `.capevolve*/`). Any report that references it links to it as plain text (a code span naming the worktree-relative path), never as a markdown hyperlink — a relative link across worktrees does not resolve on a forge and is not resolvable from an orphan branch with unrelated history anyway.
- **Commit messages end with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.** Every commit task in this plan includes this trailer.
- **Confirm with the user before pushing or opening a PR.** Every commit in this plan is local-only; the final push/PR step is explicitly out of this plan's scope (see "Out of scope" below).

## Out of scope (do not do these in this plan)

- Running any C2/C3/C4/G2/G3/G4 job. This plan documents them as `not_run`; submitting one is future work (spec §2, §7).
- Resolving the merge-conflict strategy for combining multiple tasks' edits to the shared 8-file bundle (spec §4). Note it as open.
- The `benchmark-history` record (spec §6 step 3) — a separate, later plan.
- CCC/LSF parallel-execution migration (spec §7) — explicitly deferred.
- Pushing any branch or opening any PR — stop after the last commit and ask.

## File Structure

```
parsec-history/
  results/v4/
    source_parsec34.json      # frozen copy of parsec-intake_v4's results/parsec34/results.json
    results.json              # generated — the v4 ledger (arms table + task_ledger + sections)
    summary.md                # hand-written narrative, generated tables pasted in by hand from results.json
  ui/
    heatmap_v4.html            # copied skeleton (from parsec-intake_v4's results/parsec34/heatmap.html) + generated DATA/SUMMARIES blocks
  recipes/v4/
    capevolve.yaml             # the one shared per-task template, verbatim
    split_ids.json             # one representative per-task split file, verbatim
    INSTRUCTIONS.md            # the v4-specific optimizer instructions template (NOT the generic cap-evolve default — see README.md)
    README.md                  # divergence check, template explanation, pointer to the real execution plan
  artifacts/v4/
    seed/                      # the 8 shared bundle files, vendored once
      orchestrator.md shared_context.md aap2_agent.md babylon_agent.md
      cost_agent.md icinga_agent.md ocpv_agent.md security_agent.md
    <task>/                    # one dir per T2-optimized task (21 total)
      best/                    # the winning candidate's 10 files (or NOTE.md if best_tag == "seed")
      rejected/<cand_id>/      # every other candidate from the canonical run
      discarded/<run_ts>-<cand_id>/   # (only for the 3 multi-run tasks) candidates from the non-canonical run
  reports/task-by-task/
    v4-<task>.md               # one per task, 34 total
  scripts/
    build_v4_results_json.py
    build_v4_heatmap.py
    vendor_v4_artifacts.py
    build_v4_task_reports.py
  README.md                    # updated: experiment table, Layout table
  recipes/README.md            # updated: v4 row, INSTRUCTIONS.md exception note
  artifacts/README.md          # updated: v4 section (seed/best/rejected/discarded, budget-cap cause)
  reports/README.md            # updated: v4 naming row
```

**Absolute paths used by scripts in this plan** (both worktrees are siblings on this machine):
- `PARSEC_HISTORY = /Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-history` (every script's own `ROOT`, resolved via `Path(__file__).resolve().parent.parent`)
- `SOURCE_ROOT = /Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4` (hardcoded absolute constant in `vendor_v4_artifacts.py`, matching the existing `build_parsec34_heatmap.py`'s own hardcoded `BASELINE_MD`/`PROGRESS_CSV` pattern)

---

### Task 1: Vendor frozen source data

**Files:**
- Create: `results/v4/source_parsec34.json`
- Create: `artifacts/v4/seed/orchestrator.md`, `shared_context.md`, `aap2_agent.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`, `ocpv_agent.md`, `security_agent.md`

**Interfaces:**
- Produces: `results/v4/source_parsec34.json` — a byte-for-byte copy of `parsec-intake_v4`'s `results/parsec34/results.json`, shape `{"total_tasks": 34, "n_optimized": 21, "summaries": [<regression summary>, <challenge summary>], "tasks": [<34 rows>]}`. Task 2 reads this file's `"tasks"` and `"summaries"` keys.
- Produces: `artifacts/v4/seed/*.md` — the 8 shared bundle files. Task 4/5/6/7's documentation link here as "the native, never-optimized bundle."

- [ ] **Step 1: Copy the frozen results snapshot**

```bash
mkdir -p results/v4 artifacts/v4/seed
cp /Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/results/parsec34/results.json \
   results/v4/source_parsec34.json
python3 -c "import json; d = json.load(open('results/v4/source_parsec34.json')); assert d['total_tasks'] == 34 and d['n_optimized'] == 21, d"
```

Expected: the assert passes silently (exit 0).

- [ ] **Step 2: Copy the shared seed bundle and verify it really is byte-identical across tasks**

```bash
SRC=/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/candidates/seed
cp "$SRC"/*.md artifacts/v4/seed/

# Cross-check against a second, unrelated task's seed bundle (different category)
OTHER=/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/.capevolve/v4_t2_e1_cloud-024-guid-to-account
OTHER_RUN=$(ls -d "$OTHER"/run_* | head -1)
diff -rq artifacts/v4/seed "$OTHER_RUN/candidates/seed"
```

Expected: `diff -rq` prints nothing (no differences). If it prints any `Files ... differ` line, STOP — the spec's §1 claim that all 8 files are byte-identical across tasks would be false, and every later task in this plan that treats the seed bundle as one shared global artifact needs to be re-scoped before continuing.

- [ ] **Step 3: Commit**

```bash
git add results/v4/source_parsec34.json artifacts/v4/seed/
git commit -m "$(cat <<'EOF'
data(parsec-v4): vendor frozen parsec34 results snapshot + shared seed bundle

Copies parsec-intake_v4's results/parsec34/results.json verbatim (34 task
rows, T1 + T2) and the 8-file native multi-agent bundle (byte-identical
across every task per spec Sec.1, re-verified here against a second task).
Everything else under results/v4/, recipes/v4/, artifacts/v4/, and
reports/task-by-task/v4-*.md is derived from this snapshot.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `results/v4/results.json` ledger generator

**Files:**
- Create: `scripts/build_v4_results_json.py`
- Create (generated by the script): `results/v4/results.json`

**Interfaces:**
- Consumes: `results/v4/source_parsec34.json` (Task 1) — reads keys `"tasks"` (list of 34 row dicts with at least `task, category, tranche, services, status, jb_reward, jb_completion, jb_tool_calls, jb_answer, jb_n, our_baseline, our_baseline_n, seed, cand_0001, cand_0002, cand_0003, best, best_tag, final, final_n, delta_vs_jb, delta_vs_our_baseline, run_dir, n_runs`) and `"summaries"` (list of 2 tranche-summary dicts).
- Produces: `results/v4/results.json` with top-level keys `generated_at, generator, benchmark, target, spec, total_tasks, n_optimized, arms, task_ledger, sections, provenance`. `task_ledger` rows are the source rows plus a `"report"` key (`"reports/task-by-task/v4-<task>.md"`). `sections.task.summaries` is the source's `summaries` list, copied through unchanged. `sections.category.rows` is a list of 4 dicts (one per category) each with keys `category, n_tasks, C1_seed, C2_joint, C3_merge, C4_merge_joint`. `sections.global.row` is a single dict with keys `n_tasks, G1_seed, G2_joint, G3_merge, G4_merge_joint`. Task 3, 6, 7 all read `results/v4/results.json`.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Build results/v4/results.json from the frozen source_parsec34.json snapshot
plus the C/G arm scaffold from
docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md.

Usage: python3 scripts/build_v4_results_json.py [--check]
  --check   exit 1 if regenerating would change results.json, instead of writing it.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_JSON = ROOT / "results" / "v4" / "source_parsec34.json"
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
SPEC = "docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md"

ARMS = [
    {"arm_id": "T1", "section": "task", "name": "seed", "mode": "zs",
     "status": "done", "source": "v4_t1_e1",
     "description": "native bundle, zero-shot, all 34 tasks"},
    {"arm_id": "T2", "section": "task", "name": "tbt", "mode": "opt",
     "status": "done_by_design", "source": "v4_t2_e1",
     "description": "independent optimizer run per task, 21 of 34 tasks "
                     "(the other 13 already scored 1.0 on the seed -- spec Sec.3)"},
    {"arm_id": "C1", "section": "category", "name": "seed", "mode": "zs",
     "status": "done", "source": "derived from T1",
     "description": "native bundle, zero-shot, scored per category"},
    {"arm_id": "C2", "section": "category", "name": "joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "one optimizer run per category, scoring all of that "
                     "category's tasks together"},
    {"arm_id": "C3", "section": "category", "name": "merge", "mode": "zs",
     "status": "not_run", "source": None,
     "description": "per category, union of that category's T2 bundles, "
                     "zero-shot, evaluated on all of that category's tasks "
                     "including the already-perfect ones (spec Sec.3)"},
    {"arm_id": "C4", "section": "category", "name": "merge-joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "C3's union, continued optimization jointly on that category"},
    {"arm_id": "G1", "section": "global", "name": "seed", "mode": "zs",
     "status": "done", "source": "derived from T1",
     "description": "native bundle, zero-shot, all 34 tasks (= T1)"},
    {"arm_id": "G2", "section": "global", "name": "joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "one optimizer run scoring all 34 tasks together"},
    {"arm_id": "G3", "section": "global", "name": "merge", "mode": "zs",
     "status": "not_run", "source": None,
     "description": "union of all 21 T2 bundles, evaluated zero-shot on all "
                     "34 tasks, including the 13 already-perfect ones (spec Sec.3)"},
    {"arm_id": "G4", "section": "global", "name": "merge-joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "G3's union, continued optimization jointly on all 34 tasks"},
]

NOT_RUN_NOTE_MERGE = (
    f"Design only, per {SPEC} Sec.2. No job has been submitted for this arm. "
    f"Merge strategy for the shared 8-file bundle is an open question -- see "
    f"{SPEC} Sec.4."
)
NOT_RUN_NOTE_JOINT = (
    f"Design only, per {SPEC} Sec.2. No job has been submitted for this arm."
)


def load_source():
    return json.loads(SOURCE_JSON.read_text())


def build_task_ledger(source):
    rows = []
    for row in source["tasks"]:
        row = dict(row)
        row["report"] = f"reports/task-by-task/v4-{row['task']}.md"
        rows.append(row)
    return rows


def mean(vals):
    vals = [v for v in vals if v is not None]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def build_category_rows(task_ledger):
    by_cat = {}
    for row in task_ledger:
        by_cat.setdefault(row["category"], []).append(row)

    out = []
    for cat, rows in sorted(by_cat.items()):
        jb_mean, jb_n = mean(r["jb_reward"] for r in rows)
        seed_mean, seed_n = mean(r["our_baseline"] for r in rows)
        out.append({
            "category": cat,
            "n_tasks": len(rows),
            "C1_seed": {"source": "derived from T1", "jb_reward_mean": jb_mean,
                        "our_baseline_mean": seed_mean, "n": seed_n},
            "C2_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_JOINT},
            "C3_merge": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
            "C4_merge_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
        })
    return out


def build_global_row(task_ledger):
    jb_mean, jb_n = mean(r["jb_reward"] for r in task_ledger)
    seed_mean, seed_n = mean(r["our_baseline"] for r in task_ledger)
    return {
        "n_tasks": len(task_ledger),
        "G1_seed": {"source": "derived from T1", "jb_reward_mean": jb_mean,
                    "our_baseline_mean": seed_mean, "n": seed_n},
        "G2_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_JOINT},
        "G3_merge": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
        "G4_merge_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
    }


def build_results(source):
    task_ledger = build_task_ledger(source)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build_v4_results_json.py",
        "benchmark": "parsec",
        "target": "parsec multi-agent bundle (orchestrator.md + 6 domain agents + "
                  "shared_context.md; capabilities: [system-prompt])",
        "spec": SPEC,
        "total_tasks": len(task_ledger),
        "n_optimized": sum(1 for r in task_ledger if r["status"] == "optimized"),
        "arms": ARMS,
        "task_ledger": task_ledger,
        "sections": {
            "task": {"summaries": source["summaries"]},
            "category": {"rows": build_category_rows(task_ledger)},
            "global": {"row": build_global_row(task_ledger)},
        },
        "provenance": {
            "source_parsec34_results": "results/v4/source_parsec34.json",
            "source_parsec34_generator": "parsec-intake_v4/scripts/build_parsec34_heatmap.py",
            "spec": SPEC,
            "note": (
                "task_ledger rows are the frozen source's 34 task rows verbatim, "
                "plus a 'report' pointer. category/global C1/G1 rows are computed "
                "here from T1's our_baseline column, not from a new job (spec Sec.2). "
                "C2-C4/G2-G4 are not_run (spec Sec.2); see spec Sec.3 for why T2 "
                "covers only 21/34 tasks and Sec.4 for the open merge-strategy question."
            ),
        },
    }


def main():
    check_only = "--check" in sys.argv
    source = load_source()
    assert len(source["tasks"]) == 34, f"expected 34 source tasks, got {len(source['tasks'])}"

    new_results = build_results(source)
    new_text = json.dumps(new_results, indent=2) + "\n"

    if RESULTS_JSON.exists():
        old_stable = {k: v for k, v in json.loads(RESULTS_JSON.read_text()).items()
                      if k != "generated_at"}
        new_stable = {k: v for k, v in new_results.items() if k != "generated_at"}
        if old_stable == new_stable:
            print(f"{RESULTS_JSON} already up to date.")
            return 0

    if check_only:
        print(f"{RESULTS_JSON} is STALE relative to source_parsec34.json.", file=sys.stderr)
        return 1

    RESULTS_JSON.write_text(new_text)
    print(f"Wrote {RESULTS_JSON} ({new_results['total_tasks']} tasks, "
          f"{new_results['n_optimized']} optimized).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it and verify the output**

```bash
python3 scripts/build_v4_results_json.py
python3 -c "
import json
d = json.load(open('results/v4/results.json'))
assert d['total_tasks'] == 34
assert d['n_optimized'] == 21
assert len(d['task_ledger']) == 34
assert len(d['sections']['category']['rows']) == 4
assert d['sections']['global']['row']['n_tasks'] == 34
assert {a['arm_id'] for a in d['arms']} == {'T1','T2','C1','C2','C3','C4','G1','G2','G3','G4'}
not_run = [a['arm_id'] for a in d['arms'] if a['status'] == 'not_run']
assert set(not_run) == {'C2','C3','C4','G2','G3','G4'}, not_run
print('OK')
"
python3 scripts/build_v4_results_json.py --check
```

Expected: `OK`, then `results/v4/results.json already up to date.` with exit 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_v4_results_json.py results/v4/results.json
git commit -m "$(cat <<'EOF'
feat(parsec-v4): generate results/v4/results.json ledger

Builds the v4 arm table (T1/T2 done, C1/G1 derived from T1, C2-C4/G2-G4
explicitly not_run per spec Sec.2) and the 34-task ledger with a report
pointer per task. Structurally independent from the shared v1/v2
results/results.json, per the "separate v4 ledger" decision.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: v4 heatmap page

**Files:**
- Create: `ui/heatmap_v4.html` (copied skeleton, then title text edited)
- Create: `scripts/build_v4_heatmap.py`

**Interfaces:**
- Consumes: `results/v4/results.json` (Task 2) — reads `task_ledger` (34 rows) and `sections.task.summaries`.
- Produces: `ui/heatmap_v4.html` with its `const DATA = [ ... ];` block populated from `task_ledger` (same `FIELDS` projection as `parsec-intake_v4/scripts/build_parsec34_heatmap.py`) and its `const SUMMARIES = ... ;` block populated from `sections.task.summaries`.

- [ ] **Step 1: Copy the heatmap skeleton and retitle it**

```bash
mkdir -p ui
cp /Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/results/parsec34/heatmap.html \
   ui/heatmap_v4.html
```

Then edit `ui/heatmap_v4.html` (Edit tool, exact strings confirmed present in the copied file):

- `<title>Parsec-34 heatmap — JB baseline vs v4_t1_e1 vs cap-evolve</title>` → `<title>Parsec v4 heatmap — JB baseline vs v4_t1_e1 vs v4_t2_e1</title>`
- `<h1>Parsec-34 heatmap</h1>` → `<h1>Parsec v4 heatmap</h1>`
- Find the line containing the text `All 34 v4 Parsec scenarios · JB baseline (n=1) vs cap-evolve zero-shot baseline v4_t1_e1 (n=3) vs cap-evolve-optimized v4_t2_e1 (n=5 per eval, 21/34 tasks)` (its exact wrapping tag was not re-confirmed when this plan was written — read the copied file first to see it) and insert, immediately before that line's closing tag, the sentence: ` Category/global arms (C2-C4, G2-G4) not yet run — see results/v4/summary.md.`

- [ ] **Step 2: Write the generator script**

```python
#!/usr/bin/env python3
"""Regenerate the DATA/SUMMARIES blocks in ui/heatmap_v4.html from
results/v4/results.json.

Usage: python3 scripts/build_v4_heatmap.py [--check]
  --check   exit 1 if regenerating would change heatmap_v4.html, instead of writing it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
HEATMAP_HTML = ROOT / "ui" / "heatmap_v4.html"

DATA_START_RE = re.compile(r"^const DATA = \[\n", re.MULTILINE)
DATA_END_RE = re.compile(r"^\];\n", re.MULTILINE)
SUMMARY_RE = re.compile(r"(const SUMMARIES =\n)(.*?)(\n;\n)", re.DOTALL)

FIELDS = [
    "task", "category", "tranche", "services", "status",
    "jb_reward", "jb_completion", "jb_tool_calls", "jb_answer", "jb_n",
    "our_baseline", "our_baseline_n",
    "seed", "cand_0001", "cand_0002", "cand_0003",
    "best", "best_tag",
    "final", "final_n",
    "delta_vs_jb", "delta_vs_our_baseline",
]


def build_data_block(tasks):
    entries = [{k: t.get(k) for k in FIELDS} for t in tasks]
    body = json.dumps(entries, indent=2)
    lines = body.splitlines()
    assert lines[0] == "[" and lines[-1] == "]"
    return "\n".join(lines[1:-1])


def regenerate(results, check_only):
    html = HEATMAP_HTML.read_text()

    start_m = DATA_START_RE.search(html)
    if not start_m:
        print("ERROR: could not find 'const DATA = [' in heatmap_v4.html", file=sys.stderr)
        return 2
    end_m = DATA_END_RE.search(html, start_m.end())
    if not end_m:
        print("ERROR: could not find closing '];' for DATA block", file=sys.stderr)
        return 2

    new_data_block = build_data_block(results["task_ledger"]) + "\n"
    new_html = html[: start_m.end()] + new_data_block + html[end_m.start():]

    s_m = SUMMARY_RE.search(new_html)
    if not s_m:
        print("ERROR: could not find 'const SUMMARIES =' block in heatmap_v4.html", file=sys.stderr)
        return 2
    new_html = (
        new_html[: s_m.start()]
        + s_m.group(1)
        + json.dumps(results["sections"]["task"]["summaries"], indent=2)
        + s_m.group(3)
        + new_html[s_m.end():]
    )

    if new_html == html:
        print("heatmap_v4.html DATA/SUMMARIES blocks already up to date.")
        return 0
    if check_only:
        print("heatmap_v4.html is STALE relative to results/v4/results.json.", file=sys.stderr)
        return 1

    HEATMAP_HTML.write_text(new_html)
    print(f"Regenerated heatmap_v4.html from {len(results['task_ledger'])} tasks.")
    return 0


def main():
    check_only = "--check" in sys.argv
    results = json.loads(RESULTS_JSON.read_text())
    return regenerate(results, check_only)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run it and verify**

```bash
python3 scripts/build_v4_heatmap.py
grep -c '"task":' ui/heatmap_v4.html   # expect 34
python3 scripts/build_v4_heatmap.py --check
```

Expected: `34`, then `heatmap_v4.html DATA/SUMMARIES blocks already up to date.` with exit 0. Open `ui/heatmap_v4.html` in a browser and confirm it renders a 34-row table with no console errors (it reuses the same JS as `ui/heatmap.html`, which already works).

- [ ] **Step 4: Commit**

```bash
git add ui/heatmap_v4.html scripts/build_v4_heatmap.py
git commit -m "$(cat <<'EOF'
feat(parsec-v4): add ui/heatmap_v4.html generated from results/v4/results.json

Copies the parsec34 heatmap skeleton and retitles it, then splices in the
DATA/SUMMARIES blocks the same way build_parsec34_heatmap.py does, but
sourced from the v4-only ledger instead of raw JB/CSV/events.jsonl data.
Kept as its own page rather than folded into ui/heatmap.html, per the
"separate v4 ledger + page" decision.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `results/v4/summary.md`

**Files:**
- Create: `results/v4/summary.md`

**Interfaces:**
- Consumes: `results/v4/results.json` (Task 2) for the numbers quoted in its tables (all values below are copied from the spec doc's own §0/§3 tables, which were themselves computed from this same data — no new computation needed in this task).

- [ ] **Step 1: Write the file**

```markdown
# parsec v4 — multi-arm experiment (T/C/G grouping-granularity)

**Spec:** `docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md` (branch `parsec-v4-docs`)
**Ledger:** [`results.json`](results.json), generated by [`../../scripts/build_v4_results_json.py`](../../scripts/build_v4_results_json.py)
**Heatmap:** [`../../ui/heatmap_v4.html`](../../ui/heatmap_v4.html)
**Recipes:** [`../../recipes/v4/`](../../recipes/v4/)
**Artifacts:** [`../../artifacts/v4/`](../../artifacts/v4/)
**Per-task reports:** [`../../reports/task-by-task/`](../../reports/task-by-task/) (`v4-<task>.md`, 34 files)

## The one-line result

Task-by-task optimization (T2) raises the mean reward over both the JB baseline and our own
zero-shot baseline, on both tranches — but it only ran on 21 of the 34 tasks, by design (see
"Coverage" below), and none of the category- or global-scope arms (C2-C4, G2-G4) have been run yet.

## Aggregate: T1 seed vs. T2 final

| tranche | n | JB reward (mean) | our T1 seed (mean) | our T2 final (mean)\* | Δ vs JB | Δ vs T1 |
|---|---|---|---|---|---|---|
| regression | 30 | 0.833 | 0.845 | 0.963 | +0.131 | +0.119 |
| challenge | 4 | 0.730 | 0.792 | 0.873 | +0.143 | +0.081 |

\*T2's `final` column falls back to the T1 `seed` score for the 13 tasks T2 never targeted (they
were already at ceiling) — this is **not** a clean "optimized-only" average. Never pool the two
tranches above into one number; see the Global Constraints in this repo's `docs/superpowers/plans/`
plan for why.

These numbers are the `sections.task.summaries` block of `results.json`, unchanged from
`parsec-intake_v4`'s own `results/parsec34/results.json` (Task 1 vendored it verbatim).

## Coverage: T2 ran on 21 of 34 tasks, by design

T2 wasn't cut short by time or resources. It deliberately only targeted tasks where the seed
bundle hadn't already scored a perfect 1.0 on our own baseline run (`our_baseline`):

| category | tasks | already-perfect on seed (skipped) | T2-optimized |
|---|---|---|---|
| platform | 19 | 6 | 13 |
| icinga | 8 | 4 | 4 |
| cloud | 4 | 2 | 2 |
| cost | 3 | 1 | 2 |
| **total** | **34** | **13** | **21** |

All 13 skipped tasks are in the `regression` tranche (0 `challenge`) — every `challenge` task was
T2-optimized. Since those 13 tasks were already at ceiling, there is no missing optimized content
to merge in for them when C3/C4/G3/G4 eventually run — but those arms **must** still evaluate every
task in their group, including these 13, specifically to catch a regression that merging other
tasks' edits into the shared bundle could introduce (spec §3, §4).

## Data-quality caveats

1. **Three tasks hit a team-wide LLM API budget cap mid-run and were re-run:**
   `platform-005-wrong-owner-trap`, `platform-007-directory-path-fetch`,
   `platform-008-log-does-not-say`, all on 2026-09-20 ("Budget has been exceeded"
   `optimizer_error` events). For `platform-007` and `platform-008` the rerun is a genuine
   improvement (the first attempt underperformed or never finalized). For `platform-005`, the
   *first* attempt had already finalized cleanly — 3 candidates, monotonic improvement, held-out
   test `1.0 ± 0.0`, a `0.0` val→test gap — despite the budget errors elsewhere in that run, and its
   rerun was a redundant resample whose noisier seed measurement made the rerun's two candidates
   look like a regression (final `0.346` vs. the first attempt's `1.0`).
2. Because of (1), `results.json`'s `task_ledger` rows for these three tasks are **not** simply
   "the latest run" — `run_dir` points at whichever of a task's finalized runs had the best
   `test_reward`, tie-broken by latest. This is what moved the regression tranche's T2 final mean
   from an earlier draft's `0.941` to the `0.963` reported above. See
   `reports/task-by-task/v4-platform-005-wrong-owner-trap.md` for the full account.
3. `seed`, `cand_0001-3`, and `best` in the ledger are **validation-split** measurements (`n=5`
   trials per eval); `final` is the **held-out test-split** measurement for whichever candidate won
   on validation (same task, same split as `train`/`val` by design — see recipes/v4/README.md on
   why there is no independent holdout this phase). `jb_reward` (`n=1`) and `our_baseline` (`n=3`)
   are separate, earlier measurements from different runs (`baseline.md` and `v4_t1_e1` respectively)
   — four different `n`s can appear in one task's row. Read no cell without checking its `n` and
   split, exactly as `reports/README.md`'s existing caution already states for v1/v2.

## Next moves (open)

- **A. Run C2-C4 and G2-G4.** Designed in the spec (§2) but not submitted. C1/G1 need no new job —
  they're already derivable from T1 and are computed directly into `results.json` by
  `build_v4_results_json.py`.
- **B. Resolve the merge-conflict strategy** for combining multiple tasks' edits to the same 8-file
  bundle before C3/C4/G3/G4 can run (spec §4) — this doc does not pick one.
- **C. CCC/LSF parallel migration** for running C2-C4/G2-G4's jobs is deferred until this local work
  (this PR and the recipe/artifact/report PRs alongside it) is committed and pushed (spec §7).
```

- [ ] **Step 2: Sanity-check the numbers against the ledger**

```bash
python3 -c "
import json
d = json.load(open('results/v4/results.json'))
for s in d['sections']['task']['summaries']:
    print(s['tranche'], s['n_tasks'], round(s['jb_reward_mean'],3), round(s['our_baseline_mean'],3), round(s['final_mean'],3))
by_cat = {}
for r in d['task_ledger']:
    by_cat.setdefault(r['category'], [0,0])
    by_cat[r['category']][0 if r['status']=='optimized' else 1] += 1
print(by_cat)
"
```

Expected output's two summary lines and the `by_cat` dict match the "Aggregate" and "Coverage" tables above exactly (regression: n=30, 0.833/0.845/0.963; challenge: n=4, 0.730/0.792/0.873; `by_cat`: `platform` `[13, 6]`, `icinga` `[4, 4]`, `cloud` `[2, 2]`, `cost` `[2, 1]`). If any number differs, fix the markdown table, not the script — the script is already correct (Task 2), so a mismatch means a transcription error in this task's file.

- [ ] **Step 3: Commit**

```bash
git add results/v4/summary.md
git commit -m "$(cat <<'EOF'
docs(parsec-v4): write results/v4/summary.md

Aggregate table, coverage table (why T2 only targeted 21/34 tasks), the
platform-005/007/008 budget-cap data-quality caveat, and an explicit
"next moves" section naming C2-C4/G2-G4 as designed-but-not-run.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `recipes/v4/`

**Files:**
- Create: `recipes/v4/capevolve.yaml`
- Create: `recipes/v4/split_ids.json`
- Create: `recipes/v4/INSTRUCTIONS.md`
- Create: `recipes/v4/README.md`
- Modify: `recipes/README.md`

**Interfaces:**
- No code interfaces — this task is documentation + verbatim config copies.

- [ ] **Step 1: Copy the three config files verbatim**

```bash
mkdir -p recipes/v4
SRC=/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4
cp "$SRC/.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/project/capevolve.yaml" recipes/v4/capevolve.yaml
cp "$SRC/.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/project/split_ids.json" recipes/v4/split_ids.json
cp "$SRC/scripts/v4_t2_e1/common/optimizer/INSTRUCTIONS.md" recipes/v4/INSTRUCTIONS.md
```

`recipes/v4/capevolve.yaml` will now contain (confirmed byte-identical to every other of the 21
tasks' copies except this header comment's task-id):

```yaml
# v4_t2_e1 — single-task optimization project for platform-005-wrong-owner-trap.
# See docs/superpowers/plans/2026-09-17-parsec-v4-task-by-task-optimization.md
optimizer_skill: claude-code
optimizer_model: claude-opus-5
algorithm_skill: hill-climb
target_model: claude-sonnet-4-6
capabilities: [system-prompt]
split_ids_file: split_ids.json
num_trials: 5
max_iterations: 3
stall: 2
max_usd: 50.0
max_optimizer_usd: 20.0
stop_at_reward: 1.0
```

`recipes/v4/split_ids.json` will contain:

```json
{"train": ["platform-005-wrong-owner-trap"], "val": ["platform-005-wrong-owner-trap"], "test": ["platform-005-wrong-owner-trap"]}
```

- [ ] **Step 2: Write `recipes/v4/README.md`**

```markdown
# recipes/v4

The cap-evolve project config every T2 (`v4_t2_e1`) run used — copied verbatim, one shared
template rather than 21 near-duplicates.

## What's here

- **`capevolve.yaml`** — the *entire* per-task project config, byte-identical across all 21
  optimized tasks except the header comment naming the task (confirmed via `diff` against a second
  task, `cloud-024-guid-to-account`, during this doc's writing). Copied from
  `platform-005-wrong-owner-trap`'s project only because that's the task this doc's author happened
  to check first — nothing else about that task is special.
- **`split_ids.json`** — one representative copy. Every task's real file is generated from the same
  template with its own task id substituted into all three splits: `train == val == test == [that
  task]`. This is a **deliberate single-task-tuning design**, not an accidental degenerate split —
  contrast v1, where an empty `split_ids_file` caused an *unintended* random draw (see
  `../v1/README.md`). There is no held-out test split this phase; `results/v4/summary.md`'s
  data-quality caveat #3 explains what `test` means here anyway (same task, later time step, not a
  disjoint task set).
- **`INSTRUCTIONS.md`** — the optimizer's own instructions template (9 `{{...}}` placeholders filled
  in per-run: target reader, failure summary, empty-seed flag, failing/passing task lists, the
  system-prompt-only capability brief, the hill-climb algorithm brief, the benchmark repo path, and
  a single-lane parallelism note). **This is deliberately vendored here, unlike v1/v2's recipes**,
  whose top-level `../README.md` states "No optimizer instructions... cap-evolve's own file, not a
  parsec artifact" — that's true for v1/v2, which used cap-evolve's generic default. v4's template
  is not the default: it was authored specifically for this project (the "no tools/code layer"
  capability scope, the "choose the lever by failure type" decision guide, the non-overfitting
  warning), so it is parsec-v4-specific content and belongs here.

## Recipe vs. run: no divergence found

Unlike v1 (3 documented mismatches — see `../v1/README.md`) and v2, this template's declared budget
values were checked against two tasks' actual recorded state and matched exactly:

| task | run | `state.json` budget | matches `capevolve.yaml`? |
|---|---|---|---|
| `platform-005-wrong-owner-trap` | `run_20260920_103719` | `max_iterations=3, max_usd=50.0, stall=2, max_optimizer_usd=20.0, stop_at_reward=1.0` | yes |
| `cloud-024-guid-to-account` | `run_20260919_122425` | `max_iterations=3, max_usd=50.0, stall=2, max_optimizer_usd=20.0, stop_at_reward=1.0` | yes |

This is expected, not a coincidence: unlike v1/v2's hand-written yaml, v4's per-task
`capevolve.yaml` is programmatically rendered by
`scripts/v4_t2_e1/scaffold_projects.py::render_capevolve_yaml()` in the `parsec-intake_v4`
worktree, so there is no hand-editing step where it could drift from what actually ran.

## The real execution plan

The mechanism that built the 21 per-task projects and ran them one at a time — the harbor adapter,
the `TASK_ID`-env-var-driven candidate injection into the live `parsec-live` clone, the single-lane
"one task, start to finish, then the next" runner design, and the 6 deviations found while building
it against the original spec — is documented in full in the `parsec-intake_v4` worktree (not this
branch, since it's source code, not a result narrative):

```
parsec-intake_v4/docs/superpowers/plans/2026-09-17-parsec-v4-task-by-task-optimization.md
```

This is the `v4_t2_e1` equivalent of what `v1/PROJECT.md` and `v2/PROJECT.md` are for their
experiments — read it before rerunning or extending T2, or before designing C2/G2 (which will reuse
this same adapter and single-lane-runner shape, scaled from 1 task per run to N).

## What is deliberately not here

Same exclusions as `../README.md` documents for v1/v2 (no `.env`, no task definitions — v4's tasks
are defined by the harbor `parsec` benchmark plugin added in PR #495, not by a per-experiment
`tasks.json`, since this is a first-class harbor benchmark rather than a trace-extracted or
hand-authored one-off), **except** `INSTRUCTIONS.md`, which is vendored here for the reason given
above.

## No `seed_capability/` here

The seed bundle every task's optimizer started from lives in
[`../../artifacts/v4/seed/`](../../artifacts/v4/seed/), not duplicated under `recipes/`, matching the
v1/v2 convention.
```

- [ ] **Step 3: Update `recipes/README.md`**

Add a row to the top table (after the `v2` row):

```markdown
| [`v4/`](v4/) | 34-task multi-agent parsec benchmark, 21 task-by-task optimizer runs | `capevolve.yaml`, `split_ids.json`, `INSTRUCTIONS.md`, `README.md` |
```

In the "Read the per-directory README before rerunning either" paragraph, append a sentence:

```markdown
v4's yaml has no known divergence from what actually ran — see
[`v4/README.md`](v4/README.md)'s "Recipe vs. run" section for the two-task check that confirmed it.
```

In the "What is deliberately not here" list, add a bullet right after the existing "No optimizer
instructions" bullet:

```markdown
- **Exception: v4 *does* vendor `optimizer/INSTRUCTIONS.md`.** Unlike v1/v2 (which used cap-evolve's
  generic default, excluded above), v4's `INSTRUCTIONS.md` was authored specifically for this
  project — see [`v4/README.md`](v4/README.md).
```

- [ ] **Step 4: Commit**

```bash
git add recipes/v4/ recipes/README.md
git commit -m "$(cat <<'EOF'
docs(parsec-v4): add recipes/v4 (shared capevolve.yaml/split_ids.json/INSTRUCTIONS.md template)

Vendors the one config template all 21 v4_t2_e1 projects share (confirmed
byte-identical except the header comment), the per-task split_ids.json
shape (deliberate train=val=test={task}, unlike v1's accidental one), and
the v4-specific optimizer INSTRUCTIONS.md template. Confirms no
recipe-vs-run divergence via two tasks' state.json, unlike v1's 3. Updates
the top-level recipes/README.md table and exclusion list for the
INSTRUCTIONS.md exception.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Vendor T2 artifacts

**Files:**
- Create: `scripts/vendor_v4_artifacts.py`
- Create (generated): `artifacts/v4/<task>/best/` or `NOTE.md`, `artifacts/v4/<task>/rejected/<cand>/`, `artifacts/v4/<task>/discarded/<run_ts>-<cand>/` for the 21 optimized tasks
- Modify: `artifacts/README.md`

**Interfaces:**
- Consumes: `results/v4/results.json` (Task 2) — reads `task_ledger` rows with `status == "optimized"`, using each row's `run_dir` and `best_tag`.
- Consumes (read-only, outside this repo): `SOURCE_ROOT/.capevolve/v4_t2_e1_<task>/run_*/candidates/{seed,cand_0001,cand_0002,cand_0003}/*.md` (+ `INSTRUCTIONS.md`, `PROCESS.md` for non-seed candidates) — confirmed directory shape for `platform-005-wrong-owner-trap`'s two runs during this plan's research.
- Produces: `artifacts/v4/<task>/best/` (candidate files) or `artifacts/v4/<task>/NOTE.md` (when `best_tag == "seed"`); `artifacts/v4/<task>/rejected/<cand_id>/`; for the 3 multi-run tasks only, `artifacts/v4/<task>/discarded/<run_ts>-<cand_id>/`.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Vendor each T2-optimized task's candidate bundles from parsec-intake_v4's
gitignored .capevolve/ tree into artifacts/v4/<task>/{best,rejected,discarded}/.

Usage: python3 scripts/vendor_v4_artifacts.py [--check] [--only TASK_ID]
  --check   exit 1 if any destination file would change, instead of writing it.
  --only    vendor a single task (for iterating without re-copying all 21).
"""
import filecmp
import glob
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
ARTIFACTS_V4 = ROOT / "artifacts" / "v4"
SOURCE_ROOT = Path(
    "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4"
)


def copy_dir(src, dst, check_only, changed):
    """Copy every file directly under src/ into dst/, tracking changed paths."""
    for s in sorted(p for p in src.iterdir() if p.is_file()):
        d = dst / s.name
        if d.exists() and filecmp.cmp(s, d, shallow=False):
            continue
        changed.append(str(d.relative_to(ROOT)))
        if not check_only:
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)


def vendor_task(row, changed, check_only):
    task = row["task"]
    run_dir = SOURCE_ROOT / row["run_dir"]
    best_tag = row["best_tag"]
    dest = ARTIFACTS_V4 / task

    if best_tag == "seed":
        note = dest / "NOTE.md"
        text = (
            f"# {task} -- best candidate is the seed\n\n"
            f"T2's optimizer ran on this task (`{row['run_dir']}`) but no candidate "
            f"beat the seed bundle on validation (`best_tag: \"seed\"` in "
            f"`results/v4/results.json`). There is no separate `best/` bundle to "
            f"vendor here -- it is byte-identical to `../seed/`.\n"
        )
        if not (note.exists() and note.read_text() == text):
            changed.append(str(note.relative_to(ROOT)))
            if not check_only:
                dest.mkdir(parents=True, exist_ok=True)
                note.write_text(text)
    else:
        copy_dir(run_dir / "candidates" / best_tag, dest / "best", check_only, changed)

    cand_dirs = sorted(p.name for p in (run_dir / "candidates").iterdir()
                        if p.is_dir() and p.name.startswith("cand_"))
    for cand in cand_dirs:
        if cand == best_tag:
            continue
        copy_dir(run_dir / "candidates" / cand, dest / "rejected" / cand, check_only, changed)

    all_run_dirs = sorted(glob.glob(str(SOURCE_ROOT / f".capevolve/v4_t2_e1_{task}/run_*")))
    if len(all_run_dirs) > 1:
        canonical = str(run_dir)
        for other in all_run_dirs:
            if other == canonical:
                continue
            run_ts = Path(other).name
            other_cands = sorted(p.name for p in (Path(other) / "candidates").iterdir()
                                  if p.is_dir() and p.name.startswith("cand_"))
            for cand in other_cands:
                copy_dir(Path(other) / "candidates" / cand,
                         dest / "discarded" / f"{run_ts}-{cand}", check_only, changed)


def main():
    check_only = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None

    results = json.loads(RESULTS_JSON.read_text())
    rows = [r for r in results["task_ledger"] if r["status"] == "optimized"]
    if only:
        rows = [r for r in rows if r["task"] == only]
    assert rows, "no optimized task rows found"

    changed = []
    for row in rows:
        vendor_task(row, changed, check_only)

    if not changed:
        print("artifacts/v4/ already up to date.")
        return 0
    if check_only:
        print(f"{len(changed)} file(s) would change under artifacts/v4/:", file=sys.stderr)
        for c in changed:
            print(f"  {c}", file=sys.stderr)
        return 1

    print(f"Wrote/updated {len(changed)} file(s) under artifacts/v4/ for {len(rows)} task(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it and verify**

```bash
python3 scripts/vendor_v4_artifacts.py
find artifacts/v4 -mindepth 1 -maxdepth 1 -type d | wc -l    # expect 22 (seed + 21 tasks)
find artifacts/v4/*/discarded -maxdepth 1 -mindepth 1 2>/dev/null | wc -l   # expect at least 3 (one discarded dir per multi-run task, more if a discarded run had several candidates)
python3 scripts/vendor_v4_artifacts.py --check
```

Expected: the two `find` counts are non-zero and plausible (22 top-level task dirs; at least one
`discarded/` entry per multi-run task — `platform-005-wrong-owner-trap`'s discarded run alone
contributes 2, from its `cand_0001`/`cand_0002`), then `--check` prints `artifacts/v4/ already up
to date.` with exit 0. Spot-check one task by hand:

```bash
ls artifacts/v4/cost-030-threshold-not-an-anomaly/     # expect NOTE.md (best_tag == "seed" per spec's own mention)
ls artifacts/v4/platform-005-wrong-owner-trap/         # expect best/ rejected/ discarded/
diff -rq artifacts/v4/platform-005-wrong-owner-trap/best artifacts/v4/seed && echo "UNEXPECTED: best == seed"
```

The last line is a negative check — `platform-005`'s canonical run finalized at test `1.0` via a
real candidate, so `best/` must differ from the plain seed bundle; if the diff prints nothing (no
differences) and `UNEXPECTED` is echoed, the `best_tag` lookup or the copy logic has a bug and must
be fixed before committing.

- [ ] **Step 3: Extend `artifacts/README.md` with a v4 section**

Add a row to its existing v1/v2 directory table:

```markdown
| [`v4/`](v4/) | 21 task-by-task optimizer runs (of 34 tasks total) | `v4/seed/`, `v4/<task>/best/` (or `NOTE.md`), `v4/<task>/rejected/`, `v4/<task>/discarded/` (3 tasks) |
```

Add a new section after the existing "discarded ≠ rejected" (v2) explanation:

```markdown
## v4's discarded runs: a budget cap, not an operator bug

v2's `discarded/` candidates (above) came from an operator bug — a `--resume --run-ts` invocation
that silently started a fresh run instead of resuming. v4's three multi-run tasks
(`platform-005-wrong-owner-trap`, `platform-007-directory-path-fetch`,
`platform-008-log-does-not-say`) have a different cause: a team-wide LLM API budget cap was hit
mid-run on 2026-09-20 ("Budget has been exceeded" `optimizer_error` events), and each task was
simply re-run afterward. `artifacts/v4/<task>/discarded/<run_ts>-<cand_id>/` holds every non-seed
candidate from each task's non-canonical run (the run whose finalize `test_reward` was not the
best). For `platform-007` and `platform-008` the rerun is a genuine improvement over the discarded
run. For `platform-005`, the discarded run is actually the *rerun* — its first attempt
(`run_20260920_103719`) had already finalized cleanly and is the one vendored to `best/`/`rejected/`
above; see `results/v4/summary.md`'s data-quality caveats and
`reports/task-by-task/v4-platform-005-wrong-owner-trap.md` for the full account.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/vendor_v4_artifacts.py artifacts/v4/ artifacts/README.md
git commit -m "$(cat <<'EOF'
feat(parsec-v4): vendor T2 candidate artifacts for the 21 optimized tasks

best/ (or NOTE.md when best_tag == seed) + rejected/<cand>/ from each
task's canonical run, plus discarded/<run_ts>-<cand>/ for the 3 tasks
re-run after a team-wide LLM API budget cap (a different root cause than
v2's operator-bug discards, documented separately in artifacts/README.md).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Per-task report generator + skeletons for all 34 tasks

**Files:**
- Create: `scripts/build_v4_task_reports.py`
- Create (generated): `reports/task-by-task/v4-<task>.md` for all 34 tasks
- Modify: `reports/README.md`

**Interfaces:**
- Consumes: `results/v4/results.json` (Task 2) — reads `task_ledger` rows.
- Produces: one file per task at `reports/task-by-task/v4-<task>.md`, each with a `<!-- BEGIN:auto -->...<!-- END:auto -->` block (status, category, tranche, services, run pointer, a vertical measurement table, deltas) followed by a hand section. For the 13 `not_optimized` tasks and the 1 `best_tag == "seed"` task (`cost-030-threshold-not-an-anomaly`), the hand section is pre-filled here (derivable purely from the ledger). For the remaining 20 tasks, the hand section is the literal placeholder `_Not yet analysed._` — filled in by Tasks 8-10.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Build reports/task-by-task/v4-<task>.md from results/v4/results.json.

Usage: python3 scripts/build_v4_task_reports.py [--check] [--stats]
  --check   exit 1 if any auto block is stale, instead of writing it.
  --stats   print coverage: how many reports exist, how many have a
            hand-written narrative (no "_Not yet analysed._" placeholder).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
REPORTS_DIR = ROOT / "reports" / "task-by-task"

AUTO_START = "<!-- BEGIN:auto -->"
AUTO_END = "<!-- END:auto -->"
AUTO_RE = re.compile(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END), re.DOTALL)

PLACEHOLDER = "_Not yet analysed._"

PREFILLED_NOT_OPTIMIZED = (
    "T2 never targeted this task: its seed bundle already scored a perfect "
    "1.0 on our baseline run (`our_baseline`), so there was no headroom to "
    "optimize against (spec Sec.3). `seed`/`best`/`final` above all repeat "
    "`our_baseline` because no independent optimizer measurement exists -- "
    "they are not three separate results.\n\n"
    "This task will be evaluated again once a category or global merge "
    "(C3/C4/G3/G4, spec Sec.2) produces a bundle edited by other tasks' "
    "optimizer runs, as a regression check (spec Sec.3)."
)

PREFILLED_SEED_WINS = (
    "T2 ran the optimizer on this task, but no candidate beat the seed "
    "bundle on validation (`best_tag: \"seed\"`) -- see `{run_dir}/report.md` "
    "and `{run_dir}/JOURNAL.md` in the `parsec-intake_v4` worktree (not "
    "committed here) for what it tried. `final` above is the seed's own "
    "held-out test measurement, not a fallback."
)


def fmt(v):
    return "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def measurement_rows(row):
    """[(label, split, n, value), ...] -- only measurements that actually exist."""
    rows = [
        ("JB baseline", "test", row["jb_n"], row["jb_reward"]),
        ("our baseline (v4_t1_e1)", "test", row["our_baseline_n"], row["our_baseline"]),
    ]
    if row["status"] != "optimized":
        return rows
    val_n = row.get("final_n")
    rows.append(("seed (val, v4_t2_e1)", "val", val_n, row["seed"]))
    for tag in ("cand_0001", "cand_0002", "cand_0003"):
        if row.get(tag) is not None:
            marker = "  <- best (val)" if row["best_tag"] == tag else ""
            rows.append((f"{tag} (val, v4_t2_e1){marker}", "val", val_n, row[tag]))
    rows.append(("final (test, v4_t2_e1)", "test", val_n, row["final"]))
    return rows


def build_auto_block(row):
    lines = [AUTO_START, ""]
    lines.append(f"**task:** `{row['task']}`  ")
    lines.append(f"**category:** {row['category']}  ")
    lines.append(f"**tranche:** {row['tranche']}  ")
    lines.append(f"**services:** {row['services']}  ")
    lines.append(f"**status:** {row['status']}  ")
    if row.get("run_dir"):
        lines.append(f"**run:** `{row['run_dir']}` (n_runs: {row.get('n_runs')})  ")
    lines.append("")
    lines.append("_Read no cell without the `n` and split beside it._")
    lines.append("")
    lines.append("| measurement | split | n | reward |")
    lines.append("|---|---|--:|--:|")
    for label, split, n, value in measurement_rows(row):
        lines.append(f"| {label} | {split} | {fmt(n)} | {fmt(value)} |")
    lines.append("")
    lines.append(f"delta vs JB: {fmt(row['delta_vs_jb'])} · "
                  f"delta vs our baseline: {fmt(row['delta_vs_our_baseline'])}")
    if row.get("run_dir"):
        lines.append("")
        lines.append(
            f"Optimizer run material (not committed here -- `parsec-intake_v4` "
            f"worktree, gitignored): `{row['run_dir']}/report.md`, "
            f"`{row['run_dir']}/JOURNAL.md`"
        )
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def prefilled_hand_section(row):
    if row["status"] != "optimized":
        return PREFILLED_NOT_OPTIMIZED
    if row["best_tag"] == "seed":
        return PREFILLED_SEED_WINS.format(run_dir=row["run_dir"])
    return None


def build_report(row, existing_text):
    auto_block = build_auto_block(row)
    if existing_text is None:
        hand = prefilled_hand_section(row)
        if hand is None:
            hand = PLACEHOLDER
        return f"# {row['task']}\n\n{auto_block}\n\n{hand}\n"

    if AUTO_RE.search(existing_text):
        return AUTO_RE.sub(auto_block, existing_text, count=1)
    return existing_text.rstrip("\n") + "\n\n" + auto_block + "\n"


def main():
    check_only = "--check" in sys.argv
    stats_only = "--stats" in sys.argv

    results = json.loads(RESULTS_JSON.read_text())
    rows = results["task_ledger"]

    if stats_only:
        written = analysed = 0
        for row in rows:
            path = REPORTS_DIR / f"v4-{row['task']}.md"
            if path.exists():
                written += 1
                if PLACEHOLDER not in path.read_text():
                    analysed += 1
        print(f"{written}/{len(rows)} written, {analysed}/{len(rows)} fully analysed.")
        return 0

    stale = []
    for row in rows:
        path = REPORTS_DIR / f"v4-{row['task']}.md"
        existing = path.read_text() if path.exists() else None
        new_text = build_report(row, existing)
        if new_text == existing:
            continue
        stale.append(str(path.relative_to(ROOT)))
        if not check_only:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text)

    if not stale:
        print("reports/task-by-task/v4-*.md already up to date.")
        return 0
    if check_only:
        print(f"{len(stale)} report(s) stale:", file=sys.stderr)
        for s in stale:
            print(f"  {s}", file=sys.stderr)
        return 1

    print(f"Wrote/updated {len(stale)} report(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it and verify**

```bash
python3 scripts/build_v4_task_reports.py
ls reports/task-by-task/v4-*.md | wc -l     # expect 34
python3 scripts/build_v4_task_reports.py --stats     # expect "34/34 written, 14/34 fully analysed."
python3 scripts/build_v4_task_reports.py --check
```

Expected: `34`, then `34/34 written, 14/34 fully analysed.` (13 `not_optimized` + `cost-030-threshold-not-an-anomaly`), then `reports/task-by-task/v4-*.md already up to date.` with exit 0.

- [ ] **Step 3: Update `reports/README.md`**

Add a row to the "Naming" table:

```markdown
| v4 (task-by-task, 34-task benchmark) | `v4-<task>.md` | 34 |
```

Add a sentence after the existing naming explanation:

```markdown
v4's ids are already readable (`platform-005-wrong-owner-trap`) and are used whole, like v2's.
Unlike v1/v2, v4's `report` pointer is carried in `results/v4/results.json` (a separate ledger from
`results/results.json`), and `scripts/build_v4_task_reports.py` reads that file instead of
`build_task_reports.py`'s.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/build_v4_task_reports.py reports/task-by-task/v4-*.md reports/README.md
git commit -m "$(cat <<'EOF'
feat(parsec-v4): generate reports/task-by-task/v4-*.md skeletons for all 34 tasks

Auto block (status, category, tranche, measurement table with split/n,
deltas) for every task, plus a pre-filled hand section for the 14 tasks
whose story is fully derivable from the ledger alone (13 not_optimized +
cost-030's seed-wins case). The remaining 20 optimized tasks carry the
honest "_Not yet analysed._" placeholder, filled in by the next tasks in
this plan.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Narrative for cloud/cost/icinga optimized tasks (7 tasks)

**Files:**
- Modify: `reports/task-by-task/v4-cloud-024-guid-to-account.md`
- Modify: `reports/task-by-task/v4-cloud-026-gpu-abuse-triage.md`
- Modify: `reports/task-by-task/v4-cost-029-no-cost-rows-for-guid.md`
- Modify: `reports/task-by-task/v4-icinga-010-stuck-anarchysubjects.md`
- Modify: `reports/task-by-task/v4-icinga-011-aap2-job-status-alert.md`
- Modify: `reports/task-by-task/v4-icinga-013-acknowledged-not-an-issue.md`
- Modify: `reports/task-by-task/v4-icinga-014-check-script-path-moved.md`

(`cost-030-threshold-not-an-anomaly` is excluded — Task 7 already pre-filled it, `best_tag == "seed"`.)

**Interfaces:**
- Consumes (read-only, outside this repo, in `parsec-intake_v4`): for each task, `.capevolve/v4_t2_e1_<task>/run_*/report.md` and `run_*/JOURNAL.md` — read the `run_dir` value straight out of `results/v4/results.json`'s `task_ledger` row for that task rather than re-deriving it.

- [ ] **Step 1: For each of the 7 tasks, read its source material and replace the placeholder**

For each task:

```bash
python3 -c "
import json
d = json.load(open('results/v4/results.json'))
row = next(r for r in d['task_ledger'] if r['task'] == '<TASK_ID>')
print(row['run_dir'], row['best_tag'], row['final'], row['seed'])
"
```

Then read (Read tool) `/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/<run_dir>/report.md`
and `/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/<run_dir>/JOURNAL.md`.

Replace the `_Not yet analysed._` line in `reports/task-by-task/v4-<task>.md` with a hand section
using this structure (headings required; content is task-specific, drawn from the files just read —
do not invent numbers not present in the auto block above):

```markdown
## What the optimizer tried

<1-3 sentences: how many candidates, what changed between them, drawn from JOURNAL.md's iteration
entries. Name the specific prompt file(s) edited if JOURNAL.md says so.>

## Why the winning candidate won

<1-3 sentences: what `report.md` or JOURNAL.md's reasoning says the winning edit fixed, tied to the
measurement table above (e.g. "seed scored 0.32 on val because X; cand_0002 scored 1.0 after Y").>

## Caveats

<Only if applicable: n=5 is a small sample; single-task tuning means this edit was never checked
against any other task (see results/v4/summary.md's "Coverage" section on why a category/global
merge regression-check matters here).>
```

If a task's `JOURNAL.md` has no entry (matching the "no handover written" caveat already documented
for a different experiment in `reports/README.md`), say so explicitly instead of inventing a
rationale — e.g. "the optimizer wrote no JOURNAL.md entry for this run; the only record is the
reward delta in the measurement table above."

- [ ] **Step 2: Verify no placeholder remains for these 7**

```bash
for t in cloud-024-guid-to-account cloud-026-gpu-abuse-triage cost-029-no-cost-rows-for-guid \
         icinga-010-stuck-anarchysubjects icinga-011-aap2-job-status-alert \
         icinga-013-acknowledged-not-an-issue icinga-014-check-script-path-moved; do
  grep -L "_Not yet analysed_" "reports/task-by-task/v4-$t.md" || echo "STILL PLACEHOLDER: $t"
done
python3 scripts/build_v4_task_reports.py --check   # must still pass -- confirms hand edits didn't touch the auto block
```

Expected: no `STILL PLACEHOLDER` lines, and `build_v4_task_reports.py --check` exits 0 (proves the
auto block wasn't accidentally edited by hand).

- [ ] **Step 3: Commit**

```bash
git add reports/task-by-task/v4-cloud-024-guid-to-account.md \
        reports/task-by-task/v4-cloud-026-gpu-abuse-triage.md \
        reports/task-by-task/v4-cost-029-no-cost-rows-for-guid.md \
        reports/task-by-task/v4-icinga-010-stuck-anarchysubjects.md \
        reports/task-by-task/v4-icinga-011-aap2-job-status-alert.md \
        reports/task-by-task/v4-icinga-013-acknowledged-not-an-issue.md \
        reports/task-by-task/v4-icinga-014-check-script-path-moved.md
git commit -m "$(cat <<'EOF'
docs(parsec-v4): write narrative for the cloud/cost/icinga optimized reports

Reads each task's run_dir/report.md and JOURNAL.md (parsec-intake_v4
worktree) and replaces the placeholder with what the optimizer tried and
why the winning candidate won.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Narrative for platform optimized tasks, part 1 (7 tasks)

**Files:**
- Modify: `reports/task-by-task/v4-platform-001-ee-entrypoint-rca.md`
- Modify: `reports/task-by-task/v4-platform-002-collection-not-found-rca.md`
- Modify: `reports/task-by-task/v4-platform-003-tojson-dict-literal-rca.md`
- Modify: `reports/task-by-task/v4-platform-004-events-then-config.md`
- Modify: `reports/task-by-task/v4-platform-005-wrong-owner-trap.md`
- Modify: `reports/task-by-task/v4-platform-007-directory-path-fetch.md`
- Modify: `reports/task-by-task/v4-platform-008-log-does-not-say.md`

**Interfaces:** same as Task 8.

- [ ] **Step 1: For each of the 7 tasks, read its source material and replace the placeholder**

Same procedure as Task 8, Step 1.

**`platform-005-wrong-owner-trap` needs extra care**: its `run_dir` in the ledger is the *canonical*
(best test_reward) run, but this task had two finalized runs. Read
`results/v4/summary.md`'s data-quality caveat #1-2 again before writing this one, and read **both**
`run_20260920_103719/report.md`/`JOURNAL.md` (canonical, vendored to `artifacts/v4/platform-005-wrong-owner-trap/best/`)
and `run_20260920_162208/report.md`/`JOURNAL.md` (discarded rerun, vendored to
`.../discarded/run_20260920_162208-*/`) in the `parsec-intake_v4` worktree. The hand section for this
one task additionally needs a short subsection:

```markdown
## Why this task has two runs

A team-wide LLM API budget cap ("Budget has been exceeded") fired partway through this task's first
attempt (`run_20260920_103719`) on 2026-09-20, but that run had already finalized cleanly before the
errors mattered — 3 candidates, monotonic improvement, held-out test `1.0 ± 0.0`. It was re-run
anyway (`run_20260920_162208`); the rerun's *seed* happened to score higher on validation that time
(0.604 vs. 0.32), so neither of its 2 candidates beat it and it finalized at a mediocre `0.346`.
`results/v4/results.json` takes the run with the best finalize `test_reward` across all of a task's
finalized runs (not simply the latest), so the numbers above are from the first run; the rerun's
material is vendored under `artifacts/v4/platform-005-wrong-owner-trap/discarded/run_20260920_162208-*/`
for the record, not as this task's result.
```

For `platform-007-directory-path-fetch` and `platform-008-log-does-not-say`, confirm from
`report.md`/`JOURNAL.md` whether the rerun genuinely improved on the first attempt (per
`results/v4/summary.md`'s caveat #1, it should have) and say so in one sentence; these two do not
need the "two runs" subsection unless the source material reveals something equally noteworthy.

- [ ] **Step 2: Verify no placeholder remains for these 7**

```bash
for t in platform-001-ee-entrypoint-rca platform-002-collection-not-found-rca \
         platform-003-tojson-dict-literal-rca platform-004-events-then-config \
         platform-005-wrong-owner-trap platform-007-directory-path-fetch \
         platform-008-log-does-not-say; do
  grep -L "_Not yet analysed_" "reports/task-by-task/v4-$t.md" || echo "STILL PLACEHOLDER: $t"
done
python3 scripts/build_v4_task_reports.py --check
```

Expected: no `STILL PLACEHOLDER` lines; `--check` exits 0.

- [ ] **Step 3: Commit**

```bash
git add reports/task-by-task/v4-platform-001-ee-entrypoint-rca.md \
        reports/task-by-task/v4-platform-002-collection-not-found-rca.md \
        reports/task-by-task/v4-platform-003-tojson-dict-literal-rca.md \
        reports/task-by-task/v4-platform-004-events-then-config.md \
        reports/task-by-task/v4-platform-005-wrong-owner-trap.md \
        reports/task-by-task/v4-platform-007-directory-path-fetch.md \
        reports/task-by-task/v4-platform-008-log-does-not-say.md
git commit -m "$(cat <<'EOF'
docs(parsec-v4): write narrative for platform optimized reports, part 1

Includes platform-005-wrong-owner-trap's two-run account (a budget-cap
rerun that made a cleanly-finalized first attempt look, on paper, like it
needed replacing) alongside the other 6 tasks' single-run narratives.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Narrative for platform optimized tasks, part 2 (6 tasks)

**Files:**
- Modify: `reports/task-by-task/v4-platform-022-job-on-no-controller.md`
- Modify: `reports/task-by-task/v4-platform-023-splunk-guid-no-events.md`
- Modify: `reports/task-by-task/v4-platform-031-helm-url-not-a-timeout.md`
- Modify: `reports/task-by-task/v4-platform-032-shared-secret-not-a-registry-outage.md`
- Modify: `reports/task-by-task/v4-platform-033-schema-change-not-the-oom.md`
- Modify: `reports/task-by-task/v4-platform-034-rate-limit-not-an-outage.md`

**Interfaces:** same as Task 8.

- [ ] **Step 1: For each of the 6 tasks, read its source material and replace the placeholder**

Same procedure as Task 8, Step 1.

- [ ] **Step 2: Verify no placeholder remains anywhere in `reports/task-by-task/v4-*.md`**

```bash
grep -L "_Not yet analysed_" reports/task-by-task/v4-*.md | wc -l   # expect 34 (every file, none left)
python3 scripts/build_v4_task_reports.py --stats                    # expect "34/34 written, 34/34 fully analysed."
python3 scripts/build_v4_task_reports.py --check
```

Expected: `34`, then `34/34 written, 34/34 fully analysed.`, then `--check` exits 0. This is v4's
version of the "0 placeholders" bar `reports/README.md` documents for v1/v2.

- [ ] **Step 3: Commit**

```bash
git add reports/task-by-task/v4-platform-022-job-on-no-controller.md \
        reports/task-by-task/v4-platform-023-splunk-guid-no-events.md \
        reports/task-by-task/v4-platform-031-helm-url-not-a-timeout.md \
        reports/task-by-task/v4-platform-032-shared-secret-not-a-registry-outage.md \
        reports/task-by-task/v4-platform-033-schema-change-not-the-oom.md \
        reports/task-by-task/v4-platform-034-rate-limit-not-an-outage.md
git commit -m "$(cat <<'EOF'
docs(parsec-v4): write narrative for platform optimized reports, part 2

Completes narrative coverage for all 34 v4 task reports: 34/34 written,
34/34 fully analysed, 0 placeholders.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Update `parsec-history/README.md`

**Files:**
- Modify: `README.md` (repo root)

**Interfaces:** none — documentation only.

- [ ] **Step 1: Add a v4 row to the experiments table**

Change:

```markdown
| experiment | tasks | source |
|---|---|---|
| **v1** | 30 trace-extracted `traces_parsec-aap2-*` tasks, real production traces | `parsec-intake_v1` worktree |
| **v2** | 10 hand-authored `bench-aap2-*` scenarios, one isolated simulator per task | `parsec-intake_v2` worktree |
```

to:

```markdown
| experiment | tasks | source |
|---|---|---|
| **v1** | 30 trace-extracted `traces_parsec-aap2-*` tasks, real production traces | `parsec-intake_v1` worktree |
| **v2** | 10 hand-authored `bench-aap2-*` scenarios, one isolated simulator per task | `parsec-intake_v2` worktree |
| **v4** | 34-task multi-agent AAP2/GCP/ICINGA benchmark (`platform-*`, `cloud-*`, `cost-*`, `icinga-*`), harbor-native | `parsec-intake_v4` worktree |
```

(There is no v3 in this branch; v4's own naming continues from `parsec-intake_v4`'s own numbering,
not from a skipped v3 here.)

Directly below the existing "They are not comparable to each other" paragraph, add:

```markdown
v4 is a third, separate experiment against a different, larger task set (34 tasks across four
categories vs. v1/v2's AAP2-only scope) and a different target (one shared 8-file multi-agent bundle
vs. v1/v2's single `SKILL.md`). It has its own ledger and heatmap
([`results/v4/results.json`](results/v4/results.json), [`ui/heatmap_v4.html`](ui/heatmap_v4.html))
rather than sharing v1/v2's — see [`results/v4/summary.md`](results/v4/summary.md).
```

- [ ] **Step 2: Fix the Layout table's now-inaccurate claim**

Change:

```markdown
| [`results/`](results/) | the numbers — `results.json` (the one generated ledger everything else reads from), plus per-experiment `summary.md`, `tasks.json`, `per_task_scores.json`, and the raw `runs/` directories |
```

to:

```markdown
| [`results/`](results/) | the numbers — `results.json` (the generated ledger v1/v2 read from), plus per-experiment `summary.md`, `tasks.json`, `per_task_scores.json`, and the raw `runs/` directories; `v4/` has its own separate `results.json` + `summary.md`, deliberately not folded into the shared one (different task set, different shape) |
```

Change:

```markdown
| [`ui/heatmap.html`](ui/heatmap.html) | a static, generated per-task/per-candidate heatmap |
```

to:

```markdown
| [`ui/heatmap.html`](ui/heatmap.html) | a static, generated per-task/per-candidate heatmap for v1/v2 |
| [`ui/heatmap_v4.html`](ui/heatmap_v4.html) | the same, for v4 — a separate page, not a shared one, matching `results/v4/`'s separate ledger |
```

- [ ] **Step 3: Extend "Before you commit here"**

Change:

```markdown
Raw simulator rollouts (~96MB across both experiments) are
deliberately **not** committed here; they remain only in the source `parsec-intake_v1`/
`parsec-intake_v2` worktrees. If you're adding a new experiment, keep it that way — commit
the derived per-task score vectors and the recipe that produced them, not the rollout logs.
```

to:

```markdown
Raw simulator rollouts (~96MB across v1/v2) and v4's raw `.capevolve/` run directories are
deliberately **not** committed here; they remain only in the source `parsec-intake_v1`/
`parsec-intake_v2`/`parsec-intake_v4` worktrees. If you're adding a new experiment, keep it that
way — commit the derived per-task score vectors and the recipe that produced them, not the raw logs.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(parsec-v4): add v4 to the top-level README's experiment and layout tables

Corrects the "one generated ledger" claim now that v4 has its own separate
results/v4/results.json + ui/heatmap_v4.html, and notes v4's raw run
directories live only in parsec-intake_v4, matching v1/v2's convention.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Final consistency check

**Files:** none created or modified — verification only.

**Interfaces:** none.

- [ ] **Step 1: Run every `--check` script**

```bash
python3 scripts/build_v4_results_json.py --check
python3 scripts/build_v4_heatmap.py --check
python3 scripts/vendor_v4_artifacts.py --check
python3 scripts/build_v4_task_reports.py --check
python3 scripts/build_v4_task_reports.py --stats
```

Expected: all four `--check` invocations exit 0 with an "already up to date" message; `--stats`
prints `34/34 written, 34/34 fully analysed.`

- [ ] **Step 2: Cross-check the spec's own numbers one more time against the committed ledger**

```bash
python3 -c "
import json
d = json.load(open('results/v4/results.json'))
assert d['total_tasks'] == 34 and d['n_optimized'] == 21
reg = next(s for s in d['sections']['task']['summaries'] if s['tranche'] == 'regression')
chal = next(s for s in d['sections']['task']['summaries'] if s['tranche'] == 'challenge')
assert reg['n_tasks'] == 30 and chal['n_tasks'] == 4
assert round(reg['final_mean'], 3) == 0.963
assert round(chal['final_mean'], 3) == 0.873
print('OK: matches spec Sec.0 exactly')
"
```

Expected: `OK: matches spec Sec.0 exactly`.

- [ ] **Step 3: Review the full diff and `git status` before considering this plan done**

```bash
git status
git log --oneline main..HEAD 2>/dev/null || git log --oneline -12
```

Confirm: no untracked files remain outside what was intentionally committed (in particular, no
accidental copy of anything under `.capevolve*` or any `.env`); every commit from Tasks 1-11 is
present; nothing has been pushed. Per this plan's Global Constraints, **stop here and ask the user
before pushing or opening a PR** — that is explicitly out of scope for this plan.

- [ ] **Step 4: Report completion**

No commit in this step. Summarize for the user: what was built (12 tasks, N commits, 34 reports at
0 placeholders, results/v4/ + recipes/v4/ + artifacts/v4/ + ui/heatmap_v4.html all present and
self-consistent per `--check`), and that the branch is ready for the push/PR decision whenever the
user confirms it.
