# Results

The canonical results for cap-evolve. Every number here is derived from a committed
run artifact (`examples/*/run_full/*.json`) or, where noted, from a held-out run whose
artifact is committed separately. The README's Results section is a short snapshot of
this page.

Each result is labeled by **split discipline**:
- **fit metric** — `train == val == test` (no holdout); the test number is *not* held
  out and the engine logs a `splits_warning`. Useful to show the loop works; not a
  generalization claim.
- **held-out** — test ids the optimizer never saw, scored exactly once at `finalize`.

Reward is mean task reward in `[0, 1]`. Where we quote externally reported results that use 0–100% units, we label them explicitly as percentages.
Gains are given as **absolute** and **relative %**.

---

## RH-SWE-bench (SWE-bench Verified via Harbor, fit metric, no committed artifact)

> **Read the caveats before quoting this one.** It is the only entry on this page whose run
> artifact is **not committed to this repo**, so it is the only one that cannot be
> re-derived from `examples/*/run_full/*.json`. It is recorded here because the README
> quotes it and points at this page; it is flagged rather than dropped so the gap is
> visible instead of implied.

- **Capabilities:** `[skill-package, system-prompt]`. **Harness:** Harbor (each task runs a
  full `claude-code` agent inside an isolated Docker container).
- **Optimizer:** `claude-code` @ `claude-opus-4-6`.
- **Agent under test:** `claude-sonnet-4-6` via Harbor.
- **Tasks:** 119 val tasks from SWE-bench Verified.
- **Split:** `train == val == test == 119` — **fit metric**, no holdout. The optimizer saw
  every task it was scored on, so this is *not* a generalization claim.

| | reward (119 tasks) | Δ vs baseline |
|---|---|---|
| Baseline (seed prompt + skill) | **0.580** (58.0%) | — |
| Best candidate (`cand_0002`), val | **0.765** (76.5%) | +0.185 / +31.9% relative |

2 of 7 iterations accepted: iter 1 `+0.118` (0.580 → 0.698), iter 2 `+0.067` (→ 0.765).
Per-task: 24 improved, 2 regressed, 93 unchanged.

### Caveats — three, and the third is unresolved

1. **Fit metric, no holdout.** `train == val == test`, so the +0.185 measures how well the
   optimizer fit 119 known tasks, not how it generalizes. Every held-out number on this page
   is a stronger claim than this one.
2. **No committed artifact.** There is no `run_full/` for this benchmark. The numbers above
   are transcribed from `site/results.html`; there is no run dir, commit hash, trial count,
   or cost figure in the repo to check them against. `ci/benchmarks/swebench/` holds task
   lists and split ids, not results.
3. **The published figure disagrees with these numbers, and I could not resolve which is
   authoritative.** `site/assets/rh_swe_bench.png` — the image README and `site/results.html`
   both embed next to this result — is a cross-model / cross-harness bar chart. Its bars read
   `Sonnet 4.6 Claude Code optimized with cap-evolve 73.1`, `Opus 4.6 Claude Code 63.3`,
   `Sonnet 4.6 Claude Code 55.7`, and three RedHatAI/NVIDIA-Nemotron rows at 30.8 / 22.4 /
   21.6. It contains neither 58.0 nor 76.5, and `73.1`/`55.7` appear nowhere else in the
   repo. The chart is clearly the *same* body of work — its optimized bar is labelled
   "Sonnet 4.6 Claude Code optimized with cap-evolve" and the agent under test above is
   `claude-sonnet-4-6` — so this is two scorings of one optimization, not two unrelated
   experiments. What is unresolved is **which scoring is authoritative**: either the chart is
   a later re-measurement and 58.0 → 76.5 is stale, or the two use different subsets/scoring
   and are not comparable. Until someone with the run says which, **treat both pairs as
   unconfirmed.** Note the chart is the weaker of the two (+17.4 pp vs +18.5 pp), so this is
   not a case of a figure flattering the text.

## toy_calc — deterministic, zero-API

| | val | test | notes |
|---|---|---|---|
| Seed prompt | **0.0** | — | no `[CALC]` marker |
| Optimized (`mock` adds `[CALC]`) | — | **1.0** | gate-accepted, test sealed |

Deterministic, no model call. Asserted by `core/tests/test_e2e_slice.py` and reproduced
by `bash examples/toy_calc/run.sh`.

---

## τ²-Bench airline — no-holdout fit-metric run (reproducible, committed)

Artifact: [`examples/tau2_airline/run_full/`](../examples/tau2_airline/run_full/)
(`final.json`, static dashboard under `ui/`). Reproduce: [`REPRODUCE_tau2.md`](REPRODUCE_tau2.md).

- **Capability:** airline **policy + tools** optimized jointly (`[system-prompt, tools]`).
- **Optimizer:** `claude-code` @ `claude-opus-4-6`.
- **Runner + user simulator:** `openai/gpt-oss-120b` via IBM RITS.
- **Tasks / trials:** all **50** airline tasks · **10** trials each.
- **Split:** `train == val == test == 50` — **fit metric** (no holdout).
- **Algorithm / gate:** `hill-climb --focus all`, **10** iterations, paired significance
  gate `k_se 0.2`.
- **tau2-bench commit:** `8ebb7499622fc2be9b9d510d6f7a7653461f4f29`.

| | reward (50 tasks · 10 trials) | Δ vs baseline |
|---|---|---|
| **Baseline** (seed policy + tools) | **0.536** | — |
| **Best candidate** (`cand_0007`) — val | **0.712** | **+0.176 / +32.8% relative** |
| **`cand_0007`** — sealed test (fit metric) | **0.694** pass@1 (pass² 0.584) | — |

Accepted iterations (the rest were rejected by the gate as within-noise):
iter 1 `+0.046` (0.536→0.582), iter 3 `+0.052` (→0.634), iter 5 `+0.036` (→0.670),
iter 6 `+0.014` (→0.684), iter 7 `+0.028` (→0.712). **5 of 10** iterations accepted.

What changed: deep in-code tool edits (`tools.py` 593 → 832 lines; policy 166 → 233
lines), not just prompt tweaks — five trajectory-verified before→after edits in
[`OPTIMIZATION_EXAMPLES.md`](OPTIMIZATION_EXAMPLES.md); curated walkthrough in
[`examples/tau2_airline/DEMO.md`](../examples/tau2_airline/DEMO.md).

---

## τ²-Bench airline — held-out 30(=val)/20 run

Same benchmark and capability, run with a real holdout split (`split_ids.json`,
train=val=30, test=20) so the test number is a genuine generalization result.

| split | baseline | optimized | Δ |
|---|---|---|---|
| **val** (30 tasks) | **56.7** | **70.0** | **+13.3 pp / +23.5% relative** |
| **sealed test** (20 tasks, scored once) | **30.0** | **47.5** | **+17.5 pp / +58.3% relative** |

> The held-out `run_full` artifact for this run is committed separately. Until it lands,
> treat these figures as the reported held-out result; the reproducible artifact-backed
> run above is the no-holdout fit metric.

See [`COMPARISON.md`](COMPARISON.md) for how this **+58.3% within-run relative** held-out
gain sits next to external tool-optimization work (EvoTool, Evolutionary Context Search)
— with the important caveat that those use different benchmark versions, models, splits,
and budgets and are **not** an apples-to-apples comparison.

---

## τ²-Bench airline — agent orchestration mode (`agent-optimize`), held-out 30(=val)/20

