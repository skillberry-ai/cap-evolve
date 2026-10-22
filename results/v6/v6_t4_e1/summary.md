# v6_t4_e1 — T-mrg: merging the 34 v6_t2 task edits into one bundle

Status: **complete** (2026-10-21). Three merge methods, each built blind (no train, validation or
test score was read during any merge), frozen, then scored on the train split (F, 67 tasks) and
the sealed test split (66 tasks) with **5 trials per task**. The validation split was not used.
Seed = v6_g2_e1's 10-trial Seed measurement on the same tasks, paired by task. It was not
re-measured. G = v6_g2_e1's final bundle `cand_0005`.

Plan and rules: `examples/parsec/v6_t4/PLAN.md` on `main` (PR #904). Inputs: [`../../../artifacts/v6/v6_t4_e1/merge_inputs/`](../../../artifacts/v6/v6_t4_e1/merge_inputs/) (Seed + per task
`edit.diff`, `instruction.md`, score-scrubbed `PROCESS.md`).

## The three merged bundles

| | Method | How it was built | Merge cost |
|---|---|---|---|
| m3 | smart merge | a fresh Claude Code agent (claude-opus-5-5) that never saw a score, plus 3 sub-agents, merged by meaning; every decision is in `m3_smart/MERGE_LOG.md` | 49.6 min, 10.15M tokens, ≈$14.16 (list-price estimate, see `merge_cost.json`) |
| m1 | merge by order | all 34 diffs applied in ascending T-opt gain, `git merge -X theirs` semantics (later diff wins any contested region) | 10 s script, no LLM |
| m2 | non-conflicting hunks | keep the 91 of 188 hunks no other task touches, drop every contested hunk | same 10 s script |

## Headline: reward, paired against the Seed

| Arm | Train (F, 67) | Δ vs Seed | Test (66) | Δ vs Seed | Test 95% CI (bootstrap) |
|---|--:|--:|--:|--:|---|
| Seed | 0.830 | — | 0.813 | — | — |
| T-opt (34 private bundles + Seed fallback, *not deployable*) | 0.937 | +0.107 | — | — | — |
| **m1 order** | 0.902 | **+0.072 ± 0.018** | 0.858 | **+0.046 ± 0.015** | [+0.016, +0.074] |
| **m3 smart** | 0.908 | **+0.078 ± 0.021** | 0.854 | **+0.041 ± 0.016** | [+0.011, +0.072] |
| m2 non-conflicting | 0.880 | +0.050 ± 0.015 | 0.828 | +0.015 ± 0.018 | [−0.020, +0.049] |
| G (`cand_0005`) | 0.884 (4 trials) | +0.053 ± 0.017 | 0.850 (10 trials) | +0.037 ± 0.013 | [+0.011, +0.065] |

± is the standard error of the per-task paired difference. Both T-mrg and G were optimized on F,
so the F column is fit for both. Test is the held-out number.

**Head-to-head on test (paired by task):** m1 − G = +0.009 ± 0.014; m3 − G = +0.004 ± 0.012;
m2 − G = −0.022 ± 0.015; m1 − m3 = +0.004 ± 0.014. **m1, m3 and G cannot be told apart on the
sealed test.** m2 is the weakest: its test gain is not distinguishable from zero.

### 3 trials → 5 trials (trust check)

| | F, 3 trials | F, 5 trials | Test, 3 trials | Test, 5 trials |
|---|--:|--:|--:|--:|
| m1 | +0.085 ± 0.019 | +0.072 ± 0.018 | +0.059 ± 0.016 | +0.046 ± 0.015 |
| m3 | +0.086 ± 0.022 | +0.078 ± 0.021 | +0.040 ± 0.019 | +0.041 ± 0.016 |
| m2 | +0.050 ± 0.016 | +0.050 ± 0.015 | +0.011 ± 0.020 | +0.015 ± 0.018 |

The two extra trials (fresh seeds 3–4, run about 2 hours after seeds 0–2) did not show a common
shift: on test, the mean delta of seeds 3–4 versus seeds 0–2 was m1 0.025 vs 0.059 (lower), m3
0.056 vs 0.041 (higher), m2 0.021 vs 0.011 (higher). m1's 3-trial lead was partly luck. The
ranking m1 ≈ m3 > m2 and the conclusion "m1/m3 ≈ G on test" did not change.

