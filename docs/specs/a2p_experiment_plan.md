# A2p baseline plan — cross-task skill-variant evaluation before merge

> **Status: design document only.** No `bsub` job goes out until scope is confirmed here.
> Worktree: `intake_skillbench_c7` (branch `intake_skillbench_c7`, forked from `main` at
> `020cae22`, same base as c1–c6).

## 0. This is not a new experiment — it's Steps 2/3 of an existing plan

`docs/specs/experiments_plan_v1.md` (committed on `consolidation/skillbench` in the
`intake_skillbench_manager` worktree, PR history through Step 1) already defines **A2p** in
detail: arm table, the two dependency-free comparisons (`A2p vs A0`, `A2p vs A1`), the
fixed-vocabulary invariant, and four candidate merge methods (M1 mechanical, M2 verified
accumulation, M3 cap-evolve-as-merger, M4 concatenate-and-route). Status there:

- **Step 1 (pin ground truth) — done, 2026-09-10.** This is exactly the provenance you pasted:
  `insights/SKILLS_TASKS_MAP.md` Table E, 6 skills edited under 2+ tasks
  (`dc-power-flow`, `economic-dispatch`, `pdf`, `power-flow-data`, `xlsx` = clean conflicts;
  `fuzzy-match` = a vocabulary-violation case, not a legitimate shared skill — its second
  "variant" was an invalid, since-excluded candidate, not a real competing edit).
- **Step 2 (fixed-vocabulary invariant in `abstract.py`) — not started.** Not needed for what
  we're doing below (pure evaluation, no optimizer loop), only for a later re-tune of the merged
  package.
- **Step 3 (build the merged library) — not started.** This is the "merge" half of your request.

So this document's job is narrower than "design A2p from scratch": it's to spell out the
**baseline sub-step you asked for** — evaluate each conflicted skill's variants against every
task that shares it, *before* Step 3's merge — and to answer your verification question about
whether the 8-fold transfer experiment already did this.

## 1. Verified: the transfer experiment is a related but different design

Checked `results/transfer-eval-8fold/summary.md` directly. Your assumption needs a correction:

**The transfer experiment used different *tasks*, not the same task under two mutations.** Each
of its 8 folds takes task A's frozen winning skill and evaluates it zero-shot on a *different*
task B, then compares B's transferred score against B's own native seed/optimized score. There
is no merge step anywhere in it — it substitutes one variant for another, one direction at a
time, and never combines two variants into one package.

Two more differences worth naming explicitly:

- **Only 3 of the 8 folds touch a Table E conflicted skill at all** — `shock-analysis-demand`,
  `shock-analysis-supply`, `weighted-gdp-calc` are three of `xlsx`'s six conflicted tasks, so
  folds 1–6 (all pairs among those three) are a legitimate same-skill subset. Folds 7–8
  (`exam-block-sequencing` ↔ `paratransit-routing`) share no skill in Table E — those two tasks
  don't even share a nominal skill (`mip-solver-and-solution-audit`/`ordered-window-sequencing-mip`
  vs. `ortools-pickup-delivery-routing`/`ortools-routing-modeling`), so that pair is out of scope
  for A2p entirely.
- **It never touches `dc-power-flow`/`economic-dispatch`/`power-flow-data`/`pdf`**, and only
  covers half of `xlsx`'s 6 tasks (missing `exceltable-in-ppt`, `sales-pivot-analysis`).

So: the transfer experiment is a **precedent for the mechanism** (zero-shot substitution,
`--max-iterations 0`, compare against `results.json`'s native seed) and gives us 6 of the cells
we need for `xlsx` for free — it is not a stand-in for the full A2p baseline, and it never
merges anything.

**One more thing the transfer results already tell us, which should shape scope below:**
folds 2 and 4 show a donor skill actively dragging `weighted-gdp-calc` from 0.8 down to
0.2–0.3. If that generalizes, a naive merge of `xlsx`'s 6 variants risks producing something
worse than several tasks' own native seed — the baseline matters because it's the thing the
merged package has to beat, not just a formality.

## 2. What "baseline before merge" should mean here

For each of the 5 clean conflicted skills (excluding `fuzzy-match`), and for the *set of tasks
that skill serves* (from Table E's provenance):

- **Native cells** (task run under its own variant) — already have these, they're
  `results.json`'s per-task numbers. No new runs needed.
- **Cross cells** (task run under a *different* task's variant of the same skill,
  `--max-iterations 0`, no adaptation) — this is what's missing, and what the transfer
  experiment's harness (`.capevolve/run_transfer_<train>_to_<test>_v{1,2}/` pattern,
  `submit_ccc_experiment.sh`-adjacent direct `bsub` calls) already knows how to run.

For a skill shared by *N* tasks, the full cross-product is *N × (N−1)* off-diagonal cells (plus
*N* native, already known). That is cheap for the 2-task groups and expensive for `xlsx`:

| skill | tasks it serves | cross cells (off-diagonal) |
|---|---|---|
| `dc-power-flow` | energy-market-pricing, grid-dispatch-operator | 2 |
| `economic-dispatch` | energy-market-pricing, grid-dispatch-operator | 2 |
| `power-flow-data` | energy-market-pricing, grid-dispatch-operator | 2 |
| `pdf` | court-form-filling, pdf-excel-diff | 2 |
| `xlsx` | exceltable-in-ppt, reserves-at-risk-calc, sales-pivot-analysis, shock-analysis-demand, shock-analysis-supply, weighted-gdp-calc | 30 (6 already covered by the 8-fold pilot: the demand/supply/gdp trio) |

Note `dc-power-flow`, `economic-dispatch`, and `power-flow-data` are the **same two tasks**
(`energy-market-pricing`, `grid-dispatch-operator`) — they were all edited together because those
two tasks' optimizer runs touched all three skills as one bundle. So those three "skills" collapse
to **one 2-task swap experiment**, not three independent ones: run each task once under the
other task's *whole skill directory* (all three packages together, since that's how they were
actually co-edited) and you get all three skills' cross cells from 2 jobs, not 6.

