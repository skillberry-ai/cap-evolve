---
name: report
description: Summarize a run for a human — baseline val → best val → sealed test, the winning candidate, iterations spent, and pass^k. Use after finalize. Writes report.md and prints a compact JSON summary; the source of truth for "did this optimization actually work, and by how much".
component: phase
argument-hint: "--run-dir DIR"
allowed-tools: Read, Write, Bash
provides: [report]
needs: []
sources: [evo]
---

# report — did it work, and by how much?

The result of an optimization run is not "we made edits" — it is a defensible
answer to *did this actually work, and by how much.* report reads the run dir's
`baseline.json` and `final.json` and lays them side by side: where the seed
started (val), where the best candidate landed (val), and the single **held-out
test** number that actually counts. It is the source of truth a human reads to
decide whether to ship the optimized capability.

## Inputs / outputs (manifest tokens)
- **needs:** *(reads the run dir directly — baseline.json / final.json / events)*.
- **provides:** `report` — `report.md`, a compact JSON summary, and (by default) a
  single-file `dashboard.html`.

## How to read the three numbers
The honest reading is always **test vs baseline**, with val as a sanity check in
between:

- **test ≈ baseline** → no real gain. The val improvement was overfitting or
  noise the gate let through. Do not ship; tighten `gate_k_se` or add trials.
- **test ≫ baseline** → genuine improvement on data the optimizer never saw. Ship.
- **val ≫ test** → the classic overfit signature: the optimizer learned the val
  set, not the capability. The gap *is* the overfitting, quantified.
- **wide pass^k drop vs pass^1** → the gain is *fragile* across trials — the agent
  sometimes succeeds but not reliably. A high mean with low pass^k is not a
  dependable win (τ-bench's point).

Always report the **test stderr / CI**, not just the point: "0.71" and
"0.71 ± 0.08" support very different decisions.

## How to run
```
python scripts/run.py --run-dir .agentcapo/run_XXXX
```
Writes `report.md` and a single-file **`dashboard.html`** next to the run state
(open it by double-clicking — it inlines the run data and loads ECharts from a
CDN, so it works offline from a `file://` URL). The dashboard shows KPI cards, a
baseline→val→test bar, score-over-iterations, a per-task reward heatmap, an
accept/reject timeline, a frontier scatter, and a candidate leaderboard. Pass
`--no-dashboard` to skip it.

## What good vs bad looks like
- **Good:** test reported with its uncertainty and pass^k; the baseline→val→test
  story told honestly, including a no-gain or overfit result when that is what
  happened; a no-holdout run clearly labelled as a fit metric.
- **Bad:** reporting val as if it were the result; a bare point estimate with no
  variance; spinning a `val ≫ test` overfit as success.

## References
- `references/concepts.md` — reading baseline/val/test honestly, the val-test gap
  as overfitting, pass^k fragility, and reporting uncertainty, with sources.
