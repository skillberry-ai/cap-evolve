# Experiment Plan — Can a fixed skill vocabulary retain per-task specialization?

> **Status: design document only.** Nothing in here is to be executed until the plan is
> approved. The first deliverable is this document committed to the repo; experiments follow.
>
> **First action on approval:** copy this document verbatim to
> `docs/specs/experiments_plan_v1.md` in the **`intake_skillbench_manager`** worktree
> (`../cap-evolve-worktrees/intake_skillbench_manager`, branch `consolidation/skillbench`,
> clean, 28 commits ahead of `origin/main`) and leave it staged-but-uncommitted for review.
> That worktree already holds both files this plan modifies —
> `skills/capabilities/skill-package/scripts/abstract.py` (step 2) and
> `skills/algorithms/agent-optimize/scripts/{merge_taskopt,funcmerge,integrate}.py` (step 3) —
> so the document and its implementation stay on one branch.
> Note `docs/specs/` currently uses a date-prefixed convention
> (`2026-06-24-multi-agent-support-design.md`); the explicit `experiments_plan_v1.md` name
> departs from it deliberately so the version, not the date, is the identifier.
>
> **This is a living document.** It gets amended in place as findings correct or extend it —
> not replaced by side documents — and bumps to a `_v2` filename only on a real design change to
> the arms/subtractions, not on a factual correction. The 2026-09-09 revision to Step 1 (below) is
> the first such amendment: ground truth for the seed vocabulary and per-task provenance already
> lives in `insights/SKILLS_TASKS_MAP.md` / `skills_tasks_map.html` and `ui/heatmap.html` /
> `ui/evoskill_comparison_chart_87.html` on `skillsbench-history`, so Step 1 now targets those
> artifacts instead of a new manifest script.

## Context

We have a benchmark (SkillsBench, **87 tasks**) and a skill library (**195–196 skills**), and we
have already shown that optimizing each task's own skills in isolation lifts the aggregate score
a lot. The paper's claim needs something stronger than that: a **single deployable library** that
honors a fixed vocabulary — no new skills, each skill keeps its role, but prose *and* bundled
tools may change — and a measurement of what that constraint costs.

The user's five alternatives, restated as arms, plus the decomposition needed to make the
headline number interpretable. Two decisions are already taken and are load-bearing here:

- **No held-out task set.** `train == val == test == the task(s) in scope`. The generalization
  pressure comes from *one skill having to serve several tasks*, not from unseen tasks. This is
  an owned limitation, stated in the paper, not something to fix by holding tasks out.
- **cap-evolve is the primary merger**, with the mechanical mergers as comparison variants.

### What the existing data actually says (measured, not assumed)

| fact | value | source |
|---|---|---|
| tasks | **87** (no 101; the "extra 14" is an infra-failure class, see below) | live upstream `gh api .../tasks` |
| unique seed skills | **195** in the per-task artifacts (196 counting `licenses`) | `skillsbench-history:artifacts/task-by-task/` |
| (task, skill) seed pairs | 234 → mean 2.69 skills/task | same |
| skills serving exactly 1 task | **180 / 196 (92 %)** | same |
| skills **actually edited** by an optimizer | **71** | c2+c3+c4 best-candidate dirs |
| (task, skill) pairs where best ≠ seed | **102** | same |
| skills edited under **2+ tasks** (the merge-conflict set) | **6** | same |
| per-task aggregate | 0.508 → **0.842** val, 52 improved / 35 same / 0 regressed | `results/results.json` |
| transfer of one frozen variant to another task | 0.2125 → **0.1625** (net *negative*, n=8) | `results/transfer-eval-8fold/` |

**Correction to an earlier statement of mine:** the improvement was achieved by editing **71**
skills across 102 changed (task, skill) pairs — not 5. The "5/6" figure counts only skills edited
under *more than one* task, i.e. those with competing variants. Two further points the earlier
count got wrong and that the tooling must respect:

- Divergence is often **not in `SKILL.md`**. For `pdf` / court-form-filling the optimizer left
  `SKILL.md` byte-identical and put the entire edit in `forms.md`; the two `xlsx` variants
  diverge partly through *different scripts* (`build_shock_model.py` vs `rar_solver.py`).
  **Every diff and merge must operate on the whole package, not `SKILL.md`.**
