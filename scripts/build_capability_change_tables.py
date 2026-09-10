#!/usr/bin/env python3
"""Extract per-(task, skill) capability-change classification vs seed, for every
task whose accepted best candidate differs from seed, across the c1-c5/v2
worktrees. Emits Table D (granular) and Table E (skill-level rollup) as
markdown, matching the sections appended to insights/SKILLS_TASKS_MAP.md.

Usage:
    python3 build_capability_change_tables.py --root <dir containing worktrees>
        --heatmap <path to heatmap.html>
"""
import argparse
import json
import os
import re
from pathlib import Path

WORKTREES = [
    "intake_skillbench_c1", "intake_skillbench_c2", "intake_skillbench_c3",
    "intake_skillbench_c4", "intake_skillbench_c5", "intake_skillbench_v2",
]
PROCESS_FILES = {"INSTRUCTIONS.md", "PROCESS.md"}
IGNORE_PATTERNS = (re.compile(r"__pycache__"), re.compile(r"\.pyc$"))


def parse_heatmap(path: Path):
    text = path.read_text(encoding="utf-8")
    start = text.index("const DATA = [") + len("const DATA = ")
    end = text.index("];", start) + 1
    return json.loads(text[start:end])


def find_run_dirs(root: Path, task: str):
    hits = []
    for w in WORKTREES:
        base = root / w / ".capevolve"
        if not base.is_dir():
            continue
        for name in os.listdir(base):
            if name == f"run_task_{task}" or name.startswith(f"run_task_{task}_"):
                hits.append(base / name)
    return hits


def load_best_score(run_dir: Path):
    for fname in ("final.json", "baseline.json", "state.json"):
        f = run_dir / fname
        if f.exists():
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            for key in ("best", "best_reward"):
                if isinstance(data, dict) and key in data:
                    return data[key]
    return None


def load_best_id(run_dir: Path):
    f = run_dir / "state.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text()).get("best_id")
    except Exception:
        return None


def pick_run_dir(root: Path, task: str, expected_best_tag: str):
    hits = find_run_dirs(root, task)
    if not hits:
        return None, "no run dir found"
    # authoritative: a completed run (state.json present) whose best_id matches
    # heatmap.html's recorded best_tag for this task
    exact = [h for h in hits if load_best_id(h) == expected_best_tag]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        exact.sort(key=lambda h: ("CORRUPTED" in h.name, "BROKEN" in h.name, "KILLED" in h.name))
        return exact[0], None
    if len(hits) == 1:
        return hits[0], None
    # fall back: prefer a completed, non-broken run with a seed dir
    scored = []
    for h in hits:
        if not (h / "candidates" / "seed").is_dir():
            continue
        has_state = load_best_id(h) is not None
        penalty = (0 if has_state else 1,
                   1 if "CORRUPTED" in h.name else 0,
                   1 if "BROKEN" in h.name else 0,
                   1 if "KILLED" in h.name else 0)
        scored.append((penalty, h))
    scored.sort(key=lambda t: t[0])
    return (scored[0][1], None) if scored else (hits[0], "ambiguous, no seed dir to check")


def classify_path(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) == 1 and parts[0] == "SKILL.md":
        return "prompt"
    if "scripts" in parts[:-1] or (rel.endswith(".py") and len(parts) == 1):
        return "tool"
    return "package"


def list_files(pkg_dir: Path):
    out = {}
    if not pkg_dir.is_dir():
        return out
    for p in pkg_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(pkg_dir).as_posix()
        if any(pat.search(rel) for pat in IGNORE_PATTERNS):
            continue
        out[rel] = p
    return out


