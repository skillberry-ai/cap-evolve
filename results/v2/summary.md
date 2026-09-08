# v2 — hand-authored `bench-aap2-*` (10 tasks), champion accepted

**Date:** 2026-08-16 → 2026-08-19 (local, `parsec-intake_v2` worktree)
**Agent model:** `claude-sonnet-4-20250514` (the model Parsec runs at inference)
**Optimizer model:** `claude-code` default — `claude-opus-4-7` per the telemetry payload
**Task set:** 10 hand-authored `bench-aap2-001…010` tasks, contract schema `bench/v2`
**Split discipline:** **no holdout.** `train == val ==` all 10 tasks; `test: []`
**Cap-evolve spec:** [`recipes/v2/capevolve.v2.2.yaml`](../../recipes/v2/capevolve.v2.2.yaml)
**Headline run dir:** [`runs/run_20260818_161550/`](runs/run_20260818_161550/)
**Champion:** `cand_0001` — [`artifacts/v2/best/`](../../artifacts/v2/best/)

---

## ⚠️ Read this before quoting any number on this page

**The headline `+0.086` compares an `n=9` candidate against a *reused* `n=3` baseline.** The run was
launched with `--reuse-baseline`, so `seed`'s val figure of `0.875556` is a three-trial measurement
carried over from `.capevolve/run_20260816_202942`, while `cand_0001` was measured at nine trials.
Every per-task delta the run reports, and the aggregate it gated on, is a comparison **between
different trial counts**.

The same run *did* collect the correct comparison and then did not use it: `seed_train` is the seed
re-measured at `n=9` inside the iteration. Because `train` and `val` are both "all 10 tasks", the
`seed_train`-vs-`cand_0001` comparison at `n=9` is legitimate.

| framing | seed | `cand_0001` | Δ | what it is |
|---|--:|--:|--:|---|
| what cap-evolve gated on | 0.876 (`n=3`, reused) | 0.962 (`n=9`) | **+0.086** | mixed `n`; the number in `report.md` |
| equal `n`, errored trials as zero | 0.749 (`n=9`) | 0.962 (`n=9`) | **+0.213** | equal `n`, but every errored trial is on the seed's side |
| **equal `n`, errored trials dropped** | **0.822 (`n=9`)** | **0.962 (`n=9`)** | **+0.139** | **the honest figure** |

