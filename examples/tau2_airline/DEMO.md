# Demo walkthrough — optimizing tau2-bench airline with cap-evolve

A storyboard for a screen-recorded demo. It takes a **brand-new benchmark**
(tau2-bench airline) from a single prompt to an **honest, optimized result**, and
shows where every claim is backed by a committed artifact you can open offline.

**Headline result:** baseline val **0.536 → 0.712** (best candidate `cand_0007`),
**+0.176 (≈ +33% relative)** on all 50 airline tasks × 10 trials. The `finalize`
step scored that best candidate **once** on the sealed split at **0.694 pass@1**
(pass^2 0.584). Metric = mean tau2 task reward in `[0,1]`. This example is
no-holdout (train = val = test = all 50), so **val IS the fit metric**.

> tau2 is just the worked example — cap-evolve optimizes any agent capability
> (prompt, tools, or skill) against any eval. The story below is the airline run.

---

## 0. Before you record — what's committed

Everything the demo shows is checked in under
[`run_full/`](run_full/), so a viewer can see the result **before running anything**:

| Artifact | What it is |
|---|---|
| [`run_full/ui/`](run_full/ui/) | The **full interactive dashboard** (all 10 iterations, no backend needed) — a static React UI export. Serve with `python3 -m http.server 8000` in that dir, or host on GitHub Pages / any static host. KPIs, evaluations, per-iteration git diffs, cost/intake panel, lineage, memory. |
| [`run_full/final.json`](run_full/final.json) | The sealed-test result + per-task rewards. |
| [`run_full/demo.cast`](run_full/demo.cast) | asciinema recording of a from-scratch run. |
| [`run_full/TAU2_COMMIT.txt`](run_full/TAU2_COMMIT.txt) | The resolved tau2-bench commit (`8ebb749…`) for reproducibility. |

```bash
cd examples/tau2_airline/run_full/ui && python3 -m http.server 8000
# then open http://localhost:8000 — the full interactive dashboard (all 10 iterations,
# no backend needed). Also hostable on GitHub Pages / any static host.
```

---

## Scene 1 — The dashboard (open with the result already in)

Serve `run_full/ui/` (`python3 -m http.server 8000` in that dir, then open
http://localhost:8000 — or host it on GitHub Pages / any static host) and walk its
pages. This is the full interactive dashboard (all 10 iterations, no backend needed) —
the "what did we get" view.

1. **Overview / KPIs** — the headline stair: **baseline 0.536 → best 0.712**, the
   accepted-candidate lineage, and the sealed-test KPI. Point out that the curve
   only steps **up** — the paired significance gate refused every change it couldn't
   distinguish from noise.
2. **Evaluations** — the tasks × iterations heatmap (per-task reward, 50 tasks ×
   10 trials). Call out that improvement is **uneven**: some tasks flip green while
   a few flicker — that flicker is exactly what the paired gate measures.
3. **Iterations + git diffs** — click an accepted iteration (1, 3, 5, 6, 7) and show
   the **actual git diff** for that step. This is the money shot: the optimizer is
   writing **code into the tool bodies**, not just editing prose (see Scene 2).
4. **Cost / intake panel** — per-iteration optimizer + runner cost & time, plus the
   one-time intake cost. Honest note: **RITS is internal/free**, so runner `$` is
   `$0`; the budget governs the Claude optimizer (~\$148 optimizer spend over the run,
   per-iteration capped at `--max-budget-usd 40`).
5. **Memory** — the cross-iteration `JOURNAL.md`: each iteration's intent plus the
   framework's objective **RESULT** line (what the gate accepted/rejected, and the
   exact tasks it broke/fixed) — the optimizer's institutional memory (see Scene 3).

---

## Scene 2 — The iterations: the specific changes that helped

Walk the five **accepted** candidates. The throughline: **argument-level feedback**
from failing rollouts is converted into **executable in-code guards** inside the
existing tools, with prose reserved for genuine knowledge gaps. Over the run
`tools.py` grows **593 → 832 lines** and the policy **166 → 233 lines** — most of the
lift is real code, not prompt wording.

- **Iteration 1 — `cand_0001` · 0.536 → 0.582 (+0.046).** The optimizer diagnosed
  several clusters and shipped a broad batch: in-body guards on `cancel_reservation`
  (already-cancelled / already-flown), `update_reservation_flights` (basic-economy
  changes, origin preservation), and `update_reservation_baggages` (no reductions),
  plus an enriched `get_user_details` return and policy rules for the behavioral
  clusters.
- **Iteration 3 — `cand_0003` · 0.582 → 0.634 (+0.052).** Recovered after a rejected
  iteration 2 (see Scene 3) — added the `get_all_reservation_details` **loop tool**
  that fixed the "incomplete enumeration" cluster (tasks 1, 2, …) and re-applied only
  the safe edits from the rejected batch.
- **Iteration 5 — `cand_0005` · 0.634 → 0.670 (+0.036).** A clean step that **broke
  nothing** — eligibility/state guards that fixed tasks 0, 13, 41, 49.
- **Iteration 6 — `cand_0006` · 0.670 → 0.684 (+0.014).** The **travel-certificate
  count guard** in `book_reservation` (≤1 certificate) and related payment validation.
- **Iteration 7 — `cand_0007` · 0.684 → 0.712 (+0.028) · the best.** The largest
  cluster fixed in one step: a `max_charge` budget guard on
  `update_reservation_flights`, and the output-contract rule to **state the exact
  figure from `payment_history`** instead of hand-computing it.