- The 65 edited-under-one-task-only skills need **no merge at all** — they carry into a single
  library untouched. The fixed-vocabulary constraint bites on **6 skills** covering ~20 tasks.

### The confound that reshapes the plan

Per-task runs deployed `--skills-dir` containing only *that task's ~2.7 skills*. Any single-library
arm deploys **all ~196 at once**. So a naive "per-task minus merged" gap conflates two very
different effects:

1. **compression loss** — one skill must serve several tasks (6 skills), and
2. **selection / interference load** — the agent must pick the right skill out of 196 instead of 3.

The transfer result is direct evidence that (2) is large and *harmful*: a wrong-but-plausible
skill drove `weighted-gdp-calc` from 0.8 down to 0.2. Separating (1) from (2) is the scientific
contribution and answers the "Vocabulary of Skills" write-up on its own terms — that write-up
asks whether an agent can *compose and select* from a compact vocabulary, and (2) is exactly the
selection half of that question.

**A second confound, now confirmed:** the existing "optimize all at once" runs
(`recipes/all/capevolve.all87.yaml`) seeded **only 4 skills** — `artifacts/all/seed/` contains
`docx`, `pdf`, `pptx`, `xlsx` — against a 195-skill per-task union. Their headline
(+3.11 pp joint vs +36.3 pp per-task on the 43 runnable tasks) is therefore **not** arm 4; it
compared a 4-skill library to per-task 3-skill libraries, and every joint run was additionally
KILLED with `best_id: "seed"`. Arm 4 must be re-run from the full vocabulary.

## Design — six arms, and what each subtraction means

All arms are evaluated on the **same 87 tasks** with the **same** `num_trials`, so every
comparison is paired per task. `A1` and `A3` are optimization runs; the rest are pure evaluations
(`--max-iterations 0`).

| arm | library deployed | per task, skills visible | status |
|---|---|---|---|
| **A0** per-task seed | that task's seed skills | ~2.7 | **have** (0.508) |
| **A0f** full seed | all 196 seed skills | 196 | **new, cheap, run first** |
| **A1** per-task optimized | that task's best variant | ~2.7 | have, needs clean re-score |
| **A2p** merged, per-task view | that task's skills, **merged** versions | ~2.7 | new |
| **A2f** merged, full library | all 196, merged | 196 | **new — the paper's artifact** |
| **A3** jointly optimized | all 196, optimized together | 196 | new (prior attempt invalid) |
| **A4** cluster-optimized | all 196, optimized per task-cluster | 196 | conditional on A3 |

The subtractions are the results:

- `A2f − A0f` — **the deployable gain.** One library, fixed vocabulary, honest comparison
  against the honest baseline. This is the paper's headline.
- `A1 − A2p` — **compression cost in isolation.** Selection difficulty is held constant; only the
  6 merged skills differ. Prediction: small, and confined to the ~20 tasks those 6 skills serve.
- `A0f − A0` and `A2f − A2p` — **selection / interference cost**, measured once without
  optimization and once with. If these are large and similar, vocabulary size hurts through
  selection, not through lost specialization — a sharp, falsifiable claim.
- `A3 vs A2f` — the user's arm 4: **does the route matter**, joint vs per-task-then-merge, now
  from the same starting vocabulary and the same budget.
- `A4` — run only if `A3 vs A2f` is significant under the paired gate. Clusters are defined by
  *shared skills*: the 16 multi-task skills induce a task graph; its connected components are the
  clusters, and the 71 single-task skills stay in whichever cluster their task lands in.

`A1` remains a **non-deployable oracle** — 87 libraries selected by knowing the task in advance.
It is the upper reference line, not a competing system, and the paper must say so.