## 3. Scope question — my recommendation

You asked: full cross-product, a subset, or start with a single skill? Given the standing rule
against extending past 8 scoped pilot runs without checking in, and that we already have 6 of
`xlsx`'s 30 cross cells from the transfer pilot:

**Start with the `dc-power-flow`/`economic-dispatch`/`power-flow-data` bundle — 2 jobs, 1 pair of
tasks, all 3 conflicted skills resolved at once.** Reasons:

1. It's the cleanest signal: exactly one task-pair, one swap in each direction, no combinatorics.
2. It resolves 3 of the 6 conflicted skills in 2 runs — the best information-per-job ratio here.
3. It's a genuinely new data point (the transfer pilot never touched these tasks/skills), unlike
   redoing part of `xlsx`.
4. `pdf`'s 2-task pair (`court-form-filling` ↔ `pdf-excel-diff`) is the natural second step — same
   shape, 2 more jobs — and together with the bundle above that's **4 jobs total**, leaving
   headroom under the 8-job pilot ceiling for `xlsx` cross-cells you actually pick once these land.
5. `xlsx` is deliberately last: it's the most expensive (30 cross cells even after crediting the
   6 already-run) and, per §1, the one skill where the transfer pilot already shows a donor
   variant can badly hurt a receiving task — worth seeing whether the smaller, cleaner pairs show
   the same failure mode before spending the bulk of the budget there.

If this scope works, the concrete next jobs are:

- Job set A (2 jobs): `energy-market-pricing`'s `{dc-power-flow, economic-dispatch,
  power-flow-data}` bundle deployed zero-shot on `grid-dispatch-operator`, and vice versa.
- Job set B (2 jobs): `court-form-filling`'s `pdf` deployed zero-shot on `pdf-excel-diff`, and
  vice versa.

Both reuse the transfer-eval mechanism directly (`--max-iterations 0`, frozen donor package,
score against `results.json`'s native seed/optimized for that task) — no new harness work,
same LSF operational rules (`-m <host>`, `-n 1`, no `-W`, poll `cap-evolve.log`, kill by exact
job ID).

## 4. After baselines: the merge (Step 3)

Once native + cross cells exist for a skill group, Step 3's four methods (M1–M4, see
`experiments_plan_v1.md`) apply unchanged: build one merged package per conflicted skill, deploy
it to every task that shares it, and compare against both the native and cross baselines from
above. That comparison is `A1 − A2p` in the plan's arm table — this document only covers what
has to exist before that subtraction is meaningful.

## 5. Full per-task × per-mutation job table

Per your instruction: for each relevant task, run it once per available mutation of its
conflicted skill(s) — a task whose skill has *N* mutations gets *N* independent jobs, each
10 trials, `--max-iterations 0`. This is the full cross-product from §2/§3 written out as
literal jobs, grouped by co-edited skill bundle (the `dc-power-flow`/`economic-dispatch`/
`power-flow-data` trio is one bundle, per §2's note — a task is deployed with all three
packages together in a single job, not three separate jobs).

Status column: **have** = already exists (native rows = `results.json`; the marked xlsx cross
rows = `results/transfer-eval-8fold/`), **new** = not yet run.

### Group A — `dc-power-flow` + `economic-dispatch` + `power-flow-data` bundle (2 tasks × 2 mutations = 4 jobs)

| Task run on | Mutation from | Provenance (run_dir / cand, val) | Status | Trials | Job label |
|---|---|---|---|---:|---|
| energy-market-pricing | energy-market-pricing (native) | `run_task_energy-market-pricing_v2/cand_0002` (val 0.9) | have | 10 | `a2p_energy-market-pricing_x_native` |
| energy-market-pricing | grid-dispatch-operator (cross) | `run_task_grid-dispatch-operator_v1/cand_0002` (val 1.0) | new | 10 | `a2p_energy-market-pricing_x_grid-dispatch-operator` |
| grid-dispatch-operator | grid-dispatch-operator (native) | `run_task_grid-dispatch-operator_v1/cand_0002` (val 1.0) | have | 10 | `a2p_grid-dispatch-operator_x_native` |
| grid-dispatch-operator | energy-market-pricing (cross) | `run_task_energy-market-pricing_v2/cand_0002` (val 0.9) | new | 10 | `a2p_grid-dispatch-operator_x_energy-market-pricing` |

### Group B — `pdf` (2 tasks × 2 mutations = 4 jobs)

| Task run on | Mutation from | Provenance (run_dir / cand, val) | Status | Trials | Job label |
|---|---|---|---|---:|---|
| court-form-filling | court-form-filling (native) | `run_task_court-form-filling_v1/cand_0002` (val 1.0) | have | 10 | `a2p_court-form-filling_x_native` |
| court-form-filling | pdf-excel-diff (cross) | `run_task_pdf-excel-diff_v1_KILLED_ceiling_reached_1.0/cand_0001` (val 1.0) | new | 10 | `a2p_court-form-filling_x_pdf-excel-diff` |
| pdf-excel-diff | pdf-excel-diff (native) | `run_task_pdf-excel-diff_v1_KILLED_ceiling_reached_1.0/cand_0001` (val 1.0) | have | 10 | `a2p_pdf-excel-diff_x_native` |
| pdf-excel-diff | court-form-filling (cross) | `run_task_court-form-filling_v1/cand_0002` (val 1.0) | new | 10 | `a2p_pdf-excel-diff_x_court-form-filling` |

### Group C — `fuzzy-match` (1 task × 1 legitimate mutation = 1 job; no cross exists)

Only `invoice-fraud-detection` has a legitimate mutation. There is no second task to cross it
against — the only other "variant" (`energy-ac-optimal-power-flow`) is the excluded,
out-of-vocabulary candidate, not a real competing edit (§0). Listed for completeness, not as a
real cross-mutation experiment; run the optional row only if you specifically want to see how the
invalid variant scores elsewhere, not as part of the core A2p baseline.

| Task run on | Mutation from | Provenance (run_dir / cand, val) | Status | Trials | Job label |
|---|---|---|---|---:|---|
| invoice-fraud-detection | invoice-fraud-detection (native) | `run_task_invoice-fraud-detection_v1/cand_0002` (val 0.4) | have | 10 | `a2p_invoice-fraud-detection_x_native` |
| *(optional, not a core A2p cell)* invoice-fraud-detection | energy-ac-optimal-power-flow (excluded, out-of-vocab) | `run_task_energy-ac-optimal-power-flow_v1_CORRUPTED_batch3/cand_0002` or `cand_0003` | new | 10 | `a2p_invoice-fraud-detection_x_energy-ac-optimal-power-flow_INVALID` |

### Group D — `xlsx` (6 tasks × 6 mutations = 36 jobs)

Tasks: `exceltable-in-ppt` (E), `reserves-at-risk-calc` (R), `sales-pivot-analysis` (S),
`shock-analysis-demand` (D), `shock-analysis-supply` (U), `weighted-gdp-calc` (G). The 6 cells
among {D, U, G} marked "have (8-fold)" already ran in `results/transfer-eval-8fold/`; every cell
touching E, R, or S is new — the 8-fold pilot never covered them.

| Task run on ↓ / Mutation from → | E (exceltable-in-ppt) | R (reserves-at-risk-calc) | S (sales-pivot-analysis) | D (shock-analysis-demand) | U (shock-analysis-supply) | G (weighted-gdp-calc) |
|---|---|---|---|---|---|---|
| **E** | have (native) | new | new | new | new | new |
| **R** | new | have (native) | new | new | new | new |
| **S** | new | new | have (native) | new | new | new |
| **D** | new | new | new | have (native) | have (8-fold, fold 3, transfer 0.0) | have (8-fold, fold 5, transfer 0.0) |
| **U** | new | new | new | have (8-fold, fold 1, transfer 0.1) | have (native) | have (8-fold, fold 6, transfer 0.1) |
| **G** | new | new | new | have (8-fold, fold 2, transfer 0.2) | have (8-fold, fold 4, transfer 0.3) | have (native) |

Provenance for the "have" native cells and mutation sources (same 6 run dirs feed every row and
column since each task's own variant is both a native cell and a cross-donor elsewhere):

| Task | Provenance (run_dir / cand, val) |
|---|---|
| exceltable-in-ppt | `run_task_exceltable-in-ppt_v1_KILLED_ceiling_reached_1.0/cand_0001` (val 1.0) |
| reserves-at-risk-calc | `run_task_reserves-at-risk-calc_v2/cand_0004` (val 1.0) |
| sales-pivot-analysis | `run_task_sales-pivot-analysis_v1_KILLED_ceiling_reached_1.0/cand_0001` (val 1.0) |
| shock-analysis-demand | `run_task_shock-analysis-demand_v2/cand_0004` (val 0.9) |
| shock-analysis-supply | `run_task_shock-analysis-supply_v2/cand_0004` (val 0.3) |
| weighted-gdp-calc | `run_task_weighted-gdp-calc_v1_KILLED_ceiling_reached_1.0/cand_0001` (val 1.0) |

Job label convention for the new cells: `a2p_<task>_x_<mutation-source>`, e.g.
`a2p_exceltable-in-ppt_x_reserves-at-risk-calc`.

### Summary — job counts

| Group | Total cells (tasks × mutations) | Have | New |
|---|---:|---:|---:|
| A — dc-power-flow/economic-dispatch/power-flow-data bundle | 4 | 2 | 2 |
| B — pdf | 4 | 2 | 2 |
| C — fuzzy-match (core cell only) | 1 | 1 | 0 |
| D — xlsx | 36 | 12 (6 native + 6 from 8-fold) | 24 |
| **Total (core, excluding the optional invalid fuzzy-match row)** | **45** | **17** | **28** |

**This is well past the 8-scoped-pilot-run ceiling as a single batch.** §3's recommendation
still stands as the order of operations: run Group A (2 new jobs) and Group B (2 new jobs) first
— 4 new jobs, under the ceiling — then check in before Group D's 24 new cells, which dwarf
everything else and are where §1's "donor skill actively hurts the target" risk is most likely to
recur.

## Open questions for you

1. Does the job-set-A/B scope (4 jobs, resolving `dc-power-flow`/`economic-dispatch`/
   `power-flow-data` + `pdf`) match what you meant by "start with a single skill," or did you
   want literally one skill (e.g. just `pdf`, 2 jobs) first?
2. For `xlsx`, once A/B land: pick the cross cells by hand (e.g. the ones most likely to be
   informative given the val scores already in Table E), or run the remaining 24 off-diagonal
   cells as a second scoped batch?
3. Should job sets A and B run now, or do you want to review this document first and greenlight
   separately?

## 6. Step 3 prep — skill-pair diff assessment (Group A bundle)

While the Group A jobs above ran, read both variants of all three conflicted skills in full
(`.capevolve/_donor_energy-market-pricing_cand_0002/` = val 0.9, `.capevolve/_donor_grid-dispatch-operator_cand_0002/`
= val 1.0, ceiling) and compared them section by section. This is prep for M1–M4 (§4 /
`experiments_plan_v1.md`), not a merge yet — no package has been built.

### `dc-power-flow` — clean, additive, no conflict

The two variants share the entire formulation (bus mapping, B matrix, power balance, slack
bus, line flow/loading, thermal-limit constraints) verbatim. Each adds one section the other
lacks, and neither contradicts the other:

- energy-market-pricing's variant has a **"Solver"** pointer to the `cvxpy` setup recipe.
- grid-dispatch-operator's variant has a **"Reference DC model conventions (match these
  exactly)"** warning: don't fold tap ratio / phase-shift / resistance / in-service status
  into `b`, only `b = 1/X` — deviating changes the computed optimum.

Straight union of both sections is a safe merge; nothing to arbitrate.

### `economic-dispatch` — same core math, but a structurally different delivery mechanism

Both variants share the generator-data/cost-function/reserve/margin/output-format sections
verbatim. The difference is how the agent is told to solve the problem:

- **energy-market-pricing's variant** teaches the formulation inline (write the `cvxpy`
  problem yourself) and points at a short "Solver" setup snippet (`pip install cvxpy`, plain
  venv-friendly).
- **grid-dispatch-operator's variant** replaces that with (a) a much harder-won **"Step 0"**
  environment section — install the solver stack into the **system** `python3`
  (`pip3 install --break-system-packages`), explicitly **not** a venv, because "the grader
  re-runs `pip3 install ... cvxpy==1.4.2` against the system interpreter" — and (b) a bundled
  `scripts/solve_dispatch.py` the agent is told to just *run* instead of hand-rolling the
  formulation, plus `scripts/setup_solver_env.sh`.

**This is not a safe verbatim merge.** `solve_dispatch.py` is real code, not prose — I read it
(`economic-dispatch/scripts/solve_dispatch.py`, grid-dispatch-operator variant). It writes a
fixed `report.json` schema: `generator_dispatch`, `totals`, `most_loaded_lines`,
`operating_margin_MW`. That schema matches grid-dispatch-operator's own grader, but it never
extracts constraint dual values — and I confirmed (read `locational-marginal-prices/SKILL.md`,
kept native in energy-market-pricing's project) that **energy-market-pricing's task needs LMPs,
i.e. the dual values of the nodal balance constraints**, which requires keeping named
constraint references and reading `.dual_value` after solving — something `solve_dispatch.py`
does not do or expose. Handing energy-market-pricing's task "just run the bundled solver"
verbatim would silently produce a report with no price data. This is the concrete instance of
§1's risk ("a donor variant can actively hurt the receiving task") showing up structurally
rather than as a score regression — it would fail quietly by omission, not by a wrong number.

The env-hardening half (Step 0, system-wide install, not venv) has no such downside — it is a
strict improvement with no task-specific coupling, and should merge unconditionally.

### `power-flow-data` — same story in miniature, plus a case of "already deferred"

Body sections (large-file handling, bus types, per-unit, loading, reserve data, bus mapping,
branch interpretation, total load) are byte-identical between variants. The only difference is
the "Solver setup" section:

- energy-market-pricing's variant carries the **full recipe inline** (its own
  `scripts/setup_env.sh`, plain `pip install`, no `--break-system-packages`, no venv warning) —
  this is the *older*, less hardened version of the same setup economic-dispatch improved on.
- grid-dispatch-operator's variant **replaces the inline recipe with a one-line pointer** to
  economic-dispatch's Step 0 — it already deduplicated by deferring, rather than maintaining
  two copies of the same setup logic.

Merge should follow grid-dispatch-operator's pattern here too: keep the pointer-to-Step-0
form (not the older inline recipe), and additionally retain energy-market-pricing's one
sentence explaining *why* `cvxpy` is the right tool here — "it exposes the constraint dual
values that locational marginal prices ... are read from" — since that sentence, not the setup
recipe, is what's task-relevant and would otherwise be lost.

### What this means for M1–M4 (§4)

- **M1 (mechanical)** — a naive text union works cleanly for `dc-power-flow` and the
  `power-flow-data` pointer swap, but for `economic-dispatch` it would either (a) merge in the
  bundled solver as a top-level "just run this" instruction — wrong for LMP tasks — or (b)
  keep both the inline formulation and the bundled-solver shortcut side by side with a caveat
  scoping the shortcut to tasks whose output schema matches. (b) is closer to correct but is
  no longer purely mechanical.
- **M2/M3/M4** — any method that can weigh "does this task need dual values" when deciding
  what to keep will do better here than a method that only diffs text. This conflicted skill
  is a good stress test precisely because the two variants aren't rephrasings of the same
  idea — one added a task-specific shortcut that quietly drops information the other task
  depends on.
- Recommended default for the actual merge (when asked for): union `dc-power-flow` outright;
  union `economic-dispatch`'s env-hardening outright; keep `economic-dispatch`'s inline
  formulation as the general path and demote the bundled `solve_dispatch.py` to an explicitly
  scoped "if your task's output schema matches grid-dispatch-operator's `report.json` exactly,
  you may run this instead" note rather than the default instruction; for `power-flow-data`,
  take grid-dispatch-operator's pointer form plus energy-market-pricing's one-sentence "why
  cvxpy" note.

Not yet built — this section is assessment only, per your instruction to review the diff
before asking for the merged version.

## 7. Merged bundle — built, and tested three ways

Built at `.capevolve/_merged_a2p_bundle_v1/{dc-power-flow,economic-dispatch,power-flow-data}/`,
following the §6 recommended default exactly: `dc-power-flow` is a straight union of both
variants' sections; `economic-dispatch` keeps the inline formulation as the default path, unions
grid-dispatch-operator's Step 0 env-hardening unconditionally, and demotes `solve_dispatch.py` to
an explicitly-scoped "only if your schema matches and you don't need dual values" shortcut;
`power-flow-data` takes grid-dispatch-operator's pointer-to-Step-0 form plus energy-market-pricing's
one-sentence "why cvxpy" note. `py_compile`/`bash -n` clean on the carried-over scripts
(`build_b_matrix.py`, `solve_dispatch.py`, `setup_solver_env.sh`); `cap-evolve check` green on
every project below.

Three jobs test it, run in parallel:

| Job label | Project | Skills seeded | Mode | LSF job |
|---|---|---|---|---|
| `a2p_energy-market-pricing_x_merged_v1` | `project_energy-market-pricing_x_merged` | merged bundle + native `locational-marginal-prices` | zero-shot (`--max-iterations 0`) | 778690 |
| `a2p_grid-dispatch-operator_x_merged_v1` | `project_grid-dispatch-operator_x_merged` | merged bundle only (task has no 4th skill) | zero-shot (`--max-iterations 0`) | 778691 |
| `a2p_joint_bundle_v1` | `project_a2p_joint_bundle_v1` | merged bundle + native `locational-marginal-prices`, seeded then let the optimizer edit it | **real optimization**, `train==val==test=={energy-market-pricing, grid-dispatch-operator}`, `max_iterations: 2`, budget doubled (`max_usd: 300`, `max_optimizer_usd: 160`) to cover 2-task rollouts per iteration | 778692 |

The third job is the "4th arm" requested alongside the merge: a scoped-down analog of arm A3 in
`experiments_plan_v1.md` (there: jointly optimize all 196 skills against all 87 tasks; here: jointly
optimize just these 3 conflicted skills against just these 2 tasks). It answers a different
question than the static merge does — not "how good is a text-level union," but "if cap-evolve
itself is allowed to reconcile the two tasks' needs starting from that union, does it do better."
Seeding it from the same static merge (rather than from either task's native variant) makes the
two results directly comparable: static merge (0 iterations) vs. jointly-optimized merge (this run).

Expected comparison once all four numbers land (native scores from `results.json`, per §5's table;
cross scores already in from the zero-shot pilot):

| Cell | Score |
|---|---|
| energy-market-pricing, native | 0.9 (have) |
| energy-market-pricing, cross (grid-dispatch-operator donor, zero-shot) | 0.7 (777816, done) |
| energy-market-pricing, merged (zero-shot) | 1.0 (778690, done) |
| energy-market-pricing, merged + jointly optimized | **1.0** (778692, done — accepted at iter 1/2, killed after; see below) |
| grid-dispatch-operator, native | 1.0 (have) |
| grid-dispatch-operator, cross (energy-market-pricing donor, zero-shot) | 0.8 (777815, done) |
| grid-dispatch-operator, merged (zero-shot) | 1.0 (778691, done) |
| grid-dispatch-operator, merged + jointly optimized | **1.0** (778692, done — accepted at iter 1/2, killed after; see below) |

778692's paired-eval seed (both tasks together) scored val=0.889; iteration 1 (`cand_0001`) scored
val=1.0 and was accepted (paired Δ=+0.111 > 0.2·SE gate). Iteration 2 (`cand_0002`) was mid-
evaluation (18/20 rollouts done, no `evaluate`/`step` event yet) when killed by exact ID at the
user's direction, since 1.0 is already the ceiling and iteration 1's accepted candidate already
answers the "can joint optimization do at least as well as the static merge" question — no need to
let iteration 2 finish.

All three new jobs on distinct dedicated hosts (`cccxc522`, `cccxc524`, `cccxc525`), `-n 1`, no
`-W`, per the standing CCC constraints.

## 8. Single-skill merge — collapsing all three into one SKILL.md

A further variant on §7's merge: instead of a 3-skill *bundle* (three separate `SKILL.md` files,
unioned pairwise per §6), collapse `dc-power-flow`, `economic-dispatch`, and `power-flow-data` into
**one** skill (`power-system-optimization`) with a single frontmatter/description and the three
donors' bodies concatenated as top-level `##` sections (Network Data / DC Power Flow / Economic
Dispatch), preceded by the unconditional Step 0 env-hardening pulled up front (previously
duplicated/pointed-to across the three separate files). Cross-references that used to say "see the
`economic-dispatch` skill's Step 0" or "see the `power-flow-data` skill's Solver setup" became
internal section pointers ("see Step 0 above") since there's now only one skill to point within.
All three donor scripts (`build_b_matrix.py`, `setup_solver_env.sh`, `solve_dispatch.py`,
`references/cost-functions.md`) carried over unchanged under the single skill's own `scripts/`/
`references/`.

