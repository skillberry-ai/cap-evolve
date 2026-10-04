# parsec v4 — comparing four skill-set variants (T1, G2, T4_e1, T4_e2)

**Question.** We have four versions of the 8-file multi-agent skill bundle. On the
tasks where they score differently, *why* do they score differently — and how much
of the difference is attributable to the skill text at all?

**Short answer.** Most of it is not. Two confounds — a harness tool outage and plain
re-measurement variance — account for the majority of the per-task spread, including
almost every difference between T4_e1 and T4_e2. What survives as a real,
skill-attributable result is a clean one, and it is about *scope*: the globally
optimized bundle (G2) keeps its gains, and the static per-task merge (T4) does not.

---

## 1. The four variants, and what each one actually is

| # | name | path | what it is | verified |
|---|---|---|---|---|
| 1 | **T1** | `artifacts/v4/seed/` | the original, unoptimized bundle (8 files, 2058 lines) | byte-identical across both arms |
| 2 | **G2** | `artifacts/v4/v4_g_e1/best/` | `cand_0004` — one shared bundle hill-climbed jointly against all 34 tasks (3276 lines incl. 2 optimizer-metadata files; 2855 runtime lines) | `best_id_overall == cand_0004` |
| 3 | **T4_e1** | `artifacts/v4/v4_t_e1/t4-merge/` | static region-union merge of the 21 per-task T2 bundles (6158 lines) | **byte-identical** to the bundle captured in all 34 e1 job dirs |
| 4 | **T4_e2** | *uncommitted* | T4_e1 **plus hand edits to exactly two files**: `aap2_agent.md`, `babylon_agent.md` | all other 6 files byte-identical to T4_e1 |

T4_e2 is not a re-merge and not a re-run of the same artifact. Every one of the 34 e2
job directories carries its own copy of the bundle it ran, and across all 34 that copy
differs from the committed `t4-merge/` in exactly `aap2_agent.md` and
`babylon_agent.md` — never in the other six files. The e1 job dirs' copies are
byte-identical to `t4-merge/` in all eight. So the e1→e2 content delta is precisely
and provably two files.

Those two edits were deliberate and targeted. `scripts/build_v4_t4_merge.py` in the
execution worktree carries two new `STANDALONE_OVERRIDE` entries whose own comments
name their targets: `# platform-018 regression (T4): ...` and
`# platform-019 regression (T4): ...`. So e2 is an iteration on e1, aimed at two
specific tasks.

---

## 2. Two things to know before reading the table

### (a) The measurement noise floor is enormous

The seed bundle was measured twice, independently, at n=5, by the two arms — the
*same bytes* both times (`results.json` `seed` column, T-run and G-run). Those two
measurements of one identical bundle disagree by:

- **mean |Δ| = 0.107**, median 0.034, **max 0.680** (`platform-005`: 1.000 vs 0.320)
- 20 of 34 tasks differ by more than 0.001

That is the floor for *any* per-task comparison in this table. A gap of 0.15 between
two columns carries no information on its own. Only gaps well above ~0.2, or changes
in determinism (stderr → 0), are interpretable per task.

### (b) A harness tool outage hit specific tasks in specific sweeps

Scanning all 349 trial transcripts in both T4 sweeps for tool-backend failures, 34
trials returned `"Operation specification for <tool> is unavailable"` — the simulated
tool backend was down, so the agent got nothing to report. This is infrastructure,
not capability, and **it is not evenly distributed between the sweeps**:

| task | e1 trials hit | e2 trials hit | effect |
|---|--:|--:|---|
| `cost-028-highest-spend-provider` | **5/5** | 0/5 | e1 0.400 is an artifact |
| `cost-030-threshold-not-an-anomaly` | 3/5 | 0/5 | e1 0.720 depressed |
| `cost-029-no-cost-rows-for-guid` | **5/5** | 0/5 | e1 0.960 **inflated** (see §4) |
| `platform-004-events-then-config` | 5/5 | 0/5 | none — scored 1.000 anyway |
| `icinga-010-stuck-anarchysubjects` | 0/5 | **5/5** | e2 0.243 is an artifact |
| `platform-001-ee-entrypoint-rca` | 2/5 | 4/5 | both sweeps noisy |
| **total** | **25** | **9** | |

