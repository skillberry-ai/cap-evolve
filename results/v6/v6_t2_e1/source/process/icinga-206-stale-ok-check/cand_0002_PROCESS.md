# PROCESS — cand_0002 (explainability; REQUIRED)

## Headline

Iteration 1 taught the right *framing* (anchor-and-difference) but shipped a **wrong
procedure and an arithmetically wrong worked example**. The residual loss is not variance —
it is a deterministic, reproducible off-by-one-day arithmetic bug that my own prior edit
installed. This iteration replaces the procedure with three *independent* calculations and a
corrected, machine-verified example.

## How I diagnosed

Same method as iteration 1 (aggregate `verifier/reward-detail.json` under each stub's
`metadata.trial_dir`), which remains the whole diagnosis. What changed vs iteration 1 is
decisive:

| | iter-1 parent (n=29) | cand_0001 champion (n=5) |
|---|---|---|
| scored 1.0 | 18 | **0** |
| missed `last-check-date` + `days-stale` | 8 | 0 |
| missed `last-check-date` **only** | 3 | **5 (all)** |

- `days-stale` is **fixed — 0/5 misses** (was missed in 8/29). Iteration 1's duration
  arithmetic worked.
- `last-check-date` now misses in **5/5**, and every trial scores *exactly* 0.867.
  `completion` and `tool_calls` stay 1.0 in 5/5; the single `get_services` call is intact.

**The flakiness is gone and has been replaced by a consistent wrong answer.** That is a
different problem from the one iteration 1 diagnosed, and strictly easier: the trials are now
near-identical, so the error lives in the instructions, not in sampling.

### The exact bug (reproduced numerically, not inferred)

Four of five trials emit identical reasoning. They get the duration **right** and the date
**wrong by one day**:

> "The freshest is `1794988260`. … So `restic-snapshot-age` last ran approximately
> **2026-11-08 ~22:20 UTC** — nine days before your stand-up."

Truth is `2026-11-09 02:15 UTC`; the reported value is `-1 day, 20:05` off. Solving for what
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
**`2026-02-28` 23:12 UTC**. The true value of `1772233920` is **`2026-02-27` 23:12 UTC**.
`1772614020 // 86400 − 1772233920 // 86400 = 5` calendar days, not 4. **The example I shipped
last iteration taught a method that is wrong whenever the gap crosses a midnight.**

A verification subagent checked this over 2000 random pairs: using `(A−T)//86400` as the
calendar offset is wrong in **51.9%** of cases — precisely when `A % 86400 < T % 86400`
(anchor's time of day earlier than the target's), where it is short by exactly one day. The
correct offset is the **day-number difference** `A//86400 − T//86400`. On this task's real
values the two happen to agree (both 9), so the recipe's day-count is not what failed here —
the *example* modelled duration-subtraction and the agent reproduced it.

## Ranked issues
| rank | cluster | root cause | tag | change class |
|---|---|---|---|---|
| 1 | **`last-check-date` off by one day (5/5)** | Date derived by subtracting a *duration* from a *guessed anchor wall-clock time*, crossing midnight. Time-of-day was never read off the target epoch, where it is free and exact. | KNOWLEDGE (wrong procedure) | rewrite procedure + corrected example |
| 2 | **Prior worked example is numerically false** | `//86400` of a duration used as a calendar-day offset; wrong in ~52% of cases. A wrong example is worse than none for a `sonnet`-tier reader that pattern-matches the shape. | KNOWLEDGE (defect I introduced) | replace with verified example |
| 3 | **The date was implicitly optional** | Step 1 said "convert to a date/time" and an output slot existed, but nothing said the *date* is a required fact. Trials happily reported "9 days old" and treated the date as decoration. | CONTRACT | state the date as required |

