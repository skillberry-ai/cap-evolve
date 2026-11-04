# PROCESS — cand_0002

**Headline:** cand_0001 supplied a *correct* epoch→UTC procedure and it measurably
closed two of the four leaking rubric items. The two that remain are not estimation
reproducible** slips: an hour ≥ 12 rendered on a 12-hour clock, and an offset derived
from the agent's own mis-rendered dates instead of from the epoch integers. This
iteration names both failure modes, adds worked examples that actually exercise them,
and forces the arithmetic to be shown.

## 1. What I did first (and why this is always step 1 here)

Followed the method cand_0001 left in INSIGHTS.md: `trajectories/*.json` are


| item | missed | vs seed (cand_0001's table) |
|---|---|---|

and output-contract edits are **load-bearing and must be preserved**, and its

## 2. The new observation that changed the lever

All 5 final answers are **byte-identical**. The seed drifted run-to-run (estimation);
this is deterministic. Decoding against the real epochs:

| epoch | truth | agent wrote | error |
|---|---|---|---|
| 1794938400 | 17th **18:00** | 17th **06:00** | −12 h |
| 1794952800 | 17th **22:00** | 17th **10:00** | −12 h |
| 1795204800 | **20th** 20:00 | **19th** 08:00 | −12 h **and** day −1 |

Two independent mechanical slips:

- **(a) 12-hour-clock collapse.** `18→06`, `22→10`, `20→08` — hour mod 12, three for
  three. The division is right; the *rendering* subtracts 12.
- **(b) dropped `+ 1` in the day formula.** On one row: `day_index = 323`, Nov
  cumulative `304` → wrote 19; `323 − 304 + 1 = 20`.

And `hours-since-end` is **purely downstream**: "23.5 hours ago" is exactly correct
*given the agent's own wrong 10:00*. It computed the offset from rendered dates, not
from epochs — so one rendering slip still costs two items.

Supporting observation: `agent.jsonl` contains only tool_use → tool_result → final
answer. **No intermediate reasoning turn exists.** The arithmetic happens silently
inside answer generation — exactly where cand_0001's "sanity-check every conversion"
instruction gets skipped, because nothing makes it observable.

**Why cand_0001's correct procedure didn't land:** its sole worked example converts to
`hour = 0, day = 3`. It exercises **neither** failing path — a reader never sees an
hour ≥ 12 rendered, nor a case where the `+ 1` visibly matters. The tables were
verified; the *demonstration* was unrepresentative. That is the gap I closed.

## 3. Ranked issues → edits

All edits in `icinga_agent.md`. Prompt footprint confirmed from `task.toml`
(`services = ["icinga"]`) → `orchestrator.md` + `shared_context.md` + `icinga_agent.md`.

| # | issue | lever | edit |
|---|---|---|---|
| 2 | examples don't exercise the failing paths | KNOWLEDGE | Replaced the unrepresentative example; added a **second** one chosen to be unforgiving on both paths — `hour = 22` (must not become 10:20) and a month boundary where `+ 1` is load-bearing — plus an explicit note that `day_index` counts Jan 1 as 0, so dropping `+ 1` reports the previous day |
| 3 | arithmetic done silently, never checked | CONTRACT | Require the conversion be **shown inline** (rem, day_index, secs, result). Rationale stated in-text: no shell/`date`/code here, so written-out division is the only check that exists |
| 4 | offset derived from rendered dates, so errors propagate | BEHAVIORAL | Compute offsets by subtracting the two **epoch integers**, never by comparing rendered timestamps; show the subtraction; on disagreement trust the subtraction and re-convert |
| 5 | my edit 3 contradicts "never raw epoch numbers" | CONTRACT | Reconciled: "never a raw epoch *on its own*"; epoch-alongside-conversion explicitly endorsed |

Edit 4 specifically breaks the rendering→offset propagation that makes a single slip

## 4. Verify the fix — direct, not plausible

I ran the task's **real verifier** (`tests/verify.py`) out-of-band:

  missing exactly `future-start` + `hours-since-end`. Reproduces the harness, so the
  setup is faithful.
- **Treatment:** the *same* transcript with only the six arithmetic strings corrected

So the two residual items are *purely* arithmetic, and correcting the arithmetic alone
not merely plausible advice. (Caveat, stated honestly: this proves the *target* is
right. It cannot prove the reader will now execute it — that is what the gate measures.)

**Arithmetic I publish is verified:** re-fuzzed the forward procedure over 200k random
epochs 2024–2030 against the stdlib — **0 mismatches** — and checked both new worked
examples line by line. I also **caught a real bug in my own draft**: I first wrote
"step back 31536000 from 2025 to reach 2024", which is wrong because **2024 is a leap
year** (yields 1704153600, not 1704067200). Fixed to give both constants and say which
year selects which. Publishing that unchecked would have been an invisible, actively
harmful edit.

## 5. Non-overfitting

Both rules are about reading an integer counter, not about downtimes:

- Every Icinga time field is an epoch (`last_check`, `next_check`,
  `last_state_change`, ack expiry), so **any** task reporting a time past noon hits
  edit 1, and any task quoting an age or ETA hits edit 4.
  and *"derive elapsed time from the raw integers, not from your own rendering."*
  Neither needs this task to exist.
- Leak-scanned the edited region for host/author/change-ref/count/date/epoch literals
  from this task: clean. Worked examples use neutral epochs (2025-10-09, 2023-11-14)
  in different years and months from the task's data; the `18:00`/`22:00` contrasts
  is the canonical mod-12 trap, and the example carrying it is `2023-11-14 22:20`.

## 6. What to preserve

- cand_0001's conversion tables, coverage adjudication (`is_in_effect` authoritative,
  `trigger_time == 0`, host vs service scope), and output-contract edits — the item
  table shows they fixed `expired-end` and `not-covered`.

## 7. What I skipped, and why

- **`shared_context.md`** — considered promoting the epoch rule, declined. The field
  list and `is_in_effect` semantics are Icinga-specific; per cand_0001's note, promote
  only if the same failure appears in a second, non-Icinga domain. No evidence yet.
- **The other five domain files** — not in this task's prompt footprint.
- **Fan-out across subagents** — the run config encourages it, but the splits are a
  single task with one dominant mechanism and all edits in one file (same judgment
  cand_0001 recorded in META_INSIGHTS.md). Parallel agents would rediscover one cause
  N times and add merge surface for zero coverage gain. Went serial deliberately.

## 8. Escalation (unchanged, still the real fix)

Exact calendar arithmetic on epoch integers with no code execution is **tool-shaped**.
`query_icinga` emitting ISO-8601 alongside each epoch field — or an `epoch_to_utc`
helper — makes this class structurally impossible rather than probabilistically
mitigated. The verifier experiment in §4 sharpens the case: it proves the *only*
remaining gap on this task is that one conversion, so the cost/benefit of that single
tool change is unusually clear-cut. This phase has no tools layer, so the prose above
is the honest best available.

## 9. Techniques used

  fixed (2 of 4 items) versus what it left.
  reclassified the failure from "estimation noise" to "two deterministic bugs" and
  changed the lever from *supply a procedure* to *name the failure modes + make
  execution observable*.
- Traced `hours-since-end` back to the hour bug to show one slip costs two items.
- Ran the real `verify.py` with a control and a minimally-edited treatment to prove
  sufficiency, instead of assuming the fix target.
- Brute-force fuzzed published arithmetic (200k cases) and caught a leap-year bug in
  my own draft before it shipped.
