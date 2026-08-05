# SpreadsheetBench: feedback fidelity before the loop

**Date:** 2026-08-05
**Status:** IMPLEMENTED — three changes, all in `_range_cells` / `_localize_failure`.
**Scope:** `templates/adapters/spreadsheetbench/adapter.py` and its two test modules. **No seed
capability edits** — the rules stay the optimizer's to write (#276), and no `core/` runtime change.

## How this was measured

Pilot [30906175891](https://github.com/skillberry-ai/cap-evolve/actions/runs/30906175891) reached
val 0.660 (33/50) with 17 failures. For each failure, its own final code block was **replayed**
against the gold file for the case the scorer localized on, then diffed cell by cell. The replay
agrees with the recorded per-case results everywhere they overlap (`39046`/`51359` pass case 1 with
0 diffs; `11842` fails case 1 with 2). Two dataset-wide scans (all 912 tasks) sized the rest.

The finding that reordered the work: **the feedback was not merely sparse, it was wrong on a
measurable slice** — and the precedent for what fixing that buys is #293, where correcting the
TYPE advice's direction is what finally moved the ceiling past 0.580.

## What the 17 failures were actually told

| feedback the optimizer received | tasks |
|---|---|
| only `COVERAGE: spans N; your output has a value in N` — no actionable content | **11** |
| that line plus a `TYPE` note | 5 |
| nothing at all (`answer_position` unparseable) | 1 |

And what the replay says those 11 were wrong by:

| task | cells differing | the real defect |
|---|---|---|
| `56637` | **1 of 146** | changed one cell whose expected value equals the input |
| `5192` | 1 of 3 | its own `prefix[:4]` cut one character off the string |
| `53367` | 1 of 1 | wrote the boolean `True` where a number belongs |
| `11842` | 2 of 96 | both numbers low |
| `50051` | 29 of 32 | wrote values into cells the expected output leaves empty |
| `39046` / `51359` | 1 of 5 / 1 of 4 | one number off, on a different graded copy |
| `3911`,`56996`,`57090`,`59743` | 12/63, 3/5, 3/5, 2/3 | genuinely wrong arithmetic |

## Change 1 — COVERAGE against the expected fill, not the span

Measured over all 912: the expected output fills **under 25% of `answer_position` on 90 tasks
(10.1%)** and under 60% on 203 (22.8%). The old branch `written * 4 < total` therefore fired on a
tenth of the benchmark *for correct answers*. `56427` filled 15 where the expected output fills 20
in a 324-cell span — scolded for ~300 cells it was never meant to write. `50051` filled 32 of 32
against an expected 3 and was told nothing.

COVERAGE now appends the expected fill and measures the warning against it. If the gold cannot be
read, no fill claim is made — withholding beats guessing, since guessing is the defect.

## Change 2 — the MISMATCH note

One class per differing cell, most specific first, so counts sum to the difference count and
cannot double-count. Classes were chosen from the shapes actually present, not invented:

| class | measured in |
|---|---|
| correct value stored as text | `325-44` ×15, `56427` ×14 |
| an Excel error text the agent wrote out | `55931` ×8 (`#N/A`) |
| expected value *is* an error marker, agent computed one | `57232` ×15 |
| value written where the expected output has none | `50051` ×29 |
| empty where a value is expected | `56427` ×5 |
| text is a prefix of the expected text | `5192` |
| numeric direction, only when every difference agrees | `11842`, `59743` low; `57090` high |
| (subset) CHANGED although the expected value equals the input | `56637` ×1, `56427` ×10, `325-44` ×9 |

The subset count is reported separately and marked "of these", because "the expected value is the
cell's own input" overlaps every other class while being the most actionable of them.

## Change 3 — range-parser robustness

23 of 912 `answer_position` strings (2.5%) were unreadable, in seven families. Six are now handled;
verified against the real dataset, **23 → 1**. The survivor is bare `A:G`, which names no rows:
`_range_cells` has no workbook in scope, and inventing a bound would corrupt the COVERAGE
denominator — the exact defect Change 1 removes. It stays skipped, and stays tested.

This matters to the agent too, not only the optimizer: `_target_size` shares the helper, so
`450-9`'s prompt carried no `TARGET SIZE` line while every well-formed task's did.

## Expected effect, stated honestly

A better signal is not a better score. What the evidence supports:

- **Plausible conversions** — `56637`, `5192`, `55931`, `325-44`, `56427`. All mechanical or
  convention defects, the class prose has reliably fixed before (the `_xlfn`→literal rule, the
  split/extract rule). `50051` too, though it is anti-correlated with `47741` across three
  candidates. `57232` partially: the 15 sentinel cells, not its 9 wrong numbers.
- **Not expected to convert** — `3911`, `56996`, `57090`, `59743`, `39046`, `53367`. Reasoning
  failures; they now learn "2 cells off and low", which is honest but may not be enough.
- **Blocked regardless** — `30709`, whose fix conflicts with `50630` (extract-a-date wants a real
  datetime, split-a-sentence wants text kept). No single global rule satisfies both.

A second reason to expect the named classes to land: **12 of the 17 failures already ran a
read-back verification block and still failed**, because reading back your own file shows what you
wrote, never whether it is right. The classes above are precisely the ones a self-check *can* catch.

## What was retired by this analysis

- **`trials=3`.** Justified as "make single-task wins detectable", but the gate made the correct
  call on all four rejections and the deltas came from real task flips, not noise. 3× eval cost.
- **Surfacing rejected candidates' per-task deltas.** Already built: `LEDGER.md` recorded
  `fixed={11842, 30709} broke={38332, 50630, 73-45}` verbatim and the optimizer ignored it twice.
- **"The graded copies differ in size, so the agent hardcodes extents."** False. All 17 failures
  have identical `(rows, cols)` across the three copies, as do 846 of 905 tasks (93%). The copies
  differ in data, not shape.

## Deliberate decisions

- **Gold-safety policy widened, narrowly.** Three signals now read the gold: a value's TYPE (as
  before), the expected fill count (one integer per range), and the MISMATCH classes. All are
  metadata about the answer — a count, a type, a category — never the answer.
  `test_no_gold_value_leaks_through_the_mismatch_note` asserts the invariant. The one value that
  appears, `#N/A` in the error-text class, is the agent's own.
- **The warm seed stays pinned to `cand_0002`.** Refreshing it to the 0.660 champion would raise
  the absolute score and make the next pilot unattributable — we could not tell better feedback
  from a better starting point.
- **No prompt or seed-capability edits.** The optimizer writes the rules; we only fix what it is
  told about its own failures.
