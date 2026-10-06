# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration: `r7_path` (round 7). Text branched from the champion `r3_decide`; the gated diff is the output-path text and nothing else. Gate: full val n=40 (39 paired), paired, k_se 1.0, `--gate-against control`, `--control-replicates 2`, concurrency 8, `--max-parallel 4`, 1 trial, `--skip-screen-ladder`.

**Outcome: REJECTED on the gate — val 0.8462 vs controls 0.8974 / 0.8684; Δ̄ = −0.0513 against threshold +0.0358; `verdict_stable: true`. The targeted failure occurred ZERO times in all three arms.**

## Ranked issue list
Diagnosed from round 6's regression traces plus a run-wide count over every stored val rollout. The champion leaves ~6 reachable failures against an effective val ceiling of 0.95 (341-40 is capped by openpyxl's float-on-save; 535-20 is a 415-column structural delete), so the headroom is ~0.09 over ~6 tasks against a per-round noise floor of 0.03–0.08.

| rank | cluster | tasks | shared root cause (quoted from traces) | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **OUTPUT-PATH TRANSCRIPTION TYPO** | 2 of 851 val rollouts run-wide (both landed in r6_scope) | the agent retypes the `output_path` in a later block, changes one character of the random hex directory token, and `wb.save()` SUCCEEDS into a directory nobody reads. Grader: "produced NO output file". A fully correct answer scores zero and the agent never sees it | MECHANICAL (zero blast radius on values) | task_template.md `output_path` bullet + save example; prompt.md §2 step 3 + §5 |
| 2 | WRITE-SCOPE MISCOUNT | 341-40 (capped at 0 anyway), part of 5835 | the agent writes hundreds of cells where the rule covers a handful, or stops early | BEHAVIORAL | attempted this round as the `N_RESPONSIBLE` invariant — **withdrawn before gating, see below** |
| 3 | SELF-AGREEING CHECK | 353-29 | the CHECK reconciles a value against itself and prints ALL CLEAR on 63 wrong cells | BEHAVIORAL | refuted as a form in round 5; not retried |

**The base-rate error that decided this round.** I ranked cluster 1 first because it was newly discovered and mechanically certain to be fixable — not because it was frequent. 2 typos in 851 rollouts is 0.24%, i.e. ~0.09 tasks on a 40-task val: an expected gain of ~0.002 against a noise floor 20× larger. I sized the prize from where the failure was FOUND (2 of 3 regressions in one candidate) rather than from its rate over the whole run. That is survivorship bias, and it is the substantive mistake of this iteration.

## Changes made this iteration
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | name the failure | task_template.md `output_path` field bullet | the directory ends in a random hex token that "carries no meaning and cannot be reconstructed or guessed"; copy it once into a variable and use that variable forever; never rebuild it from the task id. States the consequence explicitly — the grader reports no output file, "and you will not notice, because the save itself succeeds" | yes — says nothing about any computed value |
| 1 | make it self-detecting | task_template.md save example | `print("saved:", os.path.exists(OUT), os.path.getsize(OUT), OUT)` plus a paragraph that the line is not decoration, since `wb.save()` "succeeds just as happily into a mistyped directory" | yes |
| 1 | reinforce at the decision point | prompt.md §2 step 3, §5 new first bullet | bind `OUT` once, derive with `os.path.dirname(OUT)`, print it back and compare character by character | yes |

No task id, value, or answer is hardcoded — verified by grep for every literal that appeared in my diagnosis (`Government`, `Germany`, `Volkswagen`, `Carretera`, `48588`, `58147`, `341-40`, `353-29`, `13-1`, `535-20`, `6ab807c3`, `53647`, `5835`): none present. Placeholder contract re-verified: all 6 required placeholders plus `{max_turns}`, `missing: []`, `unknown: []`, `.format()` smoke-test passes, braces doubled inside fences.

## The invariant I built, measured, and withdrew before paying for the gate
The candidate first ALSO carried round 6's one verifiable idea: print `N_RESPONSIBLE` (how many cells the rule owns) during READ, then compare it to `CHANGED` during CHECK.

**Screen 1 killed it, and regressed 48588 — the task the path fix targets — from 1.0 to 0.0.** The trace is unambiguous:

- turn [4] wrote the **correct** answer; the CHECK printed `CHANGED: 25`
- the new line printed `CHANGED vs RESPONSIBLE: 25 / 42`
- the agent spent turns [8] and [12] "correcting" a right answer, ending with 6 cells empty and reward 0.0

