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

## τ²-Bench airline — `agent-optimize` with subset screening, disjoint 26/12/12 — **null result**

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
   *Recording gap found while auditing this:* `screens/*.json` persists `regressed` but leaves
   `fixed: null`, so a screen's positive signal is not auditable from the artifact — the
   false positive above had to be inferred from `mean_delta` and `regressed`.
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
