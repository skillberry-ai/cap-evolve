---
name: gate
description: Apply the acceptance decision that keeps optimization honest — always on the val split, by default requiring the improvement to exceed the significance bar (Δ > k·SE) so noise is not mistaken for progress. Use to inspect or reproduce a single accept/reject decision; the algorithms apply it internally every iteration.
component: phase
argument-hint: "--current R --candidate R --mode significant --k-se 1.0"
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
reward beats the current best by **more than `k` standard errors**.

## Inputs / outputs (manifest tokens)
- **needs:** `scores` — the candidate's and current best's val reward *and*
  `stderr` (from `evaluate`). The SE is not optional: significance is meaningless
  without it.
- **provides:** `decision` — `{accept, reason, delta, threshold}`, the audit
  record of why a candidate was kept or rejected.

## The significance rule (default)
```
SE = sqrt(candidate_stderr^2 + current_stderr^2)     # SE of the difference
accept  ⟺  Δ = candidate_val − current_val  >  k · SE
```
This is the standard test for "is the difference real?": the SE of a difference
of two independent means is the root-sum-of-squares of their SEs, and `Δ > k·SE`
asks whether the gap clears `k` standard errors of that difference. `k=1` is
lenient (~1σ); raise it to be stricter. It is the textual-optimization analogue of
Koehn's bootstrap significance test for metric differences — accept only when the
gap is unlikely to be noise.

**Single-trial scores report `stderr=0`, collapsing `k·SE` to 0** — then
`significant` silently degrades to `strict` and accepts any positive blip. If you
run the significance gate, score with multiple trials (see `evaluate`).

## Modes
- `significant` (default): `Δ > k·SE` — variance-aware, the honest choice.
- `strict`: `Δ > 0` — any improvement. Only safe with a near-zero-variance scorer
  (deterministic, single correct answer).
- `threshold`: `Δ > T` — a flat margin (use when you have a domain minimum
  worthwhile gain, e.g. "don't bother unless +2pp").
- `simplicity_tiebreak`: like strict, but on a (near-)tie prefer the smaller
  candidate — an Occam bias against bloated edits that don't earn their size.

## No-regression (the second gate)
A mean can rise while previously-passing tasks silently break. Pair the
significance gate with a **no-regression** check: reject a candidate that improves
the aggregate but *drops* any task that the current best passed. This is the same
dual-gate discipline SWE-bench-style harnesses use (a patch must pass the new
tests **and** not break the existing ones — FAIL_TO_PASS *and* PASS_TO_PASS).
`diagnose` provides `kept_good` (the currently-passing tasks) precisely so this
check has something to protect.

## How to run
```
python scripts/run.py --current 0.50 --candidate 0.62 \
    --mode significant --k-se 1.0 --candidate-stderr 0.03 --current-stderr 0.03
```
Algorithms call the gate internally every iteration via the harness; this skill
exists so a human or agent can reproduce and *understand* a single decision.

## What good vs bad looks like
- **Good:** `significant` mode with real multi-trial SEs; a no-regression check on
  top; every accept/reject logged with its `reason`.
- **Bad:** gating on `train` (the tool refuses this — it overfits the optimizer to
  the data it edits against); `strict` mode on a noisy agent (accepts noise);
  raising the mean while quietly regressing tasks because no-regression was off.

## References
- `references/concepts.md` — the difference-of-means SE, choosing `k`, the
  multiple-comparisons motivation, the dual-gate / no-regression rationale, and
  why gating on val (never train, never test) is the honest split, with sources.
