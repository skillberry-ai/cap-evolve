# SpreadsheetBench tier configuration

Four tiers, with **different purposes and different honesty guarantees**.

| | `smoke` | `pilot` | `full` | `full_verified` |
|---|---|---|---|---|
| Dataset | `sample_200` | `full_912` | `full_912` | **`verified_400`** |
| Tasks | 10 (from `full_verified`'s train split) | 60 (from `full`'s train split) | 912 (SpreadsheetBench original) | **400 (verified re-release)** |
| Graded cases/task | 3 | 3 | 3 | **1** |
| Split | **no-holdout FIT** | 5 / **50** / 5 — sized to measure | **held-out** — 182 / 91 / 639 | **held-out** — 80 / 40 / 280 |
| `finalize` number is | a FIT metric | **meaningless** | a real generalization number | a real generalization number |
| Agent turns | 5 | **30** | **30** | **30** |
| Container concurrency | 4 | 8 | 8 | 8 |
| Runs on `tier=all`? | yes | **no — explicit only** | yes | **no — explicit only** |
| Purpose | cheap, fast CI signal | cost/runtime measurement | comparison vs the 912 set | **comparison vs recent papers** |

`full` and `full_verified` both produce numbers that may be put next to a paper — but next to
*different* papers, because they are different benchmarks (see below). The smoke report labels
itself `train==val==test (FIT metric, not a generalization/held-out claim)`.

`full_verified` is excluded from `tier=all` for **cost, not honesty**: an `all` dispatch already
launches `full` at ~2,279 rollouts/seed, and sweeping full_verified in would put two four-figure legs
in every dispatch. Run it by name — `tier=full_verified`, or a `benchmark-full_verified-spreadsheetbench`
PR label.

## The `full_verified` tier — the set recent work actually reports on

> **Why `full_verified` and not `full400`.** The tier name is deliberately **generic**: it means
> "this benchmark's verified/curated re-release, wherever upstream publishes one". Any other
> benchmark that gains such a release uses the same tier name rather than inventing one with a
> task count baked in. SpreadsheetBench's happens to have 400 tasks — nothing else needs to,
> and a future re-release of it may not either. The task COUNT is asserted by the tier's tests,
> not encoded in its name.

WikiSkill (arXiv 2608.27454v1) Table 6 gives, for its SpreadSheet benchmark:

> Train **80** · Val **40** · Test **280** · Multi-Step · tools: `bash`
>
> "All task splits and available toolsets are strictly matched with prior work
> (Yang et al., 2026 [SkillOpt]; Alzubi et al., 2026 [EvoSkill])."

80/40/280 is **400 tasks at exactly 2:1:7** — the verified release, not the 912 set `full`
runs. Two consequences:

1. Every SkillOpt/EvoSkill/Trace2Skill number in that paper is on these 400 tasks. A `full`
   result cannot be placed beside them.
2. It **confirms the 2:1:7 reading** `full`'s split was built on. Table 2's 4:1:5 caption is an
   ablation panel, not the headline. The `--ratios 4,1,5` hedge below is no longer needed.

Reported scores there are the **average of three independent runs of the whole pipeline**, with
paired bootstrap significance testing (1,000 resamples, p<0.05). The paper does not state its
evolution-iteration budget — that remains an unmatched dimension.

### The verified 400 is NOT a filter of the 912 — do not derive it that way

All 400 ids appear in `full/tasks.json`, which makes subsetting look safe. It is not. The
verified release is a **re-release with corrected content**:

| | difference from the 912 set |
|---|---|
| Instructions | **226 of 400 rewritten** — several substantively, not cosmetically |
| `answer_position` | 4 changed |
| Golden workbooks | 61 of 394 resolvable ones differ byte-for-byte |
| Graded cases | **1 per task, not 3** |
| Filenames | `1_<id>_init.xlsx` / `_golden.xlsx`; five tasks ship bare `initial.xlsx` / `golden.xlsx` |

Filtering the 912 archive to these ids would score the **older** benchmark while claiming
comparability with work that reports the new one. It is fetched as its own archive
(`SPREADSHEETBENCH_VARIANT=verified_400`, ~15MB), and the adapter reads the number of graded
cases off disk (`_case_indices`) rather than assuming three.

> Because the verified release grades **one** case per task, `soft` and `hard` are identical by
> construction on this tier — so its number is directly comparable to a published "native hard
> score" with no caveat about which metric is quoted. On `full` that caveat is load-bearing.

Regenerate the tier (needs the fetched archive — its id list cannot come from this repo):

```bash
data=$(SPREADSHEETBENCH_VARIANT=verified_400 ci/benchmarks/spreadsheetbench/fetch_data.sh)
python3 ci/benchmarks/spreadsheetbench/utils/make_full_verified.py --data-dir "$data" --write
```

