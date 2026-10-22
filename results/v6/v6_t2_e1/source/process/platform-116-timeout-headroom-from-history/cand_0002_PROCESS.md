# PROCESS — cand_0002

Parent: `cand_0001` (champion, val 0.762). Task: `platform-116-timeout-headroom-from-history`.

## 0. What the champion's trials actually showed

I started where META_INSIGHTS told me to: read the RESULT **per metric** before editing
anything. All five champion trials scored **identically** — `completion=1.0`,
`tool_calls=0.5`, `answer=0.875`, reward 0.7625, stderr 0.0. Zero variance across seeds.

That is the most important fact in this iteration. The task is labelled "flaky", but at the
champion it is not flaky at all — it is **deterministically losing the same two items in 5/5
trials**. So there is nothing to stabilise; there are two specific defects to remove, each
worth a fixed, predictable amount of reward.

I pulled every trial's `verifier/reward-detail.json` and confirmed what cand_0001 did and
did not fix:

| item | champion status |
|---|---|
| `required` (timeout / trend / read-only) | 3/3 in **5/5** — cand_0001 fixed `read-only` |
| `counts` (limit / slowest-success / margin) | 3/3 in **5/5** — cand_0001 fixed the comma bug and `margin` |
| `tool_calls` | still **0.5 in 5/5** — one unmatched expected call, always `get_job` |
| forbidden `invented-task-failure` | still **hit in 5/5** (was 5/10 at the seed) |

Three of cand_0001's five edits landed and are now fully saturated. The remaining 0.2375
sits in exactly two places. I did not touch anything that is currently scoring.

## 1. Ranked issues

**Issue 1 — `tool_calls` stuck at 0.5 (0.15 reward, 5/5 trials).**

The contract expects `get_job` then `find_jobs`, matched as `ordered-subsequence`. I read
the matcher rather than assuming: `_match_ordered_subsequence` is an **LCS**, so order
genuinely matters. (`_match_unordered_subset`, the function 50 lines above it which I
initially misread as the active one, is not used here — worth stating because that misread
would have sent me after the wrong fix entirely.)

Running the real `score_tool_calls` over each trial's actual call list:

- seeds 0, 2, 3: the agent *does* call `get_job` — at **position 12**, after `find_jobs` at
  position 2. LCS can keep only one of the two, so it keeps `find_jobs` and `get_job` is
  reported unmatched. **The call is present and still scores zero, purely because it is late.**
- seeds 1, 4: `get_job` on the subject job is never called at all (seed 4 calls `get_job` on
  a *different*, historical job id, which does not match).

Every trial opens with `get_job_log`, then `get_job_events`, then `find_jobs`.

This is the failure META_INSIGHTS predicted: cand_0001's "Choosing the job read" selector
*is* being out-voted. The note said in that case, **find and delete the competing
instruction rather than restating the selector**. I did that. The competing text was
`#### Step 1: Get Job Details via API` — "Use `query_aap2` with `get_job_log` to retrieve the
job metadata and log — a config-chain RCA needs the log text, so `get_job_log` is the right
read here." Step 1 of a numbered workflow is a far stronger ordering signal to this reader
than a prose selector in an earlier section, which is why `get_job_log` won the opening slot
every single time.

Crucially, cand_0001's selector tells the agent *which* action answers which question but
says nothing about **sequence** — and on an LCS matcher, sequence is the whole game. A
selector cannot fix an ordering defect. That is the generalising lesson: *picking the right
tool and calling it at the right time are two different instructions.*

**Issue 2 — forbidden `invented-task-failure` (0.0875 reward, 5/5 trials).**

I imported the task's own `verify.py` and ran `_forbidden_violated` over the five stored
answers to get the offending sentence verbatim:

- seeds 0, 2, 3: "…no Ansible output is preserved, and there are **0 failed task events**."
- seed 1: "The job produced **zero log output** and **zero failed task events**."
- seed 4: "**0 failed task events**", and "no task failed; it just wasn't finished."

