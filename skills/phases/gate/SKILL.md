---
name: gate
description: Apply the acceptance decision that keeps optimization honest — always on the val split, by default (mode paired) requiring the mean per-task improvement to exceed the significance bar (Δ > k·SE) so noise is not mistaken for progress. Use to inspect or reproduce a single accept/reject decision; the algorithms apply it internally every iteration.
component: phase
argument-hint: "--current R --candidate R --mode paired --k-se 1.0 --paired-deltas 1,0,0"
allowed-tools: Bash
provides: [decision]
needs: [scores]
sources: []
---

# gate — accept only real improvements, on val

The gate is where dishonest optimization is prevented. Search is a noise
amplifier: try enough candidates and some will *look* better by chance alone
(the more candidates you screen, the larger the expected best-of-noise). The gate
is the rule that keeps a lucky draw from being promoted to "the new best". It
refuses any split but `val`, and by default accepts a candidate only when its val
reward beats the current best by **more than `k` standard errors**. The default mode
in a real run is **`paired`** — the per-task paired test over the same val tasks.

## Inputs / outputs (manifest tokens)
- **needs:** `scores` — the candidate's and current best's val reward *and*
  `stderr` (from `evaluate`). The SE is not optional: significance is meaningless
  without it.
- **provides:** `decision` — `{accept, reason, delta, threshold}`, the audit
  record of why a candidate was kept or rejected.

## The significance rule
```
# paired (the default in a real run) — candidate & current on the SAME val tasks
Δ[t] = cand_reward[t] − curr_reward[t]
accept  ⟺  mean(Δ)  >  k · SE(Δ)

# significant — the two means treated as INDEPENDENT samples
SE = sqrt(candidate_stderr^2 + current_stderr^2)     # SE of the difference
accept  ⟺  Δ = candidate_val − current_val  >  k · SE
```
Both ask "is the difference real?", but pairing is the stronger form: because the
same tasks are scored on both sides, the cross-task variance cancels and only the
paired variance counts. The unpaired version root-sum-squares the two SEs, which is
correct only when the two sides were not scored on the same tasks. `k=1` is lenient
(~1σ); raise it to be stricter. This is the textual-optimization analogue of Koehn's
bootstrap significance test for metric differences — accept only when the gap is
unlikely to be noise.

**When the SE collapses to 0** (`paired` with `n=1` or every task moving
identically; `significant` with single-trial `stderr=0`), the gate does **not**
silently act strict: it logs a `gate_warning` event and applies a documented strict
fallback (`Δ > 0`), with `SE=0 → STRICT fallback, warned` in the decision `reason`.
Score with multiple trials (see `evaluate`) so the bar is real. `paired` falling back
to `significant` (no per-task deltas) is announced the same way, prefixed
`paired→significant (no per-task deltas):`.

> **`gate_warning` events cannot be logged from this standalone script** — `run.py`
> takes no `--run-dir`, so `decide(run_dir=...)` is always `None` here and the JSON
> `reason` is the only channel for either fallback. In a real run the harness passes
> the run dir, so the events land in the run log. Don't hunt for a `gate_warning`
> after a standalone invocation; read the `reason`.

## Modes
Set via `gate_mode` in `capevolve.yaml` (`--mode` here); strictness via `gate_k_se`.

- `paired` (**the default in every real run**): `mean(per-task Δ) > k·SE(Δ)` over the
  SAME val tasks — the most powerful test. The harness builds the deltas and selects
  this mode itself whenever per-task val data aligns; that is what the algorithms'
  `--gate-mode auto` means. Its SE comes from the spread *between* tasks' deltas, so
  it is non-zero even at `num_trials=1` — a bar `significant` cannot even form there.
  **The `k_se=1.0` rule:** improving exactly one of `n` tasks gives `mean(Δ) = SE(Δ)`
  *exactly*, so the strict `>` rejects it — at every `n`, and no matter how large that
  one gain is. **Improve ≥2 tasks at `k_se=1.0`, or bank nothing** (`gate_k_se: 0.2`,
  as the examples use, banks a 1-of-n gain).
- `significant`: the independent-samples form above. Weaker than `paired`. It is the
  default of this standalone script (and of `gate.decide`'s `mode=` parameter) only
  because a caller with two means and two SEs has no per-task data to pair; `paired`
  falls back to it when no deltas are supplied.
- `strict`: `Δ > 0` — any improvement. Only safe with a near-zero-variance scorer
  (deterministic, single correct answer).
- `threshold`: `Δ > T` — a flat margin (use when you have a domain minimum
  worthwhile gain, e.g. "don't bother unless +2pp"). `T` defaults to `0.0`, so
  `--mode threshold` without `--threshold` is exactly `strict`.
- `simplicity_tiebreak`: like strict, but on a (near-)tie (`abs(Δ) ≤ 1e-9`) prefer
  the smaller candidate — an Occam bias against bloated edits that don't earn their
  size. ⚠️ **It requires `candidate_size`/`current_size`, and nothing in the harness
  or the algorithms supplies them, so in a real run it is bit-identical to `strict`**
  ([#206](https://github.com/skillberry-ai/cap-evolve/issues/206) tracks plumbing
  the sizes). Only `core/tests/test_core.py` exercises the tiebreak branch.

Full table and the small-sample caveat:
[`docs/HONEST_EVAL.md` § Gate modes](../../../docs/HONEST_EVAL.md#gate-modes).

## No-regression (the second gate)
A mean can rise while previously-passing tasks silently break. Pair the
significance gate with a **no-regression** check: reject a candidate that improves
the aggregate but *drops* any task that the current best passed. This is the same
dual-gate discipline SWE-bench-style harnesses use (a patch must pass the new
tests **and** not break the existing ones — FAIL_TO_PASS *and* PASS_TO_PASS).
`diagnose` provides `kept_good` (the currently-passing tasks) precisely so this
check has something to protect.

## Dual-mode
This phase runs two ways from the **same** SKILL.md: standalone as the slash command `/cap-evolve:gate` (the `argument-hint` shows its run.py args), and orchestrator-callable — `cap-evolve run` / the `orchestrate` skill invokes the same `scripts/run.py` headlessly and threads the run dir between phases.

## How to run
```
# unpaired (two means + two SEs)
python scripts/run.py --current 0.50 --candidate 0.62 \
    --mode significant --k-se 1.0 --candidate-stderr 0.03 --current-stderr 0.03

# reproduce the paired decision a real run makes (per-task cand-curr deltas)
python scripts/run.py --current 0.50 --candidate 0.60 \
    --mode paired --k-se 0.2 --paired-deltas 1,0,0,0,0,0,0,0,0,0
```
Algorithms call the gate internally every iteration via the harness; this skill
exists so a human or agent can reproduce and *understand* a single decision.

## What good vs bad looks like
- **Good:** `paired` (or `significant`) mode with real per-task/multi-trial SEs; a
  no-regression check on top; every accept/reject logged with its `reason`.
- **Bad:** gating on `train` (the tool refuses this — it overfits the optimizer to
  the data it edits against); `strict` mode on a noisy agent (accepts noise);
  raising the mean while quietly regressing tasks because no-regression was off.

## References
- `references/concepts.md` — the difference-of-means SE, choosing `k`, the
  multiple-comparisons motivation, the dual-gate / no-regression rationale, and
  why gating on val (never train, never test) is the honest split, with sources.
