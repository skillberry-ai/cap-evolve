# Warm-start seed — provenance

**This is NOT a hand-authored capability.** Every word of `prompt.md` and `task_template.md` in
this directory was written by the optimizer during a real run. Nothing here was added by a human,
which is what makes using it a *warm start* rather than hand-supplying the answer.

| field | value |
|---|---|
| source run | [30890657732](https://github.com/skillberry-ai/cap-evolve/actions/runs/30890657732) (`pilot`, spreadsheetbench) |
| candidate | `cand_0002` — the accepted champion |
| val reward (hard, 50 tasks) | **0.580** (seed that run scored 0.520) |
| adapter sha | `7e3b7f9d` (PR #291 — target size, graded copies, data extent) |
| agent / optimizer | `azure/gpt-5.5` / Claude Code `claude-opus-4-8` |

## Why this exists

Learning was **not cumulative across runs**. Every run started from the pristine
`seed_capability/`, so each one explored a different subset of rules and forgot the rest.
Measured across the two pilots' champions:

| rule token | 30799393875 `cand_0001` | 30890657732 `cand_0002` |
|---|---|---|
| `_xlfn` | 4 | **0** |
| `TEXTJOIN` | 3 | **0** |
| `volatile` | 3 | **0** |

Pilot 1 learned "spill/volatile functions do not survive LibreOffice recalculation — write the
literal value" and fixed tasks `47741` and `51958` with it. Pilot 2 never rediscovered it and
both regressed to failing. That is 2 tasks (0.04 val) lost purely to forgetting, and it means
some of what looked like run-to-run noise was lost knowledge rather than variance.

## Honesty rules for using this

**A warm-started run's `base→opt` delta is NOT comparable to a pristine-seed run's.** The
baseline is already optimized, so the measured optimizer gain is *smaller* while the absolute
score is *higher*. Both numbers are real; they answer different questions.

- Opt in explicitly with `SB_WARM_SEED=1`. The default stays the pristine seed.
- `run_suite.sh` prints a loud disclosure and `runmeta.json` records `"warm_seed": true`, so a
  warm-started run cannot be quoted later as a from-scratch result by accident.
- Mutually exclusive with `SB_EMPTY_SEED=1` (the no-skill control) — combining "no skill at all"
  with "start from an optimized skill" is incoherent, and `run_suite.sh` refuses it.
- When comparing against published from-scratch numbers, report the pristine-seed run.

## Refreshing this

Replace both files with a later champion's `optimized/optimized_capability/` and update the table
above. Do not edit the text by hand — hand edits would make the next measured "optimizer gain"
partly ours, which is the failure mode issue #276 describes.
