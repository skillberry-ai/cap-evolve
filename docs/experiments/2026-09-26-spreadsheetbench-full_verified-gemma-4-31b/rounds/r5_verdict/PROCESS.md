# r5_verdict — stop the task the way the harness already stops it

Parent: `r3_decide` (champion, val 0.8875). Branched from the CHAMPION, not from rejected r4_silent.
Surface: `task_template.md` interaction contract (untried surface) + `prompt.md` §2/§6/§7.

## Evidence this round was built on (read the harness, not just the traces)

| finding | where | number |
|---|---|---|
| `verify_left` auto-stop only decrements on a round that does NOT change the output file's stamp | `adapter.py:1438-1449` | 3 rounds |
| a CHECK that calls `wb.save()` refreshes that stamp, resetting the counter | `_artifact_stamp`, `adapter.py:868` | — |
| long rollouts save in 91% of turns; short ones 46% | 88 r3_decide val rollouts | 7 rollouts >=10 turns, 5 of them save on all but 2 |
| once a solution exists, ANY fence-free reply ends the task — prose works | `adapter.py:1413-1415` | — |

So the 30-turn loops were not defiance of the "never re-send an identical block" line; the agent was
re-saving inside CHECK and resetting its own stop counter. r3_decide also asked for "no code block at
all", i.e. an empty message, where one sentence of prose would have ended the task.

## Changes

| file | change | target |
|---|---|---|
| prompt.md §2 | SOLVE saves EXACTLY ONCE; CHECK never calls `wb.save()`; FINISH is one sentence of prose | reset-the-counter mechanism |
| prompt.md §6 | CHECK is read-only + rationale (a re-save round-trips `31133.024999999998` → `31133.025`, flipping the grader's 2dp) | float-corruption hazard |
| prompt.md §6 | CHECK ends with a computed `VERDICT: ALL CLEAR` / `FAILED [keys]`; act on that line alone | replace ignored prose stop rule with a computed token |
| prompt.md §7 | rewritten: "if you are about to call `wb.save()` for the third time, you are in a loop" | countable trigger |
| task_template.md | interaction contract: a solved task is ~4 rounds; exactly one block saves; CHECK read-only; VERDICT line; prose finish | untried surface, read first and as an instruction |

## Verify-the-fix

- Screen (7 ids, seeded with the blast-radius list — **13-1 included**, which r4's screen omitted):
  Δ̄ −0.0714, promote-by-default. Mechanism confirmed: **7/7 end in prose, 0 hit the turn cap**,
  13-1 30→8 turns, 53647 30→6, 11842 30→6; 13-1 and 353-29 held at 1.00.
- **Full val gate: REJECT.** 0.8000 vs controls 0.9231/0.8718; Δ −0.1026 vs threshold 0.0492,
  noise floor 0.0513. FIXED [] / BROKE [353-29, 38985, 46646].
- Behavioural deltas vs controls: saves/rollout 3.5 → **1.6**; turn-cap hits 2 → **0**; mean turns
  5.9 → 5.1; VERDICT printed 3.4x/rollout (0 in controls).

## Outcome: the mechanism worked, the edit lost anyway

Every regression has `saves=1` — one write, a CHECK that said ALL CLEAR, a confident prose finish.
353-29 printed `RECONCILE A14: '6a' vs expected '6a'` (its own output vs its own expectation) then
ALL CLEAR, stopping with 63 wrong cells; its control spent two further rounds printing
`A13: 6 (should be 6)`, `A90: None` and scored 1.0. 5835's control fixes C10/C11 `None` → `0` in a
LATER save.

**The controls' extra saves were CORRECTIONS, not waste.** Turn-efficiency was never the bottleneck:
53647 and 13-1 both burn 30 turns under r3_decide and both score 1.0. Rounds 4 and 5 attacked the
same non-problem from opposite sides and both lost.

**Form lesson:** a boolean the agent computes from its own output is not a check. I wrote the
warning ("not things you read back off your own output") immediately above the block; it was ignored.
Self-assessment must reconcile against a number from the FILE — which r3_decide §6 RECONCILE already
does, and is the version to keep.

## PRESERVE (verified under r3_decide)

13-1 (120 preserved cells), 353-29 (116 non-blank), 55817 (21), 48588 (17), 379-36 (14),
52807 (12). r5 broke 353-29 despite it passing the 7-id screen — a screen pass is not a safety proof.

## Deliberately skipped

- 341-40, 535-20: fail under every variant measured; not prompt-space.
- 38985, 56427 sandbox 500s: harness labels them infrastructure.
- No task id, cell address, or expected value is named in any edit.