def diff_skill(seed_pkg: Path, cand_pkg: Path):
    seed_files = list_files(seed_pkg)
    cand_files = list_files(cand_pkg)
    added = set(cand_files) - set(seed_files)
    removed = set(seed_files) - set(cand_files)
    common = set(seed_files) & set(cand_files)
    edited = [r for r in common if seed_files[r].read_bytes() != cand_files[r].read_bytes()]

    counts = {"skill-prompt": 0, "skill-package": 0,
              "tool-added": 0, "tool-deleted": 0, "tool-edited": 0, "other": 0}
    for r in added:
        kind = classify_path(r)
        if kind == "tool":
            counts["tool-added"] += 1
        elif kind == "package":
            counts["skill-package"] += 1
        else:
            counts["other"] += 1
    for r in removed:
        kind = classify_path(r)
        if kind == "tool":
            counts["tool-deleted"] += 1
        elif kind == "package":
            counts["skill-package"] += 1
        else:
            counts["other"] += 1
    for r in edited:
        kind = classify_path(r)
        if kind == "tool":
            counts["tool-edited"] += 1
        elif kind == "prompt":
            counts["skill-prompt"] = 1
        elif kind == "package":
            counts["skill-package"] += 1
        else:
            counts["other"] += 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--heatmap", required=True, type=Path)
    args = ap.parse_args()

    data = parse_heatmap(args.heatmap)
    rows = []
    problems = []

    for d in data:
        if d["best_tag"] == "seed":
            continue
        task = d["task"]
        run_dir, err = pick_run_dir(args.root, task, d["best_tag"])
        if err or run_dir is None:
            problems.append(f"{task}: {err}")
            continue
        cand_dir = run_dir / "candidates" / d["best_tag"]
        seed_dir = run_dir / "candidates" / "seed"
        if not cand_dir.is_dir() or not seed_dir.is_dir():
            problems.append(f"{task}: missing seed/{d['best_tag']} under {run_dir}")
            continue

        seed_skills = {p.name for p in seed_dir.iterdir() if p.is_dir()}
        cand_skills = {p.name for p in cand_dir.iterdir() if p.is_dir()}

        any_row_for_task = False
        for skill in sorted(seed_skills | cand_skills):
            row = {
                "task": task, "skill": skill, "best_candidate": d["best_tag"],
                "val": d["best"], "run_dir": str(run_dir.relative_to(args.root)),
                "skill-added": 0, "skill-deleted": 0,
                "skill-prompt": 0, "skill-package": 0,
                "tool-added": 0, "tool-deleted": 0, "tool-edited": 0, "other": 0,
            }
            if skill not in seed_skills:
                row["skill-added"] = 1
            elif skill not in cand_skills:
                row["skill-deleted"] = 1
            else:
                counts = diff_skill(seed_dir / skill, cand_dir / skill)
                if not any(counts.values()):
                    continue  # this skill's package is byte-identical; not an edited skill
                row.update(counts)
            rows.append(row)
            any_row_for_task = True
        if not any_row_for_task:
            problems.append(
                f"{task}: best_tag={d['best_tag']} (val {d['best']}) in {run_dir.name} "
                "produced no package-level file changes vs seed (score change not attributable "
                "to a skill edit; possibly rollout/eval variance)")

    cols = ["task", "skill", "best_candidate", "val",
            "skill-added", "skill-deleted", "skill-prompt", "skill-package",
            "tool-added", "tool-deleted", "tool-edited", "other"]

    def md_table(rows, cols):
        out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        totals = {c: 0 for c in cols if c not in ("task", "skill", "best_candidate", "val")}
        for r in rows:
            out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
            for c in totals:
                totals[c] += r.get(c, 0)
        total_row = ["**TOTAL**", f"{len({r['skill'] for r in rows})} distinct",
                     f"{len({r['task'] for r in rows})} tasks", ""]
        total_row += [str(totals[c]) for c in cols[4:]]
        out.append("| " + " | ".join(total_row) + " |")
        return "\n".join(out)

    print("""## Capability-change classification (Tables D and E)

For each of the 87 tasks, `ui/heatmap.html`'s `DATA` array names the accepted best candidate
(`best_tag`, `"seed"` if the optimizer never improved on seed). For every task where
`best_tag != "seed"` (52 tasks), this walks that task's run directory across the six
c1-c5/v2 worktrees, diffs `candidates/seed/<skill>/` against `candidates/<best_tag>/<skill>/`
file-by-file (excluding cap-evolve's own `INSTRUCTIONS.md`/`PROCESS.md`), and classifies every
changed file per skill. **Row key is (task, skill)**, not (task, best-candidate) alone: a
task has exactly one accepted candidate, but that one candidate snapshot can touch several skill
packages at once (e.g. `energy-ac-optimal-power-flow`'s `cand_0003` touches both
`ac-branch-pi-model` and `casadi-ipopt-nlp`), so a single task-level row would collapse
independent per-skill changes into one ambiguous line. Best-candidate ID and its val score are
metadata columns on each row, constant across all of a task's rows.

**Disambiguation**: 14 of the 52 changed tasks have more than one `run_task_<id>*` directory
across the six worktrees (reruns, corrupted batches, infra-broken attempts). Each run's
`state.json.best_id` is compared against `heatmap.html`'s recorded `best_tag` for that task; a
unique match is used. Where more than one run matches (`energy-ac-optimal-power-flow`: both its
`v2` and its `v1_CORRUPTED_batch3` run report the same `best_id`), the non-corrupted run is
preferred — for that task this agrees with `heatmap.html`'s own `source: "c2-v2"` field, i.e. it
independently confirms the corrupted run is correctly excluded. **This script does not attempt
to adjudicate `prev`-vs-`curr` for the 7 tasks with a `DATA_C4` rerun entry**
(`crystallographic-wyckoff-position-analysis`, `energy-market-pricing`, `fix-erlang-ssh-cve`,
`flink-query`, `invoice-fraud-detection`, `organize-messy-files`, `shock-analysis-demand`) — it takes whatever
the main `DATA` array already records as authoritative, since several of those reruns are
regressions or fall back to `best_tag: "seed"` rather than uniformly superseding the original
run, so "latest wins" is not a safe blanket rule there. That reconciliation is a separate,
open question from this classification and is not resolved here.

**Columns**: `skill-added`/`skill-deleted` — the whole top-level skill directory is new/missing
relative to seed (blocked once `fixed_vocabulary: true`, per Step 2, ships). `skill-prompt` —
`SKILL.md` content changed (0/1). `skill-package` — count of added/removed/edited non-`SKILL.md`,
non-script package files (`references/*.md`, `forms.md`, etc.). `tool-added`/`tool-deleted`/
`tool-edited` — counts of added/removed/edited files under `scripts/` or a top-level executable
script (e.g. `recalc.py`). `other` — anything unclassified (empty in this data).

One task, `fix-erlang-ssh-cve`, produced zero package-level file changes despite its accepted
candidate scoring above seed (0.6 -> 0.9) — the improvement is not attributable to any skill edit
in this diff; see Unresolved below.

""")
    print("## Table D — per-(task, skill) capability changes, best candidate vs seed\n")
    print(md_table(rows, cols))

    # Table D: rollup by skill
    by_skill = {}
    for r in rows:
        s = by_skill.setdefault(r["skill"], {"tasks": set(), "skill-added": 0, "skill-deleted": 0,
                                              "skill-prompt": 0, "skill-package": 0,
                                              "tool-added": 0, "tool-deleted": 0, "tool-edited": 0,
                                              "other": 0})
        s["tasks"].add(r["task"])
        for c in ("skill-added", "skill-deleted", "skill-prompt", "skill-package",
                  "tool-added", "tool-deleted", "tool-edited", "other"):
            s[c] += r[c]

    VOCAB_VIOLATION_SKILLS = {"fuzzy-match"}

    dcols = ["skill", "tasks touched", "conflict",
             "skill-added", "skill-deleted", "skill-prompt", "skill-package",
             "tool-added", "tool-deleted", "tool-edited", "other"]
    print("\n\n## Table E — skill-level rollup, cross-task conflicts\n")
    out = ["| " + " | ".join(dcols) + " |", "|" + "|".join(["---"] * len(dcols)) + "|"]
    totals = {c: 0 for c in dcols[3:]}
    n_conflict = 0
    for skill, s in sorted(by_skill.items()):
        conflict = len(s["tasks"]) >= 2
        flag = "yes" if conflict else ""
        if skill in VOCAB_VIOLATION_SKILLS:
            flag = (flag + " " if flag else "") + "vocab-violation¹"
            n_conflict += 0 if conflict else 1
        n_conflict += 1 if conflict else 0
        row = [skill, str(len(s["tasks"])), flag]
        row += [str(s[c]) for c in dcols[3:]]
        out.append("| " + " | ".join(row) + " |")
        for c in dcols[3:]:
            totals[c] += s[c]
    total_row = ["**TOTAL**", f"{len(by_skill)} skills", f"{n_conflict} conflicted"]
    total_row += [str(totals[c]) for c in dcols[3:]]
    out.append("| " + " | ".join(total_row) + " |")
    print("\n".join(out))
    print("\n¹ `fuzzy-match` is not a clean cross-task conflict under the DATA-authoritative "
          "source used here (its seed only serves `invoice-fraud-detection`); it is counted with "
          "the conflict set because a separate, since-excluded candidate for "
          "`energy-ac-optimal-power-flow` (the `v1_CORRUPTED_batch3` run, superseded by `v2` in "
          "`heatmap.html`'s own `source` field) invented an out-of-vocabulary `fuzzy-match` "
          "package — see `evidence/energy-ac-optimal-power-flow-vocabulary-violation/`. This is the "
          "6th skill in the plan's original \"6 skills edited under 2+ tasks\" count: 5 clean "
          "conflicts (`dc-power-flow`, `economic-dispatch`, `pdf`, `power-flow-data`, `xlsx`) plus "
          "this one vocabulary-violation case.")

    print("\n\n## Provenance — conflicted / vocab-violation skills\n")
    prov_skills = sorted(s for s, v in by_skill.items()
                          if len(v["tasks"]) >= 2 or s in VOCAB_VIOLATION_SKILLS)
    for skill in prov_skills:
        print(f"\n**{skill}**")
        for r in rows:
            if r["skill"] == skill:
                print(f"- `{r['task']}` -> `{r['run_dir']}` / `{r['best_candidate']}` (val {r['val']})")
        if skill in VOCAB_VIOLATION_SKILLS:
            print("- `energy-ac-optimal-power-flow` (excluded) -> "
                  "`intake_skillbench_c2/.capevolve/run_task_energy-ac-optimal-power-flow_v1_CORRUPTED_batch3` "
                  "/ `cand_0002`/`cand_0003` — out-of-vocabulary, superseded by `v2` in `heatmap.html`")

    if problems:
        print("\n\n## Unresolved\n")
        for p in problems:
            print(f"- {p}")


if __name__ == "__main__":
    main()
