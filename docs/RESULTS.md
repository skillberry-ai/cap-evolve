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

## τ²-Bench airline — held-out 30/10/10 run

Same benchmark and capability, run with a real holdout split (`split_ids.json`,
30 train / 10 val / 10 test) so the test number is a genuine generalization result.

| split | baseline | optimized | Δ |
|---|---|---|---|
| **val** (10 tasks) | **56.7** | **70.0** | **+13.3 pp / +23.5% relative** |
| **sealed test** (10 tasks, scored once) | **30.0** | **47.5** | **+17.5 pp / +58.3% relative** |

> The held-out `run_full` artifact for this run is committed separately. Until it lands,
> treat these figures as the reported held-out result; the reproducible artifact-backed
> run above is the no-holdout fit metric.

See [`COMPARISON.md`](COMPARISON.md) for how this **+58.3% within-run relative** held-out
gain sits next to external tool-optimization work (EvoTool, Evolutionary Context Search)
— with the important caveat that those use different benchmark versions, models, splits,
and budgets and are **not** an apples-to-apples comparison.

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
