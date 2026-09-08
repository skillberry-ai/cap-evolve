# v1 — trace-extracted `traces_parsec-aap2-*` (30 tasks), optimizer never won

**Date:** 2026-08-12 → 2026-08-16 (local, `parsec-intake_v1` worktree)
**Agent model:** `claude-sonnet-4-20250514` (the model Parsec runs at inference)
**Optimizer model:** `claude-code` default (`claude-opus-4-7`)
**Task set:** 30 `traces_parsec-aap2-*` tasks, mechanically extracted from scraped Parsec sessions
**Split discipline:** **no holdout.** The optimizer runs pin `train == val == test == {0047, 0048}`
**Cap-evolve spec:** [`recipes/v1/capevolve.yaml`](../../recipes/v1/capevolve.yaml)
**Headline run dir:** [`runs/run_20260814_214843/`](runs/run_20260814_214843/)
**Champion:** **`seed`** — no candidate was ever accepted in any v1 run that reached a `FINAL`

---

## The one-line result

**Nothing shipped.** Across four runs and nine candidates, the headline run's champion is the seed,
`test_delta` is `+0.0`, and [`artifacts/v1/best/SKILL.md`](../../artifacts/v1/best/SKILL.md) is
**byte-identical** to [`artifacts/v1/seed/SKILL.md`](../../artifacts/v1/seed/SKILL.md). That is not a
placeholder or a copy error — it is the result.

The interesting part of v1 is therefore **not** the optimizer. It is what the 30 contracts turned out
to measure, and the fact that the one candidate the gate threw away is the only artifact that ever
demonstrated the target behaviour.

## Aggregate

| metric | value |
|---|--:|
| Baseline sweep, all 30 tasks, `n=1` (2026-08-12) | **0.240** ± 0.281 (stdev) |
| Headline run val (`seed`, `n=30`, 2 tasks, errored dropped) | **0.317** ± 0.0348 |
| Headline run val (`seed`, `n=30`, errored **as zero**) | 0.232 |
| Headline run train (`seed_train`, `n=30`) | 0.342 |
| Headline run test (`FINAL`, `n=30`) | 0.326 — **a fit metric, not held out** |
| `test_delta` | **+0.0** |
| Candidates generated **and evaluated** across all v1 runs | 9 (3 + 4 + 0 + 2 by run) |
| Candidates accepted in the headline run | **0** |
| Harness-errored trials in the headline val cell | **16 / 60** |

## Runs

| run | role | `n` | iters | best | metric calls | opt $ | wall |
|---|---|--:|--:|---|--:|--:|--:|
| `run_20260813_120630` | first wiring proof | 1 | 3 / 3 | `cand_0002` | 14 | $8.33 | 2.6 h |
| `run_20260813_152629` | `n=10`, pass a | 10 | 4 / 5 | `cand_0002` | 180 | $8.08 | 23.4 h |
| `run_20260814_160930` | `n=10`, pass b — baseline only | 10 | 0 / 0 | `seed` | 60 | $0.00 | 4.9 h |
| **`run_20260814_214843`** | **headline, `n=30`** | **30** | **2 / 5** | **`seed`** | **300** | **$8.61** | **52.7 h** |

The headline run stopped at **2 of 5 iterations** on the `stall: 2` condition — two consecutive
rejections and the hill-climb gave up.

### Iterations, headline run

| iter | candidate | parent | val (`n=30`) | Δ vs parent | gate | accepted? |
|---|---|---|--:|--:|---|---|
| 0 | `seed` | — | 0.317 | — | (baseline) | — |
| 1 | `cand_0001` | `seed` | 0.225 | −0.092 | `paired Δ̄=-0.0917 <= 1.0·SE=0.0371 (SE=0.0371, n=2)` | ✗ |
| 2 | `cand_0002` | `seed` | 0.157 | −0.160 | `paired Δ̄=-0.1600 <= 1.0·SE=0.0221 (SE=0.0221, n=2)` | ✗ |