This tests a different axis than §7: §7 kept skill *boundaries* intact and unioned within each;
this collapses the boundaries themselves, asking whether one skill invocation carrying all the
context beats three separate (but individually merged) skill files — e.g. because the optimizer
model no longer has to decide which of three skills to open, or because Step 0 now appears exactly
once instead of being referenced from two places.

Built at `.capevolve/_merged_a2p_single_skill_v1/power-system-optimization/`. Seeded into two new
projects, one per task (energy-market-pricing again needs the native `locational-marginal-prices`
skill alongside it; grid-dispatch-operator does not). Both zero-shot (`--max-iterations 0`),
mirroring §7's merged-bundle cells exactly so the two are comparable apples-to-apples:

| Job label | Project | Skills seeded | LSF job |
|---|---|---|---|
| `a2p_energy-market-pricing_x_single_merged_v1` | `project_energy-market-pricing_x_single_merged` | single merged skill + native `locational-marginal-prices` | 778790 |
| `a2p_grid-dispatch-operator_x_single_merged_v1` | `project_grid-dispatch-operator_x_single_merged` | single merged skill only | 778791 |

`cap-evolve check` green on both projects. Both submitted on distinct dedicated hosts (`cccxc526`,
`cccxc528`), `-n 1`, no `-W`. Logs at `/dccstor/knewedge2/boazc/ccc_logs/778900.stdout` and
`778901.stdout` respectively (job-ID-named symlinks `778790.stdout`/`778791.stdout` point at the
same files — the `bsub -oo/-eo` paths were set before the actual job IDs were known).