> **Five concrete before→after edits, each verified in the trajectories** (what the
> agent did on a failing rollout vs the passing one), are written up in
> [`docs/OPTIMIZATION_EXAMPLES.md`](../../docs/OPTIMIZATION_EXAMPLES.md) — the
> certificate guard, the budget-cap validation, the enumeration loop tool, the
> "don't ask for data you can look up" knowledge rule, and the exact-figure output
> contract.

> **Show the rejected ones too.** 5 of the 10 iterations were rejected by the gate
> (iters 2, 4, 8, 9, 10). Open the **Memory** page / `JOURNAL.md`: each rejected
> iteration's RESULT line names the exact tasks it broke, and the next iteration
> drops just those edits (see Scene 3) — a failed attempt becomes a recorded lesson.

---

## Scene 3 — Cross-iteration learning (`JOURNAL` / `LEDGER` / `PROCESS` / `RUNMAP`)

Open a candidate's handover files to show this isn't blind hill-climbing. The state
between iterations has clean ownership:

- **`LEDGER.md` (framework, read-only)** — the objective table: per iteration, the
  outcome and the **exact tasks broken/fixed** vs its parent. Facts only.
- **`JOURNAL.md` (optimizer, append-only)** — each iteration appends its **intent**
  (the edits it made + the expected effect); directly below, the framework stamps an
  objective **RESULT** line. The optimizer cannot know its own gate result while
  writing — so it reads the *prior* RESULT lines to learn what actually worked.
- **`PROCESS.md` (per candidate)** — the explainability scratchpad: failure clusters
  ranked, each mapped to an edit class + "protects passing" reasoning, and a verify
  line per fix.
- **`RUNMAP.md` + `prior_iterations/<id>/`** — every prior iteration's PROCESS.md +
  the exact `diff.patch` (accepted **and** rejected), so the optimizer builds on what
  worked and avoids repeating what regressed.

The money moment: after **iteration 2 was rejected**, iteration 3's JOURNAL entry
reads —

> *"cand_0002 REJECTED (broke={13,34,43}): I re-introduced [the safe edits]… I did NOT
> re-introduce: the cancel_reservation in-body guard or the 'ENFORCES' docstring
> change (caused the regression on 13/34/43)."*

— it kept the safe edits, **dropped the one regressing edit**, and logged it as
refuted so no later iteration repeats it. That is what turns 10 cheap local edits into
a **coherent, accreting** optimization rather than 10 independent guesses.

---

## Scene 4 — The process, end to end

Tie it together (mirrors the asciinema cast and `docs/REPRODUCE_tau2.md`):

1. **Intake builds the integration.** From one prompt, intake clones + `pip install -e`
   tau2-bench (recording the commit), scaffolds `.capevolve/project`, and wires the
   adapter (`run_batch` → tau2's runner, batched `run_trials` fast path,
   `trajectories()` = native tau2 traces, `score()` reads `reward_info`), the RITS
   shim, and the editable seed capability (`policy/` + `tools/`).
2. **Hard gate.** `cap-evolve check` must return `{"ok": true}` — verifies the
   adapter contract and that `score()` is deterministic — **before any \$ is spent**.
3. **Baseline.** Score the unmodified seed on val → **0.536**.
4. **Optimize.** Each iteration: diagnose val traces into failure clusters → the
   `claude-opus-4-6` optimizer reads each capability skill's menu of change types and
   makes **many** argument-level, in-code edits (rules → guards) across both `policy.md`
   and `tools.py`, under a per-iteration `--max-budget-usd 40` cap → re-evaluate all 10
   trials in one batched pass.
5. **Significance gate.** Paired, val-only (`Δ > k·SE`) — accept or reject; every
   iteration is a git commit, and the framework stamps the JOURNAL RESULT line.
6. **Sealed test.** The best candidate (`cand_0007`) is scored **exactly once** on the
   test split (`finalize` enforces the seal in code) → **0.694 pass@1**.
7. **Report.** `report.md` + the self-contained dashboard.

---

## The two commands a viewer runs

```bash
# 0. clone the repo; put RITS creds in repo-root .env (RITS_API_KEY, RITS_API_URL);
#    be logged into Claude Code (or export ANTHROPIC_API_KEY) for the optimizer.

bash examples/tau2_airline/setup.sh    # intake onboarding: install cap-evolve, clone/install
                                       # tau2-bench, scaffold + wire adapter/RITS/seed, then
                                       # cap-evolve check (the hard gate)
bash examples/tau2_airline/run.sh      # full run: 50 tasks · 10 trials · live dashboard
```

These two commands are simply the executable transcript of pasting
[`PROMPT.md`](PROMPT.md) to a coding agent and saying *"follow [`RUN.md`](../../RUN.md)."*
Reproduce from zero: [`docs/REPRODUCE_tau2.md`](../../docs/REPRODUCE_tau2.md).

## Replay the recording

```bash
asciinema play examples/tau2_airline/run_full/demo.cast    # replay in a terminal
agg examples/tau2_airline/run_full/demo.cast demo.gif      # render to GIF for the video
```

## Honest-results footnotes (say these on camera)

- **No-holdout** (train = val = test = all 50): val **is** the fit metric and the
  sealed-test number is reported as a fit metric (the engine logs a
  `splits_warning`). For a held-out result, pin a 30/10/10 split via `split_ids.json`.
- **RITS is internal/free** → runner `$` is honestly `$0`; the budget governs the
  Claude optimizer, and the per-iteration cap is enforced by the Claude CLI itself
  (`--max-budget-usd`).
- The gate **correctly refuses** gains it can't distinguish from noise on a small
  val — that is the system working, not failing. 5 of the 10 iterations were rejected,
  and each rejection became a recorded lesson the next iteration built on.
