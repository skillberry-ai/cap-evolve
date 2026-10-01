# Issue #606: reader-profile experiment — implementation and run plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Find out, with the fewest CI runs, whether the optimizer's reader block ("THE READER") changes what hill-climb produces for Gemma-4-31B-It on SpreadsheetBench. Then measure how large the effect is and in which direction.

**Architecture:** All code lives on the temp branch `exp/606-reader-profile`, which is never merged. It adds five things:
- a verbatim reader-block file mode;
- a `reader_variant` dispatch input;
- a `full_verified_probe` tier (same train/val as `full_verified`, test = a fixed 100-task subset);
- seed reuse from a frozen copy of the saved `full_verified` slot, filtered to the subset;
- a report script that writes the per-run numbers the issue asks for.

Each run is one `workflow_dispatch` on that branch, pinned to skillberry-1. Every run, decision and result is posted as a comment on #606.

**Tech Stack:** GitHub Actions (`benchmarks.yml`), bash (`run_suite.sh`, `ci_setup.sh`), Python 3 (`core/cap_evolve`, `ci/benchmarks/spreadsheetbench/utils`), pytest.

**Spec:** GitHub issue #606 (body as of 2026-09-30), plus #538 for the baseline runs. The facts below were checked against `origin/main` at `f0a14e39` and against skillberry-1 on 2026-09-30.

## Facts this plan depends on (verified 2026-09-30)

| fact | where |
|---|---|
| The #538 runs used `ALGORITHM=hill-climb-all`, `ITERATIONS=5`, `GATE_K_SE=0.2`, `OPTIMIZER_MODEL=ibm-ete-int/aws/claude-opus-5` | logs of runs 36466624841, 36523096755, 36622615059 |
| The gateway serves `ibm-ete-int/aws/claude-opus-5-5` ("newly served" at 08:24 UTC). It is not yet in the `main` dropdown. | sync-model-lists run 36689426883 |
| The saved slot `/home/skillberry/.cache/capevolve-latest/spreadsheetbench` holds run 36622615059: tier `full_verified`, `empty_seed=1`, `reward_metric=hard_no_recalc`, splits 80/40/280, `final.json` `seed.test` reward 0.43478 with 280 per-task rows | skillberry-1 |
| Two runners have the `ibm-vpc` label: `skillberry-1` (online) and `skillberry-2` (offline). The bench job uses `runs-on: [self-hosted, ibm-vpc]`. | `gh api .../actions/runners`, `benchmarks.yml:364` |
| The bench concurrency group is `benchmarks-<tier>-<bench>-<ref>` with `cancel-in-progress: false`. GitHub keeps only one pending run per group, so a third dispatch on the same branch cancels the second. | `benchmarks.yml:380-382` |
| CI writes `target_model: $AGENT_MODEL_WIRE` into `capevolve.yaml` and never writes `target_profile_file` | `run_suite.sh:1044` |
| The hill-climb path reads `target_profile_file` (`cli.py:990` → `OptimizerContext.from_args`, `harness.py:3863`). `from_spec` (agent-optimize) ignores it, but this experiment does not use agent-optimize. | code |
| `resolve()` silently keeps the built-in brief when the profile file is missing. `reader_block()` always prints "read by `<model>` — capability tier". Variant R needs a code change. | `target_profile.py:140-150, 157-167` |
| The profile reaches the optimizer only through `{{TARGET_READER}}`. `check.py` uses the tier only for a non-blocking note. | grep |
| The seed-reuse check refuses on a different tier name, a different `empty_seed`, or any split that is not exactly equal | `run_suite.sh:1007-1028` |
| `rescore_run.py` rebuilds `final.json` `seed.test` from the stored `per_task` list when no seed test rollouts exist, using `aggregate_scores` | `rescore_run.py:66-124` |
| `dataset.json` has `instruction_type`: 275 Cell-Level and 125 Sheet-Level (all 400 tasks) | skillberry-1, `~/.cache/capevolve-ci/spreadsheetbench-data/spreadsheetbench_verified_400/dataset.json` |
| No paired-bootstrap helper exists. `cap_evolve.stats.bootstrap_ci(xs, resamples=2000, seed=0)` gives a percentile CI of a mean; applied to per-task differences it gives a paired CI. | `stats.py:97` |

## Global Constraints

- Branch `exp/606-reader-profile`, based on `origin/main`. It is **never merged**. Open a **draft** PR titled `[DO NOT MERGE] exp #606: reader-profile experiment`. Delete the branch and close the PR when the experiment ends.
- Never add a `benchmark-*` label to the temp PR. Runs start only through `gh workflow run ... --ref exp/606-reader-profile`.
- Every commit uses `git commit -s` (DCO) and ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Fixed run settings: `benchmark=spreadsheetbench`, `tier=full_verified_probe`, `iterations=1` (phase 3: `3`), `algorithm=hill-climb-all`, `gate_k_se=0.2`, `agent_model=ibm-rits/google/gemma-4-31B-it`, `optimizer_model=ibm-ete-int/aws/claude-opus-5-5`, `trials` blank (the tier default is 1), `optimizer_max_turns=80`, `optimizer_usd_per_iter` blank (0 = no cap, as in #538).
- Only the reader block differs between variants. Compare Opus 5.5 runs only with each other and with the reused seed. Never compare them with the Opus 5 runs from #538.
- Subset seed: `606`. **As built:** the subset is stratified by (`instruction_type`, seed passed?) and drawn only from the 276 test tasks where the seed has a valid score. The result is 70 Cell-Level + 30 Sheet-Level, and the seed scores 0.430 on the subset against 0.435 on all 280. Stratifying by type alone gave 0.520: a draw 8.5 points above the parent, with less headroom. The seed outcome is known before any variant runs, so stratifying on it does not bias the comparison.
- **As built:** each run's artifact also carries `reader_block.md`, `optimizer_instructions/cand_*.md` (the optimizer's real rendered instructions) and `optimizer_models.json`. That last file lists the model ids found in the Claude Code session logs that the run's candidates wrote on skillberry-1. On the hill-climb path, the artifact has no `host/` transcript.
- Never modify the live slot `~/.cache/capevolve-latest/spreadsheetbench` on skillberry-1. Runs read only a frozen copy at `/home/skillberry/.cache/capevolve-latest/spreadsheetbench-606`.

## Review Focus