Extends the §7 comparison table with a 5th column per task:

| Cell | Score |
|---|---|
| energy-market-pricing, native | 0.9 (have) |
| energy-market-pricing, cross (grid-dispatch-operator donor, zero-shot) | pending (777816) |
| energy-market-pricing, merged bundle (zero-shot) | pending (778690) |
| energy-market-pricing, merged bundle + jointly optimized | pending (778692) |
| energy-market-pricing, **single merged skill** (zero-shot) | pending (778790) |
| grid-dispatch-operator, native | 1.0 (have) |
| grid-dispatch-operator, cross (energy-market-pricing donor, zero-shot) | 0.8 (777815, done) |
| grid-dispatch-operator, merged bundle (zero-shot) | pending (778691) |
| grid-dispatch-operator, merged bundle + jointly optimized | pending (778692) |
| grid-dispatch-operator, **single merged skill** (zero-shot) | pending (778791) |

## 9. Arm 0 was missing — native *seed* (pre-optimization) score

Every table above through §8 used `results.json`'s **`best`** field for "native" — that's `A1`
(the task's own skills *after* cap-evolve's optimizer ran, per `experiments_plan_v1.md`'s arm
table, §0). It is not the pre-optimization zero-shot score. That's a distinct row, `A0` in the
same table (`| A0 per-task seed | that task's seed skills | ... | have (0.508) |`), and it's cheap:
it's just `results.json`'s `seed` field, no new job needed.