The **direction is robust** across all three framings. The **magnitude spans 2.5×**, and **none of
the three is held out** — see [No holdout](#no-holdout) below. Quote `+0.139`, and say what it is.

**How unstable is the seed?** The seed `SKILL.md` is byte-identical in all nine runs on this branch.
Across the v2 runs alone it measures anywhere from **0.367** to **1.000**; restricted to the v2.2
configuration (all 10 tasks, `train == val`) it still spans **0.643 to 0.959**:

| run | role | split / tag | n | reward |
|---|---|---|--:|--:|
| `run_20260816_143826` | v2.1 iter 1 | `train` / `seed_train` | 1 | **0.367** |
| `run_20260816_143826` | v2.1 iter 1 | `val` / `seed` | 1 | 0.767 |
| `run_20260816_162233` | v2.1 iter 2 | `train` / `seed_train` | 3 | 0.900 |
| `run_20260816_162233` | v2.1 iter 2 | `val` / `seed` | 3 | **1.000** |
| `run_20260816_202942` | v2.2 iter 1 | `train` / `seed_train` | 3 | 0.890 (0.959 as first written) |
| `run_20260816_202942` | v2.2 iter 1 | `val` / `seed` | 3 | 0.876 |
| **`run_20260818_161550`** | **headline** | `val` / `seed` **(reused)** | **3** | **0.876** |
| **`run_20260818_161550`** | **headline** | `train` / `seed_train` | **9** | **0.749** |
| `run_run_20260818_161550` | discarded iter 3 | `train` / `seed_train` | 9 | **0.643** |
| `run_run_20260818_161550` | discarded iter 3 | `val` / `seed` | 9 | 0.662 |

Two `n=9` measurements of the same skill on the same 10 tasks, two days apart, differ by **0.106**
(0.749 vs 0.643). The accepted improvement is **+0.086**. **The run's measurement noise is larger
than the effect it accepted.** The ladder in [`ui/heatmap.html`](../../ui/heatmap.html) shows all 24
seed measurements across both experiments side by side.

---

## Aggregate

| metric | seed | `cand_0001` (champion) |
|---|--:|--:|
| val reward, `n=9`, errored dropped | 0.822 | **0.962** ± 0.0230 |
| val reward, `n=9`, errored as zero | 0.749 ± 0.0501 | **0.962** |
| val reward as gated (`n=3` reused vs `n=9`) | 0.876 ± 0.0634 | 0.962 |
| tasks at 1.000 (mean over trials) | 1 / 10 | **4 / 10** |
| tasks below 0.800 | 3 / 10 | **0 / 10** |
| harness-errored trials | **8 / 90** | 0 / 90 |
| held-out test | *not measured — `test: []`* | *not measured* |

## Iterations

| iter | candidate | parent | val | Δ vs parent | gate | accepted? |
|---|---|---|--:|--:|---|---|
| 0 | `seed` | — | 0.876 (`n=3`, **reused**) | — | (baseline) | — |
| **1** | **`cand_0001`** | `seed` | **0.962** (`n=9`) | **+0.086** | `paired Δ̄=+0.0863 > 0.2·SE=0.0116 (SE=0.0581, n=10)` | ✓ ← **best** |

The run stopped after one iteration (`max_iterations: 1` in `state.json`, against `5` in the yaml —
it was driven one iteration at a time from the shell; see
[`logs/v2.2-iter2.log`](logs/v2.2-iter2.log)).

**On the gate threshold.** `gate_k_se` was lowered from `1.0` to `0.2` after v2.1 iteration 1, and it
is tempting to call that the load-bearing flaw. It is not: at `k=1.0` the threshold would have been
`SE = 0.0581`, and `Δ̄ = +0.0863` still clears it. **The loosening did not change this outcome.** The
`n=10` in the gate reason is the number of *tasks* paired, not trials.

What *is* worth noting is the scale: the baseline's own reported standard error is **0.0634**
(`baseline_reused` event), so the accepted Δ̄ of `+0.0863` is **1.36× the baseline's SE** — an effect
barely larger than the uncertainty on the thing it was compared to.

## Cost + wall clock

| | value |
|---|--:|
| Optimizer $ (headline run, `state.json`) | **$0.00** |
| Optimizer $ actually spent on `cand_0001` (from the `optimizer_error` payload) | **$3.23** |
| Runner $ | $0.00 — telemetry gap; every `cost_usd` in `events.jsonl` is `0.0` |
| Metric calls | 180 (`2 × 10 tasks × 9 trials`) |
| Runner wall clock | 19,019 s (5.3 h) |
| Total wall clock (first event → `finalize`) | 5.5 h |
| `budget.max_usd` / `max_optimizer_usd` | 50.0 / 20.0 — **never exercised**, since all costs read `0.0` |

The `$0.00` optimizer figure in `state.json` is wrong, and the run's own error payload proves it: the
`optimizer_error` event for `cand_0001` carries `"total_cost_usd": 3.2292`. Cost accounting on this
branch cannot be used for anything.

Two more telemetry facts worth carrying forward:

- **The target model id was not recognised.** `target_profile` records
  `unknown model id 'claude-sonnet-4-20250514'; defaulting to tier 'strong'`, so
  `suggested_num_trials: 3` was a **default, not a model-aware recommendation**. Nothing in the run
  chose `n=3`; `n=3` was what fell out of an unmatched string.
- **The two `test` evaluations each took ~2700 s on an empty split** (2700.14 s and 2699.89 s). That
  reads as a fixed 45-minute timeout, not a measurement — 1.5 h of the 5.5 h wall clock was spent
  scoring nothing.

---

## Per-task: what the run said vs. what the data says at equal `n`

`seed` is `n=3` (reused). `seed_train` and `cand_0001` are both `n=9`. "reported" is
`cand_0001 − seed`; "equal `n`" is `cand_0001 − seed_train`, errored trials dropped.

| task | `seed` n=3 | `seed_train` n=9 | `cand_0001` n=9 | reported Δ | **equal-`n` Δ** | verdict |
|---|--:|--:|--:|--:|--:|---|
| `001-single-job-outcome` | 0.844 | 0.500 | **1.000** | +0.156 | **+0.500** | understated 3.2× — the run's real win |
| `002-failed-jobs-on-controller` | 0.900 | 1.000 | 1.000 | +0.100 | **0.000** | **`fixed={}` is wrong** — seed was already 1.000 |
| `003-never-started-explanation` | 1.000 | 0.750 | 1.000 | +0.000 | **+0.250** | a real gain, reported as flat |
| `004-failing-task-and-host` | 0.967 | 0.800 | 0.978 | +0.011 | **+0.178** | understated 16× |
| `005-find-then-diagnose` | 1.000 | 0.844 | 1.000 | +0.000 | **+0.156** | a real gain, reported as flat |
| `006-log-root-cause` | 1.000 | 0.778 | 0.778 | −0.222 | **0.000** | **`broke={}` is wrong** — identical to 6 dp |
| `007-count-and-oldest` | 0.778 | 0.958 | 0.907 | +0.130 | **−0.051** | **the only real regression**, reported as a gain |
| `008-preceding-task` | 1.000 | 0.844 | 0.978 | −0.022 | **+0.133** | **`broke={}` is wrong** — it improved |
| `009-nonexistent-job` | 0.533 | 0.800 | 1.000 | +0.467 | **+0.200** | overstated 2.3× |
| `010-log-does-not-say` | 0.733 | 0.950 | 0.978 | +0.244 | **+0.028** | overstated 8.7× |
| **mean** | **0.876** | **0.822** | **0.962** | **+0.086** | **+0.139** | |

**Three of the run's five named per-task verdicts are wrong.** `report.md` / `JOURNAL.md` record:

> ACCEPTED (new champion) · val=0.962 Δ=+0.086 · fixed={`002`} · broke={`006`, `008`}

At equal `n`: `002` is **flat** (the seed already scored 1.000 on all eight of its valid train
trials), `006` is **flat to six decimal places** (0.777778 in both cells), and `008` **improved by
+0.133**. The one genuine regression in the run — `007`, at **−0.051** — appears in neither list and
is reported as a **+0.130 gain**.

All three errors have the same single cause: `--reuse-baseline` gated an `n=9` candidate against a
reused `n=3` baseline. **Re-derive per-task verdicts from `seed_train`, never from `report.md`.**

### The errored trials are all on the baseline's side

Eight of the 90 `seed_train` trials errored. **None of the 90 `cand_0001` trials did.**

| error | tasks | trial index | count |
|---|---|--:|--:|
| `AgentSetupTimeoutError` | 001, 002, 003, 007, 009, 010 | **0** | 6 |
| `NetworkConnectionError` | 004, 005 | **5** | 2 |

Six at trial index 0 and two at index 5 is not eight independent samples — it is two infrastructure
windows. Errored trials are written with `reward: 0.0` and are distinguishable from genuine zeros
only via `rollout.error`, so the errors-as-zero convention (`0.749`) charges the seed for eight
trials that never ran. **That is why `+0.213` is biased in the champion's favour and `+0.139` is
not.**

`results/results.json` carries both denominators on every cell (`seed_train` / `seed_train_all`), and
`per_task_scores.json` marks errored trials `null`.

---

## What the champion actually changed — and why v2 is mostly a tool-call benchmark

v2's reward is
`w_tc · (expected calls matched / n_expected_calls) + w_ans · (answer items satisfied / n_answer_items)`,
where `n_answer_items = n_required_facts + n_forbidden_facts` and **forbidden facts are satisfied by
absence** (so they contribute a free point). The weights are **per task**: `0.2/0.8` on six tasks,
`0.5/0.5` on three, `0.6/0.4` on one.

Because both denominators are small integers, each observed reward can be inverted. Solving
`w_tc·(i/n_c) + w_ans·(j/n_a)` over integers yields a **unique** `(i, j)` for 188 of the headline
run's 202 valid trials:

| component | complete | partial | ambiguous |
|---|--:|--:|--:|
| **answer** (facts) | **168** | 20 | 14 |
| **tool calls** | 130 | **58** | 14 |

**The answer half was almost never the problem.** 168 of 188 resolvable trials named every required
fact. 58 trials missed at least one expected tool call. And **every one of the champion's six edits
is about which tool to call** (see [`artifacts/README.md`](../../artifacts/README.md) for the diff).

The per-task pattern matches exactly. Tasks whose required facts live in `get_job` **metadata**
improved; tasks already served by `get_job_log` did not:

| | tasks | equal-`n` Δ |
|---|---|---|
| needs `get_job` metadata | 001, 003, 004, 005, 008, 009 | +0.500, +0.250, +0.178, +0.156, +0.133, +0.200 |
| already served by `get_job_log` | 002, 006, 007 | 0.000, 0.000, **−0.051** |

**The win is a documentation correction, not a reasoning improvement.** The seed `SKILL.md` commands,
twice and in bold, *"Always use `get_job_log` instead of `get_job`"*, and documents a **merged**
`get_job`/`get_job_log` response shape. The champion replaces both with an action-selection rule and
states that *"`get_job_log` in this simulator returns ONLY log fields … it does NOT include
metadata."*

**This is the open risk in the whole v2 result.** The seed is the *production* skill. If production's
`get_job_log` really does return metadata and only the simulator's does not, then the champion is now
correct for the simulator and **wrong for production** — a benchmark artifact promoted to a champion.
That cannot be settled from anything committed here: the `v2-baseline` trajectories on disk are from
the 2026-08-13 broken-wiring sweep and captured no tool results. **Checking the production
`get_job_log` response shape is the single highest-value follow-up in this branch.**

---

## <a name="no-holdout"></a>No holdout — and a `report.md` claim that is not true

`splits.json` for the headline run:

```json
{ "train": [ …all 10 tasks… ], "val": [ …the same 10 tasks… ], "test": [], "test_used": true }
```

`report.md` nonetheless says:

> Test was scored exactly once on the sealed split, for BOTH the baseline (`seed`) and the optimized
> skills — **the improvement above is on held-out tasks the optimizer never saw.**

**There were no held-out tasks.** `test` is empty, both test evaluations returned `0.0` after ~2700 s
of timeout, and `test_delta = +0.0` is arithmetic on two zeros. The sentence is boilerplate that
cap-evolve emits unconditionally; it is false for this run, and it is false in the same way for the
`run_run_20260818_161550` report.

The v2.1 runs (`run_20260816_143826`, `run_20260816_162233`) *did* have a disjoint 6/2/2 split — but
on a different, since-replaced task set, and at `n=1` and `n=3`.

**Nothing in v2 is a generalisation measurement.** Every number on this page is a fit metric.

## The missing handover

`JOURNAL.md` for the headline run reads, in full, for its only iteration:

> `## Iteration cand_0001 — (no handover written by the optimizer)`

`events.jsonl` records an `optimizer_error` for `cand_0001`. So the six edits that make up the
champion shipped **with no statement of intent, no per-edit expected effect, and no safety argument**
— the three things the journal template exists to capture. Every per-task attribution in
[`reports/task-by-task/`](../../reports/task-by-task/) for v2 is therefore inference from the reward
decomposition above, not a reading of the record.

The **iteration-1 run** (`run_20260816_202942`) has a complete journal entry and is the better read
for how the optimizer was reasoning. Its candidate was rejected and is kept at
[`artifacts/v2/rejected/run_20260816_202942-cand_0001/`](../../artifacts/v2/rejected/run_20260816_202942-cand_0001/).

---

## Runs in this directory

| run | role | splits | `n` | best | why it is here |
|---|---|---|--:|---|---|
| `run_20260816_143826` | v2.1 opt iter 1 | 6/2/2 disjoint | 1 | `seed` | first optimizer pass on the v2.1 task set |
| `run_20260816_162233` | v2.1 opt iter 2 | 6/2/2 disjoint | 3 | `seed` | same, at `n=3`; candidate rejected |
| `run_20260816_202942` | v2.2 iter 1 | 10/10/0 | 3 | `seed` | **the only v2 run with a full journal entry**; its `seed` val is what the headline run reused |
| **`run_20260818_161550`** | **headline** | 10/10/0 | **9** | **`cand_0001`** | the accepted champion |
| `run_run_20260818_161550` | discarded iter 3 | 10/10/0 | 9 | `cand_0002` | see below |

**`run_20260816_202942` also carries `splits.json.iter1-original`** — the split file as it stood
before it was rewritten, kept so the change is auditable.

### The discarded iteration 3 — and how the champion was lost

The doubled directory name `run_run_20260818_161550` is the tell: `--resume --run-ts` was given a
value that already carried the `run_` prefix, so cap-evolve created a **new run** instead of resuming
the existing one. Its journal confirms the consequence in the optimizer's own words:

> Building on prior RESULTS: … none — **this is iteration 1; LEDGER and RUNMAP are empty (seed
> baseline only)**.

**The champion's six edits were discarded and the search restarted from the seed.** Its `cand_0001`
is two hunks from the seed (against the champion's five) and attacks a completely different defect —
the seed's "Available Controllers" section lists a **fictional** fleet (`east`/`west`/`event0`/
`partner0`) instead of the real `prod0`/`prod1`. It then accepted two candidates of its own, reaching
`val = 0.750` at `n=9`: **below** the headline run's reused seed value (0.876) and far below the
champion (0.962).

It is kept because the fictional-controller finding is real and independent, and because its `n=9`
seed measurement of `0.643` is half of the instability evidence at the top of this page. Its
candidates live in [`artifacts/v2/discarded/`](../../artifacts/v2/discarded/), not `best/`, and its
optimizer **also** wrote no handover for `cand_0002` — the same failure as the headline run, twice in
two days.

### Two aborted runs that are *not* copied here

Two more run directories exist in the source worktree and were deliberately left out:

| run | rollouts | size | why omitted |
|---|--:|--:|---|
| `run_20260818_160322` | 0 | — | aborted immediately; no `final.json`, no `report.md` |
| `run_20260818_160757` | 60 | 4.1 M | aborted; no `final.json`, no `report.md`; `best_id: seed` |

Both are worth one line of history: they were configured with `train/val/test = 10/10/10` and each
fired cap-evolve's `splits_warning` (`test overlaps train/val (no-holdout fit)`). The successful
16:15:50 run has `test: []`. **So the test split was emptied between 16:07:57 and 16:15:50** — the
overlap warning was silenced by deleting the split rather than by finding disjoint tasks. That
sequence is the origin of the `test: []` discussed above.

They live at
`/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v2/.capevolve/run_20260818_160322/`
and `…/run_20260818_160757/`.

---

## What is in this directory

| file | what |
|---|---|
| `tasks.json` | all 10 contracts: expected calls, required / derived / forbidden facts, per-task weights, `n_golden_tool_calls` |
| `per_task_scores.json` | **per-trial reward vectors** for every task × run × tag, errored trials `null`, both `mean_valid` and `mean_all` |
| `per_task_scores.csv` | the hand-maintained per-task analysis, one note per task per iteration — **verbatim from the source**, uses the errored-as-zero convention, and its note on `006` is wrong (see that task's report) |
| `baseline_all_1786875106.json` | the `n=1` reference sweep of all 10 tasks, 2026-08-16 (mean 0.910) |
| `baseline_all_1786651164.json` | the earlier 2026-08-13 sweep, from the **broken-wiring** period — kept for provenance, not for scoring |
| `v2-baseline-summary.md`, `v2.1-baseline-summary.md`, `*-run.log` | the baseline sweeps' own write-ups and logs |
| `logs/` | per-iteration driver logs and `.wallclock` files for every v2.1 / v2.2 iteration |
| `runs/<run>/` | `state.json`, `events.jsonl`, `splits.json`, `baseline.json`, `final.json`, `report.md`, `JOURNAL.md`, `rejected.jsonl`, `history.jsonl` |

### Where the full rollouts live

**Raw rollout trajectories are not committed.** The five v2 runs carry ~53 MB of them (24 M / 14 M /
8.1 M / 4.1 M / 2.4 M / 772 K); v1 adds ~43 MB, ~96 MB in total. Everything the reports and the
ledger derive is already extracted into `per_task_scores.json` and `results/results.json`, so the
trajectories add no narrative and would multiply this branch's size by ~60×.

They remain in the intake worktree:

```
/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v2/.capevolve/<run>/rollouts/
```

If you need one, [`scripts/extract_rollout_scores.py`](../../scripts/extract_rollout_scores.py) is
the reader that produced `per_task_scores.json` and shows the layout.

---

## Next moves (open)

- **A. Check the production `get_job_log` response shape.** This is the one that decides whether the
  champion is an improvement or a simulator artifact. Cheap; blocks everything else.
- **B. Re-baseline at `n ≥ 25` before believing any per-task verdict.** Two `n=9` measurements of the
  same skill differ by 0.106 and the accepted gain is 0.086. `n=9` cannot resolve this.
- **C. Stop using `--reuse-baseline` across a `num_trials` change.** It is the sole cause of the
  three wrong per-task verdicts. If the baseline must be reused, gate against `seed_train`.
- **D. Fix `006`'s contract before scoring it again.** It is the only task where `n_expected_calls`
  (2) disagrees with `n_golden_tool_calls` (3), and every trial in its history loses exactly half the
  call credit.
- **E. Build a real test split.** Ten tasks cannot support 60/20/20; the honest options are more
  tasks or reporting v2 as a fit metric and saying so.
- **F. Recheck `007`.** It is the only genuine regression and it was invisible to the run. The
  champion's edits move its answer component the wrong way.