1. **The reader text is not the one we meant.** For example, a file path typo makes `resolve()` silently fall back to the tier brief. Expected behavior: the run fails before the optimizer starts, and the job log and artifact contain the exact rendered block. The test is in Task 4.
2. **The seed baseline on the subset is wrong.** Examples: filtered to the wrong ids, still averaging 280 tasks, or counting infra-error tasks differently. Expected behavior: the reused seed test reward equals the mean of the slot's 100 matching per-task rewards, and `n_tasks == 100`. The tests are in Task 5, plus the plumbing run in Task 7.
3. **A queued run is cancelled, or a run lands on skillberry-2** (which has no slot). Expected behavior: all queued dispatches run, one after another, on skillberry-1. The test is in Task 1.
4. **Another run replaces the live slot during the experiment.** Expected behavior: probe runs are not affected, because they read the frozen copy and never write a slot. The tests are in Tasks 3 and 4.
5. **The optimizer silently runs as a different model** (alias or fallback). Expected behavior: the report prints every model id found in the optimizer transcripts, and marks the run invalid unless the only id is `claude-opus-5-5` (or its wire form). The test is in Task 6.

---

## File structure (all on the temp branch)

| file | change | responsibility |
|---|---|---|
| `core/cap_evolve/target_profile.py` | modify | verbatim reader-block mode |
| `core/tests/test_target_profile.py` | modify | tests for the verbatim mode |
| `.github/workflows/benchmarks.yml` | modify | Opus 5.5 option, `reader_variant` input, probe tier, pin to skillberry-1, unique concurrency group |
| `ci/benchmarks/lib/ci_setup.sh` | modify | probe tier uses `verified_400` data |
| `ci/benchmarks/lib/run_suite.sh` | modify | probe tier defaults, reader variant plumbing, reuse from parent tier + subset, Gemma warm-up |
| `ci/benchmarks/spreadsheetbench/full_verified_probe/` | create | `tasks.json`, `split_ids.json`, `subset_source.json`, `overrides.env`, `reader/*.md` |
| `ci/benchmarks/spreadsheetbench/utils/make_probe_subset.py` | create | fixed-seed stratified subset generator |
| `ci/benchmarks/spreadsheetbench/utils/rescore_run.py` | modify | `--test-subset` option |
| `ci/benchmarks/spreadsheetbench/utils/exp606_report.py` | create | per-run and cross-run report |
| `core/tests/test_exp606_probe.py` | create | tests for tier, reader files, subset, report |

---

### Task 0: Branch, draft PR, frozen slot, first issue comment

**Files:** none in the repo, except this plan file, which is committed here.

- [ ] **Step 1: Check the worktree and branch.** Run `git rev-parse --abbrev-ref HEAD`. Expected: `exp/606-reader-profile`, based on `origin/main` (`f0a14e39` or later).
- [ ] **Step 2: Freeze a copy of the slot on skillberry-1.** Use `cp -a`, never `mv`:

```bash
ssh skillberry-1 'set -e; S=$HOME/.cache/capevolve-latest/spreadsheetbench; D=$S-606
test ! -e "$D"; cp -a "$S" "$D"; cat "$D/latest.json"
python3 - "$D" <<"PY"
import json, sys, hashlib, pathlib
d = pathlib.Path(sys.argv[1]); f = json.load(open(d/"run_suite/final.json"))
s = f["seed"]["test"]; print("seed.test", s["reward"], len(s["per_task"]))
h = hashlib.sha256(); [h.update(p.read_bytes()) for p in sorted((d/"run_suite/candidates/seed").rglob("*")) if p.is_file()]
print("seed files sha256", h.hexdigest())
PY'
```

Expected: `run_id 36622615059`, `empty_seed "1"`, `seed.test 0.43478... 280`.
- [ ] **Step 3: Commit the plan and open the draft PR.**

```bash
git add docs/superpowers/plans/2026-09-30-issue-606-reader-profile-experiment.md
git commit -s -m "exp(#606): add the reader-profile experiment plan (temp branch, never merged)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git push -u origin exp/606-reader-profile
gh pr create --draft --base main --head exp/606-reader-profile \
  --title "[DO NOT MERGE] exp #606: reader-profile experiment" \
  --body "Temporary branch for #606. Never merged; closed and deleted when the experiment ends. Runs are dispatched with workflow_dispatch --ref exp/606-reader-profile.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 4: Post the "experiment log started" comment on #606.** It holds the plan summary, the PR link, the frozen-slot path and sha256, and the table header from "Issue documentation" below.

---

### Task 1: Workflow changes (Opus 5.5, reader input, probe tier, pinning, concurrency)

**Files:**
- Modify: `.github/workflows/benchmarks.yml`
- Test: `core/tests/test_exp606_probe.py`

**Interfaces:**
- Produces: the dispatch input `reader_variant` (choice `A`, `B`, `C`, `R`; default `A`), exported to the job as `SB_READER`. Produces the tier name `full_verified_probe`.

- [ ] **Step 1: Write the failing test.**

```python
# core/tests/test_exp606_probe.py
"""Temp-branch tests for issue #606's reader-profile experiment (never merged)."""
import json, re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WF = (REPO / ".github/workflows/benchmarks.yml").read_text(encoding="utf-8")
PROBE = REPO / "ci/benchmarks/spreadsheetbench/full_verified_probe"
PARENT = REPO / "ci/benchmarks/spreadsheetbench/full_verified"


def test_opus_5_5_is_an_optimizer_option():
    assert "ibm-ete-int/aws/claude-opus-5-5" in WF


def test_reader_variant_input_reaches_the_job():
    assert "      reader_variant:\n" in WF and "options: [A, B, C, R]" in WF
    assert "SB_READER: ${{ github.event.inputs.reader_variant }}" in WF


def test_probe_tier_is_selectable_and_explicit_only():
    assert "full_verified_probe" in WF
    assert re.search(r"EXPLICIT_ONLY_TIERS.*full_verified_probe", WF)


def test_bench_job_is_pinned_to_skillberry_1():
    assert "runs-on: [self-hosted, ibm-vpc, skillberry-1]" in WF


def test_queued_dispatches_are_never_cancelled():
    # one group per run: the single runner serializes them, and GitHub never drops a pending one
    assert "group: benchmarks-${{ matrix.tier }}-${{ matrix.bench }}-${{ github.ref }}-${{ github.run_id }}" in WF
```

- [ ] **Step 2: Run the test and check that it fails.** `cd core && python -m pytest tests/test_exp606_probe.py -q`. Expected: 5 failures.
- [ ] **Step 3: Edit `benchmarks.yml`.**
  - Add `- ibm-ete-int/aws/claude-opus-5-5` right after `- ibm-ete-int/aws/claude-opus-5` in **both** the `agent_model` and `optimizer_model` option lists (lines ~70 and ~114). The lists are kept identical.
  - Add `full_verified_probe` to the `tier` options (line 53), to `TIERS` (line 247) and to `EXPLICIT_ONLY_TIERS` (line 272). In the `NUM_TRIALS` default (line 424), treat it like `full_verified` (1 trial).
  - Add this input after `algorithm`:

```yaml
      reader_variant:
        description: "exp #606 only: optimizer reader block. A=strong (current), B=frontier brief, C=no block, R=results-driven"
        type: choice
        default: A
        options: [A, B, C, R]
