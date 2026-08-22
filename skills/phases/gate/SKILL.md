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

## The significance rule
```
paired (the default):   accept ⟺ mean(Δ[t]) > k · SE(Δ)     over the SAME val tasks
significant (fallback): accept ⟺ Δ = cand − curr > k · sqrt(cand_se² + curr_se²)
```
The bar is `Δ > k·SE` and **not `Δ > 0`** because search is a noise amplifier:
screen enough candidates and the best-looking one is best by *luck*, so `Δ > 0`
banks noise as progress and the val curve climbs while nothing improved. Clearing
`k` standard errors of the measurement's own error is what makes an accept mean
something — turn this down and the run's numbers stop being evidence. `k=1` is
lenient (~1σ); raise it to be stricter. It is the textual-optimization analogue of
Koehn's bootstrap significance test for metric differences.

`paired` is stronger because both sides were scored on the *same* val tasks, so
per-task difficulty cancels and only the paired variance counts; `significant`
treats the two means as independent samples and is only correct when they are.

**Single-trial scores report `stderr=0`, collapsing `k·SE` to 0** — then
`significant` silently degrades to `strict` and accepts any positive blip. If you
run the significance gate, score with multiple trials (see `evaluate`).

## Modes
- `paired` (**the default**): `mean(per-task Δ) > k·SE(Δ)`. The loop selects it
  whenever per-task val data exists (`harness.py:1524-1526`, `gepa.py:741-743`)
  and `capevolve.yaml` ships `gate_mode: paired`.
- `significant`: `Δ > k·SE_combined` — the **unpaired fallback**, used when the two
  sides aren't aligned per task. `decide()`'s own `mode=` parameter defaults here
  for bare callers with no per-task data; that is not the default of a real run.
- `threshold`: `Δ > T` — a flat margin (use when you have a domain minimum
  worthwhile gain, e.g. "don't bother unless +2pp").
- `strict`: `Δ > 0` — any improvement. Only safe with a near-zero-variance scorer
  (deterministic, single correct answer).

Anything else raises. There is no simplicity/size mode: it was unreachable dead
code (nothing ever supplied a size) so it silently behaved as `strict`, and it has
been removed rather than documented.

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
python scripts/run.py --current 0.50 --candidate 0.62 \
    --mode significant --k-se 1.0 --candidate-stderr 0.03 --current-stderr 0.03
```
Algorithms call the gate internally every iteration via the harness; this skill
exists so a human or agent can reproduce and *understand* a single decision.

## What good vs bad looks like
- **Good:** `paired` mode (the default) with real multi-trial SEs; a no-regression check on
  top; every accept/reject logged with its `reason`.
- **Bad:** gating on `train` (the tool refuses this — it overfits the optimizer to
  the data it edits against); `strict` mode on a noisy agent (accepts noise);
  raising the mean while quietly regressing tasks because no-regression was off.

## References
- `references/concepts.md` — the difference-of-means SE, choosing `k`, the
  multiple-comparisons motivation, the dual-gate / no-regression rationale, and
  why gating on val (never train, never test) is the honest split, with sources.