`n=2` in the gate reason is the number of **tasks** paired. Both rejections are correct on the mean —
see [The candidate the gate was right to reject and wrong to
discard](#the-candidate-the-gate-was-right-to-reject-and-wrong-to-discard).

## Cost + wall clock (headline run)

| | value |
|---|--:|
| Optimizer $ | **$8.61** (`cand_0001` $5.52 + `cand_0002` $3.09) |
| Runner $ | $0.00 — telemetry gap; every `cost_usd` in `events.jsonl` is `0.0` |
| Metric calls | 300 |
| Runner wall clock | **187,460 s (52.1 h)** |
| Of which: the `seed` val evaluation alone | **126,091 s (35.0 h)** — 2 tasks × 30 trials |
| `budget.max_usd` / `max_optimizer_usd` in `state.json` | **100.0 / 40.0** — **not** the 50 / 20 in the yaml |

The 35 hours spent measuring the baseline on two tasks is the practical reason v1 was abandoned rather
than re-run at higher `n`: a 30-trial baseline on the full 30-task set would take roughly three weeks
of wall clock at this throughput.

**The recipe and the run disagree on the budget.** Both `capevolve.yaml` and `PROJECT.md` say
`max_usd: 50.0 / max_optimizer_usd: 20.0`; the run's `state.json` records `100.0 / 40.0`. Neither cap
was approached, so nothing turns on it — but a verbatim rerun from the committed recipe runs under
different limits than the recorded run did. See [`recipes/v1/README.md`](../../recipes/v1/README.md).

---

## What the 30 contracts actually measure

This is the load-bearing finding in v1, and it is about the benchmark, not the skill.

Each task scores `reward = gate · (0.5 · trajectory + 0.5 · assertions)`, where `trajectory` is a
`subset` match against the tool-call sequence **mechanically scraped from one real session** and
`assertions` is the fraction of `answer_contains` strings present in the answer.

### The trajectory half was unreachable on 25 of the 30 tasks

When the 30-task sweep ran on **2026-08-12**, two kaegis simulators were up — aap2 on `:8086` and
github on `:8087` — serving exactly five tools:

```
query_aap2   fetch_github_file   search_github_repo   search_github_code   search_agnosticv_prs
```

`trajectory_match` is `subset` on all 30 tasks: the demanded op sequence must appear in the
transcript in order. **One demanded op that cannot be called at all therefore fails the whole
containment.** Cross the tasks whose entire demanded sequence was callable against the tasks that
actually matched:

| was `trajectory: 1.0` reachable? | tasks | matched | mean baseline | mean assertions |
|---|--:|--:|--:|--:|
| yes — every demanded op had a running sim | 5 | **5 / 5** | 0.730 | 0.460 |
| no — at least one op was uncallable | 25 | **0 / 25** | 0.142 | 0.285 |

**Five for five, and zero for twenty-five.** The five are `0023`, `0037`, `0053`, `0074`, `0113`; they
are exactly the set [`recipes/v1/PROJECT.md`](../../recipes/v1/PROJECT.md) named on 2026-08-12 as the
tasks the 2-sim setup fully covered, written down *before* the sweep's per-task numbers were read that
way. What the other 25 needed and could not call:

| missing tool | tasks needing it | which sim would serve it |
|---|--:|---|
| `lookup_catalog_item` | **22** | babylon `:8088` (not running) |
| `query_provisions_db` | 5 | provisions_db `:8090` (not running) |
| `db_describe_table` | 5 | provisions_db `:8090` (not running) |
| `query_babylon_catalog` | 1 | babylon `:8088` (not running) |

So for 25 of 30 tasks half the reward was **unreachable by construction**, capping them at `0.500`
whatever the SKILL.md said. Every mean over those rows is a measurement of the harness. The ledger
carries this per task — `trajectory_reachable_at_baseline`, `trajectory_tools_missing_at_baseline`,
and a `trajectory-unreachable-tool-gap` flag on all 25 rows — so no downstream view can average them
in silently.

**Two things this does not license.** First, the tool gap alone would put the aggregate at
`(25 × 0.5 + 5 × 1.0) / 30 = 0.583`; the observed mean is **0.240**. The gap is a *ceiling* on the
experiment, not an excuse for its result — the assertion half was failing badly too. Second, by the
2026-08-14 pilot the babylon and provisions_db sims were up: v1's `cand_0002` matched the trajectory
on `0047` and `0048`, both of which demand `lookup_catalog_item`. Under the four-sim set **all 30
contracts are reachable**. So the 28 baseline-only rows and the 2 optimized rows were measured against
**different tool surfaces**, and nothing in this branch or the source worktree records the moment it
changed. Do not put the 2026-08-12 sweep column and the 2026-08-14 pilot columns in the same
comparison without saying that.

### Transcript length is the weaker, confounded story

The obvious-looking alternative reading is that long contracts fail because they are long:

| contract size | tasks | matched | reachable | mean baseline |
|---|--:|--:|--:|--:|
| ≤ 4 scraped ops | 4 | **4 / 4** | 4 / 4 | 0.688 |
| > 4 scraped ops | 26 | **1 / 26** | 1 / 26 | 0.172 |

Ops per task range from **2 to 36**, mean **12.4**. That table is real but it is mostly the coverage
table in disguise: four of the five reachable tasks are also the four shortest, and the fifth
(`0074`) demands **8** ops and matched anyway. Within the reachable five, demanded length ranges 2–8
and **every one matched** — so length has no residual predictive power once reachability is known.
Reachability separates the outcome perfectly; length does not.

It remains true, and worth fixing, that half of every v1 reward is gated on a quantity nobody chose
deliberately: how many tool calls the human in the scraped session happened to make. That is a reason
to rewrite the contracts. It is not the reason the trajectory column is all zeros.

### The assertion half is sparse — and one task's is vacuous

**39 of 171 assertion strings passed at baseline** (22.8%), spread across 30 tasks with 0 to 14
assertions each.

**`traces_parsec-aap2-0052` has zero assertions.** An empty list of `answer_contains` strings is
trivially all-satisfied, so its assertion component scores a **vacuous 1.000**, its trajectory scores
0.000, and its reward is exactly `0.500` — **above the 0.240 set mean**. A task that checks nothing
drags the aggregate **up**. It is the shortest and most damning report in
[`reports/task-by-task/v1-aap2-0052.md`](../../reports/task-by-task/v1-aap2-0052.md).

Three more tasks sit at exactly `0.500` for the mirror-image reason — full assertions, zero
trajectory (`0016`, `0036`) or full trajectory, zero assertions (`0113`). All four carry the
`capped-at-0.5-by-50/50-weighting` flag in the ledger.

### Baseline distribution, all 30 tasks at `n=1`

| bucket | tasks |
|---|---|
| `1.000` | `0037` |
| `0.900` | `0074` |
| `0.625` | `0023`, `0053` |
| `0.500` | `0016`, `0036`, `0052`, `0113` |
| `0.400` | `0049` |
| `0.111 – 0.250` | `0081`, `0082`, `0084`, `0085`, `0087`, `0088`, `0094` |
| `0.036 – 0.091` | `0004`, `0005`, `0006`, `0021`, `0030`, `0092`, `0112` |
| `0.000` | `0018`, `0032`, `0044`, `0047`, `0048`, `0080`, `0104` |

`0047` and `0048` are the only two tasks with `gate == 0.0` at baseline — the agent produced no usable
answer at all — which is exactly why the pinned split selected them. **The optimizer ran on those two
tasks and nothing else.** The other 28 have one trial each and no candidate ever saw them; their
reports are accounts of a *contract*, not of an optimization.

---

## <a name="the-candidate-the-gate-was-right-to-reject-and-wrong-to-discard"></a>The candidate the gate was right to reject and wrong to discard

`cand_0002` (headline run) scored `0.157` against the seed's `0.317` and was correctly rejected on the
mean. It is also **the only artifact in the entire v1 experiment that ever matched a trajectory on
either optimized task**:

| task | seed, 30 trials | `cand_0001`, 30 trials | `cand_0002`, 30 trials |
|---|---|---|---|
| `0047` | every trial `0.333` or `0.000`; **never above 0.333** | never above `0.333` | one trial at **`0.833`** = trajectory 1.000 + assertions 0.667 |
| `0048` | every trial `0.400` or `0.000`; **never above 0.400** | one trial at `0.500` = **5 of 5 assertions**, no trajectory | one trial at **`0.900`** = trajectory 1.000 + assertions 0.800 |

Two trajectory matches, in 60 candidate trials, both from the candidate that was thrown away. The
journal had predicted the ceiling before the run — *"Achievable upper bound on 0047 stays ~0.83"* —
and the one trial that got there scored `0.8333`.

**The gate is measuring the right statistic for the wrong question.** A paired mean is correct for
"ship a champion that is better on average." It is wrong for "did this edit teach the agent a
behaviour it did not have," and on these two tasks the answers diverge completely. The stall condition
then ended the run, so the finding was never followed up.

The optimizer's own refutations are the other genuinely useful v1 output, and they are on the record in
[`runs/run_20260814_214843/JOURNAL.md`](runs/run_20260814_214843/JOURNAL.md):

> The reader (sonnet-4-5) does not obey a second set of rules layered on top of an already-detailed
> skill — the fix has to be a MODIFICATION of the existing decision points, not an addition.

Both candidates are kept at [`artifacts/v1/rejected/`](../../artifacts/v1/rejected/) with their
`INSTRUCTIONS.md` and `PROCESS.md`.

---

## Data-quality problems you must carry with every v1 number

**1. The seed is not a stable measurement.** The seed `SKILL.md` is byte-identical across all four
runs and measures anywhere from **0.000** to **0.367**:

| run | split / tag | n | reward |
|---|---|--:|--:|
| `run_20260813_120630` | `val` / `seed` | 1 | **0.000** |
| `run_20260813_152629` | `val` / `seed` | 10 | **0.017** |
| `run_20260813_152629` | `train` / `seed_train` | 10 | **0.367** |
| `run_20260814_160930` | `val` / `seed` | 10 | **0.220** |
| `run_20260814_160930` | `train` / `seed_train` | 10 | 0.130 |
| `run_20260814_214843` | `val` / `seed` | 30 | 0.317 |
| `run_20260814_214843` | `train` / `seed_train` | 30 | 0.342 |

**Two `n=10` `val` measurements of the same skill on the same two tasks, one day apart, differ by
0.203** (0.017 vs 0.220). At `n=1` the same skill scores 0.000. Any v1 delta smaller than ~0.2 is
inside the noise.

**2. Sixteen of the 60 trials in the headline baseline cell never ran.** Both tasks lost the *same
eight contiguous trial positions* (16–23), all `NetworkConnectionError` — one outage window, not
sixteen coincidences. The journal recorded it at the time as *"~5/30 trials"*; the rollouts say
**8 per task**. The run under-counted its own infrastructure loss.

Because errored trials are written with `reward: 0.0`, the convention matters: the headline val figure
is **0.317 with them dropped** and **0.232 with them counted as zero**. cap-evolve reported the first.
`results/results.json` carries both on every cell.

**3. `run_20260813_152629` made `cand_0002` champion on a cell where 12 of 20 trials errored.** Its
val reads `0.367` under the errored-dropped convention and `0.147` with errors as zeros. That run is
kept for history and its champion is not the one this branch ships.

**4. That same run recorded two different `seed_train` values, `0.037` and `0.367`.** The rollouts on
disk reconcile only with the later one, so the ledger marks the first `unreconciled` with reason
`superseded-measurement` rather than guessing. Both are visible in
[`results.json`](../results.json).

**5. `test` is never held out.** Every v1 optimizer run pinned `train == val == test == {0047, 0048}`
and cap-evolve fired its own warning on all four:

> `test overlaps train/val (no-holdout fit) — the test number is NOT held out; report it as a fit
> metric`

The headline `FINAL` of `0.326` is a re-measurement of the two tasks the optimizer was tuned on, and
`test_delta = +0.0` merely reflects that the champion is the seed. **No v1 number on this branch is a
generalisation result.**

---

## What is in this directory

| file | what |
|---|---|
| `tasks.json` | all 30 contracts: the demanded tool-call op sequence, match mode, and every `answer_contains` string |
| `per_task_scores.json` | **per-trial reward vectors** for every task × run × tag, errored trials `null`, both `mean_valid` and `mean_all` |
| `baseline_all_1786543049.json` | the `n=1` reference sweep of all 30 tasks, 2026-08-12 (mean 0.240) |
| `runs/<run>/` | `state.json`, `events.jsonl`, `splits.json`, `baseline.json`, `final.json`, `report.md`, and where present `JOURNAL.md`, `rejected.jsonl`, `history.jsonl` |

`run_20260814_160930` has no `JOURNAL.md` or `rejected.jsonl` because it ran **zero iterations** — it
is a baseline re-measurement only, and the absence is the record, not a gap.

### Where the full rollouts live

**Raw rollout trajectories are not committed.** The four v1 runs carry ~43 MB of them (26 M / 12 M /
4.3 M / 1.0 M); v2 adds ~53 MB, ~96 MB in total, against 1.6 MB for this whole branch. Everything the
reports and the ledger derive is already extracted into `per_task_scores.json` and
`results/results.json`.

They remain in the intake worktree:

```
/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v1/.capevolve/<run>/rollouts/
```

[`scripts/extract_rollout_scores.py`](../../scripts/extract_rollout_scores.py) is the reader that
produced `per_task_scores.json` and documents the layout.

---

## v1 is not comparable to v2

Do not put v1's `0.317` and v2's `0.962` in the same sentence without this paragraph. They are
different benchmarks that share a target skill:

| | v1 | v2 |
|---|---|---|
| tasks | 30, **mechanically extracted** from scraped sessions | 10, **hand-authored** with a stated discrimination axis each |
| reward | `gate · (0.5·trajectory + 0.5·assertions)` | `w_tc·(calls matched) + w_ans·(answer items)`, **per-task weights** |
| trajectory / call check | `subset` over 2–36 scraped ops | `ordered-subsequence` over 1–2 chosen calls |
| answer check | substring `answer_contains` | required / derived / **forbidden** facts |
| what a high score means | every demanded tool happened to be served by a running sim | the chosen calls were made and the chosen facts stated |

| tool coverage when measured | 25 of 30 contracts demand a tool no running sim served | all 10 contracts fully served |

v2 scores higher for two reasons that have nothing to do with the skill: its contracts ask for 1–2 tool
calls instead of 12, and every tool they ask for was actually callable.

---

## Next moves (open)

- **A. Do not re-run v1 as it stands, and do not re-run it without all four sims.** 25 of the 30
  contracts demand a tool that was not being served when they were scored, so their trajectory term
  measured the harness. Bring babylon `:8088` and provisions_db `:8090` up first — that alone makes all
  30 reachable — and *then* fix the contracts (or drop the trajectory component and score assertions
  only, which is the cheaper honest option given the ops are mechanically scraped).
- **B. Delete or repair `0052`.** A task with zero assertions scores a vacuous 0.500 and lifts the set
  mean. Ship neither.
- **C. Retry `cand_0002`'s pivot, expressed as a modification.** It is the only v1 edit with any
  demonstrated upside, and the journal's own next-lever note says why the additive form failed.
- **D. Fix the harness before the skill.** An 8-trial outage inside a 30-trial measurement, and a
  35-hour baseline on two tasks, are both larger problems than any prompt edit.
- **E. If v1 is revived, pin the split in the recipe.** `split_ids_file` is empty in the committed
  yaml, so a verbatim rerun would draw a random 60/20/20 split instead of the pinned two tasks. See
  [`recipes/v1/README.md`](../../recipes/v1/README.md).
