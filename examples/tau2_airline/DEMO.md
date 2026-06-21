# Demo walkthrough — optimizing tau2-bench airline with cap-evolve

A storyboard for a screen-recorded demo. It takes a **brand-new benchmark**
(tau2-bench airline) from a single prompt to an **honest, optimized result**, and
shows where every claim is backed by a committed artifact you can open offline.

**Headline result:** baseline val **0.496 → 0.702** (best candidate `cand_0013`),
**+0.206 (≈ +41% relative)** on all 50 airline tasks × 10 trials. A 10-iteration
finalize scored its best candidate (`cand_0009`) **once** on the sealed split at
**0.676 pass@1**. Metric = mean tau2 task reward in `[0,1]`. This example is
no-holdout (train = val = test = all 50), so **val IS the fit metric**.

> tau2 is just the worked example — cap-evolve optimizes any agent capability
> (prompt, tools, or skill) against any eval. The story below is the airline run.

---

## 0. Before you record — what's committed

Everything the demo shows is checked in under
[`run_full/`](run_full/), so a viewer can see the result **before running anything**:

| Artifact | What it is |
|---|---|
| [`run_full/dashboard.html`](run_full/dashboard.html) | **Self-contained** dashboard — open in any browser, **offline**, no CDN. KPIs, evaluations, per-iteration git diffs, cost/intake panel, lineage, memory. |
| [`run_full/final.json`](run_full/final.json) | The sealed-test result + per-task rewards. |
| [`run_full/demo.cast`](run_full/demo.cast) | asciinema recording of the from-scratch run. |
| [`run_full/TAU2_COMMIT.txt`](run_full/TAU2_COMMIT.txt) | The resolved tau2-bench commit (`5ebebbe…`) for reproducibility. |

```bash
open examples/tau2_airline/run_full/dashboard.html   # the static, offline dashboard
```

---

## Scene 1 — The dashboard (open with the result already in)

Open `run_full/dashboard.html` and walk its pages. This is the "what did we get"
view; it loads instantly because the run is embedded in the file.

1. **Overview / KPIs** — the headline stair: **baseline 0.496 → best 0.702**, the
   accepted-candidate lineage, and the sealed-test KPI. Point out that the curve
   only steps **up** — the significance gate refused every change it couldn't
   distinguish from noise.
2. **Evaluations** — the tasks × iterations heatmap (per-task reward, 50 tasks ×
   10 trials). Call out that improvement is **uneven**: some tasks flip green while
   a few flicker — that flicker is exactly what the paired gate measures.
3. **Iterations + git diffs** — click an accepted iteration (1, 2, 9, 13) and show
   the **actual git diff** for that step. This is the money shot: the optimizer is
   writing **code into the tool bodies**, not just editing prose (see Scene 2).
4. **Cost / intake panel** — per-iteration optimizer + runner cost & time, plus the
   one-time intake cost. Honest note: **RITS is internal/free**, so runner `$` is
   `$0`; the budget governs the Claude optimizer (~\$183 optimizer spend, one-time
   intake ~\$2.8 over the run).
5. **Memory** — the cross-iteration `MEMORY.md`: what was tried, what the gate
   **rejected**, and why — the optimizer's institutional memory (see Scene 3).

---

## Scene 2 — The iterations: the specific changes that helped

Walk the four **accepted** candidates. The throughline: **argument-level feedback**
from failing rollouts is converted into **executable in-code guards** inside the
existing tools. Over the run, `tools.py` grows **593 → 982 lines** and the policy
**166 → 212 lines** — most of the lift is real code, not prompt wording.

### Iteration 1 — `cand_0001` · 0.496 → **0.606** (+0.110)
The single biggest jump. The optimizer diagnosed 8 failure clusters and **converted
5 of 6 rule-violations into in-code guards inside existing tools**:
- `cancel_reservation`: guard rejecting already-cancelled and already-flown reservations.
- `update_reservation_flights`: guards rejecting already-flown flights, basic-economy flight changes, and origin/destination changes (policy says those need cancel+rebook).
- `update_reservation_baggages`: guard rejecting bag **removal**.
- Added a `get_all_reservation_details` **loop tool** to kill the "incomplete enumeration" cluster (agent only checked some reservations).
- Plus 7 new operational policy rules for the **behavioral** clusters code can't enforce (transfer-stall, stating amounts).