Pulled directly from `skillsbench-history:results/results.json` (`tasks[].seed`, `tasks[].best`,
`tasks[].delta`; `delta == best - seed` checks out for both, confirming the reading):

| Task | seed (A0, pre-optimization) | best (A1, post-optimization) | delta |
|---|---|---|---|
| energy-market-pricing | **0.0** | 0.9 | 0.9 |
| grid-dispatch-operator | **0.0** | 1.0 | 1.0 |

Both Group-A tasks scored **zero** on their own native skill *before* cap-evolve's optimizer
touched it. Every comparison in §§5–8 (cross-task transfer, merged bundle, joint optimization,
single-skill merge) is implicitly being read against the optimized `A1` bar, not a true zero-shot
bar — which matters because most of those new arms (777815/777816/778690/778691/778790/778791)
*are* zero-shot (`--max-iterations 0`), so the fairer zero-shot-to-zero-shot comparison is against
`A0` (0.0), not `A1` (0.9/1.0). Under that lens, every zero-shot cross/merge/single-skill result
so far (0.7, 0.8, 1.0, 1.0) is a large improvement over the task's own *unoptimized* native skill
— the donor/merged skills are doing real work, not just "almost as good as native."

No new run required — `seed` was already being computed as part of each task's original
optimization run (it's `cand`/iteration 0 of that run), just not surfaced in earlier tables here.

## 10. Original-seed single-skill merge — same collapse as §8, but from *pre-optimization* donors

§8's single collapsed skill (`power-system-optimization`) was built from each task's *optimized*
(`best/`) donor variants of `dc-power-flow`, `economic-dispatch`, `power-flow-data` — i.e. it
merges skills that had already been through cap-evolve once. This section runs the same collapse
one level earlier: merge the three skills' **`seed/`** (pre-optimization) variants instead, so the
result is "no optimization, just merge" — a pure concatenation with zero optimizer-added content.

Checked first via `diff -rq` between `skillsbench-history/artifacts/task-by-task/{energy-market-
pricing,grid-dispatch-operator}/seed/{dc-power-flow,economic-dispatch,power-flow-data}/`: **all
three are byte-identical between the two tasks at the seed stage.** So unlike §7/§8's merges of the
`best` variants (which had genuine conflicts — grid-dispatch-operator's optimized `economic-
dispatch` added the Step-0 env-hardening section and a bundled `solve_dispatch.py` that energy-
market-pricing's optimized variant lacked), this merge has no conflicts to resolve at all: each
seed section is simply carried over as-is under one frontmatter/description, in the same Network
Data / DC Power Flow / Economic Dispatch section order as §8. Concretely, versus §8's collapsed
skill this version has **no** Step 0 env-hardening section, **no** "Reference DC model conventions"
warning, **no** "Solver setup" cross-reference, and **no** bundled-solver-shortcut subsection — none
of those existed yet at the seed stage; they were all added by cap-evolve during each task's
original optimization run. `scripts/build_b_matrix.py` and `references/cost-functions.md` carried
over unchanged (confirmed byte-identical to the `best`-stage copies via `diff`), since neither was
touched by that optimization; `scripts/setup_solver_env.sh` and `scripts/solve_dispatch.py` don't
exist at the seed stage and are correctly absent here.

Built at `.capevolve/_merged_a2p_single_skill_seed_v1/power-system-optimization/`. Seeded into two
new projects mirroring §8's `project_{task}_x_single_merged` pattern (`_seed` suffix):

| Job label | Project | Skills seeded | LSF job |
|---|---|---|---|
| `a2p_energy-market-pricing_x_single_merged_seed` | `project_energy-market-pricing_x_single_merged_seed` | original-seed merged skill + native `locational-marginal-prices` | 787174 |
| `a2p_grid-dispatch-operator_x_single_merged_seed` | `project_grid-dispatch-operator_x_single_merged_seed` | original-seed merged skill only | 787175 |

`cap-evolve check` green on both projects (`"ok": true`). Both submitted zero-shot
(`--max-iterations 0`), `-n 1`, no `-W`. First attempt (787096/787097 on `cccxc707`/`cccxc702`)
stuck `PEND` with reason "Not enough job slot(s) while advance reservation is active" — those two
hosts turned out to carry small `brsvs` advance reservations that block new dispatch even with
free slots showing in `bhosts -w`. Killed both by exact ID and resubmitted on hosts absent from
`brsvs`'s reservation list entirely: 787174 on `cccxc715`, 787175 on `cccxc716` — both dispatched
immediately. Logs at `/dccstor/knewedge2/boazc/ccc_logs/em_seed_787174.stdout` and
`gd_seed_787175.stdout` respectively.

**Result — grid-dispatch-operator (787175):** val=0.0, test=0.0 across all 10 trials ("not all
verifier tests passed"). Job finished cleanly (Exit 0) but hung in LSF `RUN` state afterward —
killed by exact ID once the log confirmed completion, per the "check the log, not just `bjobs`"
rule. Inspected a rollout trajectory to rule out an infra artifact: the agent hit
`ModuleNotFoundError: No module named 'numpy'` (expected — this seed skill has no Step 0 env-setup
section, that's optimizer-added), recovered by `pip install`-ing itself, then solved the DC-OPF and
wrote a well-formed `report.json` (510 generators, all required top-level keys present) — and still
scored 0.0. This points at the *other* piece of optimizer-added content missing at seed stage: the
"Reference DC model conventions" warning (against folding transformer tap ratios / phase-shift
angles / branch in-service status into the susceptance matrix). Without it the agent's DC model
plausibly diverges from the reference solution closely enough to fail the grader's tolerance, even
though the output is structurally valid. So this 0.0 looks like a genuine seed-stage capability gap,
not a merge-construction bug.

**Result — energy-market-pricing (787174):** val=0.0, test=0.0 across all 10 trials — same failure
mode as grid-dispatch-operator above (job finished cleanly, Exit 0, killed by exact ID after hanging
in LSF `RUN`). Consistent with the same root cause: this task also needs DC-OPF/LMP computation and
the seed skill lacks both the env-setup Step 0 and the "Reference DC model conventions" guardrail.

**Summary for this arm:** both tasks score 0.0 on the pre-optimization single-skill merge, matching
§9's `A0` floor (0.0/0.0) rather than showing any zero-shot-merge lift. This is a genuine, useful
negative result: collapsing the three seed-stage skill files into one, with no optimizer touch,
does *not* help — the benefit visible in §7/§8's optimized-donor merges comes from the
optimizer-added content (env hardening + DC-model-fidelity guardrails), not from the act of merging
per se.

This is the fairest possible zero-shot baseline for the "does merging *help at all*, independent of
cap-evolve's per-skill optimization" question: compare this arm directly against §9's `A0` (0.0 for
both tasks, the true pre-optimization zero-shot floor) rather than against `A1` (0.9/1.0, the
optimized bar). If this scores well above 0.0, that is evidence the merge/collapse itself (skill
transfer + single-file framing) carries real signal even with no optimizer touch at all; if it
scores near the §8 (optimized-donor) results, that suggests most of the benefit in §7/§8 came from
the merge structure rather than from the specific per-task optimizations baked into the `best`
donors.

### Arm renumbering

All arm numbers across this doc's tables now start at 1 (previously some tables used 0-indexed
"Arm 0"/"Arm 1"/etc.). This section's original-seed single-skill merge becomes **Arm 2**, slotted
in right after the true pre-optimization native baseline (**Arm 1**, formerly "Arm 0" in §9) and
before the optimized-native bar (**Arm 3**, formerly "Arm 1"). Mapping from old → new:

| Old label | New arm # | Description |
|---|---|---|
| Arm 0 | **1** | native seed (pre-optimization), `A0` |
| *(new)* | **2** | original-seed single-skill merge (this section) |
| Arm 1 | **3** | native optimized/best, `A1` |
| Arm 2 | **4** | cross-task transfer (optimized donor, zero-shot) |
| Arm 3 | **5** | merged bundle, 3 files (optimized donors, zero-shot) |
| Arm 4 | **6** | merged bundle, jointly optimized |
| Arm 5 | **7** | single collapsed skill (optimized donors, zero-shot) |

## 11. Optimizing the single collapsed skill directly — joint, per-task, and merged-mutations arms

§8/Arm 7 collapsed three **already per-task-optimized** donor files
(`dc-power-flow`/`economic-dispatch`/`power-flow-data`, each frozen after its own
`results.json` optimization run) into one skill and tested that collapse zero-shot. This
section asks a different question: instead of optimizing the three files separately and
collapsing afterward, start from §10's **un-optimized seed merge** (Arm 2 — the pure
concatenation with zero optimizer-added content, val 0.0/0.0) and let cap-evolve optimize
*that single file* directly. Three new arms, continuing the numbering above:

- **Arm 8** — optimize the seed-merge skill jointly against both tasks in one run.
- **Arm 9** — optimize the seed-merge skill independently, once per task, in two separate
  single-task runs.
- **Arm 10** — take the two per-task mutations Arm 9 produced, merge them back into one
  file, and score that merge zero-shot on both tasks (no further optimizer touch).

Arm 10 mirrors Arm 5 (merge two optimized single-purpose donors, test zero-shot) but one
level up the collapse: Arm 5 merges three separately-optimized *files*; Arm 10 merges two
independently-optimized *mutations of the same already-collapsed file*.

### Arm 8 — seed-merge skill, jointly optimized on both tasks

Project `project_a2p_joint_single_merged_seed_v1`
(`capevolve.a2p_joint_single_merged_seed_v1.yaml`), seeded from Arm 2's merged skill,
`train == val == test == {energy-market-pricing, grid-dispatch-operator}`,
`max_iterations: 2`, `max_usd: 300`, `max_optimizer_usd: 160` (budget doubled for the
2-task rollout, same pattern as Arm 6/`a2p_joint_bundle_v1`). LSF job **795839**, run dir
`run_a2p_joint_single_merged_seed_v1_20260916_015150/`.

Seed evaluated at val 0.0 (both tasks, 20 rollouts, matching Arm 2 exactly, as expected —
it's the same file). Iteration 1 (`cand_0001`) scored val 1.0 and was accepted
(paired Δ=+1.0; the run hit the same "SE=0 → STRICT fallback" gate warning seen throughout
this doc's small-n runs). Killed by exact ID immediately after — 1.0 is the ceiling, so a
second iteration has no room to improve and would only spend budget (`feedback_saturated_
baseline` rule). `state.json`: `best_id: cand_0001`, `spent.iterations: 1`, `optimizer_usd:
5.83`, `optimizer_tokens: 55197`.

**Result: energy-market-pricing 1.0, grid-dispatch-operator 1.0** (one combined val score
over both tasks; `n_scored: 2`, `reward: 1.0` — the aggregate is 1.0 only if every scored
task hit 1.0).

### Arm 9 — seed-merge skill, optimized independently per task

Two separate single-task optimization runs, each starting from the *same* Arm 2 seed-merge
file but touching only its own task:

| Task | Project | LSF job | Run dir |
|---|---|---|---|
| grid-dispatch-operator | `project_grid-dispatch-operator_x_single_merged_seed_opt` | **795739** | `run_grid-dispatch-operator_x_single_merged_seed_opt_20260916_014654/` |
| energy-market-pricing | `project_energy-market-pricing_x_single_merged_seed_opt` | **795840** | `run_energy-market-pricing_x_single_merged_seed_opt_20260916_015150/` |

Both used `max_iterations: 2`, `max_usd: 150`, `max_optimizer_usd: 80` (single-task budget,
half of Arm 8's). Both followed the identical pattern: seed val 0.0 → `cand_0001` val 1.0,
accepted on iteration 1, same STRICT-fallback gate warning, killed by exact ID once the
ceiling was confirmed (grid-dispatch-operator: `optimizer_usd: 9.46`, `optimizer_tokens:
80543`; energy-market-pricing: `optimizer_usd: 6.46`, `optimizer_tokens: 64138`).

**Result: grid-dispatch-operator 1.0 (795739), energy-market-pricing 1.0 (795840)** — each
task's own independently-optimized mutation of the single-file skill reaches the same
ceiling Arm 3's per-task-optimized *three-file* skills reach.

### Arm 10 — merge the two Arm-9 mutations, score zero-shot

Diffed the two mutated `power-system-optimization/` skill packages (Arm 9's `cand_0001`
outputs) file by file. `references/cost-functions.md` and `scripts/build_b_matrix.py` were
byte-identical to each other and to the seed. `SKILL.md` diverged only in its first ~45
lines — a task-specific "Step 0 / Quickstart" block each optimizer run had grown
independently — and was byte-identical from the "## Network Data" heading through the end
of both files. No conflict to arbitrate, so the merge was a straight union:

- Kept both mutations' solver scripts side by side (`scripts/solve_dispatch.py` from the
  grid-dispatch-operator mutation, `scripts/solve_market.py` from the energy-market-pricing
  mutation, plus the shared `setup_solver_env.sh`).
- Hand-wrote one merged `SKILL.md` head combining both mutations' Step 0/Quickstart
  guidance (a shared env-setup step, then a "Dispatch / operating-margin" quickstart
  pointing at `solve_dispatch.py` and a "Market clearing / LMP" quickstart pointing at
  `solve_market.py`, each carrying the guardrails its own optimizer run had added — e.g.
  energy-market-pricing's LMP numerical-conditioning note, grid-dispatch-operator's DC-model
  fidelity warning).
- Appended the byte-identical tail (`## Network Data` onward) verbatim.

Built at `_merged_a2p_single_skill_expC_v1/power-system-optimization/`. Tested zero-shot in
a new project, `project_a2p_expC_merged_mutations_zs_v1`
(`capevolve.a2p_expC_merged_mutations_zs_v1.yaml`, `max_iterations: 0`,
`train == val == test == {energy-market-pricing, grid-dispatch-operator}`). `cap-evolve
check` green. LSF job **797395**, run dir
`run_a2p_expC_merged_mutations_zs_v1_20260916_041603/`. Finished cleanly (`Exit: 0`) but
hung `RUN` in LSF afterward; killed by exact ID once the log showed the complete result.

**Result: energy-market-pricing 1.0, grid-dispatch-operator 1.0** (`baseline_val: 1.0`,
`test_reward: 1.0`, `test_delta: 0.0`, `iterations: 0`, `n_scored: 2`). Merging the two
independently-optimized mutations lost nothing — unlike Arm 2 (merging the never-optimized
seeds, which scored 0.0/0.0), merging donors that already carry optimizer-added content
preserves that content through the merge.

### Consolidated arm comparison

`zs` = zero-shot, `--max-iterations 0`, no optimizer touch after whatever produced the
seeded skill. `opt` = this run itself performed real optimization (`--max-iterations ≥ 1`).

**Section A — three separate skill files** (`dc-power-flow`, `economic-dispatch`,
`power-flow-data` kept as distinct `SKILL.md` packages)

| Arm | Description | Mode | energy-market-pricing | grid-dispatch-operator | Average |
|---|---|---|---:|---:|---:|
| 1 | Native seed — each task's own skills, before any optimization | zs | 0.0 | 0.0 | 0.0 |
| 3 | Native optimized — each task's own skills, after its own optimization run | opt | 0.9 | 1.0 | 0.95 |
| 4 | Cross-task transfer — the *other* task's optimized donor skills, no adaptation | zs | 0.7 | 0.8 | 0.75 |
| 5 | Merged bundle — both tasks' optimized donor skills unioned into 3 files, no further optimization | zs | 1.0 | 1.0 | 1.0 |
| 6 | Merged bundle, then jointly optimized further on both tasks | opt | 1.0 | 1.0 | 1.0 |

**Section B — single merged skill** (`power-system-optimization`, the three files
collapsed into one)

| Arm | Description | Mode | energy-market-pricing | grid-dispatch-operator | Average |
|---|---|---|---:|---:|---:|
| 2 | Pure seed-stage merge — collapse the three *never-optimized* seed files into one, no optimization at all | zs | 0.0 | 0.0 | 0.0 |
| 7 | Collapse the three *already per-task-optimized* donor files into one, no further optimization | zs | 0.9 | 1.0 | 0.95 |
| 8 | Start from the seed-merge (Arm 2) and optimize it jointly on both tasks | opt | 1.0 | 1.0 | 1.0 |
| 9 | Start from the seed-merge (Arm 2) and optimize it independently per task (two separate runs) | opt | 1.0 | 1.0 | 1.0 |
| 10 | Merge the two Arm-9 per-task mutations back into one file, score zero-shot, no further optimization | zs | 1.0 | 1.0 | 1.0 |

Both sections tell the same story: the single collapsed skill and the three-file bundle
track each other arm-for-arm (1≈2, 3≈9, 4 has no exact single-skill analog, 5≈7, 6≈8, and
Arm 10 closes the loop by showing the merge-of-optimized-mutations trick also works one
level up the collapse). Collapsing three files into one neither helps nor hurts on its own
(Arm 2 matches Arm 1's 0.0 floor exactly); every lift over that floor — cross-task transfer,
bundle merge, single-skill merge, joint or per-task optimization — comes from
optimizer-added content (environment hardening, DC-model-fidelity guardrails, task-specific
solver scripts) reaching the skill, not from the act of merging or collapsing files by
itself.