The outage ran *against* e1 on three cost tasks and *against* e2 on `icinga-010`.
Any e1-vs-e2 comparison on these six tasks is comparing infrastructure weather.

Independent corroboration that this was a known, separately-fixed infrastructure
problem rather than an inference from the reward pattern: the task-runner's own job
tree contains `_run/jobs/verify_durable_cost_fix_20260930/`, dated the day the e2
sweep finished and holding exactly one task — `bench-v4-cost-028-highest-spend-provider`.
Someone was verifying a cost-tool fix against the very task whose score the outage
moved furthest.

---

## 3. The table

Rows: every task not at 1.000 in at least one variant (30 of 34). The four remaining
tasks — `cloud-025`, `icinga-015`, `platform-006`, `platform-021` — are 1.000 in all
four and are omitted.

- **T1** = seed bundle, `seed` column, G-run sweep (n=5)
- **T1′** = seed bundle, `seed` column, T-run sweep (n=5) — *the same bytes as T1,
  measured again*; included so the noise floor is visible in every row
- **G2** = `cand_0004` (n=5) · **T4_e1**, **T4_e2** = n=5 each

| task | tranche | T1 | T1′ | G2 | T4_e1 | T4_e2 | e1→e2 | can e1→e2 edit reach it? | harness outage |
|---|---|--:|--:|--:|--:|--:|--:|:--:|---|
| `platform-031-helm-url-not-a-timeout` | challenge | 0.642 | 0.441 | **0.877** | 0.866 | 0.965 | +0.099 | yes |  |
| `platform-032-shared-secret-not-a-registry-outage` | challenge | 0.790 | 0.487 | **0.983** | 0.645 | 0.715 | +0.070 | yes |  |
| `platform-033-schema-change-not-the-oom` | challenge | 0.893 | 0.402 | **1.000** | 1.000 | 1.000 | +0.000 | yes |  |
| `platform-034-rate-limit-not-an-outage` | challenge | 0.816 | 0.386 | **0.892** | 1.000 | 0.984 | -0.016 | yes |  |
| `cloud-024-guid-to-account` | regression | 0.200 | 0.200 | **1.000** | 1.000 | 1.000 | +0.000 | no |  |
| `cloud-026-gpu-abuse-triage` | regression | 0.940 | 0.940 | **0.953** | 0.613 | 0.977 | +0.363 | no |  |
| `cloud-027-azure-pool-database-trap` | regression | 1.000 | 1.000 | **0.910** | 1.000 | 1.000 | +0.000 | no |  |
| `cost-028-highest-spend-provider` | regression | 1.000 | 1.000 | **1.000** | 0.400 | 1.000 | +0.600 | no | e1 5/5 outage |
| `cost-029-no-cost-rows-for-guid` | regression | 0.800 | 0.800 | **1.000** | 0.960 | 0.640 | -0.320 | no | e1 5/5 outage |
| `cost-030-threshold-not-an-anomaly` | regression | 0.944 | 1.000 | **1.000** | 0.720 | 1.000 | +0.280 | no | e1 3/5 outage |
| `icinga-010-stuck-anarchysubjects` | regression | 0.495 | 0.467 | **0.551** | 0.439 | 0.243 | -0.196 | yes | e2 5/5 outage |
| `icinga-011-aap2-job-status-alert` | regression | 0.944 | 0.860 | **1.000** | 1.000 | 1.000 | +0.000 | no |  |
| `icinga-012-nodes-ready-threshold` | regression | 0.972 | 1.000 | **1.000** | 1.000 | 1.000 | +0.000 | no |  |
| `icinga-013-acknowledged-not-an-issue` | regression | 0.512 | 0.448 | **0.608** | 0.640 | 0.640 | +0.000 | no |  |
| `icinga-014-check-script-path-moved` | regression | 0.965 | 0.860 | **1.000** | 1.000 | 1.000 | +0.000 | no |  |
| `icinga-016-hosts-most-problems` | regression | 0.936 | 1.000 | **1.000** | 1.000 | 1.000 | +0.000 | no |  |
| `icinga-017-invented-action-trap` | regression | 1.000 | 1.000 | **1.000** | 1.000 | 0.972 | -0.028 | no |  |
| `platform-001-ee-entrypoint-rca` | regression | 0.752 | 0.860 | **0.892** | 0.760 | 0.696 | -0.064 | yes | e1 2/5, e2 4/5 outage |
| `platform-002-collection-not-found-rca` | regression | 0.837 | 0.907 | **0.907** | 0.957 | 0.690 | -0.267 | yes |  |
| `platform-003-tojson-dict-literal-rca` | regression | 0.560 | 0.563 | **0.930** | 1.000 | 1.000 | +0.000 | yes |  |
| `platform-004-events-then-config` | regression | 0.787 | 0.787 | **1.000** | 1.000 | 1.000 | +0.000 | yes | e1 5/5 outage |
| `platform-005-wrong-owner-trap` | regression | 1.000 | 0.320 | **0.888** | 0.912 | 0.744 | -0.168 | yes |  |
| `platform-007-directory-path-fetch` | regression | 0.790 | 0.470 | **1.000** | 1.000 | 0.595 | -0.405 | no |  |
| `platform-008-log-does-not-say` | regression | 0.960 | 0.800 | **1.000** | 1.000 | 1.000 | +0.000 | yes |  |
| `platform-009-catalog-item-no-config` | regression | 1.000 | 1.000 | **1.000** | 0.825 | 0.770 | -0.055 | yes |  |
| `platform-018-find-jobs-window` | regression | 1.000 | 1.000 | **0.720** | 0.028 | 0.028 | +0.000 | yes |  |
| `platform-019-anarchysubject-state` | regression | 0.660 | 1.000 | **1.000** | 0.320 | 1.000 | +0.680 | yes |  |
| `platform-020-ocpv-vm-inventory` | regression | 1.000 | 1.000 | **1.000** | 0.340 | 0.215 | -0.125 | yes |  |
| `platform-022-job-on-no-controller` | regression | 0.665 | 0.595 | **0.965** | 1.000 | 1.000 | +0.000 | yes |  |
| `platform-023-splunk-guid-no-events` | regression | 1.000 | 0.960 | **1.000** | 1.000 | 0.960 | -0.040 | no |  |