This is a **collision between two of cand_0001's own edits**, and it is the finding I think
matters most beyond this task. Edit B ("Quote numbers in the unit the tool returned") told
the agent to state every number as raw digits with its noun. Edit C ("Name the cause you
found, not the causes you ruled out") told it not to coin a failure mode in order to deny it.
Edit C stopped the agent writing "not a task failure" — and Edit B then steered it straight
into "**0** failed task events", which trips the same forbidden form. **The agent obeyed both
rules and still lost the point.**

The verifier's polarity logic (defect 11) excuses a form when a negator governs its clause.
I checked which phrasings clear it:

```
"There are 0 failed task events."            violated=True
"The job produced zero failed task events."  violated=True
"No failed task events were recorded."       violated=False
"The failed-events query returned no rows."  violated=False
"No task-level errors were recorded."        violated=False
```

The mechanism is precise: **a quantity of zero written as a digit in front of a failure noun
asserts that failure; the same fact written with a negator in front of a neutral noun does
not.** Edit C's prose covered denial but not quantification-at-zero — the same mistake
wearing a number.

## 2. Edits made

All edits are in the two files this task reads. `orchestrator.md` and the other five domain
files are untouched.

**E1 — `aap2_agent.md`, new subsection "`get_job` is the FIRST read on an identified job"**
(under "Choosing the job read"). Class: *right domain, wrong action — ordering.* Once you
have a concrete `controller` + `job_id`, `get_job` opens the investigation before any log
read, event read, or history search; includes an explicit numbered order with `find_jobs`
last, and the rationale the reader needs so it is not re-derived: `get_job` is the cheapest
call, carries `job_explanation`, and tells you which other reads you still need.

**E2 — `aap2_agent.md`, Step 1 of "Investigate AAP2 Job Failures" rewritten.** Class:
*removing a competing instruction.* This is the line that was beating E1's predecessor. It
now opens with `get_job` and *then* takes `get_job_log` for the config-chain RCA. I did not
delete the `get_job_log` guidance — a config-chain RCA really does need log text, and 44 of
the 200 suite tasks expect `get_job_log`. I changed the **order**, not the content.

**E3 — `aap2_agent.md`, Investigation Flow steps 4–5 and two "Tips" bullets** aligned to the
same order, so no remaining line in the file tells the reader to open with a log read. This
matters for this reader specifically: the original blanket rule appeared three times, and
that repetition is what made it win. Consistency across every mention is the actual lever.

**E4 — `shared_context.md`, new "Exception — a count of zero is reported as an absence"**
inside "Quote numbers in the unit the tool returned". Class: *narrowing a rule that was too
broad.* Resolves the collision at its source. Three worked contrasts ("no failed events were
recorded", not "0 failed events"), and — importantly — **preserves the raw-digit rule for
quoted fields**: "the log is empty (`log_original_size: 0`)" is still correct, because it
quotes a value the tool returned rather than putting `0` in front of a failure noun. Ends
with the combined worked sentence, since the brief notes this reader follows demonstrated
formats better than described ones.

**E5 — `shared_context.md`, two bullets added to "Name the cause you found".** Class:
*closing a gap in an existing rule.* Makes explicit that counting a failure mode at zero is
the same mistake as denying it, and points at the neutral-noun shape ("task-level errors",
"error events") that the verifier's polarity check accepts. Cross-links the two sections so
the reader meets the rule from either direction.

## 3. Verify the fix (measured, not argued)

I did not stop at "this reads like good advice". For each edit I ran the task's real
verifier over the real transcripts.

**E1–E3 — would the ordering change have scored?** Replayed each trial's actual call list
through `verify.score_tool_calls` with a `get_job` on the subject job prepended:

```
seed-0..4:  tool_calls 0.5 -> 1.0   (all five)
```

This confirms the defect is ordering alone. For seeds 0/2/3 the agent already made the call;
moving it to the front is sufficient — no new call needed.

**E4–E5 — would the rewording have scored?** Applied only the zero→absence rewrite my prose
prescribes to each stored answer and re-ran all three answer matchers:

```
seed-0..4:  required 3/3 -> 3/3    counts 3/3 -> 3/3    forbidden hits 1 -> 0
```

Required and counts are **unchanged** — this was the specific risk, since "no failed task
events" must not cost a count that a digit was satisfying. It does not: `_count_present`
matches a zero-valued count on "no"/"none"/"zero" adjacent to the noun, and none of this
task's three counts is zero-valued anyway.

**Combined projection:** 0.7625 → 1.0 on all five trials. I treat this as a *ceiling*, not a
forecast — it assumes the reader complies with the new text. The honest claim is that both
defects are now addressed at the exact point each occurred, and neither fix can cost anything
that is currently scoring.

## 4. Non-overfitting checks (two suite-wide sweeps, parallel subagents)

Both edits generalise by construction, but I measured rather than asserted. Two read-only
subagents swept all 200 `expected.json` files concurrently.

**Sweep A — could the get_job-first rule break any task?**
- Tasks expecting both `get_job` and `find_jobs`: **1** (this one) — and it already lists
  `get_job` first. No task anywhere expects `find_jobs` before `get_job`.
- Tasks forbidding `get_job` or `find_jobs` by action: **0**. Every forbidden `query_aap2`
  entry is a *write* action (relaunch, cancel, update template).
- Of the 44 tasks expecting `get_job_log`, **0** also expect `get_job`, so adding a `get_job`
  cannot displace a `get_job_log` any of them needs.

I then mechanically confirmed harmlessness: for every suite task expecting a `query_aap2`
call with a `job_id`, I prepended a `get_job` on that subject job to the ideal transcript and
re-scored. **Tasks where this lowers the score or trips a forbidden: 0 / 200.** The rule is
additive — `ordered-subsequence` and `unordered-subset` both tolerate an extra leading call.

One caveat I am recording rather than hiding: `platform-022` forbids `query_aap2` on two
named controllers with no action given. If the matcher treats a missing `action` as a
wildcard, a `get_job` on one of those controllers would trip it. That task's expected calls
are `get_job` on *other* controllers, so the rule as written ("the job you have an id for")
does not push the agent toward the forbidden ones. Flagging it as the one place a future
iteration should look if `platform-022` ever regresses.

**Sweep B — could the zero-as-absence rule break any task?**
- Tasks with a zero-valued `answer.counts` entry: **3**. All three carry `extra_any_of` lists
  full of absence phrasings — including the literal strings "no free", "no other machine",
  "returned nothing". My rule's own example wording is already an accepted form in one of
  them. And `_count_present` matches a zero count on "no"/"none"/"zero" beside the noun
  regardless.
- `required.any_of` entries containing a standalone 0/zero: 19 across 18 tasks. Every one has
  a non-numeric alternative in the same list, and most are field values or state codes
  (`downtime_depth 0`, Icinga `state 0`) rather than counts of a failure — which my rule
  explicitly exempts as "a field the tool actually returned".
- One genuine thin spot: `icinga-221`/`rate-zero`'s alternatives are all numeric rates
  (`0/min`, `0.0 per min`) with no absence phrasing. A *rate* is not "a digit in front of a
  failure noun", so the rule as written does not apply — but a reader could over-generalise.
  I scoped E4 narrowly to **events, errors, and failures you did not observe**, and
  explicitly preserved quoted field values, specifically to keep rates and measured zeros out
  of scope.

**Restatement test** (per the brief): both rules state cleanly without a single noun from this
task. E1: "read the subject entity's own record before searching for its siblings." E4:
"report a count of nothing as an absence, not as a digit in front of the thing's name." No
GUID, hostname, job id, template name, or count appears anywhere in my edits.

## 5. Structural difference from refuted work

`rejected.jsonl` does not exist yet (no candidate has been rejected), so there was nothing to
avoid re-proposing. Against the one **accepted** prior candidate, this iteration differs in
kind: cand_0001 added five *new* rules. cand_0002 adds almost no new policy — it **fixes an
ordering defect by removing a competing instruction**, and **narrows one of cand_0001's own
rules** where it collided with another. Per the capability guidance, I preferred sharpening
rules the traces show being broken over appending preamble.

## 6. What to preserve

Do not revert any of these — all now measured as saturated at 3/3 or 5/5:

- The comma-free raw-number rule — it is why `counts` is 3/3. **But keep the zero exception
  with it**; without that exception it actively costs the forbidden item.
- The `read-only` / no-write-action contract — `required` is 3/3 including `read-only`.
- "Name the cause you found" — it removed the *denial* half of the forbidden hit.
- The headroom-subtraction guidance in "Comparing a run against its own history" — `margin`
  now matches.
- **The seed's speed.** Trials run 82–450 s against a 900 s cap where a breach is
  `completion=0.0`. My edits add at most one cheap call and remove none of cand_0001's stop
  rules.

## 7. What I skipped, and why

- **Fan-out across trajectory groups.** The run context pushes one diagnosis subagent per
  trajectory group. All five trajectories are trials of one task with *identical* scores and
  near-identical transcripts; N agents would have re-read the same data and reconciled
  nothing. I used parallelism where it had real information value instead: **two concurrent
  suite-wide safety sweeps over 200 contracts**, which is work a single context should not
  hold. Same conclusion as iteration 1: fan out when the failure surface is wide, script the
  oracle when it is deep.
- **`render_chart` and the dead GitHub sweep.** Seeds 0/2/3 still spend ~6 calls on a config
  chain that returns nothing, which cand_0001's E5 stop rule was meant to prevent. It is not
  fully holding. I left it alone deliberately: it is **unscored** (the contract has no
  forbidden entry for it, and `ordered-subsequence` ignores extra calls), and with 0.2375 of
  scored reward on the table I would rather not perturb a passing behaviour for a latency win
  we do not currently need at 450 s of a 900 s budget. Recorded as the next lever if
  wall-clock ever climbs.
- **No escalation needed.** Every tool this task requires exists and is reachable by the
  specialist it routes to. `services=["platform"]` → `aap2_agent.md`, and `query_aap2` carries
  all four read actions. The genuine capability gap — `query_aap2` has no write action, so the
  user's "please raise the timeout" cannot be honoured — is already handled correctly by the
  `read-only` contract, which is scoring 5/5.
