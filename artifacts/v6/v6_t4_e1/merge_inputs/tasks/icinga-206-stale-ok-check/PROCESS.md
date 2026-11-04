# PROCESS — cand_0002 (explainability; REQUIRED)

## Headline

Iteration 1 taught the right *framing* (anchor-and-difference) but shipped a **wrong
procedure and an arithmetically wrong worked example**. The residual loss is not variance —
it is a deterministic, reproducible off-by-one-day arithmetic bug that my own prior edit
installed. This iteration replaces the procedure with three *independent* calculations and a
corrected, machine-verified example.

## How I diagnosed

decisive:

| | iter-1 parent (n=29) | cand_0001 champion (n=5) |
|---|---|---|
| missed `last-check-date` + `days-stale` | 8 | 0 |
| missed `last-check-date` **only** | 3 | **5 (all)** |

  arithmetic worked.

**The flakiness is gone and has been replaced by a consistent wrong answer.** That is a
near-identical, so the error lives in the instructions, not in sampling.

### The exact bug (reproduced numerically, not inferred)

**wrong by one day**:

> "The freshest is `1794988260`. … So `restic-snapshot-age` last ran approximately
> **2026-11-08 ~22:20 UTC** — nine days before your stand-up."

the agent did: it knew the anchor's *calendar date* (2026-11-18, stated in the prompt) but
**not its time of day**, assumed one, then subtracted the **full duration 9d 5h36m** from that
wall-clock guess. `9d5h36m` back from any assumed anchor time earlier than ~05:36 rolls across
midnight into Nov 8. The agent's implied anchor was `2026-11-18 03:56` vs the real `07:51`.
**One guessed quantity (the anchor's clock time) poisoned a fact that never needed it.**

Iteration 1's text caused this directly: it said *"Subtract that many days from the anchor's
calendar date"* while its worked example demonstrated subtracting a **duration** — and the
reader copied the example's shape, not the sentence.

### Iteration 1's worked example was itself wrong

`1772614020 − 1772233920 = 380100` s = 4d 9h35m, and the example concluded
`1772614020 // 86400 − 1772233920 // 86400 = 5` calendar days, not 4. **The example I shipped
last iteration taught a method that is wrong whenever the gap crosses a midnight.**

A verification subagent checked this over 2000 random pairs: using `(A−T)//86400` as the
(anchor's time of day earlier than the target's), where it is short by exactly one day. The
correct offset is the **day-number difference** `A//86400 − T//86400`. On this task's real
the *example* modelled duration-subtraction and the agent reproduced it.

## Ranked issues
| rank | cluster | root cause | tag | change class |
|---|---|---|---|---|

## Changes made
| # | cluster | file | what | protects passing? |
|---|---|---|---|---|
| E1 | 1,2 | `icinga_agent.md` → "Converting an epoch timestamp" | Replaced the single recipe with **three independent calculations**: (1) duration `A−T` → d/h/m; (2) **date** via day-number difference `A//86400 − T//86400` subtracted from the anchor's *date*; (3) **time of day** from `T % 86400` **alone**. Added an explicit "the trap" callout: `calendar_days` and `days` are often different numbers and the date needs the former; never subtract `d+h+m` from a wall-clock time known only approximately. States that steps 2–3 need no knowledge of the anchor's clock time at all. | Yes — no action name, no extra call |
| E4 | 1 | `shared_context.md` → Grounding | Domain-general: **"An age is not a date — compute and report both."** Derive the date from the older timestamp, not by subtracting an age from an approximate reference time (crosses a midnight ~half the time); check the date is N or N+1 days before the reference. Applies to AAP2 `finished`, Babylon `modified`, cost report periods. | Yes — no rule loosened |

## Verify-the-fix (the decisive check)

Ran the **new** procedure literally on the real payload, using only facts the agent provably
had — the sibling epochs, the stale epoch, and the stated stand-up date — and **withholding
the anchor's time of day**, which is the thing it guessed wrong:

```
step1 duration : 9 days 5h36m
step2 cal_days : 20775 − 20766 = 9  ->  2026-11-18 − 9d = 2026-11-09
=> "2026-11-09 02:15 UTC", 9 days old        matches golden alias: True
sanity check  : cal_days == days or days+1 ? True (9, 9)
```

**Step 3 is what actually fixes this task.** Reading time-of-day off `T % 86400` removes the
dependence on the anchor's clock time entirely — the precise quantity the agent was
changes behaviour at exactly the point the trace goes wrong, rather than being merely
plausible advice: under the old text the agent had **no way** to obtain the time of day except
by subtracting from a guess; under the new text it never needs the anchor's clock at all.

substance. No forbidden action name (`get_check_results`/`get_last_check`) appears in either
edited file; no task-specific noun (host, service, `restic`, `backup`, either real epoch, or
either real date) appears anywhere in my new text — grepped to confirm.

## Non-overfitting restatement

Every added rule restates without a task-specific noun: *"a stored record's calendar date must
be derived from its own timestamp, not by subtracting its age from an approximately-known
reference time; and the day offset between two timestamps is their day-number difference, not
the floor of their elapsed duration."* No hostname, service, count, or date from this task
the example teaches the class, not the instance.

## Process & features used
- **Subagent:** one read-only verification subagent, handed the arithmetic claims as
  independently caught that iteration 1's example was wrong (its claim 6). I did **not** fan
  one fact five times. Fan-out suits many distinct clusters; the leverage here was adversarial
  *numeric* verification, so that is where the agent went.
- **Prior iterations read:** `prior_iterations/cand_0001/` (PROCESS.md + diff.patch). This
  iteration is a direct correction of that diff, not a new direction.

## Good things to PRESERVE
  writes in prose only; never add an action name to these files.
- **The staleness / `enable_active_checks` / "cannot confirm" reasoning and the avoided
- **Deriving time-of-day from `T % 86400`** — the load-bearing line. Anything that
  reintroduces "subtract the age from the anchor's wall-clock time" reinstates the bug.

## Deliberately skipped
  `orchestrator.md` untouched.
- **`days-stale`, the staleness narrative, the forbidden phrase** — all at ceiling.

## Escalation (unchanged, now better evidenced)

No tool converts epoch→wall-clock and the agent has no clock. This iteration makes the
workaround *correct* rather than merely *present*, but the structural fix is still a time
helper, or an MCP layer rendering `last_check` as ISO-8601 beside the raw epoch. **This
iteration is itself the evidence**: a prose arithmetic recipe is fragile enough that the
previous iteration shipped a wrong one and the reader faithfully reproduced the error. One
line of formatting code would retire this entire failure class. **Recommended for the tools
phase.**