### Iteration 2 — `cand_0002` · 0.606 → **0.660** (+0.054)
Tightened **eligibility and authorization** as code:
- `cancel_reservation`: full eligibility guard (24h / business cabin / insurance / airline-cancelled) via a new optional `reason` parameter.
- `send_certificate`: eligibility + **amount** validation guard (membership/insurance/cabin + the \$50/100×passengers formula) — fixes the "unauthorized compensation" and social-engineering clusters.
- `book_reservation`: payment-profile validation + per-type limit guard (≤1 cert, ≤1 CC, ≤3 GC).
- Notably **repaired iter 1's only regression** (task 0: a regular member got an unauthorized certificate) by adding the `send_certificate` guard.

### Iteration 9 — `cand_0009` · 0.660 → **0.680** (+0.020)
By now the eligibility rules are guarded; remaining failures are **redundant writes**
and **selection** errors:
- `update_reservation_flights`: **idempotency** guard (no-op when cabin+flights already match).
- `book_reservation`: baggage free-allowance consistency validation (`nonfree = max(0, total − free)`).
- `update_reservation_passengers`: no-op guard on unchanged data.
- Policy rules 12-16 for behavioral selection (exhaustive search for open-ended destinations, look up past flights, honor cost thresholds, never repeat a successful write).

### Iteration 13 — `cand_0013` · 0.680 → **0.702** (+0.022) · the best
The last accepted step targets **output-contract / knowledge** gaps the gate proved
were the remaining lever:
- Policy rules 17-21: look up reservations immediately when IDs are given; complete **all** doable work in multi-request tasks; state the **exact** dollar figure from the tool's `payment_history` (not re-computed); "smallest balance" = smallest **sufficient** balance; "fastest" = shortest **elapsed** time.
- `book_reservation`: route-validation guard (flights must match origin/destination for the trip type).
- Improved the basic-economy error to spell out the cancel+rebook recipe, and wrapped the payment call to surface the exact price difference.

> **Show the rejected ones too.** 11 of 15 iterations were rejected by the gate.
> Open `run_full/rejected.jsonl` (or the memory page): a recurring lesson is
> "enriching tool **returns** with new computed fields consistently breaks tasks
> 0/39/6" — the optimizer learned to stop doing it.

---

## Scene 3 — Cross-iteration learning (`STATE.md` / `MEMORY.md`)

Open a candidate's handover files to show this isn't blind hill-climbing:

- **`STATE.md` (per candidate)** — the optimizer's scratchpad: failure clusters
  ranked by `#tasks × trials`, a table mapping each cluster to the **exact edit
  class** (in-code guard vs docstring vs policy) and "protects passing" reasoning,
  a **VERIFY-THE-FIX** line per fix (trace → guard fires), and a **Handover**.
  > Show iter 1's line: *"Rule-violations found: 6. Converted to in-code checks: 5."*
- **`MEMORY.md` (cross-iteration)** — what prior iterations tried, and crucially
  **"Approaches that regressed AS IMPLEMENTED"** with the gate's reject reason and
  per-task impact. This is why later iterations stop re-submitting losing ideas
  (enriching returns, insurance-reason gating, transfer-tool guards) and pivot to
  the levers that still have headroom (policy/output-contract rules in iter 13).

This handover is what turns 15 cheap local edits into a **coherent, accreting**
optimization rather than 15 independent guesses.

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
3. **Baseline.** Score the unmodified seed on val → **0.496**.
4. **Optimize.** Each iteration: diagnose val traces into failure clusters → the
   `claude-opus-4-6` optimizer makes **argument-level**, in-code edits (rules →
   guards) under a per-iteration `--max-budget-usd 40` cap → re-evaluate all 10
   trials in one batched pass.
5. **Significance gate.** Paired, val-only (`Δ > k·SE`) — accept or reject; every
   iteration is a git commit.
6. **Sealed test.** The best candidate is scored **exactly once** on the test split
   (`finalize` enforces the seal in code) → here **0.676 pass@1** for the 10-iter
   finalize.
7. **Report.** `report.md` + the self-contained `dashboard.html`.

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
  val — that is the system working, not failing. 11 of 15 iterations were rejected.
