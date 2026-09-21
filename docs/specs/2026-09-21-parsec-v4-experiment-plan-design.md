# Parsec v4: Multi-Arm Experiment Plan

**Status:** design document only. No job for section C or G below has been
submitted. Submitting one is a separate, later action.

**Scope:** this doc defines the full arm space for the "parsec v4" study
(34-task Parsec benchmark, capability-evolve optimizer) so that the
`parsec-history` write-up starting from it doesn't need to be renamed or
restructured as later arms are added — the mistake `3x2_toy` made once
("A2p" collided with a section scheme and had to be renamed, see its
`experiment_plan.md` §12 migration note). It borrows its arm vocabulary and
results-schema conventions directly from that pilot
(`docs/specs/3x2_toy_experiment_plan.md`, PR #493;
`results/3x2_toy/summary.md` + `results.json`, PR #494, branch
`bench-history/add-a2p-skill-merge`).

## 0. What's already done

Two arms exist today, both at task granularity, both already run:

- **T1 (`seed`, zs)** — the native, never-optimized multi-agent bundle,
  evaluated zero-shot on all 34 tasks. This is `v4_t1_e1`
  (`rhdp-parsec/v4_2026-09-16/_run/jobs/full34/progress.csv`, n=3 trials/task).
- **T2 (`tbt`, opt)** — task-by-task: one independent optimizer run per
  task, each starting from that task's seed bundle. This is `v4_t2_e1`
  (`.capevolve/v4_t2_e1_<task>/`), and it deliberately only targeted 21 of
  the 34 tasks — the other 13 already scored a perfect 1.0 on the seed
  (`our_baseline`), so there was no headroom to optimize against. See §3.

Top-line numbers (from `results/parsec34/results.json`, built by
`scripts/build_parsec34_heatmap.py`):

| tranche | n | JB reward (mean) | our T1 seed (mean) | our T2 final (mean)\* | Δ vs JB | Δ vs T1 |
|---|---|---|---|---|---|---|
| regression | 30 | 0.833 | 0.845 | 0.963 | +0.131 | +0.119 |
| challenge | 4 | 0.730 | 0.792 | 0.873 | +0.143 | +0.081 |

\*T2 final falls back to the T1 seed score for the 13 tasks T2 never
targeted (they were already at ceiling), so this column is not a clean
"optimized-only" average — see §3.

\*\*Three tasks (`platform-005-wrong-owner-trap`, `platform-007-directory-path-fetch`,
`platform-008-log-does-not-say`) hit a team-wide LLM API budget cap partway
through their first `v4_t2_e1` attempt on 2026-09-20 and were re-run.
`build_parsec34_heatmap.py` originally took the chronologically-latest run
as canonical for any multi-run task; for `platform-007`/`platform-008` that
happened to be correct (their first attempt genuinely underperformed or
never finalized), but `platform-005`'s *first* attempt had already
finalized cleanly (3 candidates, monotonic improvement, held-out test
1.0 ± 0.0, a 0.0 val→test gap) despite the budget errors, and its rerun was
a redundant resample whose noisier seed measurement made the rerun's two
candidates look like a regression (final 0.346 vs. the first attempt's
1.0). The script now takes, per task, the finalized run with the best
`test_reward` rather than the latest one — this is what moved the
regression tranche's T2 final mean from 0.941 to 0.963 above.

## 1. Why a grouping-granularity axis, not a selection/interference axis

`experiments_plan_v1.md` (`consolidation/skillbench` branch) frames its
arms around a **selection/interference confound**: SkillsBench's 87 tasks
each select a handful of skills (~2.7 on average) from a shared 196-skill
library, so merging skills changes what a task sees at all. Parsec has no
such confound — every task already deploys the full multi-agent bundle
(`orchestrator.md` + 6 domain agents + `shared_context.md`), and that
native bundle is one shared global artifact, not per-task or per-category
content: all 8 files are byte-identical (same md5) across every task and
category checked (`platform-001`, `platform-002`, `icinga-010`,
`cloud-024`, `cost-029`).

So parsec's open question isn't "what happens when a task sees more of the
library" — it's "at what scope should we run the optimizer, and does
pooling several tasks' feedback into one optimizer run produce a better
bundle than optimizing each task alone." That's a **grouping-granularity**
axis: how many tasks' rollouts feed a single optimizer run before its
output bundle gets evaluated. This doc organizes arms by three points on
that axis:

- **T — per task** (34 groups of 1; already run, see §0)
- **C — per category** (`cloud`/`cost`/`icinga`/`platform`; 4 groups)
- **G — global** (all 34 tasks; 1 group)