The first run driven in **agent orchestration mode** (`orchestration_mode: agent`,
`algorithm_skill: agent-optimize`): the conversational agent understood the benchmark, ran the
baseline, then proposed the policy edits itself, gated every candidate on the full val split, and
sealed the test once — see [`AGENT_ORCHESTRATION.md`](AGENT_ORCHESTRATION.md). Reproduce:
[`REPRODUCE_tau2.md`](REPRODUCE_tau2.md#8-agent-mode-reproduction-held-out-3020-litellm-proxy).

- **Capability:** airline **policy** (`system-prompt`) optimized by the agent itself (no per-iteration optimizer subprocess).
- **Runner + user simulator:** `aws/gpt-oss-120b` via the IBM ete litellm proxy.
- **Split:** **30 train == 30 val** (fit) · **20 sealed test** (held out, disjoint) — user-pinned ids.
- **Candidates:** 5 proposed, gate-decided each round; winner `cand_5` (payment-construction discipline via the `calculate` tool was the load-bearing edit; plus a basic-economy scope fix, a don't-transfer-in-scope rule, and a worked booking example).
- **Gate:** significance / paired, `k_se 1.0`.

**Headline (single-trial `num_trials: 1` — the pipeline default and the basis for the deterministic head-to-head):**

| split | baseline (seed) | best (`cand_5`) | Δ |
|---|---|---|---|
| **val** (30, fit) | **0.500** | **0.633** | **+0.133 / +26.7% relative** — gate-significant (Δ > k·SE) |
| **sealed test** (20, held-out, scored once) | **0.400** | **0.550** | **+0.150 / +37.5% relative** |

**Stable re-evaluation (`num_trials: 3`, for honesty about variance):**

| split | baseline | best | Δ |
|---|---|---|---|
| **val** (30, fit) | 0.544 | 0.644 | +0.100 / +18.4% — paired-significant (Δ/SE = 1.80) |
| **test** (20, held-out) | 0.467 | 0.400 | −0.067 (SE 0.105 — not significant) |

**Head-to-head vs deterministic orchestration (same split, same `gpt-oss-120b`, same proxy):** the
bounded deterministic `hill-climb` run (`claude-code` optimizer) proposed candidates reaching val
0.567 but none cleared the gate, so its best stayed the seed and its sealed test was 0.35 (Δ 0).
**Agent mode produced the only gate-accepted improvement and the only positive held-out test.**

**Honest reading.** τ²-Bench airline is high-variance at `num_trials: 1`: the single-trial numbers
above are real observations but noisy (the same policy drew val 0.63–0.73 across runs). The stable
n=3 numbers are the sober view — a paired-significant **val fit** gain that, because `train == val`,
is fitting rather than generalization, and a held-out test that is flat within noise. The
**requested 0.78 / >75% val target was not reached**: `gpt-oss-120b`'s stable val ceiling on this set
is ~0.64 (the opus-driven, 10-trial no-holdout run above peaked at 0.712). What agent mode *did* show
honestly: it drove the whole loop itself, gated on val, sealed the test once, beat the deterministic
run head-to-head, and improved the single-trial held-out test +37.5%. A genuine, stable held-out gain
here needs a stronger runner model or tool-level edits (which drove most of the lift in the
no-holdout run).

---

## τ²-Bench airline — `agent-optimize` on `gpt-oss-120b`, disjoint 26/12/12, `num_trials: 5` — **fourth null result; trial-averaging fixed the significance test and the no-regression veto became the blocker**

Fourth attempt on the same benchmark, split and models. v3 had established that at
`num_trials: 1` a byte-identical copy of the seed measured paired **Δ̄ = −0.0833** and was
rejected, so no edit of any quality could be detected. v4 changed **exactly one
substantive spec field** — `num_trials: 1 → 5` — leaving `gate_mode: paired` and
`gate_k_se: 0.2` untouched, because the bar was never the problem. **Nothing cleared the
gate.** What v4 adds is the measurement that says *why*, and this time the cause is a
different one from v3's.

- **Spec:** [`examples/tau2_airline/capevolve.agentopt.v4.gptoss.yaml`](../examples/tau2_airline/capevolve.agentopt.v4.gptoss.yaml)
  — a copy of `capevolve.agentopt.gptoss.yaml` with `num_trials: 5`, `max_metric_calls: 600`
  and a rollout-denominated `stop_condition` (the proxy does not meter dollars).
- **Agent + user simulator:** `aws/gpt-oss-120b` via the IBM litellm proxy. **Optimizer:**
  `aws/claude-opus-5` (the conversational agent itself).
- **Split:** disjoint **26 train / 12 val / 12 test** (`agentopt_split.json`), `paired`,
  `k_se 0.2`, **`num_trials: 5`** — so `pass^k` is defined here, unlike v3.
- **Cost:** **550 rollouts** (360 in the loop + 130 train + 60 sealing test), 5 gated
  candidates, **158 min** wallclock / 172 min runner time. Dollars remain **UNMETERED**
  (`usd: 0.0` is missing data; `spend.py` reports `runner_spend_metered: false`), so the
  budget unit is rollout counts.
- Artifacts, including `events.jsonl`, the five per-candidate gate verdicts, and the two
  analysis scripts, in [`run_agentopt_v4/`](../examples/tau2_airline/run_agentopt_v4/).

### The result table

| split | n | trials | seed | best (`= seed`) | paired Δ̄ | pass^1 | pass^2 |
|---|--:|--:|--:|--:|--:|--:|--:|
| train (never gated; diagnosis surface) | 26 | 5 | 0.5308 ± 0.0818 | 0.5308 ± 0.0818 | 0.0 | 0.5308 | 0.3962 |
| val (the gate) | 12 | 5 | 0.5667 ± 0.1180 | 0.5667 ± 0.1180 | 0.0 | 0.5667 | 0.4167 |
| **test** (sealed once) | 12 | 5 | **0.5000 ± 0.1254** | 0.5000 ± 0.1254 | 0.0 | 0.5000 | 0.3750 |

Every `0.0` is **by construction** — `best_id == seed`, so `measure.py` scored one
capability on both sides and emits that warning itself. **This is a null result with a
diagnosed cause, not a 0.000 improvement.** The requested goal of train ≥ 0.90 was neither
reached nor approached: train is 0.5308, and 0.90 on n=26 needs 24/26, i.e. fixing ~10 of
the 12 failing train tasks while breaking none. That was never achievable in this run and
is not claimed.

### The headline: three null-edit controls at 5 trials

v3 ran one null-edit control. v4 ran **three**, each a byte-identical copy of the seed
(`diff -r` clean — and `candidate_diffs.txt` contains no entry for any of them, which is the
artifact-level proof), each evaluated on full val at 5 trials and put through the same
`gate_check.py`:

| measurement of the SAME capability | val | paired Δ̄ vs the frozen seed | no-regression veto |
|---|--:|--:|---|
| `seed` (the gate's baseline) | 0.5667 | — | — |
| `c0_null5` | 0.4667 | **−0.1000** | fired: 8, 12, 20, 40 |
| `c0_null5b` | 0.5167 | **−0.0500** | fired: 8, 12, 32, 40 |
| `c0_null5c` | 0.5667 | **−0.0000** | fired: 8, 40 |

**Four measurements of one unchanged capability: mean 0.5292, SD 0.0479.** v3's four
equivalent measurements at 1 trial were mean 0.6042, **SD 0.1423**. So trial-averaging
worked: the per-eval spread fell **3.0×** (better than the √5 = 2.24 predicted, on 4 points
each, so treat the ratio as approximate). Pooling all four evals gives the run's best
estimate of the seed's val score, **0.5292 ± 0.1100 over 20 trials/task**.

The significance half of the gate is now sound and its SE is *predictable*:
[`noise_power.py`](../examples/tau2_airline/run_agentopt_v4/noise_power.py) derives, from
the baseline's own measured per-task rates, that a null Δ̄ should have SD **0.0632** at 5
trials — and the five gates measured SE 0.0628 / 0.0702 / 0.0696 / 0.0672 / 0.0796. The same
formula gives 0.1414 at 1 trial, against v3's observed 0.1423. The model of the noise is
right.

But **`c0_null5c` is the finding.** It measured an *exactly equal* val mean to the seed —
Δ̄ = −0.0000, the significance test cannot fault it — and the gate still **rejected** it,
because two tasks' fractional rewards had dipped. That is the whole v4 result in one row.

### Why nothing can be accepted: the veto reads the parent's upward noise as truth

> **Correction, and it changes the conclusion.** The first version of this section said
> `gate_check.py` and `harness` "both" define a regression as any strictly lower per-task
> reward. They did **not**, and the difference is the whole bug:
>
> - `harness._candidate_task_impact` vetoes only `par[t] >= 1.0 - eps and cand[t] < par[t] - eps`
>   — the parent must have measured-and-**passed**, which is what `SKILL.md:221` specifies.
> - `gate_check.regressions` vetoed on **any** strict drop from **any** parent level, while
>   its own docstring claimed to "mirror the harness's no-regression rule exactly".
>
> So the trap was specific to **agent-optimize's** gate, which was silently stricter than
> every other algorithm's, and it did *not* apply to `hill-climb` / `gepa` / `skillopt`.
> Simulated against this run's measured per-task val rates:
>
> | `num_trials` | any-drop (old `gate_check`) | parent-passed (`harness`, and now `gate_check`) |
> |--:|--:|--:|
> | 1 | 0.889 | 0.889 |
> | 5 | **0.983** | 0.428 |
> | 10 | **0.990** | 0.129 |
>
> The old rule got *worse* as trials rose, so no trial count could fix it. The harness rule
> **converges**, which is the behaviour a variance-aware gate must have. `gate_check` has
> been fixed to match, pinned by `core/tests/test_regression_gate.py`, which also asserts
> the harness predicate's source text so the two cannot drift apart again.

At `num_trials: 1` rewards are 0/1, so only real flips register. At 5 trials every reward is
a fifth, so noise alone produces small drops — and the parent's reference vector is **frozen
from a single 5-trial draw at baseline time**. Whichever tasks the baseline happened to
over-measure become veto triggers for every later candidate.

Val task 8 is the worked example: the baseline drew **4/5 = 0.80**; over the 15 later trials
of the *same* capability (the three null controls) its rate is **5/15 = 0.33**, and its best
estimate over all four unchanged evals is **9/20 = 0.45**. Task 8 therefore regressed in **all five** gates
of this run — including all three byte-identical seed copies. (Honest limit: a Fisher exact
test of the baseline window against the later windows gives p = 0.127 for task 8, so this is
regression to the mean off a lucky draw, **not** a demonstrated drift over time. No val task
showed a significant baseline-vs-later shift.)

Simulating the veto against the measured per-task rates shows the trap closes as trials
rise — the opposite direction from the significance test:

| `num_trials` | SD of a null Δ̄ | P(no-regression veto fires on a NULL edit) |
|--:|--:|--:|
| 1 | 0.1414 | 0.80 |
| 5 | 0.0632 | **0.95** |
| 10 | 0.0447 | 0.97 |
| 20 | 0.0316 | 0.98 |

**Under the old any-drop rule no trial count could make this gate accept anything**: raising
trials sharpened the significance test and simultaneously made the veto near-certain. With
`gate_check` corrected to the harness rule, that specific trap is gone.

#### But two bugs were cancelling, and the second one is now exposed

Fixing the veto does **not** make this run's candidates acceptable — it reveals that the
significance bar was never doing any work. At 5 trials:

| quantity | value |
|---|--:|
| null-edit Δ̄ spread (SD of 4 measurements of the *same* capability) | **0.0479** |
| the gate's bar at `gate_k_se: 0.2` | **0.0134** |
| `cA_partial` / `cB_becabin` measured Δ̄ | +0.0167 |

The bar sits **~3.6× below the noise floor**, so both real candidates "cleared significance"
on a Δ̄ that is one sixth of the span the null controls span by chance. An over-strict veto
was the only thing preventing false accepts, and it was rejecting byte-identical seeds to do
it. Neither +0.0167 is evidence of improvement, and this run must not be read as one.

What the numbers actually require, for anyone running a stochastic benchmark:

- **`num_trials: 10`** — enough for a 2-task val gain (0.1667) to sit at >3 SD. A 1-task gain
  needs `num_trials ≥ 26` (312 rollouts per candidate); a 3-task gain needs only 3.
- **`gate_k_se` well above 0.2.** `gate_check`'s own default is 1.0; the tau2 agent-optimize
  spec set 0.2, which on this benchmark is far inside the noise. It was deliberately **not**
  changed here — loosening or tightening the bar to reach a desired verdict is precisely the
  move this project exists to prevent, and the right value follows from a measured noise
  floor, not from a target. The measurement now exists: k·SE should exceed ~0.05 at 5 trials,
  i.e. k ≳ 1 on the paired SE this run observed.
- **a no-regression tolerance** is still worth having for the harness rule at high trial
  counts, though it is no longer the binding constraint (0.129 at 10 trials).

### The two real candidates, and what they actually measured

Both were narrow `policy.md` edits (diffs in `candidate_diffs.txt`), aimed at the two val
tasks the pooled 20-trial estimate showed to be genuinely near-zero and therefore worth
winning: task 24 (0.05) and task 32 (0.20).

| candidate | val | paired Δ̄ | bar `0.2·SE` | veto | verdict |
|---|--:|--:|--:|---|---|
| `cA_partial` — a barred part of a multi-part request is not grounds for transfer: refuse that part, complete the rest | 0.5833 | +0.0167 | 0.0134 | fired: 8 | **reject** |
| `cB_becabin` — a basic-economy flight change may go via a confirmed cabin change first, barred if any segment has flown | 0.5833 | +0.0167 | 0.0159 | fired: 8, 32, 40 | **reject** |

Both cleared the significance bar and **neither is evidence of an improvement**: +0.0167 is
one sixth of the spread the three null controls span (−0.1000 … −0.0000). Clearing a
`0.2·SE` bar of 0.013 is not a meaningful test at this noise level. Per-task, the edits did
essentially nothing to what they aimed at:

- **`cA_partial` executed but missed.** `check_transfers.py` shows transfers on task 24 fell
  2/5 → 1/5 and `book_reservation` was called on both sides, so the edit changed behaviour —
  but task 24 stayed **0/5**. The v3 single-trial transcript this edit was designed from
  ("agent transferred instead of booking") was **not representative**: at 5 trials task 24's
  modal failure is a *wrong* `book_reservation` argument set, not abandonment. Diagnosing a
  stochastic benchmark from one rollout produced a correct-looking edit aimed at the wrong
  defect.
- **`cB_becabin` moved its target the wrong way**, 0.20 → 0.00 on task 32, within the null
  range (the controls gave 0.40 / 0.00 / 0.20 there). It did *not* break the paired case it
  was scoped to protect: task 36, where refusing is correct because a segment has already
  flown, held at 1.00 across all five trials.

### Verified exclusions

Both re-checked from rollouts rather than taken on trust: **val task 40** and **train task
7** are user-simulator defects, not capability defects — the simulator answers the agent's
confirmation request and appends `###STOP###` in the same turn, ending the episode before
the agent can act (train task 7 also leaks a `<reasoning>` block into the user turn). Task
40 is not, however, hopeless: at 5 trials it scores 0.20–0.40, so the defect is
intermittent. Val tasks 24 (0.05) and 44 (0.00) are the genuinely stuck ones, and 44 is a
five-reservation itinerary-arithmetic task that no one-paragraph rule will fix.

No subset screen was run. At `val_n 12` the tier-1 floor of 6 tasks gives a breakeven kill
rate of 0.5, and with two candidates a screen could not pay for itself; full val was paid
directly for each.

---

## τ²-Bench airline — `agent-optimize` on `gpt-oss-120b`, disjoint 26/12/12 — **third null result; the gate rejects a byte-identical copy of the seed**

Third attempt on the same spec, split and models as the section below, built to convert
that run's diagnosis into a measured gain. **Nothing cleared the gate again**, and this
time the run establishes *why* with a control the two earlier runs never ran: a
**null-edit candidate — a byte-identical copy of the seed capability — was evaluated on
full val and put through the honest gate, and the gate REJECTED it.**

- **Spec:** [`examples/tau2_airline/capevolve.agentopt.gptoss.yaml`](../examples/tau2_airline/capevolve.agentopt.gptoss.yaml),
  `orchestration_mode: agent`, `algorithm_skill: agent-optimize`, capabilities
  `[system-prompt, tools]`. Same file as the v2 run except `stall: 3 → 5` and the prose
  `stop_condition`'s "3 rejects in a row" → "5" (the prose ceiling, not the spec field,
  was what actually stopped v2 at 3 of 8 iterations). **`gate_mode`, `gate_k_se` and
  `num_trials` were NOT touched.**
- **Agent + user simulator:** `aws/gpt-oss-120b` via the IBM litellm proxy. **Optimizer:**
  `aws/claude-opus-5` (the conversational agent itself).
- **Split:** disjoint **26 train / 12 val / 12 test** (`agentopt_split.json`),
  `num_trials: 1`, `paired`, `k_se 0.2`.
- **Cost:** **134 rollouts** (122 in the loop + 12 sealing test; `metric_calls: 134`), 5 iterations, ~2 h of runner wall-clock. **Runner dollars remain UNMETERED** on this path
  (`usd: 0.0` is missing data, not a free run — `spend.py` reports
  `runner_spend_metered: false`), so the budget unit here is rollout counts.
- Artifacts, including `events.jsonl`, in
  [`run_agentopt_v3/`](../examples/tau2_airline/run_agentopt_v3/).

### The result table

| split | n | seed | best (`= seed`) | paired Δ̄ |
|---|--:|--:|--:|--:|
| train (never gated; diagnosis surface) | 26 | 0.5385 ± 0.0997 | 0.5385 ± 0.0997 | 0.0 |
| val (the gate) | 12 | 0.6667 ± 0.1421 | 0.6667 ± 0.1421 | 0.0 |
| **test** (sealed once) | 12 | **0.5000 ± 0.1508** | 0.5000 ± 0.1508 | 0.0 |

Every `0.0` is **by construction** — `best_id == seed`, so `finalize` scored one
capability on both sides. `measure.py` emits that warning itself.

**The requested target — train mean ≥ 0.90 — was not reached and was not approached.**
Train stayed at its baseline 0.5385 because no candidate was ever accepted, and train may
never gate. Nothing here is progress toward 0.90. For the record, 0.90 on n=26 requires
24/26, i.e. fixing 10 of 12 failing train tasks while breaking none; at least one of those
12 (task 7) is unfixable by any capability edit, because the **user simulator** ends the
episode on its second turn.

### The null-edit control — the finding that supersedes both earlier diagnoses

Five candidate measurements (four distinct edits, one of them measured twice) all came back
at **exactly 0.4167** on full val while the seed measured 0.6667. Unrelated edits landing on
the same mean was implausible enough to test the
pipeline itself, so an unmodified copy of the seed (`c0_nulledit`, verified byte-identical
with `diff -r`) was run through the same evaluate → `gate_check.py` path:

```
NULL-EDIT (byte-identical to seed) gate verdict: reject
  paired Δ̄=-0.0833 <= 0.2·SE=0.0167 (SE=0.0833, n=12)
  regressions ['8']  paired_n 12
```

A **known-zero-effect** candidate produced a negative Δ̄ *and* tripped the no-regression
veto. The bar is not the problem — 0.0167 is negligible. The problem is that at
`num_trials: 1` a single per-task reward vector is noisy enough that zero change registers
as **minus one task**. Any real +1-task gain has to clear noise of the same magnitude, in
the same direction, on the same measurement. That is a measurement-power limit, and it
explains all three null results on this benchmark better than any of the behavioural
diagnoses offered for v1 and v2.

### A second, stronger control: `c5_guards_only` never fired a guard

`c5_guards_only` changes only tool *bodies* — no policy text, no tool docstring, no schema.
Auditing its 12 val rollouts for the guard error strings shows **not one guard fired on any
val task**:

| val task | guarded tool called | guard fired |
|--:|---|---|
| 12, 16 | `update_reservation_baggages`, `update_reservation_flights` | **no** |
| all others | none | **no** |

So on this split `c5_guards_only` is **functionally identical to the seed** — same prompt,
same tool schemas, and no added code path ever executed. Its true Δ is 0 by construction.
The gate measured **Δ̄ = −0.2500 with regressions on tasks 8, 16 and 20.**

That gives **four** measurements of a capability that is functionally identical to the seed
on val:

| measurement | val |
|---|--:|
| v2 seed | 0.7500 |
| v3 seed (the gate's baseline) | 0.6667 |
| `c0_nulledit` (byte-identical copy) | 0.5833 |
| `c5_guards_only` (no guard ever fired) | 0.4167 |

**Mean 0.6042, SD 0.139, range 4 of 12 tasks.** The consequence is blunt: **0.4167 is
inside the observed range of the seed itself**, so *none* of the five candidate results
below can be called evidence of harm, and the −0.25 deltas the gate computed are not
measurements of the edits. The gate behaved correctly given its input; the input cannot
support the question.

### The noise floor, measured four ways

| replication | result |
|---|---|
| val, 4 functionally-identical-to-seed measurements | **0.7500 / 0.6667 / 0.5833 / 0.4167** — mean 0.6042, SD 0.139 |
| val, tasks that flip across the 3 byte-identical draws | **2 of 12** (tasks 8 and 32) |
| train, 2 draws of the identical seed capability (v2, v3) | mean identical at **0.5385** both times, but **6 of 26 per-task rewards flipped** (23%) — tasks 10, 11, 15, 30, 38, 49 |
| val, one candidate (`c2_toolguard`) measured twice, once concurrently and once serially | **0.4167 both times**, 2 of 12 per-task flips — so process concurrency is *not* a confound |

Three val tasks (**24, 40, 44**) fail in every one of 11 measurements and no candidate
ever fixed any of them. So the gate's usable signal is 3 immovable failures against 2–6
coin-flip tasks.

### The six candidates, and the real gate numbers for each

Every reject is a **genuine full-val paired gate decision** (`paired_n: 12`,
`coverage: 1.0`), recorded with the new machine-readable `reject_basis: gate`. This closes
the v2 run's weakest point, where `gate_check.py` never fired on real data.

| candidate | lever | val | Δ̄ | bar (`k·SE`) | regressed | fixed |
|---|---|--:|--:|--:|---|---|
| `c1_verify` | prompt: verification obligations only | 0.4167 | −0.2500 | 0.0261 | `8 12 20` | — |
| `c2_toolguard` | tools: DB-checked policy guards + a search docstring | 0.4167 | −0.2500 | 0.0261 | `8 12 20` | — |
| `c3_finish` | prompt: act-on-confirmation + finish-every-part | 0.4167 | −0.2500 | 0.0261 | `8 12 20` | — |
| `c5_guards_only` | tools: the guards **alone**, policy byte-identical | 0.4167 | −0.2500 | 0.0261 | `8 16 20` | — |
| `c6_onerule` | prompt: **one sentence**, verification only | 0.5000 | −0.1667 | 0.0298 | `12 20` | — |
| `c0_nulledit` *(control, not a proposal)* | **none — byte-identical to seed** | 0.5833 | −0.0833 | 0.0167 | `8` | — |

**Not one candidate fixed a single val task** — that part is a real, repeated observation.
The "regressed" column is **not**: every candidate, and both controls, "broke" task 8, a
knife-edge pass the seed itself wins in only 2 of 8 measurements. Read the Δ̄ column as
what the harness reported, not as an effect of the edit.

`c6_onerule` was a deliberate dose-response probe: **one sentence** of verification-only
policy text instead of a block. It scored 0.5000 — higher than every multi-rule candidate
and the only candidate that kept task 8 — but still below the seed draw it was gated
against, and still a reject. Suggestive of a text-volume effect on this weak reader, and
nothing more: one measurement, inside the noise band established above.

The two hypotheses this run was built to test both failed, and failed *distinguishably*:

1. **Verification-only prompt rules** (`c1_verify`, and `c3_finish` with an explicit clause
   that a confirmation never authorises a forbidden action) did not raise the val mean, and
   the measurement cannot say whether they lowered it. What they *do* falsify is v2's
   explanation for the task-12 regression: v2 blamed "compliance obligations", yet task 12
   regressed here under `c1_verify`, a rule set carrying none. Across all 11 measurements in
   this run and v2, task 12 passes only **4 of 11** times; it is a fragile task, not a
   casualty of a compliance rule.
2. **The tools lever was exercised for the first time in isolation.** `c5_guards_only`
   moves four policy invariants that tau2's API deliberately does *not* enforce into the
   tool bodies — cancellation eligibility (24h / airline-cancelled / business / insured,
   checked against the DB rather than the user's claim), no reduction of checked bags,
   basic-economy flights immutable, route and trip type immutable — each raising an error
   that names the rule and the actual values checked. The guards were unit-checked to fire
   on real DB cases the seed silently accepted (e.g. it cancelled reservation `3RK2T9`,
   created 2024-05-02, basic economy, uninsured, on the user's unverified claim that it was
   "booked ten hours ago") and to leave a legitimately cancellable reservation alone. They
   are *correct*, they would have blocked exactly the wrong writes in three failing tasks
   (train 48, train 49, val 44) — **and none of them fired anywhere on val**, which is what
   makes `c5_guards_only` the strongest control in the run rather than a result about tools.
   The tools lever is therefore still **untested for effect**: it was exercised, audited and
   shown correct, but this split never gave it an opportunity to act.

### The acceptance split cannot see the tools lever

The guard error strings appear in **zero** val rollouts across all three tools candidates
(`c2_toolguard`, `c2_toolguard_solo`, `c5_guards_only`). The cases the guards exist for do
occur in the data — the seed illegally cancels reservation `3RK2T9` in train tasks 48 and
49 and cancels an already-flown reservation in val task 44 — but on val the guarded paths
are either never reached or reached only on legitimate calls. So half the capability
surface under optimization (`capabilities: [system-prompt, tools]`) is **invisible to the
split that decides acceptance**. Diagnosing on train and gating on val is the right
discipline, and here it means a correct tools edit can never be accepted, however good it
is. A tools-lever run on this benchmark needs a val split chosen to contain
policy-invariant cases, or `capabilities` narrowed to what val can actually score.

### v2's central mechanism claim was wrong

The v2 section reports task 40 as "the agent replies *the name has been updated* without
ever calling the tool — a hallucinated success". Re-reading the persisted rollout,
**that text is in the `user` message, not the assistant's**: the user simulator (also
`gpt-oss-120b`) emitted `Yes.<reasoning>Agent will likely confirm and process.</reasoning>
Your request has been processed. The passenger name on reservation 3RK2T9 has been updated
… ###STOP###`. It answered, then role-played the agent's reply, then terminated the
episode. Task 40 is a **user-simulator defect**, not an agent defect, and no edit to the
policy or tools can fix it. Same for train task 7, which the simulator ends on its second
turn. That is 1 of 12 val tasks and 1 of 26 train tasks that are unwinnable by
construction — and one of the three val tasks that fail in all 11 measurements.

### What this run adds to the method

1. **The null-edit control is now part of the protocol.** Evaluating a byte-identical copy
   of the parent through the same evaluate → gate path costs one val eval and bounds the
   harness's own false-reject rate. Both earlier null results on this benchmark are
   reinterpretable in its light; neither ran it.
2. **`commit.py --reject-basis`** records the *driver's* disposition
   (`gate|screen_kill|ceiling|budget|infra`) machine-readably next to the screen's own
   verdict. `screen.py`'s `decision` is authoritative only as the screen's statistical
   verdict — by invariant 1 it can only say `kill` or `promote`, and "promote" never meant
   "was then evaluated on full val". In v2 that ambiguity made two artifacts read as a
   contradiction (`screen: promote` beside a commit note saying "not promoted to full
   val"); both were true. Every reject in this run carries `reject_basis: gate`, so the log
   asserts that a full-val paired gate actually ran.
3. **The gate was exercised on real data six times** (`paired_n: 12`, `coverage: 1.0` each),
   closing v2's weakest provenance point, where `gate_check.py` never fired on a real
   full-val eval and two rejects rested on an arithmetic ceiling.
4. **Skipping the screen ladder was the right call and is now measured, not argued.** At
   `val_n 12` the tier-1 floor of 6 gives a breakeven kill rate of 0.5, and with 2 of 12
   val tasks flipping on an identical capability a 6-task screen carries no signal. All six
   candidates went straight to full val; `screen_ledger` is empty by design, not by neglect.

### Honest reading

The optimizer did not find an improvement, and this run shows the harness could not have
recognised one — nor could it correctly reject a non-change. Two controls, one
byte-identical and one functionally identical on the scored split, were both rejected by
the honest gate. Concretely: the gate rejects a copy of the seed, half of
val is coin-flips, and 3 of 12 val tasks are immovable (one of them because the user
simulator breaks). The correct next step is **not** a looser gate — `k_se` was left at
0.2 and the bar was never the obstacle. It is `num_trials > 1` so each per-task reward is
a mean rather than a single Bernoulli draw, and a wider val, in that order. Until then any
accept on this configuration would be a coin flip dressed as a result.

## τ²-Bench airline — `agent-optimize` on `gpt-oss-120b`, disjoint 26/12/12 — **second null result, sharper diagnosis**

> **Kept as history, superseded by the v3 section above.** Its central mechanism claim
> about task 40 is **wrong** — the "hallucinated success" text is in the *user simulator's*
> message, not the agent's; see "v2's central mechanism claim was wrong" above. Its
> conclusion (no accept) stands and was reproduced.

Re-run of the section below with the agent+user-simulator switched from `claude-haiku-4-5`
to **`aws/gpt-oss-120b`** to restore headroom, and with the algorithm's own defects fixed
first. **Nothing cleared the gate again**, but this time the mechanism was read directly
out of the transcripts rather than inferred from means, and the run cost 68 rollouts
instead of 110.

- **Spec:** `.capevolve/project/capevolve.agentopt.yaml` (derived from
  [`examples/tau2_airline/capevolve.agentopt.yaml`](../examples/tau2_airline/capevolve.agentopt.yaml)),
  `orchestration_mode: agent`, `algorithm_skill: agent-optimize`, capabilities
  `[system-prompt, tools]`.
- **Agent + user simulator:** `aws/gpt-oss-120b` via the IBM litellm proxy. **Optimizer:**
  `aws/claude-opus-5` (the conversational agent itself — no per-iteration subprocess).
- **Split:** disjoint **26 train / 12 val / 12 test** (`agentopt_split.json`),
  `num_trials: 1`, `paired`, `k_se 0.2`.
- **Architecture change:** diagnosis on **train** (26), acceptance gated on **val** (12),
  test sealed once. Previously `diagnose` was hardcoded to val, so train was unreachable
  and the run was fitting the split it was judged on.
- **Cost:** **68 rollouts**, 48 min of runner wall-clock, ~75 min end to end. **Runner
  dollars are UNMETERED on this serving path** — the proxy returns no cost, litellm logs
  `model isn't mapped yet`, and the ledger records `usd: 0.0`. That 0.0 is missing data,
  not a free run; rollout counts are the honest unit here. Pre-run
  `cap-evolve estimate` said $50.39 expected (runner $10.52 + optimizer $39.86) from prior
  calibration — not comparable, and reported only for the record.
- **Stopped on its own `stall` rule** (3 consecutive rejects), at iteration 3 of 8.

| split | n | seed | best (`= seed`) | paired Δ̄ |
|---|--:|--:|--:|--:|
| train (never gated; diagnosis surface) | 26 | 0.5385 ± 0.0997 | 0.5385 ± 0.0997 | 0.0 |
| val (the gate) | 12 | 0.7500 ± 0.1306 | 0.7500 ± 0.1306 | 0.0 |
| **test** (sealed once) | 12 | **0.7500 ± 0.1306** | 0.7500 ± 0.1306 | 0.0 |

Every `0.0` is **by construction** — `best_id == seed`, so `finalize` scored one
capability on both sides. `measure.py` emits that warning itself. Artifacts, including
`events.jsonl`, in [`run_agentopt_v2/`](../examples/tau2_airline/run_agentopt_v2/).

**The requested target — train mean ≥ 0.90 — was not reached, and was never approached.**
Train stayed at its baseline 0.5385 because no edit was ever accepted. Nothing here
should be read as progress toward it.

### Headroom was restored; the gate was still not the bottleneck

Switching to `gpt-oss-120b` did what it was supposed to: baseline val fell from 0.8333
(haiku, 10/12) to 0.7500 (9/12), and train sits at 0.5385 (14/26) — 12 failing train
tasks to work with instead of 2 val tasks. And the gate bar was never the obstacle:

> For exactly one val task flipping +1 out of `n` paired deltas, Δ̄ = 1/n and SE = 1/n
> **exactly**, so Δ̄/SE = 1.0000 for *every* n. At `k_se 0.2`, n=12, a single clean flip
> gives Δ̄ = 0.0833 against a bar of 0.0167 — it clears comfortably. Widening val would
> not have helped; for two flips the ratio actually *falls* slightly with n (1.483 at
> n=12 vs 1.439 at n=30). Both null results are failures to move the **mean**, not
> failures of resolution.

### The mechanism, read from transcripts

Val's 3 failures (24, 40, 44) and 11 of train's 12 share one cluster signature
(`database state does not match`), so train-driven edits *could* bank — the overlap was
checked for free before any spending. Within it, two sub-modes: the required write was
**never called** (7/12 train, 3/3 val), or it was called with **wrong arguments** (6/12
train, `update_reservation_flights` four times). Task 40's transcript is the purest case:
the agent asked for confirmation, the user said "Yes", and the agent replied *"the
passenger name has been updated"* **without ever calling the tool**.

Three candidates, each rejected, each for a reason visible in the rollouts:

| candidate | edit | screen decision | fixed | regressed |
|---|---|---|---|---|
| `cand_r1_disc` | +70-line "Execution discipline" section (policy) | promote (inconclusive) | 0 of 3 | `12` |
| `cand_r2_short` | +18-line policy section + once-and-only-once / last-resort contracts in 6 tool docstrings | **kill** (Δ̄ −0.333, SE 0.211) | 0 of 3 | `12`, `16` |
| `cand_r3_lookup` | +13 lines, policy only, one scoped rule (look it up; don't transfer) + an explicit "this does not widen what is permitted" clause | promote (inconclusive) | 0 of 3 | `12` |

**All three regressed task 12, and none fixed anything.** Task 12's transcripts say why,
and it is not noise. Under the seed, the user asks to upgrade *one* passenger to business
and add bags; the agent correctly **refuses** the partial upgrade (cabin must be uniform),
the user falls back to bags only, and the agent makes one correct write → 1.0. Under
`cand_r2_short`, the same "act on confirmation / answer every part" pressure made the
agent **comply with the request it should have refused** — it upgraded both segments to
business and added bags → wrong DB state → 0.0. `cand_r3_lookup` reproduced it even with
an explicit precedence clause telling it not to.

So on this model the edits traded **policy compliance for eagerness**. Pushing
`gpt-oss-120b` to act more decisively makes it act *wrongly* on the tasks whose correct
answer is a refusal — a genuine capability trade-off, correctly refused three times. A
secondary effect is visible too: `cand_r2_short` drove task 44 from 20 to **54** turns of
runaway `search_direct_flight` calls, and its screen took 10 minutes against the seed's 2.

### What this run adds to the method

1. **A screen can prove a reject arithmetically.** When the tier-1 subset already covers
   every val task the parent fails, the unscreened remainder is all tasks the parent
   passes, so it can only stay level or regress — and the candidate's best conceivable
   full-val mean is *computable*. For `cand_r1_disc`: at most 8/12 = 0.667 against the
   parent's 0.750, best-case Δ̄ = −0.0833. The gate needs Δ̄ > k·SE ≥ 0, so **no full-val
   eval could have accepted it**. This is now `subsample.full_val_ceiling()`, reported in
   every screen artifact, and it escalates a promote to a *provable* kill when the ceiling
   is strictly below the parent. It cannot ever conclude "accept", so honesty invariant 1
   is intact. Consequence for this run: **no candidate was ever taken to a full-val eval,
   so `gate_check.py` never fired on real data.** All three rejects rest on screen
   evidence, one statistical and two arithmetic — weaker provenance than a full-val gate
   rejection, and stated as such.
2. **A narrow val makes the ladder uneconomic, and the artifact now says so.**
   `savings.breakeven_kill_rate` = `fired / full_val_rollouts` = **0.5** at val 12. With
   1 kill in 3 screens the recorded ledger is `net_rollouts −6` — screening was still a
   net cost under its own accounting, which assumes every promote gets paid for.
3. **The subset floor moved from 3 to 6.** The 3-task tier-1 screen in the run below
   reported `fixed: ["44"]` for a candidate full val showed never fixed 44. At 6 the
   holdout caught the task-12 regression on all three candidates.
4. **val predicted test here.** val 0.7500 and sealed test 0.7500 for the same seed, on
   the same index-stride split that previously gave val 0.8333 / test 0.4167. Train
   (0.5385) is materially harder than either — the stride split balances draw order, not
   difficulty.

### Defects fixed before this run (each was silently wrong, not merely inconvenient)

- **`diagnose` was hardcoded to `rollouts/val`** — train was unreachable by every one of
  the five algorithms, so "diagnose on train, gate on val" was undocumentable and
  unrunnable. Now `--split train|val`, default unchanged.
- **`spend.py` / `measure.py` read `project/capevolve.yaml` by filename**, but
  `cap-evolve run --spec` supports any filename. Every agent-mode run of a variant spec
  silently reported `predicates: []` — the whole re-read-your-constraints discipline
  no-opping without a word. Now `specfile.spec_for_run()` reads the path `cli` already
  logs into the run dir's `run_config` event.
- **Unmetered runner spend read as $0/rollout**, so `usd_needed` was 0.0, a `max_usd`
  ceiling could never block anything, and *any* fan-out came back `affordable: true`.
  Now reported as `runner_spend_metered: false` with the rate `null`.
- **A train/test-qualified score goal was parsed into `target_val_score`**, which is only
  ever checked against the full-val mean — so `"reach train mean >= 0.9"` would have
  enforced a **val** bar while reporting it as the train one. Now reported in
  `ambiguous`.
- **`commit.py` accepted a duplicate candidate id.** The tag collision documented below
  was possible because nothing checked. It now refuses a tag that already carries an
  accept/reject event, reading `events.jsonl` so the guard holds across processes.
- **`measure.py --train on` re-ran the seed's whole train split** even with complete
  rollouts already on disk. Candidate dirs are immutable snapshots, so those rollouts are
  measurements of exactly that capability; reuse saved 26 rollouts here.

### Rollout isolation, verified before spending

The gate reads `*__<tag>__t*.json`, and screens write `<tag>__screenN`. Probed
adversarially — a screen rollout claiming 1.0 and a full-val rollout claiming 0.0 for the
same candidate — the full-val read returns **0.0**; and on the live run dir, a full-val
read of `cand_r1_disc` (which has only screen rollouts) returns `n_scored: 0` rather than
6. Both probes are permanent checks in
`skills/algorithms/agent-optimize/scripts/check.py`.

### Honest reading

Two independent runs, two models, seven candidates, zero accepts. The consistent finding
is not that the optimizer is weak but that **the airline policy is not the binding
constraint for these models on these tasks** — the seed policy already states the rules
the failures violate, and adding restatements of them makes a mid-tier model less
compliant, not more. The next thing worth testing is not more prose but the lever that
carried the no-holdout run: **tool-level change** (composite or guard-railed tools that
make the correct write the easy one), and a runner strong enough that the compliance
trade-off does not bite. Reporting a 0.90 train number here would have required either
gating on train or loosening `k_se`; neither was done.

---

## τ²-Bench airline — `agent-optimize` with subset screening, disjoint 26/12/12 — **null result**

> **Kept as history, superseded by the `gpt-oss-120b` section above.** This is the earlier
> `claude-haiku-4-5` run. It is retained in full because it is real evidence about the
> method — and because the second run reproduced its central finding (no accept) with a
> different model and a different diagnosis, which makes the pair more informative than
> either alone. The defects it exposed (tag collision, screen width, the `--mode paired`
> CLI, the `work/` dir) are fixed; see the section above for what changed.

The run that exercised subset screening and prose-constraint parsing for the first time.
**Nothing cleared the gate.** Recorded because a null result with a diagnosed cause is
evidence, and because two integrity findings came out of it.

- **Spec:** `examples/tau2_airline/capevolve.agentopt.yaml`, `orchestration_mode: agent`,
  `algorithm_skill: agent-optimize`, capabilities `[system-prompt, tools]`.
- **Agent + user simulator:** `claude-haiku-4-5` via the IBM Anthropic-compatible gateway.
- **Split:** disjoint **26 train / 12 val / 12 test**, `num_trials: 1`, `paired`, `k_se 0.2`.
- **Cost:** **$12.98** ($10.58 runner including screens + $2.40 optimizer), 5 iterations,
  110 metric calls. Stopped on its own `stall` rule (3 consecutive rejects), not on a cap.

| split | n | seed | best (`= seed`) | paired Δ̄ |
|---|--:|--:|--:|--:|
| train | 26 | 0.6154 ± 0.0973 | 0.6154 ± 0.0973 | 0.0 |
| val | 12 | 0.8333 ± 0.1124 | 0.8333 ± 0.1124 | 0.0 |
| **test** (sealed once) | 12 | **0.4167 ± 0.1486** | 0.4167 ± 0.1486 | 0.0 |

Every `0.0` is **by construction, not by measurement** — `best_id == seed`, so `finalize`
scored the same capability on both sides. `measure.py` emits that warning itself.

### All four candidates, rejected with their own reasons

| candidate | val | Δ̄ | bar (`k·SE`) | SE | n | regressed | fixed |
|---|--:|--:|--:|--:|--:|---|---|
| `cand_tools` | 0.8333 | **+0.0000** | 0.0246 | 0.1231 | 12 | `24` | `8` |
| `cand_r1` | 0.5833 | −0.2500 | 0.0359 | 0.1794 | 12 | `16 20 24 36` | `8` |
| `cand_r2` | 0.7500 | −0.0833 | 0.0167 | 0.0833 | 12 | `32` | — |
| `cand_r3` | 0.4167 | −0.4167 | 0.0297 | 0.1486 | 12 | `12 16 20 24 36` | — |

Re-derived from the persisted rollouts in
[`run_agentopt/val_per_task.json`](../examples/tau2_airline/run_agentopt/val_per_task.json);
the seed fails exactly two tasks, `8` and `44`.

`cand_tools` is **churn**: mean identical to the seed, different tasks passing (fixed 8, broke
24). That is the failure mode the no-regression veto exists for, now observed a third time
across runs. **No candidate ever fixed task 44** — only `cand_tools` and `cand_r1` moved
anything, both unlocking task 8 and both breaking task 24 to do it. The edits were audited as
general, not task-keyed. This is a real capability trade-off, correctly refused.

### Both levers were genuinely exercised

Every candidate edited **both** the prompt and the tool code — `policy/policy.md` +2 to +11
lines and `tools/tools.py` +71 to +87 across 3 hunks (new `_to_minutes()` /
`_scheduled_duration_hours()` helpers, `get_flight_status` returning `duration_hours` with a
`+1` next-day-arrival rule). So the qualitative claim — it edits prompts *and* tool code
jointly — is demonstrated. The statistical claim is not.

### Why it found nothing — four causes

1. **The effect size is below the noise floor.** Baseline is 10/12, so only 2 tasks are
   winnable and one flipped task is Δ̄ ≈ 0.083 against a paired SE of 0.08–0.18. This split
   cannot resolve a one-task gain. A measurement-power limit, not an optimizer failure.
   `k_se 0.2` was already permissive and was **not** loosened to manufacture an accept.
2. **`num_trials: 1` collapses the paired gate on identical trials** (`SE = 0` → STRICT
   fallback, emitted as a `gate_warning`).
3. **Subset screening was pure overhead here — a measured loss.** 4 screens, **0 kills, 4
   promotes**, 12 rollouts fired, 0 avoided, `net_rollouts −12`, `screen_usd $1.367`. All four
   returned `inconclusive: true`. Worse, `cand_r3`'s screen produced a **false positive**: its
   subset was `[16, 44, 8]` with `regressed: ["16"]` and `mean_delta 0.0`, which requires a
   `+1` on 44 or 8 to average out — yet full val shows `cand_r3` fixed *neither*. So a 3-task
   screen read an improvement that does not exist. That vindicates the rule that a screen may
   never accept, and undercuts 3 as a sufficient triage width. The ladder behaved as designed;
   this run does not demonstrate the cost win it exists for.
   *Correction (2026-08-16):* an earlier revision of this section claimed `screens/*.json`
   leaves `fixed: null`. That was wrong. The artifacts do record it, under
   `paired.fixed` — `cand_r3__screen1.json` says `paired.fixed: ["44"]` and
   `paired.regressed: ["16"]`. The top-level `regressed` key (from `screen_decision`) has no
   `fixed` sibling, which is what the earlier audit read. The false positive is therefore
   directly auditable from the artifact, not inferred.
4. **val does not predict test on this split.** val 0.8333 vs sealed test 0.4167 for the *same*
   seed capability, despite index-stride stratification. Second observation across runs.

### Integrity finding: a tag collision invalidated one decision

Two concurrent optimizer drivers both tagged a candidate `cand_r2`. The event log holds **two**
`reject cand_r2` events with different notes describing different edits, but only **one**
`evaluate cand_r2`, one `screen cand_r2`, and one set of 12 rollouts — so one edit was rejected
on the other's evidence, and the second snapshot overwrote the first in `candidates/cand_r2`.

Direction of harm matters: it produced a spurious **reject**, not a spurious accept, and
`best_id` is `seed`, so no reported number rests on it. This is `agent-optimize`'s own
unique-tag invariant (rollouts are `<task>__<tag>__t<k>.json`, so a shared tag silently
collapses two candidates into one) being violated by real concurrent agents. By contrast the
`<tag>__screenN` isolation held perfectly under the same pressure — 12 files per candidate
tag, 3 per screen tag, no bleed.

### Reproducibility gap

The run only works with `TAU2_AGENT_MODEL` / `TAU2_USER_MODEL` set to an anthropic-looking
model string; otherwise `rits.llm_args_for()` falls through and demands `RITS_API_KEY`. Neither
appears in the spec. This broke the first `finalize` attempt (the seal survived — the failure
preceded `mark_test_used()`). Worth recording in the spec or the adapter docstring.

---

## τ²-Bench airline — Qwen 2.5 14B (tools only, held-out)

Same benchmark, capability, split, and algorithm as the held-out run above, with a
self-hosted open model (**Qwen 2.5 14B-Instruct** via vLLM on OpenShift) replacing the
Claude runner.

- **Capability:** airline **policy + tools** (`[system-prompt, tools]`).
- **Optimizer:** `claude-code` @ `claude-sonnet-4-6` (Vertex AI).
- **Runner + user simulator:** `Qwen/Qwen2.5-14B-Instruct` via vLLM on OpenShift.
- **Tasks / trials:** all **50** airline tasks · **5** trials each.
- **Split:** **train=val=30, test=20** — **held-out**.
- **Algorithm / gate:** `hill-climb --focus all`, **10** iterations, paired significance gate `k_se 0.3`.

| split | baseline | optimized | Δ |
|---|---|---|---|
| **val** (30 tasks) | **0.200** (20.0%) | **0.387** (38.7%) | **+0.187 / +93.5% relative** |
| **sealed test** (20 tasks, scored once) | **0.170** (17.0%) | **0.240** (24.0%) | **+0.070 / +41.2% relative** |

3 of 10 iterations accepted. The optimizer added code-level enforcement of cancellation
rules, input validation guards, and pre-flight status checks — hardening tool
implementations rather than rewriting policy prose.

---

## τ²-Bench airline — Qwen 2.5 14B, all capabilities (held-out)

Same model and split as above, with all three capability types optimized jointly.

- **Capability:** `[skill-package, system-prompt, tools]`.
- **Optimizer:** `claude-code` @ `claude-sonnet-4-6` (Vertex AI).
- **Runner + user simulator:** `Qwen/Qwen2.5-14B-Instruct` via vLLM on OpenShift.
- **Tasks / trials:** all **50** airline tasks · **5** trials each.
- **Split:** **train=val=30, test=20** — **held-out**.
- **Algorithm / gate:** `hill-climb --focus all`, **10** iterations, paired significance gate `k_se 0.3`.

| split | baseline | optimized | Δ |
|---|---|---|---|
| **val** (30 tasks) | **0.273** (27.3%) | **0.520** (52.0%) | **+0.247 / +90.5% relative** |
| **sealed test** (20 tasks, scored once) | **0.120** (12.0%) | **0.270** (27.0%) | **+0.150 / +125.0% relative** |

3 of 10 iterations accepted, 7 rejected. The optimizer edited tool code, policy rules,
and skill prose jointly — combining code-level guards with policy clarifications and
structured methodology in SKILL.md.

**Best held-out test gain across all Qwen 14B runs (+125%).** On a self-hosted 14B model,
`[skill-package, system-prompt, tools]` with `hill-climb` outperformed the tools-only run
(+41.2%) when paired with hill-climb's conservative gating.

## SkillsBench — full 87-task optimization (fit metric, Opus 4.6)

A 3-iteration hill-climb over the same four shared office-document skills as the
baseline section above, starting from the `run_baseline_opus` frozen baseline
(reused via `--reuse-baseline`). Same fit-metric split (train == val == test =
all 87), `num_trials: 1`, paired gate `k_se: 0.2`.

Artifacts under `.capevolve/run_opus_optimize3/` (gitignored, per-run): `SUMMARY.md`,
`summary.json`, `baseline.json`, `final.json`, `events.jsonl`, `PATCH_NOTE.md`,
`rollouts/val/*.json` (348: 87 seed + 87 × 3 candidates), `rollouts/test/*.json`
(174: 87 optimized + 87 baseline-seed).

| | baseline (seed) | best (`cand_0001`) | Δ |
|---|---|---|---|
| val_reward (mean) | 0.281 ± 0.048 | **0.357 ± 0.050** | **+0.076 (+27.2% relative)** |
| pass_at_1 (fully-passing tasks / 87) | 23 (26.4%) | **28 (32.2%)** | **+5 tasks (+22% relative)** |
| test_reward (fit metric = val by construction) | 0.281 * | **0.357** | +0.076 |

\* The finalize step's baseline-test re-evaluation broke overnight (VPN drop; every
task returned 0 across a 5-hour eval); `test_baseline_reward` here is manually
spliced from the properly-scored seed val in `run_baseline_opus`. Under the fit-
metric split (train == val == test = same 87 tasks) the seed's test reward is
identical to its val reward by construction, so the splice is exact.
Documented in a `PATCH_NOTE.md` file inside the (gitignored) run dir on the
recording host; the raw broken artifacts remain untouched for audit.

### Iterations

| iter | candidate | parent | val | Δ vs parent | accepted? |
|---|---|---|---|---|---|
| 1 | `cand_0001` | `seed` | **0.357** | **+0.077** | ✓ (paired gate: Δ > 0.2·SE) |
| 2 | `cand_0002` | `cand_0001` | 0.325 | −0.033 | ✗ regressed |
| 3 | `cand_0003` | `cand_0001` | 0.170 | −0.187 | ✗ large regression |

The optimizer converged to `cand_0001`; two follow-up attempts both regressed
and were correctly rejected. Optimizer spend: ~$32 total (well below the $400 cap).

### What the optimizer changed (net delta on task passes)

**8 tasks newly passing under `cand_0001`** (5 non-office + 3 office):
`bike-rebalance`, `energy-ac-optimal-power-flow`, `energy-market-pricing`,
**`exceltable-in-ppt`** (xlsx+pptx), `grid-dispatch-operator`,
`paper-anonymizer`, `paratransit-routing`, **`weighted-gdp-calc`** (xlsx).

**3 tasks regressed from baseline**: `citation-check`,
`crystallographic-wyckoff-position-analysis`, **`pptx-reference-formatting`** (pptx).

Net: **+5 tasks** (23 → 28) on `pass_at_1`. Two of the newly-passing tasks and
one of the regressed tasks are shared-office-skill tasks — the optimizer's edits
to `xlsx`/`pptx` had real cross-task effect.

### Caveats

- **Fit metric, not held-out.** `test == val` by construction; the `test_delta`
  above just re-affirms the val_delta at higher confidence. Not a generalization
  claim.
- **Single trial.** `num_trials: 1` — one draw per task per iteration. The paired
  gate still ran cleanly on the accepted iteration (Δ = +0.077 > 0.007 = 0.2·SE).
- **Not directly comparable to EvoSkills' 71.1%.** Different paradigm (shared
  4-skill package vs per-task skills), different setup (BenchFlow strips each
  task's own bundled skills and mounts ours). This is the same
  shared-skill approach as the baselines above.

---

## SkillsBench — skill-package optimization (held-out, committed)

Artifact: [`examples/skillsbench/run_full/`](../examples/skillsbench/run_full/)
(`report.md`, `final.json`). Reproduce: [`REPRODUCE_skillsbench.md`](REPRODUCE_skillsbench.md).

- **Capability:** the four shared office-document **skill packages** (`docx`/`pptx`/`xlsx`/`pdf`).
- **Agent under test:** `claude-sonnet-4-6` in a Docker sandbox.
- **Optimizer:** `claude-code` @ `claude-opus-4-8`.
- **Tasks / trials:** **7** val tasks (`train == val`) · **3** trials; **3** sealed test tasks.
- **Iterations:** 7 (best `cand_0004`, 4 accepted).

| | reward | Δ |
|---|---|---|
| Baseline — val | **0.333** | — |
| Optimized (`cand_0004`) — val | **0.714** | **+0.381 / +114% relative** |
| Baseline seed skills — sealed test | **0.556** | — |
| Optimized skills — sealed test (held-out) | **0.667** | **+0.111 / +20.0% relative** |

Test was scored once on the sealed split for **both** baseline and optimized skills, so
the improvement is on tasks the optimizer never saw. The optimizer edited all four
`SKILL.md` bodies and added executable scripts, then stopped on a real ceiling
(diagnosing two unsolved tasks as broken oracles rather than overfitting them).

---

*Last reviewed: 2026-07-13.*
