# SpreadsheetBench: structural facts in the prompt

**Date:** 2026-08-04
**Status:** IMPLEMENTED — two changes, `A1` (name the graded copies) + `B` (structural preview).
**Scope:** `templates/adapters/spreadsheetbench/adapter.py`, its seed `task_template.md`, and
`core/pyproject.toml` dev extras. No `core/` runtime changes.

## The two changes

**A1 — name the other graded copies.** Each task is scored on three copies of the workbook
whose data differs, and copies 2 and 3 sit in the same mounted directory as the input. The
agent was told 201 times across 150 rollouts that its code is "replayed on two other copies"
and referenced them **zero** times, because nothing said where they are and it never
enumerated the directory. `_sibling_inputs()` now states their paths.

Kept deliberately **factual, not prescriptive** — it does not tell the agent to self-test.
That strategy is left for the optimizer to discover, so any gain is credited to the optimizer
rather than hand-supplied by us (issue #276). Targets the 8 partial-pass tasks; under hard
scoring each is worth full credit, so the ceiling is +0.16 val.

One hazard it must close: cases 2 and 3 are produced by replaying the agent's **final** code
block with filenames substituted. A final block that itself looped over copies would have
those names rewritten too, corrupting the graded outputs. The injected text therefore states
that the final block must read exactly one input.

**B — structural preview.** `TARGET SIZE` (from `_range_cells`, the same helper the scorer
grades with) plus each sheet's real data extent. Targets the 4 severe coverage shortfalls.

> **Correction that reshaped this spec (2026-08-04).** Its first draft claimed ~19–24 coverage-short
> tasks, derived by counting the `COVERAGE:` string in scorer feedback. That was wrong:
> `_localize_failure` emits `COVERAGE:` for *every* failure with a parseable range, so the
> count was tracking failures, not shortfalls. Corrected numbers on the seed's 25 failures
> over 50 val tasks (pilot 30799393875):
>
> | failure mode | seed | champion `cand_0001` | fixable by this spec? |
> |---|---|---|---|
> | filled == span, **values wrong** | **15** | 14 | No |
> | filled < span (real shortfall) | 9 | 6 | Yes |
> | ⤷ severe (<70% filled) | 4 | 4 | Yes — the real targets |
> | no COVERAGE number | 1 | — | — |
>
> Shortfall fill ratios at seed: `0.05, 0.23, 0.55, 0.62, 0.71, 0.84, 0.90, 0.99, 0.99`
> (the `0.99`s are off-by-one boundary cases, not "assumed the data ended early").
>
> So extent is **not** the main bottleneck. This fix's ceiling is ~9 tasks (+0.18 val) if
> every shortfall converted perfectly, realistically ~4–5 (+0.08–0.10). The dominant
> failure — 60% of failures — is **correct coverage, wrong values**, matching the
> optimizer's own `PROCESS.md` cluster rank 4 ("genuine logic / ambiguous-spec misreads",
> 15 tasks), which it marked not prose-fixable.
>
> Unchanged and still the important finding: the agent does one-shot reasoning in 3.3 of 30
> turns and prose provably cannot change that. What was wrong is *which* failure that costs
> us — mostly wrong-values, not wrong-extent.
>
> That diagnosis was then done at $0 from the artifacts, and produced `A1` above. Two further
> hypotheses were tested and **refuted** — do not re-run them: (1) the replay's naive
> `str.replace` silently breaking solutions that build paths dynamically — no, all 50 tasks
> emit both literal filenames, and upstream `inference_multiple.py:121-124` does the identical
> substitution; (2) gold being read by the agent — no, 0 gold filename references and 0
> `load_workbook` calls on an answer path across 150 trajectories, though gold IS reachable in
> the mount and that exposure is worth hardening with #276.

## Problem

The agent fills a fraction of its target range because it infers the input's extent from a
five-row preview, and it will not spend turns discovering the real extent.