## How much of T-opt's fit survives integration

On the 34 optimized train tasks the Seed scores 0.788 and every T-opt champion scores 1.0
(+0.212). After merging:

| | 34 optimized tasks (Δ) | retained | 33 tasks T never touched (Δ) | tasks down > 0.1 among the 33 |
|---|--:|--:|--:|--:|
| m3 smart | +0.199 ± 0.023 | **94%** | **−0.046 ± 0.020** | 6 |
| m1 order | +0.154 ± 0.028 | 73% | −0.013 ± 0.008 | 1 |
| m2 non-conflicting | +0.114 ± 0.024 | 54% | −0.016 ± 0.010 | 2 |
| G | +0.124 ± 0.026 | (59%) | −0.020 ± 0.014 | 4 |

The smart merge keeps almost all of the local gain but costs the most on tasks no edit was written
for. Dropping contested hunks (m2) loses half the gain, so most of the value is in the hunks that
several tasks wanted to change. Those are mostly `shared_context.md` and `aap2_agent.md` rules.

## Per-task regressions on test (the release-gate question)

| | up > 0.05 | down > 0.05 | worst task |
|---|--:|--:|---|
| m1 | 34 | 10 | platform-141 −0.27 |
| m3 | 31 | 13 | platform-135 −0.37 |
| m2 | 25 | 18 | platform-141 −0.62 |
| G | 27 | 6 | platform-131 −0.40 |

Every deployable bundle has at least one severe per-task regression, so the release-gate problem
is not specific to G. The T merges move more tasks in both directions. G's platform-131 regression
is milder under m3 (−0.04) and m1 (−0.13).

**Routing-gap tasks** (9 test tasks the regex fast router sends to a specialist lacking a required
tool): every arm is slightly negative there (m1 −0.032, m3 −0.023, m2 −0.006, G −0.025) and
positive on the other 57 (m1 +0.058, m3 +0.051, m2 +0.018, G +0.047). This agrees with
"outside the editable surface".

## Size and serving cost

| | words | vs Seed (14,753) | added / removed | per-trial tokens (F) | per-trial $ (F) |
|---|--:|--:|--:|--:|--:|
| Seed | 14,753 | — | — | 37.5k | $0.124 |
| G | 25,060 | +70% | 11,125 / 818 | 59.6k | $0.191 |
| m2 | 33,127 | +125% | 18,595 / 221 | 52.1k | $0.168 |
| m1 | 41,281 | +180% | 26,855 / 327 | 66.3k | $0.212 |
| m3 | 59,852 | +306% | 45,511 / 412 | 88.0k | $0.278 |

Word counts are over the 8 skill files (merge logs excluded). Per-trial tokens and dollars are
the harness's own accounting. G's comes from its train-split candidate trials, the merges' from
their F evaluations.

The smart merge did not compress: it is the largest bundle, 2.4× G, and the most expensive to
serve (+46% $/trial vs G). One T-opt edit is small (median +1,239 words), but the integrated T
artifact is larger than G's.

## Cost

| Item | m1 | m3 | m2 |
|---|--:|--:|--:|
| Merge | $0 | ≈$14.16 | $0 |
| Eval, train F (5 trials) | $70.45 | $92.99 | $55.19 |
| Eval, test (5 trials) | $78.03 | $107.93 | $65.63 |
| **Eval total** | **$148.47** | **$200.93** | **$120.82** |

T-mrg total for all three methods: **$484.38** (eval $470.22 + merge $14.16).

**Cost to produce a deployable bundle, before the test split is opened**, counting the shared
$83.09 Seed sweep for both:
- T path: $83.09 + T-opt $319.37 + merge $0–14 ≈ **$402–417**
- G path: $83.09 + optimizer $355.02 + screens/validation gates $494.06 ≈ **$932**

The T path cost about 2.3× less and gives a test result statistically equal to G's. The T path
had no validation gate at all.

## Running example: AAP2 Rule 4 ("don't re-fetch job data")

The Seed's rule 4 forbids a second call on a job, while the failed-event flow needs a different
action on the same job.
- T-opt (`platform-004`) rewrote the rule in place.
- G kept rule 4 unchanged and added an overriding job-read section elsewhere (contradiction left
  in place).