**The invariant is wrong by construction.** `CHANGED` counts cells that DIFFER FROM THE INPUT; `N_RESPONSIBLE` counts cells the rule WRITES. A pre-filled worked-example cell whose correct value the rule reproduces appears in neither list — so `CHANGED < N_RESPONSIBLE` is the NORMAL state on exactly the tasks prompt.md §3 teaches about, and the counter tells the agent its correct answer is broken. 5835 shows the same shape: `CHANGED vs RESPONSIBLE: 5 / 17`, and the grader replies "4 cell(s) were CHANGED although the expected value is the cell's own original input". I removed it, re-diffed against the champion to confirm the remaining diff was the path text alone, and re-screened before spending the gate.

This is the round's one clean win: a screen caught a value-destroying invariant on the candidate's own target task, for 9 rollouts instead of 120.

## Verify-the-fix
- **Did the rule fire?** Yes, and this is the decisive measurement: **39 of 40** r7_path rollouts print the `saved:` line; **0 of 40** in each control replicate. The form was read and obeyed.
- **Did the target failure occur?** **No — 0 "NO output file" failures in r7_path, 0 in `ctl_null_i6`, 0 in `ctl_null_i6r1`.** An edit whose target cluster does not appear in the measurement cannot win; it can only lose.
- **What did it cost?** 353-29: **0.0 under r7_path vs 1.0 under BOTH controls**, finishing in 7 turns against the controls' 9 and 13 — one cell written past the end of the answer. 5835: **0.0 vs 1.0 / 1.0**, a lookup miss. Both reproduce against both controls, so they are the edit, not variance: ~400 words of path warning placed in the two spots the agent reads first displaced the reading and scoping work that decides these tasks.
- **Screens (2 × 9 ids, the 2 typo tasks + the 6 preserve-dependent tasks + 53647):** both said `kill` at Δ̄ = −0.1667, but named DIFFERENT regressed pairs — `[48588, 5835]` then `[353-29, 5835]`. I read the divergence as variance and went to the gate anyway; the gate reproduced screen 2's pair exactly. The constant task across screens (5835) was the signal; the varying one was noise; the `kill` verdict was correct both times.

## Measured outcome
`r7_path` **0.8462** (n=39 paired), controls **0.8974** (`ctl_null_i6`) and **0.8684** (`ctl_null_i6r1`). `gate_delta −0.0513`, `gate_threshold +0.0358`, SE 0.0585, `verdict: reject`, `verdict_stable: true`. Booked `--decision reject --reject-basis gate`.

Round noise: `parent_vs_gate_ref_drift +0.0099` — the smallest of the run (prior rounds: +0.0671, +0.0712, −0.067, +0.0356, −0.0625), and `null_delta_between_control_replicates 0.029`. So this round had an unusually low evidence bar and the edit still lost by 1.4 SE. The reject is well-resolved.

## PRESERVE (do not undo) — inherited from r3_decide, still standing
- prompt.md §1 fence contract, verbatim (round 1's largest win).
- §4 DECIDE in full, including the "if neither reproduces it, BOTH are wrong" clause.
- The **absence** of any rule stating what a plausible filler value is. Round 2 proved that costs a task.
- "The scope ends where the DATA ends" — without it, "silence is an answer too" over-fills by one row (353-29).
- The two-load `data_only` recipe, the format-clause-beats-example rule, `to_excel` prohibition, preview offset, literal-A1 CHECK with EMPTY/CHANGED and RECONCILE, FINISH condition, never-re-send-identical-block.
- **New:** the absence of any counter comparing CHANGED to cells-the-rule-owns (this round), and the absence of any rule making cells-written a progress signal (round 4).

## Deliberately skipped
- 341-40 and 535-20 (not prompt-space: openpyxl float round-trip vs the grader's 2dp rounding; a 415-column structural delete).
- Anything naming a task id, a real task's cell address, or a gold value.

## What a future round should take from this
1. **Compute the cluster's base rate over the run's rollouts BEFORE proposing, and multiply by the split size.** If expected Δ < the noise floor, the edit is unmeasurable on this harness however real it is. This is now the first check, ahead of "is it safe".
2. **Do not re-introduce any check comparing a count of CHANGED cells to a count of cells the rule owns.** If the invariant is wanted, count the cells the code ASSIGNED, never the cells that differ from the input.
3. **Prose added to §2/§5 of prompt.md and the field list of task_template.md is not free.** Three rounds now (r4, r5, r7) have added correct, safe, well-targeted text at the top of what the agent reads and lost 0.05–0.10 by displacement. For this reader, added words at the front cost attention at the back.
4. **Scoreboard by edit KIND, updated:** decision-procedure edits about what to COMPUTE 1 of 2 (r3 accept). Process-control edits about when to stop / how much to write 0 of 3 (r2, r4, r5). Mechanical/plumbing edits 0 of 1 (r7). The only accept this run changed how the agent DECIDES, not how it behaves around the write.
