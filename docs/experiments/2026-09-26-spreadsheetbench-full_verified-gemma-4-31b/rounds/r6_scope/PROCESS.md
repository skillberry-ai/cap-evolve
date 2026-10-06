# r6_scope — the loose question is WHICH CELLS, not which formula

Parent: `r3_decide` (champion, val 0.8875). Surfaces: `prompt.md` §4 + §6, `task_template.md` READ
step. Form: worked example + counted invariant (new — r3's two-function recipe had 0/80 uptake,
r4/r5's prose rules were ignored).

## Cluster ranking — from POOLED measurements, not one trial

Pooling r3_decide + 4 null controls (244 rollouts, 5-7 measurements/task) changes which tasks look
broken. Per-task pooled means below 1.0:

| task | pooled | n | note |
|---|---|---|---|
| 341-40 | 0.00 | 6 | never passes |
| 535-20 | 0.00 | 6 | never passes; genuine `delete_cols` (415 of 1592 cols), structural |
| 11842 | 0.14 | 7 | 2 of 96 cells, "number HIGHER than expected" |
| 5835 | 0.43 | 7 | lookup task |
| 38985 | 0.50 | 6 | intermittent sandbox 500 |
| 56427 | 0.50 | 6 | intermittent sandbox 500 |
| 33722 | 0.71 | 7 | |
| 36097, 51249, 53647, 353-29, 46646 | 0.83-0.86 | 6-7 | coin flips |

28 of 40 tasks pass every measurement. Scope hedging: **9 of 30 failing rollouts, only 341-40 and
5835** — both also carrying `changed although the expected value is the cell's own original input`.
Picked that cluster: two tasks, ~2.2 of the 5.5 val points the champion loses.

## Changes

| file | change | target |
|---|---|---|
| prompt.md §4 | new subsection: the loose question is WHICH CELLS; print every pre-filled target cell with its condition verdict; a pre-filled cell where the condition is FALSE and holds an unrelated value IS the spec for the other branch (non-matching rows keep what they have); mirror case (pre-filled block at top, all agreeing with the rule ⇒ keep filling) | 341-40, 5835 |
| prompt.md §6 | CHECK prints `CHANGED n vs rows the rule covers N_RESPONSIBLE` + how to read a mismatch | makes the scope decision verifiable |
| task_template.md | READ step: answer "how many cells am I responsible for writing?" in printed output, before computing anything | same, earlier |

No task id, value, or answer appears in either file (verified by grep for every literal from the
diagnosed tasks).

## Verify-the-fix

- Screen 1 (7 ids incl. the whole PRESERVE list): Δ̄ 0.0, regressed [5835].
- Screen 2 (5835, 33722, 353-29 at **2 trials**): Δ̄ +0.1667, regressed [] — screen 1's 5835 flag was
  variance.
- **Full val gate: REJECT.** 0.7692 vs controls 0.8250/0.8718; Δ −0.0513 vs threshold 0.0513, noise
  floor 0.0468. FIXED [] / BROKE [38985, 48588, 58147].

## What the round actually established

1. **The edit did what it was designed to do.** On 341-40 the write set went from 202 wrong cells to
   exactly gold's 7 (`Q7, Q147, Q229, Q442, Q506, Q582, Q617`), reconciled against the pre-filled
   worked example at Q3.
2. **341-40 is environment-capped at 0.** A no-op `load_workbook` + `save` (openpyxl 3.1.5) rewrites
   **126 untouched float cells** in that file — `11135.599999999999` → `11135.6` — in columns L/J/I
   the instruction never mentions; the grader counts each as a changed cell whose expected value is
   its own original input. The identical test on 13-1 and 353-29 changes 0 cells. No prompt text can
   avoid this: the corruption happens on save, which the task requires.
3. **2 of the 3 regressions are path typos, not scope errors.** 58147 was given
   `.../58147_0_19da123e/...` and saved to `58147_0-19da123e`; 48588 was given `48588_0_6ab807c3` and
   saved to `48588_0_6ab07c3`. Across all 851 val rollouts of this run only 2 have this defect and
   both fell in this candidate, so the −0.05 is two coin flips. The edit's own effect is unmeasured
   rather than refuted.
4. **Why a path typo is silently fatal** (`adapter.py:1413-1415`): finish-on-prose requires
   `solution_code`, set only when a save changes the stamp of the file at the harness's chosen path.
   A typo'd save leaves the answer invisible, so the closing prose reply gets "No python code block
   was found ... the round was wasted" and the agent burns its remaining turns with a correct
   workbook at the wrong path.

## PRESERVE (held this round)

13-1, 353-29, 55817, 48588 (typo, not scope), 379-36, 52807 — the scope rule did NOT cause
over-writing on any preserve-heavy task; screen 1 and the gate both confirm.

## Deliberately skipped

- 341-40 / 535-20 as score targets: proven unwinnable (float-on-save) and structural respectively.
- 38985, 56427: intermittent sandbox 500s, labelled infrastructure by the harness.
- Hardcoding any task id, cell address or expected value.
