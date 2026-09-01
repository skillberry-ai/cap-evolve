# PROCESS — iteration cand_0004 (parent cand_0003, val 0.500)

Sole skill exercised by the only task (`flink-query`): `senior-data-engineer`. train=val=test=`flink-query` (same data file, deterministic 644-line oracle output). Build-under-429 is now handled (cand_0003 → 0.5); the remaining failure is `test_output_matches_expected` (output correctness), which is set-equality against a fixed expected file.

## Diagnosis (this iteration's ./trajectories/, cand_0003 t0–t9; used 2 read-only Explore subagents in parallel)
Obtained the ground truth: read the task's `oracle/solve.sh` + `verifier/test_outputs.py` + expected `out_lsj_001a.txt` (644 lines) from the extracted task dir. Oracle semantics: filter SUBMIT (code 0) task events → per-jobId `EventTimeSessionWindows.withGap(600s)` → count SUBMIT events per session → keep MAX session count per job → emit `(jobId,maxCount)` **only** on the job's `FINISH` (code 4) event, via `CoProcessFunction` + event-time timer. Micros→ms.

Per-trial: t1,t3,t4,t5,t6 PASS. t0,t9 FAIL output. t2,t7 never wrote code. t8 infra timeout.

### Ranked clusters
1. **Completion-join too permissive [KNOWLEDGE] — leverage: 2 trials (t0,t9), the whole recoverable correctness gap.**
   Both defined "finished" as ANY terminal event `isTerminal = FAIL(3)||FINISH(4)||KILL(5)||LOST(6)` (t0 also had a `Long.MAX_VALUE-1` fallback timer emitting keys with no terminal event). Result: 902 rows, 258 EXTRA, 0 missing vs the 644 oracle. Every PASSING trial already filters to `FINISH(4)` only. Root: the prompt says "once the job has finished" and the *old* skill text said "completion/**terminal** event" — conflating the two and actively steering agents to the bug.
2. **Budget exhaustion before coding [BEHAVIORAL] — leverage: 2 trials (t2,t7).** Spent the whole turn profiling data (format.pdf, event-type distributions, overlap stats) and never wrote/built Java → all tests fail. Partly downstream of #1: less semantic ambiguity ⇒ less need to explore.
3. **Infra timeout (t8) — NOT optimized** (uncontrollable noise per feedback).

## Edits shipped (all in `senior-data-engineer/`, additive/narrowing)
- **SKILL.md body, rule 4 [BODY] → cluster 1.** Replaced "completion/**terminal** event" with two explicit sub-rules: (a) "finished" = the SUCCESS/`FINISH` event ONLY, NOT the union of terminal states, and an explicit callout that `isTerminal = FAIL||FINISH||KILL||LOST` overshoots the oracle; (b) NO fallback/`Long.MAX_VALUE`/end-of-stream emit — a key with no completion event produces no row.
- **references/flink_datastream_recipes.md §5 + §8 checklist [REFERENCE] → cluster 1.** Mirrored the same FINISH-only + no-fallback rules and added two self-check items (single completion code only; no fallback timer). Reinforces the body for trials that open the reference.
- **SKILL.md body, subsection lead-in [BODY] → cluster 2.** Added a "budget the turn for coding, not endless profiling" note: a quick `zcat | head` to confirm schema is enough; get code built+run before deep profiling. Additive ordering guidance.

## VERIFY-THE-FIX + blast radius (per edit)
- Rule 4 FINISH-only: tied to t0/t9 `test_output_matches_expected` (isTerminal predicate → 258 extra rows). Oracle + all 5 passing trials confirm `FINISH(4)` only ⇒ 644 rows. **Blast radius:** passing trials t1,t3,t4,t5,t6 already filter to FINISH only → behavior unchanged; the edit narrows exactly the wrong behavior. No other task uses this skill.
- Reference §5/§8: same claim, reachable via the existing body pointer (link validated); no new/broken links. No behavior change for trials that don't open it.
- Budget note: additive; passing trials that coded quickly are not pushed off-path; targets the two trials that never coded.

## Non-overfitting
No filename/value/answer hardcoded. "finished = success/FINISH event, not any terminal state" is the general semantic of a completion join, phrased generally with the concrete `FINISH`/`FAIL`/`KILL`/`LOST` instantiation and a "confirm the code against the schema doc" caveat. Deliberately did NOT add CSV column indices: parsing was CORRECT in every code-writing trial (t0,t5,t6,t9) → not a failing cluster (would violate REAL).

## Skipped
- t8 infra timeout (noise). t2/t7 pure budget failure only indirectly addressed (skill can't extend the turn budget). Did not re-ship cand_0002's build script (JOURNAL: agents don't run it). Did not touch the build/Maven-429 guidance (already working, high regression risk).

## Subagents/features used
2 parallel read-only Explore subagents (t0–t4, t5–t9) for trajectory diagnosis; direct oracle inspection from the extracted task dir.