Measured on pilot run 30799393875 (sha `83e1296b`, PR #289) over 50 paired val tasks:

| | mean turns (cap 30) | median | val reward | coverage-short |
|---|---|---|---|---|
| seed | 3.52 | 3.0 | 0.500 | 24/50 |
| champion `cand_0001` | **3.32** | 3.0 | 0.560 | 20/50 |

PR #289 successfully fixed the *signal*: its localized `COVERAGE` diagnostic reached the
optimizer, which named coverage as failure cluster rank 2 in `PROCESS.md` and added a
"count non-empty cells versus range size" rule to `task_template.md`. But turn usage went
**down** (−0.20 overall, −0.21 on the 24 coverage-short tasks specifically), and only 5 of
those 24 converted to a pass.

**Conclusion: prose cannot buy reconnaissance.** The optimizer wrote the inspection rules
and the agent ignored them. So the next lever must *remove the need* for reconnaissance
rather than request it.

### Worked example — task `110-2` (real, from the run's own trajectory)

The agent was given `answer_position = 'Sheet1'!A1:C13` (39 cells) and this preview:

```
Sheet Name: Sheet1
   Column 1  Column 2  Column 3  Unnamed: 3 ... Column 1.1  Column 2.1  Column 3.1
0         1        11       101         NaN            1.0        11.0       101.0
1         2        12       102         NaN            2.0        12.0       102.0
2         3        13       103         NaN            NaN         NaN         NaN
3         4        14       101         NaN            NaN         NaN         NaN
4         5        15       102         NaN            NaN         NaN         NaN
```

It produced 9 filled cells — exactly `3 rows × 3 cols`. The target needs `13 rows × 3 cols`.
The preview showed it Excel rows 2–6 only; rows 7–13 were never visible, and nothing in the
prompt stated that the target spans 13 rows.

## Design

### 1. What gets injected

Prepended into the existing `{spreadsheet_content}` placeholder:

```
TARGET: 'Sheet1'!A1:C13 — 39 cells across 1 sheet ('Sheet1').
The range above is what you must FILL. The data extents below are what the input
CONTAINS — do not assume the data ends where the sample rows end.

Sheet Name: Sheet1  [data extent: rows 1-13, cols A-I  (12 data rows x 9 cols)]
   <existing five-row pandas preview, unchanged>
(showing first 5 of 12 data rows)
--------------------------------------------------
```

Multi-range, multi-sheet targets are summed and listed, e.g. for task `19-7`
(`'MINUS'!B2:E11,'PLUS'!B2:E5200`): `20,836 cells across 2 sheets ('MINUS', 'PLUS')`
— 40 + 20,796.

Cost: roughly 30–60 tokens per prompt.

### 2. Data sources, and why this is gold-safe

| fact | source | added I/O | leaks gold? |
|---|---|---|---|
| target cell count, sheets named | `_range_cells(answer_position)` — the same helper the scorer grades with | none | No — arithmetic on a string the agent already has |
| per-sheet data extent | the `DataFrame` `_spreadsheet_preview` already parses | none | No — it is the input file the agent is given |

Two deliberate choices:

- **Reuse `_range_cells`.** The count the agent sees is then *the same number* the
  `COVERAGE` diagnostic later grades it against. Any other parse risks teaching a number
  that disagrees with the grade.
- **Use `df.shape`, never `openpyxl`'s `ws.max_row`/`max_column`.** `max_row` counts
  formatted-but-empty cells, so it overstates extent. That would teach the agent to
  overfill and could regress currently-passing tasks — a real risk, since 28 of 50 val
  tasks already pass.

### 3. Structure

All in `templates/adapters/spreadsheetbench/adapter.py`:

- **`_target_facts(answer_position) -> str`** — new. Pure function, zero I/O, no
  dependencies beyond `_range_cells`. Independently unit-testable.
- **`_spreadsheet_preview(path, rows)`** — extended to append the per-sheet extent
  annotation, derived from the frame it already parses. Still one pandas pass; no doubled
  I/O.
- Composed at the call site (`adapter.py:1104`).

`answer_position` is already available at the call site (`entry["answer_position"]`, passed
to `.format()` on the next line), so no plumbing is needed to reach it.

### 4. Error handling

`_spreadsheet_preview` at `:1104` is currently **not** wrapped, and this file has a
documented history of a pandas/PyArrow `SIGSEGV` in exactly this call path taking down a
whole algorithm process (run 30634898569 lost 68 minutes and ~$6). The new composition gets
a `try/except` that degrades to today's plain preview text, so a structure-computation
failure can never cost a rollout. A malformed `answer_position` that `_range_cells` cannot
parse yields no `TARGET:` line rather than an error — matching `_range_cells`'s existing
`continue`-on-no-match behaviour.

### 5. Testing

Follows the existing `core/tests/test_spreadsheetbench_*.py` pattern:

- `_target_facts` on the real notation forms: single range; multi-range multi-sheet
  (`'MINUS'!B2:E11,'PLUS'!B2:E5200` → 20,836 / 2 sheets); `$`-absolute (`$B$2:$E$11`);
  single cell (`'S'!B2`); malformed input → degrades to empty, no raise.
- The extent annotation reports pandas' `shape`, asserted *not* to equal an
  `openpyxl.max_row` value on a fixture with trailing formatted-but-empty rows.
- The composed block still contains every load-bearing placeholder's content and the
  five data rows.
- A failure injected into the structure path falls back to the plain preview.

### 6. Validation

This fix is measurable **before any optimization**: the next pilot's *seed baseline*
prices it with the optimizer uninvolved. If the facts help, seed val rises above the
measured 0.500 immediately.

Pass criteria for the follow-up pilot (~$45, ~2h) before committing to a full run:

| signal | current | pass |
|---|---|---|
| coverage-short tasks | 19/50 | ≤ 10 |
| mean turns | 3.32 | ~flat — **flat is the point** |
| val reward | 0.500 seed | any increase |

Flat turn usage is the intended outcome, not a disappointment: it demonstrates the fix
removed the need for reconnaissance rather than begging for it. A turn *increase* would
suggest the facts prompted more exploration, which is fine but is a different mechanism.

This deliberately changes the prompt, so the new seed is **not** comparable to prior runs'
seed. That is by design, and the seed-vs-seed delta (0.500 → new) is itself a measurement.

## Out of scope

- The 182 train tasks never being evaluated (hill-climb with `focus=all` consumes train
  nowhere, so the optimizer's evidence and the acceptance gate are the same 91 val tasks).
  Tracked separately; likely the next lever after this.
- `skillopt_loop` (meta-skill / slow-update / protected regions) — the faithful path to the
  paper's 80–85%, and a substantially larger piece of work.
- The capability text itself. Writing rules is the optimizer's job; this change only makes
  the facts available.