Every T4_e1 and T4_e2 cell above was independently recomputed from the raw per-trial
rollout JSON in the job directories and matches the published `results.json` to
within 0.002 on all 34 tasks, both sweeps — so the table is not inheriting a
summarization bug.

---

## 4. What the skill text actually explains

### The one clean, attributable win: `platform-019-anarchysubject-state` (0.320 → 1.000)

This is the single largest e1→e2 move and the only one that clears the noise floor by
a wide margin. It is also the *only* task in either table where a named,
documented intervention lines up with a measured effect:

- The `babylon_agent.md` edit scopes the "stop and write the report now" trigger so
  that a request's own chained *"...then look up X and report Y"* counts as part of
  "every thing the investigator asked for," not a bonus to drop once the first fact
  lands.
- `platform-019`'s instruction is exactly that shape: *"report its current state and
  its desired state. **Then** look up its governor's component definition ... and
  report how many instances that component expects and which cloud provider it
  uses."*
- e1: `[0.15, 0.15, 0.15, 0.15, 1.00]` — four of five trials stop after hop one.
  e2: `[1.00] × 5`, deterministic.
- The task loads `babylon_agent.md` (confirmed from its actual tool calls:
  `query_babylon_catalog`, `query_provisions_db`).

A targeted edit, aimed at this task by name, matching its structure, producing the
predicted effect, on a task that loads the edited file. That is attribution.

### The confirmed null: `platform-018-find-jobs-window` (0.028 → 0.028)

The `aap2_agent.md` edit names this task too — it adds an exception so an explicitly
given date range is passed through instead of being replaced by inferred
burst-clustering. It did nothing: the same multiset of trial scores, reordered.

The reward breakdown shows why the fix was aimed too narrowly. The failure is not
"wrong window" — it is that the agent makes only two `query_aap2` calls (one still
unmatched) and its answer misses **4/4 required facts and 1/1 counts**, i.e. an
answer score of 0. Something upstream of the window logic is stopping this task from
doing its investigation at all. Worth noting: `platform-018` is the one task that
regresses under *both* optimized variants — 1.000 at T1 → 0.720 under G2 → 0.028
under T4 — so it is uniquely fragile to other tasks' edits, and the e2 fix did not
touch whatever that fragility is.