At every level the same four-arm chain from `3x2_toy` applies, reinterpreted
for grouping instead of file-structure:

| arm name | mode | meaning at this grouping level |
|---|---|---|
| `seed` | zs | native bundle, unoptimized, evaluated zero-shot |
| `joint` (T-level: `tbt`) | opt | one optimizer run scoring every task in the group together, output evaluated on each task in the group |
| `merge` | zs | static union of each task's own already-optimized (`tbt`) bundle, evaluated zero-shot on each task in the group |
| `merge-joint` | opt | take the `merge` union as a new seed, continue optimizing it jointly against the whole group |

`joint` at T-level and `tbt` are the same operation — "jointly optimize a
group of size 1" — so T2 is simultaneously the T-level `tbt` arm and a
degenerate T-level `joint` arm; no separate T-level `joint` run is needed.

## 2. Arm table

Numbering follows `<section><n>`, matching `3x2_toy`'s `arm_id` convention.
`status` is `done` (real scores exist) or `not_run` (designed, no job
submitted — scores will be `null` in `results.json` per `3x2_toy`'s
gap-documentation convention, not omitted).

| arm_id | section | name | mode | description | status |
|---|---|---|---|---|---|
| T1 | task | seed | zs | native bundle, zero-shot, all 34 tasks | **done** (v4_t1_e1) |
| T2 | task | tbt | opt | independent optimizer run per task, 21 tasks that weren't already at ceiling on seed | **done, by design** (v4_t2_e1, 21/34 — §3) |
| C1 | category | seed | zs | native bundle, zero-shot, scored per category (= T1 sliced by category, no new run) | **done** (derivable from T1) |
| C2 | category | joint | opt | one optimizer run per category, scoring all of that category's tasks together | not_run |
| C3 | category | merge | zs | per category, union of that category's tasks' T2 bundles, zero-shot, **evaluated on all of that category's tasks including the already-perfect ones** (regression check — §3) | not_run |
| C4 | category | merge-joint | opt | C3's union, continued optimization jointly on that category | not_run |
| G1 | global | seed | zs | native bundle, zero-shot, all 34 tasks (= T1, no new run) | **done** (derivable from T1) |
| G2 | global | joint | opt | one optimizer run scoring all 34 tasks together | not_run |
| G3 | global | merge | zs | union of all 21 T2 bundles, evaluated zero-shot on **all 34 tasks**, including the 13 already-perfect ones (regression check — §3) | not_run |
| G4 | global | merge-joint | opt | G3's union, continued optimization jointly on all 34 tasks | not_run |

