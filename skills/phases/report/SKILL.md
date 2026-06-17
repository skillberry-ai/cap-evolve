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
- **needs:** *(reads the run dir directly — baseline.json / final.json / events /
  per-task rollouts / git store)*.
- **provides:** `report` — `report.md`, a compact JSON summary, a self-contained
  `dashboard.html`, and an on-demand ANSI terminal report.

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

## Dual-mode
This phase runs two ways from the **same** SKILL.md: standalone as the slash command `/cap-evolve:report` (the `argument-hint` shows its run.py args), and orchestrator-callable — `cap-evolve run` / the `orchestrate` skill invokes the same `scripts/run.py` headlessly and threads the run dir between phases.

## How to run
```
python scripts/run.py --run-dir .capevolve/run_XXXX            # JSON summary + report.md + dashboard.html
python scripts/run.py --run-dir .capevolve/run_XXXX --terminal # colored in-chat ANSI report (no browser)
python scripts/run.py --run-dir .capevolve/run_XXXX --no-dashboard
```

### The dashboard (`dashboard.html`)
A **fully self-contained** static file — inline CSS + vanilla JS + inline SVG, **no
CDN, no server, no network**. It is the single shareable artifact; open it by
double-clicking (works from `file://`). The builder first **reduces** the event log
(plus baseline/final, per-task rollouts, and the git store) into a candidate **graph
+ run-summary**, then renders eight panels:

1. **KPI strip** — best / baseline / %Δ-vs-baseline (abs Δ off a zero baseline),
   counts by status (accepted/rejected/failed/seed), frontier, sealed test, wall
   clock, cost split **optimizer vs runner**, tokens.
2. **Cumulative-best stair** over a per-iteration scatter — running-best step
   polyline, champion star, record-holder rings, hover tooltip (id/status/val/Δ).
3. **tasks×iterations pass/fail heatmap** — rows sorted worst-first; reveals
   regressions, persistent failures, and per-task specialists the mean hides; click
   a cell for that task's feedback.
4. **Diff vs parent** — prompt/skill/tools diff of a candidate against its parent
   (split/unified toggle), computed from the candidate dirs.
5. **Lineage tree** — parent→child DAG (merges = multi-parent), best-lineage spine
   highlighted.
6. **Cost / tokens / latency** — per-iteration + cumulative, split optimizer vs
   runner, plus a cumulative-cost-vs-best-score plot.
7. **Annotations & diagnoses** — gate reasons + diagnose/optimizer-error output.
8. **Candidate leaderboard** + the git iteration-store log.

All values pass through a recursive **secret redactor** first, so a shared dashboard
never leaks `RITS_API_KEY` / `BOBSHELL_API_KEY` / `WATSONX_*` etc. Optional panels
**degrade silently** when per-task data, diffs, or finalize are missing.

### The terminal report (`--terminal` / `--ansi`)
A colored cumulative-best chart + one-line KPI strip + top-N candidate table for
in-chat progress without opening the browser. Sized to the terminal width and
**CLAUDECODE-margin-aware** (subtracts ~6 cols when `CLAUDECODE=1` so it doesn't wrap
inside the tool-output frame). `--no-color` / `NO_COLOR=1` for plain text;
`--top-n N` sets the table size.

## What good vs bad looks like
- **Good:** test reported with its uncertainty and pass^k; the baseline→val→test
  story told honestly, including a no-gain or overfit result when that is what
  happened; a no-holdout run clearly labelled as a fit metric.
- **Bad:** reporting val as if it were the result; a bare point estimate with no
  variance; spinning a `val ≫ test` overfit as success.

## References
- `references/concepts.md` — reading baseline/val/test honestly, the val-test gap
  as overfitting, pass^k fragility, and reporting uncertainty, with sources.
- `references/dashboard.md` — the reduced graph + summary schema, what each of the
  eight panels reads from, the `--terminal`/`--ansi` mode, secret redaction, and the
  graceful-degradation rules.