### The control group: the e1→e2 differences are mostly not content

Partitioning the 33 scored tasks by whether they can even *reach* the two edited
files (determined empirically from the tools each task actually called):

| group | n | mean \|e1→e2 Δ\| | max |
|---|--:|--:|--:|
| **can** be affected (loads `aap2`/`babylon` tools) | 19 | **0.092** | 0.680 |
| **cannot** be affected (prompt provably byte-identical in e1 and e2) | 14 | **0.145** | 0.600 |

Tasks whose prompt text did not change *at all* between the two sweeps moved **more**
on average than tasks whose prompt did change. Excluding `platform-019`, the "can be
affected" group's mean drops to 0.059. The honest reading: apart from
`platform-019`, the e1→e2 table is dominated by the outage and by ordinary
run-to-run variance, not by the two edits.

The largest "cannot be affected" movers each have a non-skill explanation:

- `cost-028` **+0.600** — 5/5 e1 trials hit the tool outage. In e1 the agent called
  all three provider queries with correct arguments and then correctly reported *"all
  three tools returned errors ... this is an infrastructure problem, not a data
  absence"*; the grader scored 1/7 because there were no numbers in the answer. In e2
  the tools worked and it scored 7/7. **The skill behaved identically and
  arguably correctly in both.**
- `cost-029` **−0.320** — the reverse, and the most instructive case in the table.
  Ground truth for this task is *"there is no cost data; say so and do not give a
  figure"* (`required: no-data`, `forbidden: invented-figure`). In e1 the outage made
  the agent say "no cost data could be retrieved" — the right answer for the wrong
  reason, scoring 0.8–1.0. In e2, with the tools working, it reported a concrete
  $84,217 total and failed. **e1's 0.960 was a false positive created by the outage;
  e2's 0.640 is the more honest measurement of this bundle.**
- `cost-030` **+0.280** — 3/5 e1 trials hit the outage.
- `platform-007` **−0.405** — no outage, but this task's own T2 report documents that
  across 25 historical runs the GitHub simulator served the authored fixture in only
  9, substitute LLM-generated content in 6, and a tool error in 10. Its e2 pattern
  (`0.325 ×3, 1.000 ×2`) is that documented fixture lottery, and its prompt content
  was identical in both sweeps.
- `cloud-026` **+0.363** — content identical between sweeps; e1 included a 0.000 and
  a 0.417 trial, e2 was `[1.000 ×4, 0.883]`. Variance on a multi-step task.

---

## 5. The result that does survive: scope beats merging

With the per-task noise understood, the aggregate comparison is where the real signal
is — means over all 34 tasks, and over the 28 tasks untouched by the outage:

| variant | mean (34 tasks) | mean (28 outage-free tasks) | regressed tasks that were 1.000 at T1 (of 12) | catastrophic (<0.70) |
|---|--:|--:|--:|---|
| **T1** seed | 0.8488 | 0.8601 | — | — |
| **T1′** seed re-measured | 0.7810 | — | — | — |
| **G2** `cand_0004` | **0.9434** | **0.9512** | 3 | **none** |
| **T4_e1** | 0.8360 | 0.8623 | 5 | `platform-018` 0.028, `platform-020` 0.340, `cost-028` 0.400\* |
| **T4_e2** | 0.8481 | 0.8663 | 6 | `platform-018` 0.028, `platform-020` 0.215 |

\*`cost-028`'s T4_e1 figure is the outage artifact described above.

**The static merge nets to approximately zero.** On the outage-free subset, T4 scores
0.862 / 0.866 against the unoptimized seed's 0.860 — inside the noise floor. All of
T2's per-task gains, bought at $437 and 39 hours, do not survive being merged into
one bundle. Meanwhile **G2 delivers +0.091 over the same seed and never
catastrophically breaks a task** that previously worked.

That is the one difference in this study that is unambiguously about the skills rather
than the harness, and it is a difference in *how* the bundle was produced:

- **G2 was scored on all 34 tasks every iteration.** It could never accept an edit
  that helped one task and broke another — the aggregate signal priced that in
  immediately. Its edits to the globally-loaded files are correspondingly
  conservative: `shared_context.md` 237 → 492 lines, `orchestrator.md` 245 → 361.
- **T4 was never scored at all before being assembled.** It is a textual union of 21
  bundles, each optimized against one task's signal in isolation, with
  hand-reconciled conflicts. It triples the always-loaded instruction text
  (`shared_context.md` + `orchestrator.md`: 482 → 1567 lines) with rules written for
  other tasks, and no measurement ever gated that.

The failure signature is visible per-task. `platform-020-ocpv-vm-inventory` is the
cleanest example: its own domain file `ocpv_agent.md` is **byte-identical in all four
variants** (128 lines, untouched by both optimizers), yet it scores 1.000 at T1 and
G2 and collapses to 0.340 / 0.215 under T4. The reward detail shows the agent making
only **one** of three required `query_ocpv_cluster` calls and then wandering into
`query_aws_account_db` and `query_babylon_catalog` — other domains' tools. Nothing in
its own instructions changed; what changed is everything around them.

---

## 6. Hypotheses tested and rejected

Recorded so they are not re-proposed later:

1. **"T4 regressions are explained by prompt dilution."** The natural quantitative
   form — ratio of task-relevant domain text to always-loaded generic text — does
   **not** predict the T4-minus-T1 delta: Pearson r = **−0.057** (n=32). The
   `platform-020` case above is a real and well-evidenced instance of cross-domain
   distraction, but "more global text ⇒ worse score" fails as a general law, because
   the same bundle that breaks `platform-018`/`platform-020` also *improves*
   `platform-003` (+0.440) and `platform-022` (+0.335). The merge's damage is
   specific, not proportional.
2. **"The grader or task definitions changed between sweeps."** No. Every file under
   `_run/tasks/bench-v4-cost-028-*` (and the task path in `harbor_config.json`) is
   unchanged since 2026-09-16; the two sweeps' configs differ only in `jobs_dir`.
3. **"T4_e1 and T4_e2 are two runs of one static bundle."** No — two files differ,
   proven from the per-run captured bundles (§1).
4. **"The committed `t4-merge/` is what produced the e2 numbers."** No — it is the
   **e1** bundle. See §7.

---

## 7. Before any re-run (the deferred Part 2)

Two things need fixing first, or a re-run will not reproduce either sweep:

1. **The e2 bundle is not committed anywhere — by decision.** It exists only as
   uncommitted edits in `cap-evolve-worktrees/parsec-intake_v4_t4_e1` (two `.md`
   files plus the two `STANDALONE_OVERRIDE` entries in
   `scripts/build_v4_t4_merge.py`), and the call has been made not to commit it,
   since e2 buys nothing over e1 once the confounds above are accounted for (§4).
   The consequence worth recording: **e2's numbers are not reproducible from this
   repository.** A re-run sourced from `parsec-history` silently uses the **e1**
   bundle, and would "fail to reproduce e2" for reasons having nothing to do with
   reproducibility. If e2 ever does need reproducing, that worktree is the only
   source and should be treated as perishable.
2. **The tool outage needs to be detectable, not discovered after the fact.** It
   moved six tasks across the two sweeps and inverted the sign on at least two
   (`cost-028`, `cost-029`). A re-run should fail or quarantine any trial whose
   transcript contains `Operation specification for ... is unavailable`, rather than
   scoring it. Without that, a third sweep produces a third set of numbers and no way
   to tell which differences are real.

Given the noise floor in §2(a), n=5 is also too small to resolve the per-task
differences this analysis is being asked about. If the goal is per-task attribution
rather than an aggregate arm comparison, that needs more trials per task.

---

## 8. Naming

The original working name was `v4_t4_err_analysis`. The work turned out to span all
four variants, and its two main results are a harness confound and a scope
comparison rather than T4 error analysis — so this is filed as
**`v4-skillset-variant-comparison`**. If the investigation is ever promoted to a
named experiment directory alongside `v4_t_e1`/`v4_g_e1`,
`v4_skillset_variant_comparison` keeps it aligned with this file.