### Cost, versus `full`

Per-iteration evaluation hits the selection split only; `finalize` evaluates test twice.
At `trials=1, iterations=10`:

| | rollouts / seed | × 3 seeds (the paper's protocol) |
|---|---|---|
| `full` (912) | `91 + 10×91 + 2×639` = **2,279** | 6,837 |
| `full_verified` (400) | `40 + 10×40 + 2×280` = **1,000** | 3,000 |

**~44% of the token cost**, and better than that on wall clock: each rollout also drops from
three LibreOffice recalc+compare cycles to one, and the deterministic replay of the final code
block onto cases 2 and 3 disappears entirely. That is what makes three seeds affordable.

The agent model is pinned to `full`'s (`aws/gpt-oss-120b`) so the two tiers differ in the
dataset **only**. The paper's own model axis (Qwen-3.5-4B/9B, Qwen-3.6-27B, Gemma-4-31B,
Gemini-3.5-Flash) is a separate decision: the two small Qwens fit a laptop, the 27B/31B need
real GPUs (the `openshift/` vLLM path), and Gemini is API-only.

### The split is SkillOpt's released split

`full_verified/split_ids.json` is **SkillOpt's own published partition**, not a reconstruction:
the id manifests in [microsoft/SkillOpt `data/spreadsheetbench_id_split`](https://github.com/microsoft/SkillOpt/tree/79124b37e9a6371e13b753f8bcd7adb1e493ade1/data/spreadsheetbench_id_split)
(MIT), built from the same `spreadsheetbench_verified_400.tar.gz` (HF revision `ab0b742b`). WikiSkill
matches its splits to SkillOpt's, so this is the partition both papers' numbers sit on.
`split_source.json` pins the commit and a digest of each split; regenerate with
`python3 ci/benchmarks/spreadsheetbench/utils/make_skillopt_split.py --write`.

Runs before this change used our own seed-42 2:1:7 draw, kept as
`split_ids.capevolve_seed42.json` (it shares 194 of 280 test tasks with SkillOpt's). Their
numbers stay valid on that split but are not on the papers' partition.

### The reward is the workbook as saved; recalculation is recorded too

Each output workbook is compared twice. First **exactly as the agent saved it**, then after
headless LibreOffice recalculates formula caches. On every tier the **reward** is the as-saved
comparison (`hard_no_recalc` / `soft_no_recalc`, following `SB_SCORING`). The recalculated one
is recorded as the non-primary `hard_restriction` / `soft_restriction`. Both appear per task in
`metrics.jsonl` and per candidate and split in `report.md`; `runmeta.json` names the reward in
`reward_metric`.

We score as saved because that is how SkillOpt's evaluator works, and WikiSkill matches
SkillOpt's setup: it loads with `openpyxl.load_workbook(..., data_only=True)` and never
recalculates, so an answer written as a formula reads back as `None` and fails. The SkillOpt
maintainers measured that choice at ~21 points of no-skill score for gpt-5.4 (41.4 vs 62.1,
[SkillOpt#35](https://github.com/microsoft/SkillOpt/issues/35)). On `full_verified` with
Gemma-4-31B-It the no-skill test score is 43.5 as saved and 58.3 recalculated (run
36387149344). When a case fails only because its cells hold formulas, the feedback to the
optimizer says so.

`SB_REWARD_RECALC=1` (in a tier's `overrides.env`) makes the recalculated comparison the reward
again. **Runs before this default** (before #538's follow-up) graded after recalculation, so
their published spreadsheetbench numbers are higher and not comparable with later ones.

### The latest run is kept on the runner

Every spreadsheetbench run replaces the kept slot for its **tier and agent model**, at
`~/.cache/capevolve-latest/spreadsheetbench-slots/<tier>__<model>` on the runner (for example
`full_verified__ibm-rits_google_gemma-4-31B-it`; override with `SB_LATEST_DIR`). A slot holds the
whole run dir, `latest.json` (run id, tier, sha, model), and every output workbook, both
`*_output.xlsx` (recalculated) and `*_output.norecalc.xlsx` (as saved). Set
`SB_KEEP_LATEST_RUN=0` to skip it. One run is kept per tier and model, so a run on another model
never overwrites a seed that a different experiment reuses. Slots are per runner machine.

`SB_REUSE_LATEST_BASELINE=1` (in `overrides.env`) builds a run on the kept run's **seed**: its
val and train rollouts and its sealed test score carry over, and the seed is not re-evaluated.
It refuses if the kept run is another tier or another split. The seed's test score is used only
while the seed capability is byte-identical; the seed snapshot comes from the kept run, so an
empty-seed kept run gives an empty-seed baseline.

The reuse works on a **copy** of the kept run, re-scored under this run's reward by
`utils/rescore_run.py`: each rollout's recorded metric becomes its reward, and `baseline.json`
and the seed's test result are rebuilt from them. A kept run graded after recalculation can
therefore seed a run with the as-saved reward, and the other way round. The kept slot itself is
never modified.

## The `smoke` tier — 10 tasks that are also part of `full_verified`

Smoke is the cheap signal guarding the tiers we report, so its roster is **not arbitrary**:

    pool = sample_200 ids  ∩  full_verified TRAIN ids        (15 candidates; 10 chosen, seed 42)

This is the lesson of the scoring bug this tier configuration was written alongside. Smoke used
to be 10 unrelated tasks from the 200-task sample, and it passed green while `full_verified`
would have scored **0.000 on all 400 tasks** — the two shared only 3 of 10 ids and nothing tied
them together. Both halves of the rule are load-bearing:

- **`sample_200`**, because that is the dataset the smoke tier actually evaluates. An id outside
  it cannot be scored — and the adapter now **refuses** such a run instead of silently dropping
  the task and reporting a clean, shorter run (`assert_run.py` checks the infra-failure
  *fraction*, not the task count, so a shrunken run looked identical to a healthy one).
- **`full_verified`'s TRAIN split**, not its whole roster, because smoke runs a real (if short)
  optimization. 0 of the 10 touch that tier's selection or sealed-test splits.

Both instruction types stay represented (currently 7 Cell-Level / 3 Sheet-Level): they exercise
different comparison paths, and a single-type smoke set silently stops guarding the other.

> **Smoke tasks are part of `full_verified` by ID, not by content.** Smoke grades each task using
> `sample_200`'s copy, so for ids the verified release rewrote (226 of 400) it sees the older
> wording. That is deliberate: keeping smoke on `sample_200` is what preserves cheap coverage of
> the **three-graded-case** path `full` and `pilot` depend on. The verified release's single-case
> layout is covered by unit tests instead of a paid rollout — see
> `core/tests/test_spreadsheetbench_case_layout.py`, which reproduces the 0.000 bug end to end.

Only **4** of the 15 candidates also sit outside `full`'s sealed test split, so the generator
takes those first and then fills: 6 of the 10 overlap `full`'s test ids. (Regenerated when
`full_verified` moved to SkillOpt's split, which changed its train split.)
Widening the pool to `full_verified`'s val split too reaches only 9 of 10 clean, which is not
worth touching a second reported split for. Regenerate with:

```bash
data=$(SPREADSHEETBENCH_VARIANT=sample_200 ci/benchmarks/spreadsheetbench/fetch_data.sh)
python3 ci/benchmarks/spreadsheetbench/utils/make_smoke.py --data-dir "$data" --write
```

## Upstream data defects, and what they cost

The number of graded cases is read off disk (`_case_indices`), not assumed. That surfaced two
real defects, both now handled — and one of them **changes `full`'s numbers**:

| Dataset | Task(s) | Defect | Effect before the fix |
|---|---|---|---|
| 912 | `43026`, `46444`, `4714` | ship **1** test case, not 3 | scored 0 at `hard`, capped at 1/3 at `soft` |
| 912 | `52964` | ships **2** test cases | scored 0 at `hard`, capped at 2/3 at `soft` |
| verified 400 | `42930` | golden misnamed `1_43930_golden.xlsx` (no such id) | task could never score |

> **All four defective 912 tasks are in `full`'s sealed `test` split.** At `SB_SCORING=hard`
> they were **unwinnable** in every `full` run to date. Grading them on the cases that exist
> raises `full`'s sealed score by up to **+0.63pp** (4 of 639) from the fix alone, independent
> of any prompt change. When comparing a new `full` row against an older one on the benchmarks
> page, that much of any gain is bookkeeping: the old denominator was too harsh.

`full_verified` is unaffected by this — it had no valid numbers to be inconsistent with, because the
tier is new.

## The `pilot` tier — a measurement rig, not a benchmark

`pilot` exists to answer three questions before a ~$450 full run is launched:

1. **What does a rollout cost and take at `MAX_TURNS=30`?** Every other anchor comes from
   smoke at 5 turns and does not transfer.
2. **Does `azure/gpt-5.5` work on the gateway at all?** Nothing has exercised it yet.
3. **Does the parallel LibreOffice recalc hold up at non-trivial volume?**

Its split is deliberately *not* 2:1:7. `val` is 50 because that is what every iteration
evaluates (full's is 91, so one pilot iteration extrapolates directly); `test` is 5 because
`finalize` evaluates it twice and teaches nothing new about per-rollout cost; `train` is 5
because with `algorithm_focus: all` the train split is never evaluated.

> **Pilot reward numbers are not comparable to anything** — not to SkillOpt, not to `full`, not
> across pilot runs. A 5-task test split is a cost probe, not a measurement of quality. This is
> why `pilot` is excluded from `tier=all`: the aggregate job publishes every leg to
> `benchmark-history`, and sweeping it in would put meaningless rows on the benchmarks page.

Pilot tasks are drawn **only from `full`'s train ids**, so `full`'s selection and test splits
stay untouched by any pilot run. Regenerate with:

```bash
python3 ci/benchmarks/spreadsheetbench/utils/make_pilot.py --write
```

Suggested dispatch — `tier=pilot`, `trials=1`, `iterations=2`, `agent_model=azure/gpt-5.5`.
At those settings it is `50 + 2×50 + 2×5` = **160 rollouts**.

## The held-out split

`full/split_ids.json` is committed, and `run_suite.sh` uses it instead of the default
no-holdout split because it exists. Regenerate with:

```bash
python3 ci/benchmarks/spreadsheetbench/utils/make_split.py --write
```

### What it reconstructs — and what it does not

It reconstructs **SkillOpt's stated default** (arXiv 2605.23904):

- `split_seed = 42` — stated globally in the paper.
- **2:1:7** train/selection/test — Appendix C's "default 2:1:7 split when no benchmark-specific
  split is stated", which the train-size ablation protocol repeats.

These are **our** choices, because the paper does not publish them:

- **No SpreadsheetBench-specific split is given**, so the 2:1:7 default is applied.
- **No SpreadsheetBench task count is given**, so all 912 tasks are used.
- Table 2's caption says **4:1:5**, but for an *ablation panel*; two other mentions say 2:1:7,
  so 2:1:7 is taken as the headline configuration. If that reading is wrong:
  `make_split.py --ratios 4,1,5 --write`.

> **Therefore: this is a documented reconstruction, not a reproduction of SkillOpt's split.**
> Any comparison must say so. Do not describe a result here as "on SkillOpt's split".
>
> This applies to `full` (912) only. SkillOpt has since released its split for the verified 400,
> and `full_verified` uses it verbatim — see "The split is SkillOpt's released split" above.

### Seeds

The partition is fixed by the committed file, so `SPLIT_SEED` varies only the **per-trial
rollout seeding** — which is what makes independent seeds possible on one split. For the
"≥3 seeds" requirement, set the repo variable `BENCH_SPLIT_SEED` to `42`, then `43`, then `44`
between dispatches. (`workflow_dispatch` caps inputs at 10 and that list is full, which is why
this is a repo variable rather than an input.)

## Editable scope — how "skill text only" is actually enforced

SkillOpt edits a **single natural-language skill document, skill text only**. Here:

- `capabilities: [system-prompt]`, and the seed capability is a **single `prompt.md`** with no
  scripts. There is nothing but text to edit.
- This is a *closer* match than `capabilities: [skill-package]` would be — skill packages also
  ship scripts, which is precisely the scope difference to avoid.
- **`actions: [edit]` is not a machine-enforced constraint.** It appears in some example specs
  but nothing in `core/` or `skills/` reads it. Scope comes from the capability selection above,
  which *is* passed to the optimizer. Do not cite `actions:` as a guarantee.

Our seed is ~190 tokens; SkillOpt's initial skill artifact was **224 tokens**, growing to 1,995
over 4 accepted edits — so seed-to-seed the starting points are comparable.

## Reading a result against the paper

SkillOpt's GPT-5.5 direct-chat column: **No skill 41.8 · human skill 72.9 · GEPA 73.6 ·
SkillOpt 80.7**.

- Compare our **sealed test %** against 80.7 / 73.6 / 72.9.
- **Do not equate our seed baseline with 41.8.** Their "No skill" is the frozen model run with
  *the benchmark's default system prompt* — not an empty context, and not our tuned seed. Their
  own optimization started from a 224-token seed skill whose score the paper does not report.
- Their harness rows use different baselines again (Codex 27.5, Claude Code 22.1), so pin one
  harness and say which.

## Cost and runtime, before you launch a full run

Per-iteration evaluation hits the **91-task selection split only** (with `algorithm_focus: all`
the train split is never evaluated; `finalize` evaluates test twice — best and baseline).

At `trials=1, iterations=10`: `91 + 10x91 + 2x639` = **2,279 rollouts**. Measured smoke rate was
~$0.048/rollout and ~13 s/rollout wall at concurrency 4, so roughly **$110–150 and ~10 h per
seed** — but that anchor predates `MAX_TURNS=30`, and more turns means more cost and more wall
clock per rollout.

**Run a ~50-task pilot at `iterations=2` first** and re-derive both numbers before committing
to 912 x 3 seeds. Also note the shared model gateway has a spend cap; a four-figure run will
start returning `429 budget_exceeded`, which zeroes every rollout.