**Correction (2026-09-09) — A0f is not a dependency for A2p.** An earlier draft of this plan
claimed A0f had to land, and hold up, before A2p could be interpreted ("if A0f collapses, A2p's
result is uninterpretable anyway"). That was wrong, and rested on an incorrect assumption that
A2p deploys the full 196-skill library like A2f/A3/A4 do. It does not: **A2p deploys each task's
normal per-task skill set (~2.7 skills), with only the 6 shared/merged skills' packages swapped
in** — the same selection load as A0, not as A0f. So:

- **A0f is a real dependency only for A2f, A3, and A4** — the arms that deploy all 196 skills at
  once, where the selection/interference confound A0f is designed to isolate actually applies.
  The Risks section's "this is why A0f is ordered first" reasoning is about *those* arms.
- **A2p has two valid, dependency-free comparisons**: **A2p vs A0** (direct — does unifying the
  6 shared skills cost anything, with selection load held constant at ~2.7 skills/task) and
  **A2p vs A1** (the compression-cost-in-isolation subtraction already in the table above). Both
  can run, and be reported, without waiting on A0f.
- Practical effect on sequencing: **A2p can start in parallel with A0f**, not after it. A0f still
  gates A2f/A3/A4, per the Risks section and Delivery order below.

### Step 1 — pin the ground truth (no compute, mostly no new artifact)

**Correction:** an earlier draft of this step proposed a new `build_vocabulary_manifest.py` /
`VOCABULARY.json`, on the premise that this ground truth "lives nowhere as data." That premise
was wrong — it already lives, richly, in four artifacts on `skillsbench-history`:

- `insights/SKILLS_TASKS_MAP.md` and `insights/skills_tasks_map.html` (same content, two
  formats) — Table A (87 tasks → skill numbers, by category), Table B (196 skills → task sets,
  categories, task numbers), and the boilerplate-filename list (`README.md`/`LICENSE`/etc.,
  which is exactly the 195-vs-196 discrepancy: `licenses`-style boilerplate is already excluded
  from the 196 skill numbering). **This pins the seed vocabulary size and every skill's seed task
  set already — no new script needed.**
- `ui/heatmap.html` — an embedded per-task JSON (`DATA`, plus a `DATA_C4` block for the c4 re-run
  comparison) carrying, per task: source worktree/run tag, every candidate's val score, the
  accepted best, and status. It already merges **six** named sources including
  `mac-v2` ("Boaz's Mac, 7 CCC-blocked retried") — **the v2-worktree/Mac baselines are already
  in here**, contrary to what I said; nothing needs to be added on that front. It also already
  resolves the `energy-market-pricing` "3 variants" question directly: `DATA_C4` shows
  `prev` (source `c2-v2`, best `cand_0002`=0.9) vs `curr` (source `c4v1`, best `cand_0005`=1.0) —
  one task, two dated runs, latest wins. Matches the plan's existing "latest run wins" rule
  exactly.
- `ui/evoskill_comparison_chart_87.html` — the aggregate pass_rate headline (73.6% / 83.1% excl.
  no-signal) and per-category rollup vs. the EvoSkill paper baseline. This is the A1 number's
  home, not something Step 1 needs to touch.

**What these four do *not* yet carry, and what Step 1's actual (small) deliverable is:** a
skill-centric conflict view. Table B lists, per skill, which tasks its *seed* serves — it has no
notion of an optimizer-introduced competing variant. That's the genuine gap: which of the 196
skills have **2+ tasks with divergent best-candidate packages**, and what are those variants'
provenance (`task`, `worktree`, `run`, `candidate`, whole-package hash). This is exactly the
`fuzzy-match` (seed: 1 task; optimizer: introduced a 2nd, invalid, out-of-vocabulary use — see the
evidence link below) and `dc-power-flow`/`energy-market-pricing` (2 seed tasks, then a superseding
c4 rerun of one of them) cases, now already explained by `heatmap.html`'s own data.

Deliverable: **append**, not invent — a new "Table D — optimizer-edited skills and cross-task
conflicts" section in `SKILLS_TASKS_MAP.md` (mirrored into `skills_tasks_map.html`), listing the
6 skills edited under 2+ tasks, their variants' provenance, and a pointer to
`evidence/energy-ac-optimal-power-flow-vocabulary-violation/` for the one case where a variant is
an invalid new skill rather than a legitimate competing edit (that evidence currently has only one
inbound link, from a bullet in `SKILLSBENCH_INVENTORY.md` — cross-link it from `heatmap.html`'s
`energy-ac-optimal-power-flow` row too, since that row's `DATA` entry already exists there
(`status: "KILLED_val_1.0"`) with no note that one of its candidates was later found to be an
out-of-vocabulary skill accepted by a degenerate gate).
Sources for the append: the c2/c3/c4 worktree run dirs (authoritative — they contain `references/`
and `scripts/`, `heatmap.html`'s JSON does not) cross-checked against
`skillsbench-history:artifacts/task-by-task/`.

**Step 1 complete (2026-09-10).** Two corrections to the plan text above, both confirmed while
building the append:

- **A new script was needed after all.** The "no new script needed" claim held for Table A/B (the
  seed vocabulary and per-task provenance) but not for the conflict view itself — computing a
  correct per-(task, skill) diff requires walking each task's actual run directory across all six
  c1–c5/v2 worktrees and diffing whole skill packages, not just reading `heatmap.html`'s JSON
  (which has no package contents). `scripts/build_capability_change_tables.py` (on
  `skillsbench-history`, PR #484) does this; it disambiguates the 14 tasks with multiple
  `run_task_<id>*` directories via each run's `state.json.best_id` matched against
  `heatmap.html`'s `best_tag`.
- **The append landed as Table D and Table E, not Table C/D as planned above** —
  `SKILLS_TASKS_MAP.md` already has an unrelated, pre-existing "Table C" (the train/test split),
  which this plan's earlier draft hadn't accounted for. Table D is the granular per-(task, skill)
  view described above; Table E is the skill-level rollup with the cross-task `conflict` flag.

The "6 skills edited under 2+ tasks" figure reconciles as **5 clean cross-task conflicts**
(`dc-power-flow`, `economic-dispatch`, `pdf`, `power-flow-data`, `xlsx`) **plus `fuzzy-match`** —
not a legitimate shared skill, but the vocabulary-violation case already on file at
`evidence/energy-ac-optimal-power-flow-vocabulary-violation/` (a since-excluded, corrupted
candidate invented an out-of-vocabulary `fuzzy-match` package). One further finding surfaced by
the diff and logged in the tables' own "Unresolved" section: `fix-erlang-ssh-cve`'s accepted
candidate scores above seed (0.6 → 0.9) with **zero attributable skill-package change** in this
methodology — its package is byte-identical to seed outside cap-evolve's own bookkeeping files.

### Step 2 — enforce the fixed-vocabulary invariant (currently unenforced)

`skills/capabilities/skill-package/scripts/abstract.py` discovers sub-packages dynamically —
`_subpackages()` returns any immediate sub-dir containing `SKILL.md` — so the optimizer can freely
create `newskill/SKILL.md` or delete one. `apply()` gates edits by kind against a policy `allow`
set, but `add` cannot simply be dropped: new reference files and new tool scripts are exactly what
the user wants to keep allowed.

The correct invariant, added to `apply()` and asserted in `validate()`:

- an `add` whose path's **first segment names a sub-package that does not already exist** is
  refused (`"fixed vocabulary: cannot create a new skill"`);
- `remove` of any existing `<skill>/SKILL.md` is refused;
- `validate()` fails a candidate whose top-level sub-package **set** differs from the seed's.

Gate it behind a spec key `fixed_vocabulary: true` so existing runs are unaffected, and record
the seed's sub-package set at run start. Add a unit test alongside the existing capability tests.

**Second invariant, needed for A2p specifically (added 2026-09-09, per the user's framing):**
`fixed_vocabulary: true` alone allows the optimizer to keep a *different* variant of a shared
skill alive per task — it only pins the sub-package **set**, not the sub-package **contents**
across tasks. A2p additionally requires: **for each of the 6 shared skills, exactly one package
is deployed, identical across every task that shares it** — cap-evolve must never hold more than
a single mutation of a given skill live at once for that arm. Restated as the user put it: "I
will find the 6 shared skills, and their tasks, and will ask cap-evolve to always use the same
skill mutation."

This is an enforcement question, not just a bookkeeping one, and has several candidate
mechanisms, not yet chosen:

- **Run-level**: seed A2p at the *already-merged* package from Step 3 for each of the 6 shared
  skills (i.e., merging happens first, A2p deploys the fixed result) — cap-evolve then never sees
  divergent variants to begin with, and this invariant is satisfied by construction rather than by
  a new check.
  Optimizer edits to a shared skill inside `split_ids` for the joint arms (A3/A4) is the case that
  actually needs a **cross-task lock** on the candidate representation, since those arms *are* the
  optimization step for shared skills. A2p itself only *evaluates* — plan for A2p to consume
  Step 3's output, not to re-derive this invariant inside the optimizer.
- **Validate-time (only relevant if A2p is ever run with `--max-iterations` > 0, e.g. a sanity
  re-tune)**: `validate()` would need to hash each shared skill's package per candidate and reject
  a candidate where two tasks sharing a skill resolve to different hashes. Not needed for the
  currently-planned pure-evaluation A2p, but worth stating so a future run doesn't silently violate
  the invariant.

Given A2p is planned as `--max-iterations 0` (pure evaluation, per the arms table), the run-level
mechanism is sufficient: **A2p's deployment is only correct if it is built from Step 3's single
merged package per shared skill, never from separately-selected per-task variants.** Record this
as a precondition Step 3 must satisfy before A2p can start.

### Step 3 — build the merged library (arm A2)

Only **6 skills** need merging, so all four methods are cheap enough to run and compare. Reuse the
existing machinery in `skills/algorithms/agent-optimize/scripts/` rather than inventing:

- **M1 mechanical** — `merge_taskopt.py` (`git merge-file` 3-way across N variants). Its
  `FILES_DEFAULT = "policy/policy.md,tools/tools.py"` is tau2-shaped; extend it to enumerate
  whole packages. Pair with `funcmerge.py` (per-function AST 3-way) for the diverging scripts,
  which is what it was written for. Conflicts are reported, never auto-resolved.
- **M2 verified accumulation** — `integrate.py`: merge one variant, measure, drop steps that
  regress, with canaries and a noise floor. Its docstring at ~line 127 already anticipates
  "a skill-package capability would pass `SKILL.md` instead" — this is the intended extension.
- **M3 cap-evolve as merger (primary, per the user)** — seed a run at the union of variants for
  one conflicted skill, `split_ids` = exactly the tasks that skill serves, `fixed_vocabulary: true`,
  and let the optimizer reconcile them under the paired gate. This is the only method that can
  *rewrite* toward a genuinely general skill instead of splicing text, and it directly instantiates
  the write-up's compositionality question.
- **M4 concatenate-and-route** — a control: keep both variants as sections under one `SKILL.md`
  with a selection preamble. Cheap, and it isolates "was the merge even necessary, or is routing
  enough?"

Pick per-skill by M2-style verified measurement on that skill's own tasks; report all four so the
merge method is a measured choice, not an assumption. The concrete conflicts to expect: `xlsx`
(13 tasks) and `pdf` (11 tasks) dominate, and the `xlsx` variants carry **directly contradictory
first-action mandates** plus hardcoded output paths (`/root/output/rar_result.xlsx`) — overfit
that a splice will preserve and that M3 is best placed to remove.

### Step 4 — arm A3, joint optimization, done properly

New spec `recipes/all/capevolve.vocab87.yaml`: `capability_path` = the **full 195/196-skill** seed
library, `split_ids` = all 87, `train == val == test`, `fixed_vocabulary: true`,
`algorithm_focus: all`.

Budget must be **matched to A1's total spend** (rollouts + optimizer $), not to its iteration
count — A1 was 87 separate runs. Use `core/cap_evolve/subsample.py` (`select_screen_subset`,
`screen_decision`, `screen_savings`) so each iteration screens on an informative task subset and
only promising candidates pay for the full 87, which is how this becomes affordable at all.
Record the budget-matching arithmetic in the run's `PROJECT.md`.

Two failure modes from the prior attempts to pre-empt, both already documented: the optimizer hung
for 2 h at iteration 4, and 11 % of tasks errored on infra. Cap optimizer turns, and restrict to
the runnable set if infra failures exceed a stated threshold — reporting that restriction rather
than silently absorbing it.

### Step 5 — statistics

87 paired tasks per arm. Reuse `core/cap_evolve/gate.py::decide(mode="paired")` with the run's
`gate_k_se` for arm-vs-arm significance, and `core/cap_evolve/stats.py`
(`combined_stderr`, `bootstrap_ci`, `pass_k`) for intervals. `stats.py` has no rank test; add a
paired-bootstrap or Wilcoxon helper there if a distribution-free check is wanted — the per-task
deltas are bounded and lumpy, so a rank test is the honest companion to the mean.

Report per arm: mean reward, paired Δ vs `A0f` with CI, improved/same/regressed counts, and the
delta restricted to the **~20 conflicted-skill tasks** versus the rest. That split is where the
compression story lives; the aggregate will hide it, since 67 of 87 tasks are untouched by merging.

### Step 6 — the write-up's framing, as reported metrics

The "Vocabulary of Skills" position is that specificity, vocabulary size and generalization trade
off, and that composition may resolve it. Make that measurable rather than merely cited — for
each arm report vocabulary **size** (fixed by construction), **reuse** (tasks per skill),
**specialization** (per-task lift attributable to a skill), **compositionality** (skills invoked
per task from the rollouts), and **selection accuracy** (was the intended skill the one that
fired). `A0f − A0` is the cleanest number we can offer to that debate: the cost of vocabulary
size with specialization held at zero.

## Verification

1. Table D — hand-check `sum(seed task-count)` across its 6 rows against the 234 seed pairs'
   per-skill counts already in Table B, and that intra-task reruns collapsed (no skill lists more
   variants than it has tasks).
2. Invariant tests: a candidate adding `newskill/SKILL.md` is refused; a candidate adding
   `xlsx/references/new.md` and `xlsx/scripts/new.py` is **accepted**; deleting `pdf/SKILL.md` is
   refused; `validate()` fails on a changed sub-package set.
3. Merge sanity before any paid eval: every merged package passes the existing
   `skill-package` `validate()` (frontmatter, ≤500-line body, one-level refs, scripts compile and
   `--self-check`), and the merged library has exactly the pinned number of sub-packages.
4. Smoke A2f on 3 tasks — one conflicted (`shock-analysis-demand`), one single-skill-edited, one
   never-improved — before committing to 87.
5. Reproduce A0 (0.508) from the A0f harness with the per-task library, as a wiring check that the
   new full-library deployment path did not change scoring.
6. `cap-evolve check` green on each new project dir before submission.

## Risks

- **A0f may collapse.** 196 skills in context could dominate everything else; the transfer result
  says interference is real. If so, that *is* the paper's finding, but it should be discovered at
  step "A0f first" for a few hundred rollouts, not after A3 has been paid for. This is why A0f is
  ordered first.
- **Overfit variants may not merge into anything useful.** Hardcoded paths and contradictory
  mandates may mean the honest merged skill is close to seed. M3 is the mitigation; M4 is the
  fallback that at least preserves both behaviours.
- **`train == val == test`** means every arm's number is in-sample. Acceptable per the user's
  decision, but the paper must state that arm-vs-arm *differences* are the claim, not the absolute
  levels, and that `A1`'s 0.842 in particular is a search maximum over candidates.
- **Infra excludes ~44 tasks.** ~26 fail on `python:3.12-slim` apt/chown, ~14 on docker-compose
  `networks:` versus forced `network_mode: host` (**this is almost certainly the origin of the
  "extra 14 tasks"**), ~4 on exotic base images. The `add-python-slim-base-support` worktree is
  the unmerged fix for the largest class; landing it before A3 would materially widen coverage.
  Decide explicitly whether the paper runs 87-with-errors or a stated runnable subset.
- **LSF operational rules apply** (standing memory): no `-W`, `-n 1` for `--max-iterations 0`
  evals, dedicated hosts per concurrent podman job, check `cap-evolve.log` not just `bjobs`, kill
  by exact job ID.

## Delivery order

1. This document → `docs/specs/experiments_plan_v1.md` on `consolidation/skillbench` in the
   `intake_skillbench_manager` worktree (see the Status note above). Staged, not committed —
   you commit it. Optionally cross-linked later from
   `skillsbench-history:proposals/` alongside `train_test_split_proposal.md` and
   `transfer_eval_runs.md`, which is where the *data* provenance docs live; the plan itself
   belongs with the code that implements it.
2. **Done (2026-09-10).** Step 1 — Table D/E append to `SKILLS_TASKS_MAP.md`/`skills_tasks_map.html`
   + evidence cross-links, via `scripts/build_capability_change_tables.py` (no compute; a new
   script was needed after all — see Step 1's completion note above). Landed on
   `skillsbench-history` PR #484.
3. Step 2 invariant + tests (no compute) — **next up**.
4. **A0f** — cheapest arm, highest information, and it de-risks everything downstream.
5. A1 re-score, A2 merge + A2p/A2f.
6. A3, then A4 only if warranted.

## Out of scope

- Adding skills, or changing any skill's role — the constraint under study.
- A held-out task split — explicitly excluded by decision; revisit only if reviewers demand it.
- Deleting the live c1–c5 worktrees (zips exist) and the disposition of `add-ccc-support`.
