---
name: report
description: Summarize a run for a human — baseline val → best val → sealed test, the winning candidate, iterations spent, and pass^k. Use after finalize. Writes report.md and prints a compact JSON summary; the source of truth for "did this optimization actually work, and by how much".
component: phase
argument-hint: "--run-dir DIR [--terminal] [--no-dashboard]"
allowed-tools: Read, Write, Bash
provides: [report]
needs: []
sources: [evo]
---

# report — did it work, and by how much?

The result of a run is not "we made edits" — it is a defensible answer to *did this
actually work, and by how much.* report lays three numbers side by side: where the
seed started (val), where the best candidate landed (val), and the single **held-out
test** number that counts. It is what a human reads to decide whether to ship.

Runs standalone as `/cap-evolve:report`, or headlessly as the last step of
`cap-evolve run` — same `scripts/run.py` either way. There is no `cap-evolve report`
subcommand; invoke the script.

## How to read the three numbers
The honest reading is always **test vs baseline**, with val as a sanity check in
between. `scripts/run.py` produces the numbers; this is the judgment you add on top:

- **test ≈ baseline** → no real gain. The val improvement was overfitting or noise
  the gate let through. Do not ship; tighten `gate_k_se` or add trials.
- **test ≫ baseline** → genuine improvement on data the optimizer never saw. Ship.
- **val ≫ test** → the classic overfit signature: the optimizer learned the val set,
  not the capability. The reported val→test gap *is* the overfitting, quantified.
- **pass^k far below pass^1** → the gain is *fragile* across trials; the agent
  sometimes succeeds but not reliably. A high mean with low pass^k is not a
  dependable win (τ-bench's point).

Every number is rendered with its stderr when one was measured, because "0.71" and
"0.71 ± 0.08" support very different decisions. A gain smaller than the noise floor
is not a result — say so plainly rather than quoting the point estimate alone.

## Output contract
`scripts/run.py` owns both artifacts and writes them deterministically from the run
dir — do not hand-write or paraphrase them, or two runs stop being comparable.

`report.md` is exactly this skeleton (bracketed lines appear only when they apply):

```
# cap-evolve run report — <run_id>

[> **NOT FINALIZED** — no held-out test number. Run the finalize phase first; …]
[> **No holdout** (train == val == test). The test number below is a *fit* metric, …]

- Best candidate: `<best_id>`
- Baseline val: <r> ± <se>
- Best val: <r> ± <se>
- **Held-out test (optimized skills): <r> ± <se>**  (pass^1=…, pass^k=…)
[- Held-out test (baseline `<baseline_id>` skills): <r> ± <se>]
[- **Test improvement (optimized − baseline): <+Δ>**]
[- Val→test gap: <+Δ> — selection optimism on val; this gap IS the overfitting]
- Iterations: <n>
[- Optimized for: <consuming model> (tier <t>)]

[<sealed note — omitted entirely when the run was never finalized>]
```

stdout is **exactly one** JSON object — `cap-evolve run` echoes it as its own result, so
it is the machine contract for everything downstream. Keys (null for whatever the run
dir does not carry; an unfinalized run is `finalized: false` with null test numbers):
`run_dir`, `best_id`, `finalized` bool, `no_holdout` bool, `baseline_val`,
`baseline_val_stderr`, `best_val`, `test_reward`, `test_stderr`,
`test_baseline_reward`, `test_baseline_stderr`, `test_delta`, `test_pass_k` (k→float),
`val_test_gap`, `iterations`, `target_profile` (`{model,tier,resolution_note}`), plus
`dashboard` / `dashboard_server` / `*_error` on the paths that produce them.

## How to run
```
python scripts/run.py --run-dir .capevolve/run_XXXX            # JSON + report.md + dashboard.html
python scripts/run.py --run-dir .capevolve/run_XXXX --terminal # colored in-chat ANSI report
python scripts/run.py --run-dir .capevolve/run_XXXX --no-dashboard
```
`--dashboard-mode` / `--dashboard-port` / `--dashboard-url` are orchestrator-supplied.
Re-reporting by hand after `cap-evolve run` needs `--dashboard-url <the URL run printed>`
or `--no-dashboard` — launching is deliberately not idempotent, so a bare re-run spawns
a second server on a second port and reports that one instead.

## The dashboard (`dashboard.html`)
One self-contained static file (inline CSS/JS/SVG, no CDN, no server, no network — opens
from `file://`); the single shareable artifact. Eight panels reduced from the event log
plus baseline/final, rollouts and the git store; every value passes a recursive secret
redactor so a shared dashboard leaks no API keys; optional panels degrade silently when
per-task data, diffs, or finalize are missing. `--terminal` renders the same reduction
as an ANSI chart for in-chat progress.

## References
- `references/concepts.md` — why the val→test gap measures overfitting, pass^k
  fragility, reporting uncertainty, with sources. Load when writing the human
  interpretation and you want the reasoning or a citation.
- `references/dashboard.md` — the reduced graph + summary schema, per-panel field
  sources, `--terminal`, redaction, degradation matrix. Load when changing or
  debugging the dashboard; not needed to run the phase.