- **m3** rewrote rule 4 itself: "Don't re-fetch job data — but a different action, or a failed
  call, is not a re-fetch", folding in three other tasks' exceptions. This is the interpretable,
  in-place fix.
- **m1** kept the Seed's rule 4 text, appended another task's timeout exception to it, and has the
  "different action is not a re-fetch" text in a separate section. This is the git-style
  accumulation.

platform-004 on F: Seed 0.76, G 0.91, m1/m3/m2 all 1.00.

## Caveats (what this does not show)

1. **The Seed was not re-measured.** Every Δ above compares a bundle run on 2026-10-21 with Seed
   trials from the v6_g2 run, days earlier. G's test numbers were measured alongside its own Seed.
   Drift in the simulator, gateway or model would bias T-mrg's Δ but not G's. A same-day Seed
   sweep on test, 5 trials, would cost about $40–80 and remove this confound.
2. **Three methods, one test split.** No method may be selected because it scored best on test.
   All three are reported, and m1 vs m3 is within noise, so no conclusion rests on choosing one.
   If the paper needs one "T-mrg" number, pre-declare it, or select on validation. Validation is
   unused, and 5 trials cost about $55–95 per method.
3. **No validation gate on T-mrg.** The merges are static and ungated. That matches G on test is
   a result, not a protocol choice. It also raises the question of what G's validation gate
   bought in this run. Its full validation remeasurement already disagreed in sign with test.
4. **Trials:** 5 per task for T-mrg vs 10 for G on test. The SEs are similar because the per-task
   variance is dominated by task differences.
5. **Errored trials** are absent, never scored as 0. These tasks have fewer than 5 trials:
   - m1: F `cost-407` (3).
   - m3: test `cloud-026`, `platform-114` (4 each).
   - m2: F `cloud-057`, `cloud-074`, test `cloud-027` (2 each).
6. **One run per arm:** a single T-opt run, a single G optimizer seed, and a single smart merge.
   The v4 pilot merge, recorded in the paper's `paper_notes.md`, failed. v6 differs in task count,
   per-task protocol and merge methods, so the two are not a replication.

## Files

| Path | What |
|---|---|
| [`RESULTS_FOR_PAPER.md`](RESULTS_FOR_PAPER.md) | **the four core tables** (reward; cost/tokens/time; words; the Rule 4 running example) with definitions, comments and the paper edit map |
| [`rule4_table.json`](rule4_table.json), [`pr57_aap2_agent.diff`](pr57_aap2_agent.diff) | Table 4 as data (each arm's Rule 4 verbatim, counts, platform-004 reward); upstream PARSEC PR #57's diff |
| [`../../../ui/v6_tables_main_table.html`](../../../ui/v6_tables_main_table.html), [`cost_table`](../../../ui/v6_tables_cost_table.html), [`size_table`](../../../ui/v6_tables_size_table.html), [`rule4_table`](../../../ui/v6_tables_rule4_table.html) | the four tables, rendered |
| [`../../../artifacts/v6/v6_t4_e1/`](../../../artifacts/v6/v6_t4_e1/) | `m1_order/` (merge by order), `m3_smart/` (smart merge), `m2_nonconflict/` (non-conflicting hunks): frozen bundles + `MERGE_LOG.md`; `merge_inputs/` |
| [`per_task/{m1,m3,m2}.json`](per_task/) | per task: all 5 trial rewards (seeds 0–2 and 3–4 listed separately), cost, tokens |
| [`eval/`](eval/) | per-suite collector outputs: 3-trial (`v6t4_m*.json`), top-up (`v6t4_m*x.json`), pooled (`v6t4_m*_5t.json`); `analysis*.json`; runner log; host blocklist; the 7 re-run m3 tasks |
| [`cost_table.json`](cost_table.json), [`size_table.json`](size_table.json) | Tables 2 and 3 as data (size includes per-file counts) |
| [`merge_cost.json`](merge_cost.json), [`m3_smart_usage.json`](m3_smart_usage.json) | merge time/tokens/cost; smart merge's per-message token record |

Generators: `examples/parsec/v6_t4/{analyze_t4,cost_table,size_table}.py` on `main` (PR #904). They read
the run directories in the `parsec-intake_v6-t2` worktree, which are not committed here.