## Changes made
| # | cluster | file | what | protects passing? |
|---|---|---|---|---|
| E1 | 1,2 | `icinga_agent.md` → "Converting an epoch timestamp" | Replaced the single recipe with **three independent calculations**: (1) duration `A−T` → d/h/m; (2) **date** via day-number difference `A//86400 − T//86400` subtracted from the anchor's *date*; (3) **time of day** from `T % 86400` **alone**. Added an explicit "the trap" callout: `calendar_days` and `days` are often different numbers and the date needs the former; never subtract `d+h+m` from a wall-clock time known only approximately. States that steps 2–3 need no knowledge of the anchor's clock time at all. | Yes — no action name, no extra call |
| E2 | 2 | same | Replaced the wrong example with invented May-2026 values (`1779356400`/`1779055500`) **chosen so the two methods disagree** (duration 3 days, calendar offset 4) — the example now *demonstrates* the midnight crossing and states the naive method would give 2026-05-18 instead of the correct 2026-05-17. All 14 numeric claims machine-verified. | Yes |
| E3 | 1,3 | same, step 1 + new "Sanity checks" | The date is now a **required fact** ("an age alone does not tell the reader which night was covered"); age and date are computed separately. Added a cheap self-check: `anchor_date − T_date` must equal `calendar_days`, and must be `days` or `days+1`, never more — exactly the invariant the 5/5 failure violates. | Yes — output only |
| E4 | 1 | `shared_context.md` → Grounding | Domain-general: **"An age is not a date — compute and report both."** Derive the date from the older timestamp, not by subtracting an age from an approximate reference time (crosses a midnight ~half the time); check the date is N or N+1 days before the reference. Applies to AAP2 `finished`, Babylon `modified`, cost report periods. | Yes — no rule loosened |

## Verify-the-fix (the decisive check)

Ran the **new** procedure literally on the real payload, using only facts the agent provably
had — the sibling epochs, the stale epoch, and the stated stand-up date — and **withholding
the anchor's time of day**, which is the thing it guessed wrong:

```
step1 duration : 9 days 5h36m
step2 cal_days : 20775 − 20766 = 9  ->  2026-11-18 − 9d = 2026-11-09
step3 tod      : 1794190500 % 86400 = 8100 -> 02:15 UTC
=> "2026-11-09 02:15 UTC", 9 days old        matches golden alias: True
sanity check  : cal_days == days or days+1 ? True (9, 9)
```

**Step 3 is what actually fixes this task.** Reading time-of-day off `T % 86400` removes the
dependence on the anchor's clock time entirely — the precise quantity the agent was
hallucinating. Steps 1–2 already produced `9 days`, which 5/5 trials got right. So the edit
changes behaviour at exactly the point the trace goes wrong, rather than being merely
plausible advice: under the old text the agent had **no way** to obtain the time of day except
by subtracting from a guess; under the new text it never needs the anchor's clock at all.

Also verified: `days-stale` (currently 0/5 missed) is preserved — step 1 is unchanged in
substance. No forbidden action name (`get_check_results`/`get_last_check`) appears in either
edited file; no task-specific noun (host, service, `restic`, `backup`, either real epoch, or
either real date) appears anywhere in my new text — grepped to confirm.

## Non-overfitting restatement

Every added rule restates without a task-specific noun: *"a stored record's calendar date must
be derived from its own timestamp, not by subtracting its age from an approximately-known
reference time; and the day offset between two timestamps is their day-number difference, not
the floor of their elapsed duration."* No hostname, service, count, or date from this task
appears. The worked example uses invented values in a different month, deliberately picked to
exhibit the general midnight-crossing case that this task's own values do *not* exhibit — so
the example teaches the class, not the instance.

## Process & features used
- **Subagent:** one read-only verification subagent, handed the arithmetic claims as
  propositions to refute over 2000 random pairs. It established the 51.9% failure rate and
  independently caught that iteration 1's example was wrong (its claim 6). I did **not** fan
  out per-trajectory: 4 of 5 trials are token-identical, so per-trace agents would re-derive
  one fact five times. Fan-out suits many distinct clusters; the leverage here was adversarial
  *numeric* verification, so that is where the agent went.
- **Prior iterations read:** `prior_iterations/cand_0001/` (PROCESS.md + diff.patch). This
  iteration is a direct correction of that diff, not a new direction.

## Good things to PRESERVE
- **Single `get_services` call, `tool_calls` = 1.0** — unbroken across 34 trials. Recommend
  writes in prose only; never add an action name to these files.
- **The staleness / `enable_active_checks` / "cannot confirm" reasoning and the avoided
  forbidden phrase** — 5/5; `days-stale` is now 5/5 too. Do not re-argue any of it.
- **Deriving time-of-day from `T % 86400`** — the load-bearing line. Anything that
  reintroduces "subtract the age from the anchor's wall-clock time" reinstates the bug.

## Deliberately skipped
- **Routing** — `services=["icinga"]`; all trials reached the right agent with the right call.
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