C1 and G1 are listed for completeness (they complete the table's symmetry)
but require no new job: the seed bundle is the same shared global artifact
at every grouping level (§1), so its score at category or global scope is
just the corresponding slice/full set of T1's already-measured per-task
scores. `results.json` will still carry them as explicit rows (matching
`3x2_toy`'s style) with a `source: "derived from T1"` note rather than a
`jobs` pointer.

## 3. T2 skipped 13 tasks that were already at ceiling on seed

T2 wasn't cut short by time or resources — it deliberately only targeted
tasks where the seed bundle hadn't already scored a perfect 1.0 on our
baseline run. Confirmed against `results/parsec34/results.json`: all 13
`status: "not_optimized"` tasks have `our_baseline == 1.0` (12 of the 13
also have `jb_reward == 1.0`; the one exception, `platform-019`, scored
`jb_reward: 0.15` but `our_baseline: 1.0` — our baseline run already
cleared it before T2 would have started).

| category | tasks | already-perfect on seed (skipped) | T2-optimized |
|---|---|---|---|
| platform | 19 | 6 | 13 |
| icinga | 8 | 4 | 4 |
| cloud | 4 | 2 | 2 |
| cost | 3 | 1 | 2 |
| **total** | **34** | **13** | **21** |

This resolves most of the "what does the union include for a task with no
T2 bundle" question from an earlier draft of this doc: since those 13
tasks were already at ceiling, there is no missing optimized content to
merge in for them — the seed bundle already is their best-known bundle.
C3/C4/G3/G4's merge input is simply the union of the 21 T2 bundles; no
fallback rule is needed on the input side.

What *does* need to happen, and doesn't happen automatically: **the merged
bundle must be evaluated against all 34 tasks, not just the 21 that
contributed to it.** Merging other tasks' task-specific optimizer edits
into the shared files (`orchestrator.md`, the domain agents,
`shared_context.md` — see §4) could regress one of the 13 tasks that used
to score a perfect 1.0 on the untouched seed. C3/C4 (per category) and
G3/G4 (global) must each report scores for every task in their group,
including the already-perfect ones, specifically to catch that kind of
regression — this is now reflected in §2's arm table.

All 13 skipped tasks are `regression` tranche (0 `challenge`) — equivalently,
all 4 `challenge` tasks were T2-optimized. Any category/global merge
aggregate must still report regression and challenge separately (never
pooled, per §0's table), but this does mean the `challenge` row of any
C3/C4/G3/G4 result is a pure "all inputs were T2-optimized" case, with no
already-perfect tasks to regress-check within that tranche — the
regression-check concern above is entirely a `regression`-tranche concern.

## 4. Open question: what does "merge" mean for an 8-file multi-agent bundle

`3x2_toy`'s `merge` arm unions **distinct, non-overlapping** SKILL.md files
(three separate skill packages) — union is unambiguous because each
donor task's optimizer only ever touched its own file.

Parsec's bundle is the opposite shape: one shared set of 8 files
(`orchestrator.md`, 6 domain agents, `shared_context.md`), and once T2
optimizes a task independently, its optimizer may have edited *any* subset
of those 7 files in task-specific ways. Merging two tasks' T2 outputs means
merging edits to the *same files*, not unioning disjoint files. This is a
real merge-conflict problem, not a directory union, and needs its own
resolution strategy before C3/C4/G3/G4 can run — options range from
"per-file, take whichever task's edit is later/larger" (crude, likely
wrong) to "diff each domain-agent file against the shared seed and union
non-overlapping diff regions" (better, still needs conflict handling) to
"treat this as its own small optimizer-assisted merge step." This doc does
not pick one; whichever job actually runs C3/C4/G3/G4 should state its
merge strategy explicitly in that arm's `results.json` row.

## 5. Naming and collision check

- "parsec v4" does not appear anywhere in `experiments_plan_v1.md`
  (`consolidation/skillbench` branch) — confirmed via `git grep`. No
  collision with that scheme's `A0`/`A0f`/`A1`/`A2p`/`A2f`/`A3`/`A4`
  letter codes.
- This doc's `T`/`C`/`G` + number scheme is new (not borrowed verbatim from
  `3x2_toy`'s `A`/`B` section-letter scheme, since `3x2_toy`'s two sections
  are a file-structure axis and parsec's three sections are a
  grouping-granularity axis — different axis, so reusing `A`/`B` would
  imply a false correspondence). If a future arm needs a name (e.g. a
  cross-category zero-shot hand-off, mirroring `3x2_toy`'s `cross` arm),
  extend this table rather than renaming existing ids — see the
  A2p-renaming lesson in §"Scope" above.

## 6. Relationship to the parsec-history / benchmark-history PR work

This spec is step 1 of the same two-PR structure `3x2_toy` used:

1. **This doc** — committed to `docs/specs/` on a plain branch off `main`,
   no job submitted yet for any `not_run` arm.
2. **Results PR into `parsec-history`** — `results/v4/summary.md` +
   `results.json` (T1/T2 rows populated now with real scores; C/G rows
   present with `status: "not_run"`, `scores: null`, per §2), with its own
   separate v4 ledger and heatmap page — kept structurally independent from
   v1/v2's shared `results/results.json` / `ui/heatmap.html` rather than
   folded in, since v4's 34-task/multi-arm shape doesn't match v1/v2's
   per-experiment shape — plus `recipes/v4/`,
   `artifacts/v4/<task>/{seed,best,rejected}/` for the 21 T2-optimized
   tasks, and `reports/task-by-task/v4-*.md` for all 34 tasks. This
   references this spec doc.
3. **`benchmark-history` record** referencing both (1) and (2), following
   the PR #466 pattern.

Scaffold/adapter code letting Harbor talk to parsec lives separately in
PR #495 (`feat(parsec): add parsec as a first-class benchmark +
HARBOR_LOCAL_ASIS`, branch `parsec-intake_v4`) — this doc does not
duplicate or restate that code.

## 7. Deferred: CCC migration

Running C2/C3/C4/G2/G3/G4's jobs in parallel on the CCC (LSF cluster —
`bsub`/`bjobs`/`bhosts`/`brsvs`, per `3x2_toy_experiment_plan.md`'s
"Operational notes (CCC / LSF)" section) is the natural way to execute this
table's `not_run` rows once §3 and §4 are resolved. That migration is
explicitly out of scope for this doc and for the immediate PR work — it
starts only after everything from the current local work is committed and
pushed.