```

  - In the bench job `env:`, add `SB_READER: ${{ github.event.inputs.reader_variant }}`.
  - Change line 364 to `runs-on: [self-hosted, ibm-vpc, skillberry-1]`.
  - Change the concurrency group to `benchmarks-${{ matrix.tier }}-${{ matrix.bench }}-${{ github.ref }}-${{ github.run_id }}`.
- [ ] **Step 4: Run the new tests, the workflow tests and the tier tests.**

```bash
cd core && python -m pytest tests/test_exp606_probe.py tests/test_spreadsheetbench_full_verified_tier.py -q
python -c "import yaml,sys; yaml.safe_load(open('../.github/workflows/benchmarks.yml'))"
```

Expected: the 5 new tests pass. Existing tests pass. If a picker-parity test requires the two lists to match the gateway list, it still passes, because the gateway serves the new id.
- [ ] **Step 5: Commit.** Message: `exp(#606): Opus 5.5 option, reader_variant input, probe tier, pin to skillberry-1`.

---

### Task 2: Verbatim reader-block mode

**Files:**
- Modify: `core/cap_evolve/target_profile.py` (the `reader_block` function)
- Test: `core/tests/test_target_profile.py`

**Interfaces:**
- Produces: if the text of `target_profile_file` starts with `## THE READER`, `reader_block(profile)` returns that text exactly, with one trailing newline. Otherwise behavior is unchanged. An agnostic profile (empty `target_model`) still returns `""`.

- [ ] **Step 1: Write the failing tests.** Add to `core/tests/test_target_profile.py`:

```python
def test_verbatim_reader_file_replaces_the_whole_block(tmp_path):
    f = tmp_path / "r.md"
    f.write_text("## THE READER (who consumes what you edit)\nYou do not know which model reads this skill.\n")
    out = tp.reader_block(tp.resolve("rits/google/gemma-4-31B-it", f))
    assert out == "## THE READER (who consumes what you edit)\nYou do not know which model reads this skill.\n"
    assert "gemma" not in out and "capability tier" not in out


def test_brief_only_file_keeps_the_rendered_frame(tmp_path):
    f = tmp_path / "b.md"
    f.write_text("Custom brief.")
    out = tp.reader_block(tp.resolve("gpt-oss-120b", f))
    assert out.startswith("## THE READER") and "`gpt-oss-120b`" in out and "Custom brief." in out


def test_verbatim_file_is_ignored_when_agnostic(tmp_path):
    f = tmp_path / "r.md"
    f.write_text("## THE READER\nx\n")
    assert tp.reader_block(tp.resolve("", f)) == ""
```

- [ ] **Step 2: Run them and check that the first test fails.** `cd core && python -m pytest tests/test_target_profile.py -q`. Expected: `test_verbatim_reader_file_replaces_the_whole_block` fails. The other two pass.
- [ ] **Step 3: Implement.** In `reader_block`, after the `is_agnostic` check:

```python
    # A profile file that is already a whole block (it opens with the block's own header) is used
    # as written, so an experiment can control every word the optimizer reads (#606).
    if profile.brief.startswith("## THE READER"):
        return profile.brief.rstrip("\n") + "\n"
```

- [ ] **Step 4: Run the reader tests.** `cd core && python -m pytest tests/test_target_profile.py tests/test_target_reader_render.py tests/test_target_reader_wiring.py tests/test_target_profile_metadata.py -q`. Expected: all pass.
- [ ] **Step 5: Commit.** Message: `exp(#606): a profile file that is a whole reader block is used verbatim`.

---

### Task 3: The `full_verified_probe` tier and its fixed subset

**Files:**
- Create: `ci/benchmarks/spreadsheetbench/utils/make_probe_subset.py`
- Create: `ci/benchmarks/spreadsheetbench/full_verified_probe/{tasks.json,split_ids.json,subset_source.json,overrides.env}`
- Create: `ci/benchmarks/spreadsheetbench/full_verified_probe/reader/{R_results_driven.md,B_frontier.md}`
- Modify: `ci/benchmarks/lib/ci_setup.sh:227`, `ci/benchmarks/lib/run_suite.sh:784,794,804`
- Test: `core/tests/test_exp606_probe.py`

**Interfaces:**
- Produces: `split_ids.json` with keys `train` (80, the same as the parent), `val` (40, the same as the parent) and `test` (100, a subset of the parent's test). `tasks.json` holds exactly those 220 ids, with the parent's entry format. `subset_source.json` holds `{seed, parent_split_sha256, counts_by_type, sha256_sorted_ids, seed_test_reward_on_subset}`.

- [ ] **Step 1: Write the generator.**

```python
#!/usr/bin/env python3
"""Write full_verified_probe/: full_verified's train/val and a FIXED 100-task test subset (#606).

The subset is drawn once, with a stated seed, stratified by instruction_type in the same proportion
as the parent test split. The seed's per-task test rewards from the frozen #538 slot give the
subset's no-skill baseline, which is recorded in subset_source.json for the runs to check against.

    python3 make_probe_subset.py --dataset <verified_400>/dataset.json --slot <frozen slot dir> [--write]
"""
from __future__ import annotations
import argparse, hashlib, json, random
from pathlib import Path

SEED, N = 606, 100
UTILS = Path(__file__).resolve().parent
PARENT, PROBE = UTILS.parent / "full_verified", UTILS.parent / "full_verified_probe"


def digest(ids): return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def build(dataset: Path, slot: Path):
    split = json.loads((PARENT / "split_ids.json").read_text())
    kind = {str(x["id"]): x["instruction_type"] for x in json.loads(dataset.read_text())}
    test = sorted(split["test"])
    types = sorted({kind[i] for i in test})
    share = {t: sum(kind[i] == t for i in test) for t in types}
    want = {t: round(N * share[t] / len(test)) for t in types}
    want[max(types, key=lambda t: share[t])] += N - sum(want.values())
    rng = random.Random(SEED)
    sub = sorted(i for t in types for i in rng.sample([i for i in test if kind[i] == t], want[t]))
    per = {str(p["task_id"]): float(p["reward"])
           for p in json.loads((slot / "run_suite/final.json").read_text())["seed"]["test"]["per_task"]}
    missing = [i for i in sub if i not in per]
    if missing:
        raise SystemExit(f"seed has no test score for {missing}")
    out_split = {"train": sorted(split["train"]), "val": sorted(split["val"]), "test": sub}
    parent_tasks = {str(t["id"]): t for t in json.loads((PARENT / "tasks.json").read_text())}
    keep = set(out_split["train"]) | set(out_split["val"]) | set(sub)
    tasks = [dict(t, tag="full_verified_probe") for i, t in parent_tasks.items() if i in keep]
    source = {"seed": SEED, "parent": "full_verified",
              "parent_split_sha256": {k: digest(v) for k, v in split.items()},
              "counts_by_type": want, "counts": {k: len(v) for k, v in out_split.items()},
              "sha256_sorted_ids": {k: digest(v) for k, v in out_split.items()},
              "seed_test_reward_on_subset": sum(per[i] for i in sub) / len(sub),
              "seed_test_reward_on_parent": sum(per.values()) / len(per)}
    return out_split, tasks, source


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--slot", type=Path, required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    split, tasks, source = build(a.dataset, a.slot)
    print(json.dumps(source, indent=2))
    if a.write:
        PROBE.mkdir(exist_ok=True)
        (PROBE / "split_ids.json").write_text(json.dumps(split, indent=1, sort_keys=True) + "\n")
        (PROBE / "tasks.json").write_text(json.dumps(tasks, indent=1) + "\n")
        (PROBE / "subset_source.json").write_text(json.dumps(source, indent=2) + "\n")


if __name__ == "__main__":
    main()
```

  Before running it, check the per-task field names in the slot's `final.json`, and whether `reward` is the as-saved value. If the entries use other names, adjust the `per` line.
  Before writing `tasks.json`, check the format of `full_verified/tasks.json` (`id`, `tag`, `agent`). If `run_suite.sh` filters tasks by `tag`, keep the parent's tag instead.

- [ ] **Step 2: Run it on skillberry-1, where the dataset and the frozen slot are.** Copy the script and the two parent files over, run it with `--write`, then copy the three outputs back:

```bash
scp -r ci/benchmarks/spreadsheetbench/utils/make_probe_subset.py ci/benchmarks/spreadsheetbench/full_verified skillberry-1:/tmp/exp606/   # keep the utils/.. layout: mkdir -p /tmp/exp606/utils first
# on skillberry-1: python3 /tmp/exp606/utils/make_probe_subset.py \
#   --dataset ~/.cache/capevolve-ci/spreadsheetbench-data/spreadsheetbench_verified_400/dataset.json \
#   --slot ~/.cache/capevolve-latest/spreadsheetbench-606 --write
scp 'skillberry-1:/tmp/exp606/full_verified_probe/*.json' ci/benchmarks/spreadsheetbench/full_verified_probe/
```

  Expected output: counts 80/40/100, type counts that add up to 100, and `seed_test_reward_on_parent` = 0.43478 (± rounding from infra-error rows). Record `seed_test_reward_on_subset`.
- [ ] **Step 3: Write `overrides.env`.**

```sh
# full_verified_probe — exp #606 ONLY (temp branch, never merged).
# full_verified's train/val, and a fixed 100-task test subset (subset_source.json). The seed is the
# #538 empty seed, reused from a FROZEN copy of the saved slot, which probe runs never write.
SB_SCORING=hard
GATE_K_SE=0.2
SB_EMPTY_SEED=1
SB_REUSE_LATEST_BASELINE=1
SB_REUSE_FROM_TIER=full_verified
SB_LATEST_DIR=/home/skillberry/.cache/capevolve-latest/spreadsheetbench-606
SB_KEEP_LATEST_RUN=0
```

  Check that `load_overrides.sh` keeps absolute paths as they are (it parses the file and does not expand variables, so no `$HOME`).
- [ ] **Step 4: Write the reader files.** `reader/R_results_driven.md`:

```markdown
## THE READER (who consumes what you edit)
You do not know which model reads this skill. Infer its strengths and weaknesses from the trajectories and failures you are given, and strengthen the areas where it fails.
```

  `reader/B_frontier.md`: generate it, so that it is the exact block `reader_block` would render for a frontier-tier Gemma. Its only differences from A are the tier word and the brief.

```bash
cd core && python -c "
from cap_evolve import target_profile as tp
p = tp.TargetProfile(model='rits/google/gemma-4-31B-it', tier='frontier', brief=tp.TIERS['frontier']['brief'])
open('../ci/benchmarks/spreadsheetbench/full_verified_probe/reader/B_frontier.md','w').write(tp.reader_block(p))"
```

- [ ] **Step 5: Register the tier in the scripts.**
  - `ci_setup.sh:227`: change the pattern to `full_verified|full_verified_probe) SB_VARIANT="verified_400" ;;`.
  - `run_suite.sh`: add `full_verified_probe` to the three `case "$TIER"` patterns at lines 784, 794 and 804: the data dir, concurrency 8, and 30 max turns.
- [ ] **Step 6: Add the tests.** Append to `core/tests/test_exp606_probe.py`:

```python
def _j(p): return json.loads(p.read_text(encoding="utf-8"))


def test_probe_split_shares_train_val_and_subsets_test():
    s, parent = _j(PROBE / "split_ids.json"), _j(PARENT / "split_ids.json")
    assert sorted(s["train"]) == sorted(parent["train"]) and sorted(s["val"]) == sorted(parent["val"])
    assert len(s["test"]) == 100 and set(s["test"]) <= set(parent["test"])


def test_probe_tasks_cover_the_split_exactly():
    s = _j(PROBE / "split_ids.json")
    ids = [str(t["id"]) for t in _j(PROBE / "tasks.json")]
    assert len(ids) == len(set(ids)) == 220
    assert set(ids) == set(s["train"]) | set(s["val"]) | set(s["test"])


def test_subset_digest_is_pinned():
    import hashlib
    src, s = _j(PROBE / "subset_source.json"), _j(PROBE / "split_ids.json")
    for k in ("train", "val", "test"):
        assert hashlib.sha256("\n".join(sorted(s[k])).encode()).hexdigest() == src["sha256_sorted_ids"][k]
    assert src["seed"] == 606 and sum(src["counts_by_type"].values()) == 100


def test_probe_overrides_never_touch_the_live_slot():
    env = dict(l.split("=", 1) for l in (PROBE / "overrides.env").read_text().splitlines()
               if l and not l.startswith("#"))
    assert env["SB_KEEP_LATEST_RUN"] == "0"
    assert env["SB_LATEST_DIR"].endswith("spreadsheetbench-606")
    assert env["SB_REUSE_FROM_TIER"] == "full_verified" and env["SB_EMPTY_SEED"] == "1"


def test_reader_files_are_whole_blocks():
    r = (PROBE / "reader/R_results_driven.md").read_text()
    b = (PROBE / "reader/B_frontier.md").read_text()
    assert r.startswith("## THE READER") and "gemma" not in r.lower() and "tier" not in r.lower()
    assert b.startswith("## THE READER") and "**frontier**" in b and "gemma-4-31B-it" in b
```

- [ ] **Step 7: Run the tests.** `cd core && python -m pytest tests/test_exp606_probe.py tests/test_spreadsheetbench_full_verified_tier.py -q && bash -n ../ci/benchmarks/lib/run_suite.sh ../ci/benchmarks/lib/ci_setup.sh`. Expected: all pass.
- [ ] **Step 8: Commit.** Message: `exp(#606): full_verified_probe tier — parent train/val, fixed 100-task test subset (seed 606)`.

---

### Task 4: `run_suite.sh` — reader variant, reuse from the parent tier, Gemma warm-up

**Files:**
- Modify: `ci/benchmarks/lib/run_suite.sh` (reuse block at 1007-1036, spec heredoc at 1039-1080)
- Modify: `ci/benchmarks/lib/ci_setup.sh` (before `probe_model`, ~line 366)
- Test: `core/tests/test_exp606_probe.py`

**Interfaces:**
- Consumes: `SB_READER` (Task 1), the `reader/*.md` files and the `overrides.env` keys (Task 3), `rescore_run.py --test-subset` (Task 5).
- Produces: `$OUT/reader_block.md` (in the artifact) and a `>>> reader:` log line with its sha256. The spec gets `target_model` / `target_profile_file` per variant.

- [ ] **Step 1: Add the reader variant block before the spec heredoc.** It fails the run early on a bad value or a missing file:

```bash
# exp #606: which reader block the optimizer gets. A = the current rendering (tier strong),
# B/R = a whole block from the probe tier's reader/ dir, C = none (agnostic).
TARGET_MODEL_LINE="target_model:       $AGENT_MODEL_WIRE"
TARGET_PROFILE_LINE=""
case "${SB_READER:-A}" in
  A) ;;
  B|R)
    RF="$REPO/ci/benchmarks/$BENCH_DIR/$TIER/reader/$( [ "$SB_READER" = B ] && echo B_frontier.md || echo R_results_driven.md )"
    [ -s "$RF" ] || { echo "::error:: SB_READER=$SB_READER but $RF is missing or empty" >&2; exit 1; }
    TARGET_PROFILE_LINE="target_profile_file: \"$RF\"" ;;
  C) TARGET_MODEL_LINE="target_model:       \"\"" ;;
  *) echo "::error:: SB_READER must be A, B, C or R (got '$SB_READER')" >&2; exit 1 ;;
esac
READER_TM=$([ "${SB_READER:-A}" = C ] && echo "" || echo "$AGENT_MODEL_WIRE")
PYTHONPATH="$REPO/core" "$PY" - "$READER_TM" "${RF:-}" "$OUT/reader_block.md" <<'PY' || exit 1
import hashlib, sys
from cap_evolve import target_profile as tp
tm, rf, out = sys.argv[1:4]
block = tp.reader_block(tp.resolve(tm, rf or None))
if rf and block != open(rf, encoding="utf-8").read().rstrip("\n") + "\n":
    raise SystemExit(f"::error:: rendered reader block is not the file {rf} verbatim")
open(out, "w", encoding="utf-8").write(block)
print(f">>> reader: variant sha256={hashlib.sha256(block.encode()).hexdigest()[:12]} chars={len(block)}\n{block or '(no reader block)'}", file=sys.stderr)
PY
```

  Put the `>>> reader:` line where `SB_READER` is also printed, so that the job log has both. Make sure `$OUT` exists at that point; if it does not, create it with `mkdir -p "$OUT"`.
- [ ] **Step 2: Use the two lines in the heredoc.** Replace `target_model:       $AGENT_MODEL_WIRE` with `$TARGET_MODEL_LINE`, and add `$TARGET_PROFILE_LINE` on the next line. An empty line is valid YAML.
- [ ] **Step 3: Relax the reuse check, and filter to the subset.** In the Python heredoc at 1010-1028:
  - Pass `"${SB_REUSE_FROM_TIER:-$TIER}"` as the tier to compare.
  - Keep equality for `train` and `val`.
  - For `test`, require `set(want["test"]) <= set(prior["test"])`, and print `>>> reusing on a {n}-task test subset of the kept run's {m}` when they differ.
  - Then change the `rescore_run.py` call to add `--test-subset "$PROJ/inputs/split_ids.json"`.

```python
reuse_tier = sys.argv[6] if len(sys.argv) > 6 else tier
if meta.get("tier") != reuse_tier:
    raise SystemExit(f"::error:: the kept run is tier {meta.get('tier')!r}, this run reuses {reuse_tier!r}")
...
for k in ("train", "val"):
    if set(map(str, prior.get(k, []))) != set(map(str, want[k])):
        raise SystemExit(f"::error:: the kept run's {k} split differs from this tier's split_ids.json")
pt, wt = set(map(str, prior.get("test", []))), set(map(str, want["test"]))
if not wt <= pt:
    raise SystemExit(f"::error:: this tier's test split is not a subset of the kept run's ({len(wt - pt)} ids missing)")
if wt != pt:
    print(f">>> reusing on a {len(wt)}-task test subset of the kept run's {len(pt)}", file=sys.stderr)
```

- [ ] **Step 4: Add a Gemma warm-up before the preflight probe.** Put it in `ci_setup.sh`, before `probe_model` runs, and only for ibm-rits agents. It sends one small request with a 180 s timeout and never fails the job, so that the 60 s preflight does not hit a cold endpoint (#538 note):

```bash
if [ "$(classify_provider "$PF_AGENT")" = "ibm-rits" ]; then
  resolve_provider "$PF_AGENT"
  curl -sS -m 180 -o /dev/null -w ">>> rits warm-up: HTTP %{http_code} in %{time_total}s\n" \
    "$RESOLVED_API_BASE/chat/completions" -H "Content-Type: application/json" \
    -H "RITS_API_KEY: $RESOLVED_API_KEY" \
    -d "{\"model\":\"$RESOLVED_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":1}" || true
fi
```

  Copy the exact variable names (`PF_AGENT`, the header name, the key variable) from `probe_model` in the same file. The names above are the expected ones, but `probe_model` is the source of truth.
- [ ] **Step 5: Add the tests.** Append to `core/tests/test_exp606_probe.py`:

```python
RS = (REPO / "ci/benchmarks/lib/run_suite.sh").read_text(encoding="utf-8")


def test_run_suite_rejects_unknown_reader_and_missing_file():
    assert "SB_READER must be A, B, C or R" in RS
    assert "is missing or empty" in RS and "not the file" in RS


def test_reuse_allows_a_parent_tier_and_a_test_subset_only():
    assert "SB_REUSE_FROM_TIER" in RS and "--test-subset" in RS
    assert 'for k in ("train", "val"):' in RS and "wt <= pt" in RS
```

  Also run the reader-variant block for real, with a fake environment, for each of `A B C R` plus `X`:

```bash
for v in A B C R X; do
  SB_READER=$v REPO=$PWD BENCH_DIR=spreadsheetbench TIER=full_verified_probe \
  AGENT_MODEL_WIRE=rits/google/gemma-4-31B-it OUT=$(mktemp -d) PY=python3 \
  bash -c "$(sed -n '/^# exp #606: which reader block/,/^PY$/p' ci/benchmarks/lib/run_suite.sh)" \
    && echo "$v ok" || echo "$v FAILED"
done
```

  Expected: `A`, `B`, `C`, `R` print their block (C prints `(no reader block)`), and `X` fails. Also run a copy with the R file path misspelled; it must fail.
- [ ] **Step 6: Run the tests.** `cd core && python -m pytest tests/test_exp606_probe.py -q && bash -n ../ci/benchmarks/lib/run_suite.sh ../ci/benchmarks/lib/ci_setup.sh`. Expected: all pass.
- [ ] **Step 7: Commit.** Message: `exp(#606): reader variant per dispatch, reuse the parent tier's seed on a test subset, warm Gemma before preflight`.

---

### Task 5: `rescore_run.py --test-subset`

**Files:**
- Modify: `ci/benchmarks/spreadsheetbench/utils/rescore_run.py`
- Test: `core/tests/test_exp606_probe.py`

**Interfaces:**
- Produces: `rescore(run_dir, metric, test_ids: set[str] | None = None)`. When `test_ids` is set, `splits.json` `test` becomes the sorted `test_ids`. `final.json` `seed.test` / `test_baseline` (and `test` when the seed is best) are re-aggregated over only those tasks. It raises if any id has no stored row.

- [ ] **Step 1: Write the failing test.** Build a tiny run dir with the helpers that `core/tests/test_spreadsheetbench_rescore_run.py` already uses. Copy its fixture builder for a run dir with `baseline.json`, `splits.json` and a `final.json` that carries `seed.test.per_task` for ids `a,b,c,d`, with rewards `1,0,1,1` and no test rollouts. Then:

```python
def test_rescore_restricts_seed_test_to_the_subset(tmp_path):
    run = _make_run(tmp_path, test_ids=["a", "b", "c", "d"], seed_test={"a": 1, "b": 0, "c": 1, "d": 1})
    out = rescore_run.rescore(run, "hard_no_recalc", test_ids={"a", "b"})
    final = json.loads((run / "final.json").read_text())
    assert out["test"] == 0.5
    assert {p["task_id"] for p in final["seed"]["test"]["per_task"]} == {"a", "b"}
    assert json.loads((run / "splits.json").read_text())["test"] == ["a", "b"]


def test_rescore_subset_with_an_unknown_id_fails(tmp_path):
    run = _make_run(tmp_path, test_ids=["a", "b"], seed_test={"a": 1, "b": 0})
    with pytest.raises(SystemExit):
        rescore_run.rescore(run, "hard_no_recalc", test_ids={"a", "z"})
```

- [ ] **Step 2: Run it and check that it fails.** Expected: `TypeError: unexpected keyword argument 'test_ids'`.
- [ ] **Step 3: Implement.** In `rescore()`, after `test = _split(...)`:

```python
        if test_ids is not None:
            rows = [pt for pt in test.get("per_task") or [] if str(pt["task_id"]) in test_ids]
            missing = test_ids - {str(pt["task_id"]) for pt in rows}
            if missing:
                raise SystemExit(f"::error:: kept seed has no test row for {sorted(missing)}")
            test = _rescore_result("test", dict(test, per_task=rows), metric)
```

  After `final.json` is written, rewrite `splits.json`: load it, set `test = sorted(test_ids)`, and write it back. Keep every other key, including the test-seal flag that `reuse_baseline` resets. In `main()`, add `--test-subset PATH`. It reads `json.load(open(PATH))["test"]` and passes it as a `set(map(str, ...))`.
- [ ] **Step 4: Run the tests.** `cd core && python -m pytest tests/test_exp606_probe.py tests/test_spreadsheetbench_rescore_run.py tests/test_reuse_baseline_carries_seed_train_and_test.py -q`. Expected: all pass.
- [ ] **Step 5: Check against the real slot on skillberry-1.** Use a scratch copy only:

```bash
ssh skillberry-1 'rm -rf /tmp/exp606-rs && cp -a ~/.cache/capevolve-latest/spreadsheetbench-606/run_suite /tmp/exp606-rs'
# copy the branch's rescore_run.py + core/ to /tmp/exp606 on skillberry-1, then:
# PYTHONPATH=/tmp/exp606/core python3 /tmp/exp606/rescore_run.py /tmp/exp606-rs --metric hard_no_recalc --test-subset /tmp/exp606/full_verified_probe/split_ids.json
```

  Expected: the printed test reward equals `seed_test_reward_on_subset` from `subset_source.json`, and `n_tasks == 100`.
- [ ] **Step 6: Commit.** Message: `exp(#606): rescore_run --test-subset restricts the reused seed test to the probe subset`.

---

### Task 6: The report script

**Files:**
- Create: `ci/benchmarks/spreadsheetbench/utils/exp606_report.py`
- Test: `core/tests/test_exp606_probe.py`

**Interfaces:**
- Consumes: one downloaded artifact dir per run (`gh run download <id> -D runs/<id>`), holding `metrics.jsonl`, `steps.jsonl`, `runmeta.json`, `reader_block.md`, `optimized/optimized_capability/{prompt.md,task_template.md}`, `ui/data/events.jsonl` and `host/*.gz`.
- Produces: `summarize(run_dir) -> dict` with keys `run_id, variant, test_seed, test_opt, delta, delta_ci, val_seed, val_cand, accepted, opt_usd, opt_minutes, wall_minutes, models, skill_shape`. Also `compare(runs_a, runs_b) -> dict` with keys `diff, ci` (per-task mean of A minus per-task mean of B over the common tasks, paired bootstrap with 2,000 resamples and seed 0). The CLI prints Markdown tables that can be pasted into the issue.

- [ ] **Step 1: Write the failing tests.** Use small synthetic artifacts built in `tmp_path`:

```python
from importlib import util as _u
_spec = _u.spec_from_file_location("r", REPO / "ci/benchmarks/spreadsheetbench/utils/exp606_report.py")
rep = _u.module_from_spec(_spec); _spec.loader.exec_module(rep)


def _art(tmp, rid, opt, base, models=("claude-opus-5-5",), accept=True):
    d = tmp / rid; (d / "optimized/optimized_capability").mkdir(parents=True); (d / "ui/data").mkdir(parents=True)
    (d / "metrics.jsonl").write_text("".join(json.dumps({"task_id": t, "reward_baseline": base[t], "reward_opt": opt[t]}) + "\n" for t in opt))
    (d / "runmeta.json").write_text(json.dumps({"run_id": rid}))
    (d / "reader_block.md").write_text("## THE READER\nYou do not know which model reads this skill.\n")
    (d / "optimized/optimized_capability/prompt.md").write_text("# Rules\n1. a\n2. b\n\nExample:\n```\nx\n```\n")
    (d / "optimized/optimized_capability/task_template.md").write_text("t")
    ev = [{"kind": "baseline_reused", "val": 0.5}, {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.7},
          {"kind": "step", "candidate": "cand_0001", "accept": accept, "val": 0.7, "opt_cost_usd": 12.0}]
    (d / "ui/data/events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ev))
    (d / "host").mkdir(); import gzip
    with gzip.open(d / "host/t.jsonl.gz", "wt") as f:
        for m in models: f.write(json.dumps({"message": {"model": m}}) + "\n")
    return d


def test_summarize_reads_scores_cost_and_models(tmp_path):
    d = _art(tmp_path, "1", {"a": 1, "b": 1, "c": 0, "d": 1}, {"a": 0, "b": 1, "c": 0, "d": 0})
    s = rep.summarize(d)
    assert s["test_seed"] == 0.25 and s["test_opt"] == 0.75 and s["delta"] == 0.5
    assert s["variant"] == "R" and s["accepted"] is True and s["opt_usd"] == 12.0
    assert s["models"] == ["claude-opus-5-5"] and s["valid"] is True
    assert s["skill_shape"]["numbered_rules"] == 2 and s["skill_shape"]["code_examples"] == 1


def test_wrong_optimizer_model_marks_run_invalid(tmp_path):
    d = _art(tmp_path, "2", {"a": 1}, {"a": 0}, models=("claude-opus-5-5", "claude-opus-5"))
    assert rep.summarize(d)["valid"] is False


def test_compare_is_paired_on_common_tasks(tmp_path):
    a = [_art(tmp_path, "a1", {"x": 1, "y": 1}, {"x": 0, "y": 0})]
    b = [_art(tmp_path, "b1", {"x": 0, "y": 1, "z": 1}, {"x": 0, "y": 0, "z": 0})]
    c = rep.compare([rep.summarize(r) for r in a], [rep.summarize(r) for r in b])
    assert c["n_tasks"] == 2 and c["diff"] == 0.5
```

- [ ] **Step 2: Run the tests and check that they fail** (the module does not exist yet).
- [ ] **Step 3: Implement `exp606_report.py`.** Rules:
  - **Test score.** Read the per-task `reward_baseline` and `reward_opt` from `metrics.jsonl`. Skip rows where either value is null (infra error) on both sides. Compute `delta_ci = cap_evolve.stats.bootstrap_ci([o - b ...], resamples=2000, seed=0)`.
  - **Val and cost.** Read them from `events.jsonl` only, never from rollout files (#538 note). `val_seed` comes from `baseline_reused.val`, and `val_cand` from the `evaluate` event with `split=="val"` and a tag that is not `seed`. `accepted` comes from `step.accept`. `opt_usd` is the sum of `step.opt_cost_usd`, falling back to the `host.usd` events.
  - **Time.** `opt_minutes` comes from `steps.jsonl`, and `wall_minutes` from `runmeta.json` start and end when present.
  - **Variant.** `R` if `reader_block.md` contains "You do not know which model", `B` if it contains `**frontier**`, `A` if it contains `**strong**`, `C` if it is empty. Also take `SB_READER` from `runmeta.json` when present. If the two disagree, set `valid=False`.
  - **Models.** Collect every `"model"` value found in `host/*.gz` and `host/*.jsonl`, at any depth. `valid` requires the set to be exactly one id, and that id must contain `claude-opus-5-5`.
  - **Skill shape.** For `prompt.md` + `task_template.md`: `chars`, `numbered_rules` (lines matching `^\s*\d+[.)]\s`), `bullets` (lines matching `^\s*[-*]\s`), `code_examples` (count of fenced blocks), `worked_examples` (lines matching `(?i)\bexample\b`), and `grader_contract`. `grader_contract` is True when all of `data_only`, `formula` and `2 decimal`/`round` appear (case-insensitive).
  - **`compare`.** Average each variant's per-task `reward_opt` over its runs. Pair the two variants on the task ids they share. Report `diff`, `ci` and `n_tasks`.
  - **CLI.** `exp606_report.py runs/<id> [runs/<id> ...]` prints one table row per run in the column order of the issue table (below). It then prints `compare` for each pair of variants present.
- [ ] **Step 4: Run the tests.** `cd core && python -m pytest tests/test_exp606_probe.py -q`. Expected: all pass.
- [ ] **Step 5: Commit, push, and check that PR CI passes.** Commit message: `exp(#606): report script — paired test deltas, val, cost, skill shape, model check`. Then run `gh pr checks <n>` and check that `DCO` passes.

---

### Task 7: Plumbing run (cheap, before any optimizer spend)

- [ ] **Step 1: Dispatch with `iterations=0`.** The run reuses the seed, proposes nothing, and finalizes with the reused seed test.

```bash
gh workflow run benchmarks.yml --ref exp/606-reader-profile \
  -f benchmark=spreadsheetbench -f tier=full_verified_probe -f iterations=0 \
  -f algorithm=hill-climb-all -f gate_k_se=0.2 \
  -f agent_model=ibm-rits/google/gemma-4-31B-it -f optimizer_model=ibm-ete-int/aws/claude-opus-5-5 \
  -f reader_variant=R
```

- [ ] **Step 2: Check the job log.** Every item below must be true:
  - the runner is `skillberry-1-capevolve`;
  - the `>>> rits warm-up` line appears, followed by a passing preflight for both models;
  - `>>> reader:` shows R's text;
  - `>>> reusing the seed of kept run 36622615059`;
  - `>>> reusing on a 100-task test subset of the kept run's 280`;
  - the `finalize` event `test_baseline_reward` equals `seed_test_reward_on_subset`;
  - no test rollouts were run;
  - on skillberry-1, `latest.json` in **both** slot directories is unchanged (`saved_at 2026-09-30T02:53:39Z`).
- [ ] **Step 3: Check the report on the artifact.** Run `exp606_report.py` on the downloaded artifact. It must print one row with `delta = 0`.
- [ ] **Step 4: Post the result on #606.** If any check fails, fix the problem on the branch and repeat Task 7. Do not start Phase 1 until every check passes.

---

### Task 8: Phase 1 — the extremes, R and B × 2

- [ ] **Step 1: Queue four runs in interleaved order: R, B, R, B.** Interleaving spreads any drift in endpoint load or time of day over both variants. The unique concurrency group (Task 1) keeps all four queued, and the single pinned runner runs them one after another.

```bash
for v in R B R B; do
  gh workflow run benchmarks.yml --ref exp/606-reader-profile \
    -f benchmark=spreadsheetbench -f tier=full_verified_probe -f iterations=1 \
    -f algorithm=hill-climb-all -f gate_k_se=0.2 \
    -f agent_model=ibm-rits/google/gemma-4-31B-it -f optimizer_model=ibm-ete-int/aws/claude-opus-5-5 \
    -f reader_variant=$v
  sleep 5
done
gh run list --workflow benchmarks.yml --branch exp/606-reader-profile -L 4 --json databaseId,status
```

- [ ] **Step 2: Watch the first run closely.** It is the first real Opus 5.5 round. Check these points, and post them on #606:
  - the job log's `>>> reader:` block;
  - the optimizer's instructions saved in `host/` contain that exact block;
  - the model ids in the transcripts;
  - the optimizer cost and minutes for the round.

  If the cost per round is far above the #538 figure of $11–14 (for example more than 3×), stop the queued runs with `gh run cancel` and ask the user before continuing.
- [ ] **Step 3: After each run, download the artifact, report it, and post one comment.** Use the "per-run comment" template below.

```bash
gh run download <id> -D runs/<id> && python3 ci/benchmarks/spreadsheetbench/utils/exp606_report.py runs/<id>
```

- [ ] **Step 4: After all four runs, post the phase 1 decision comment.** Apply the rules below to `compare(R, B)`, and include the table from `exp606_report.py runs/*`.

**Decision rules after phase 1.** Here `d = mean test(R) − mean test(B)` on the 100 tasks, and `CI` = its paired 95% CI.

| outcome | condition | next |
|---|---|---|
| **clear difference** | \|d\| ≥ 5 points, CI excludes 0, and both runs of the better variant score above both runs of the other | The reader block matters. Go to phase 2 (A, C). Run phase 3 if R is the better variant. |
| **no difference** | \|d\| < 3 points and CI includes 0 | Likely negative. Add a third run of R and of B to confirm. If it is still < 3 points, report "no measurable effect at 1 iteration", then run phase 3 once (R, 3 iterations) as the only remaining test of the "learns over iterations" idea. |
| **unclear** | anything else | Add a third run of R and of B, then apply the rules again with 3 runs each. |
| **invalid** | any run `valid=False`, or round 1 rejected in ≥ 2 of 4 runs | Stop and post the problem. A rejected round means the test equals the seed, and the comparison measures the gate, not the reader. Ask the user before changing the design. |

---

### Task 9: Phase 2 (only if needed) — A and C × 2, and third repeats

- [ ] **Step 1: Queue `A C A C`,** plus any third R/B repeats the rules asked for, with the same command and `reader_variant` set to each value.
- [ ] **Step 2: Report and comment on each run,** as in Task 8.
- [ ] **Step 3: Post the phase 2 comment.** It holds the full 4-variant table, and `compare` for R–B, R–A, B–A and R–C. It answers two questions:
  - Does the current text (A) sit between the two extremes?
  - Does R's instruction add anything over saying nothing (R–C)?

---

### Task 10: Phase 3 (only if needed) — R with 3 iterations

- [ ] **Step 1: Queue one run** of `reader_variant=R`, `iterations=3` (~3–4 h). Queue a second only if the first gains ≥ 5 points over the phase 1 mean for R.
- [ ] **Step 2: Report the run.** Also post the per-round `step` events (val per round, accepted or not) and each accepted round's prompt diff. These show whether later rounds target the weak areas found in round 1.

---

### Task 11: Final write-up and cleanup

- [ ] **Step 1: Post the final comment on #606.** It holds:
  - the results table;
  - the phase decisions;
  - the answer (does the reader block matter, in which direction, and by how many points with CI);
  - a `<details>` excerpt of each variant's champion `prompt.md` (the first ~40 lines, and the grader-contract section);
  - the skill-shape table;
  - total runner hours and optimizer dollars;
  - the list of run ids.
- [ ] **Step 2: Put the records somewhere that lasts.** Artifacts expire, so the issue comments are the lasting record. Ask the user whether to also open a small docs-only PR to `main` with `docs/experiments/2026-10-xx-reader-profile/` (report tables, `reader/*.md`, `subset_source.json`, and each run's champion capability).
- [ ] **Step 3: Clean up.**
  - Close the draft PR, with a comment that links the final result.
  - Delete the remote and local branch.
  - Remove the worktree.
  - Remove `/tmp/exp606*` on skillberry-1.
  - Keep `spreadsheetbench-606` until the user confirms; it is the only frozen copy of the #538 empty seed.

---

## Issue documentation (#606)

Every comment starts with `**exp #606 — <kind>**` so that the thread can be scanned. Kinds are `log started`, `plumbing run`, `run`, `phase 1 decision`, `phase 2`, `phase 3` and `final`.

**Per-run comment template:**

```markdown
**exp #606 — run** `R` #1 · [run <id>](https://github.com/skillberry-ai/cap-evolve/actions/runs/<id>) · branch sha `<sha>`

| variant | test seed (100) | test opt | Δ [95% CI] | val seed → cand (40) | accepted | opt $ | opt min | wall min | optimizer model(s) | valid |
|---|---|---|---|---|---|---|---|---|---|---|
| R | 0.xx | 0.xx | +x.x [+a, +b] | 0.xx → 0.xx | yes | xx.x | xx | xx | claude-opus-5-5 | ✅ |

Skill shape: chars N · numbered rules N · bullets N · code examples N · worked examples N · grader contract yes/no
Reader block sha256 `<12 chars>` (as printed by `>>> reader:`).
Notes: <anything unusual: infra-error tasks excluded, retries, warm-up time>
```

The running table in the final comment uses the same columns, with one row per run and a mean row per variant.

## Time and cost (from #538, Opus 5.5 cost to be measured on run 1)

| stage | runs | runner time |
|---|---|---|
| Task 7 plumbing | 1 | ~15 min |
| Phase 1 | 4 | ~6–8 h, queued at once, done without supervision |
| Phase 2 (if needed) | 4–6 | ~6–10 h |
| Phase 3 (if needed) | 1–2 | ~3–4 h each |

The first answer (positive, negative or unclear) comes after phase 1: about one working day from the start of Task 0, including ~3–4 h of code and tests.
