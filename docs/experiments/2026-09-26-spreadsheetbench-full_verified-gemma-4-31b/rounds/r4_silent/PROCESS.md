# r4_silent — make every turn return information

Parent: `r3_decide` (accepted champion, val 0.8875 stored). Surface: `prompt.md` §7 + DECIDE
rewrite, `task_template.md` interaction contract.

## Cluster ranking (from 79 r3_decide val rollouts)

| # | cluster | evidence | picked |
|---|---|---|---|
| 1 | **Silent turns** — block saves but prints nothing | 55/79 rollouts hit `[Code executed successfully with no output]`; FAIL n=9 mean 4.56 silent vs PASS n=70 mean 1.97; 56427 re-sent one silent block 29/30 turns | YES |
| 2 | **Turn-cap loops** — identical block re-sent to exhaustion | maxdup 5.00 on FAIL vs 2.41 on PASS | partly (prose rule, did not take) |
| 3 | **Anchor-cell choice** — 46646 reads `O11` (2018) instead of `B3` (2016) | passes 2 of 3 trials; the failing trial picks the wrong year cell | YES (§4 bullet) |
| 4 | DECIDE scaffolding unused | `reading_a`/`reading_b`/`| A:` in 0 of 80 rollouts | YES (replaced with one print) |
| — | 341-40, 535-20 | fail under seed, parent and both controls; not reachable from prompt text | excluded |
| — | 38985, 56427 sandbox 500s | harness labels these "Infrastructure error, not a prompt defect" | excluded |

## Changes

| file | change | target |
|---|---|---|
| prompt.md | new §7: end every block with an actionable `print`; a no-output block is a bug not a result; print assumptions not conclusions; don't re-send a block differing only in a constant; halfway-point rule | cluster 1 |
| prompt.md | §7 final bullet (added after screen 1): "printing the same correct answer twice is how a finished task fails — same output means finish, not refine" | cluster 2 |
| prompt.md | §4: replaced the `reading_a`/`reading_b` recipe with a single side-by-side `print` | cluster 4 |
| prompt.md | §4 new bullet: "which cell holds the single value the whole answer keys off" — print every candidate address, prefer the one adjacent to the label that names it | cluster 3 |
| prompt.md | §5 new bullet (added after screen 1): a continued sequence stops at the last row with DATA | 353-29 regression from screen 1 |
| task_template.md | print requirement in the interaction-contract preamble; SOLVE step 3 requires printing the write-back | cluster 1 |

## Verify-the-fix

- Screen 1 (6 ids, 14 min): Δ̄ 0.0, regressed [11842, 353-29]. Silent turns fell 4.44 → 2.38, so
  the edit reached its target — but the failure MODE moved: 33722 and 53647 began burning all 30
  turns at maxdup 26–29 while still printing. The prints gave them no exit.
- Screen 2 (6 ids, 20.7 min) after the two corrective edits: Δ̄ +0.10, regressed [11842] only.
  33722 30 turns → 5 turns / maxdup 4; 353-29 recovered to 1.0. Promote.
- **Full val gate: reject.** 0.8421 vs controls 0.8205 / 0.8974; Δ +0.0270 against threshold 0.0472
  and a control-replicate noise floor of **0.0769**. Below the mean of its own two controls.
- Per-task vs BOTH controls: FIXED [5835], BROKE [13-1, 353-29, 53647] — all three are 1.00 → 0.50.

## Outcome and cause

Rejected, and the cause is legible: §7 makes proof-of-work a COUNT of cells written, and on this
benchmark much of `answer_position` is correct *because it was left alone*. 13-1 (120 preserved
cells) and 353-29 (116 non-blank) are the two most preserve-dependent tasks in the run and both
dropped to half credit. Screen 2 could not see it — 13-1 was in neither subset.

## PRESERVE (must keep passing; verified under r3_decide)

13-1 (120 cells), 353-29 (116 non-blank), 55817 (21), 48588 (17), 379-36 (14), 52807 (12) — all
depend on ORIGINAL contents surviving inside `answer_position`. Any future edit that encourages
writing more cells must be screened against this list.

## Deliberately skipped

- 341-40, 535-20: not prompt-space (fail under every variant measured).
- Hardcoding any task id, cell address as an answer, or expected value: forbidden, and none of the
  edits above name a task.
- Lowering the gate or gating on the screen subset to rescue the +0.10 screen result.
