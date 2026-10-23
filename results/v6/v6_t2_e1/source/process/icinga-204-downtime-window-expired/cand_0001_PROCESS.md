# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I diagnosed (the key move this iteration)

The `trajectories/*.json` files carry `trace: null` and `tool_calls: []`, so they
alone cannot tell you *why* a trial lost points. But each one's
`metadata.trial_dir` points at a live harbor trial directory that still exists on
disk, containing both `agent/agent.jsonl` (the full transcript) and
`verifier/reward-detail.json` (the **per-rubric-item** miss list).

Joining those two across all 10 val trials turned "reward 0.69, answer=0.5" into an
exact, itemized failure table. This is the highest-leverage thing I did; a future
iteration should start here rather than reasoning from the reward number.

Measured misses over the 10 val trials (rubric has 6 required + 1 count + 1 forbidden):

| rubric item | trials missed | what it wanted |
| --- | --- | --- |
| `future-start` | **10 / 10** | the later window's start date |
| `hours-since-end` | **10 / 10** | the exact offset from the stated "now" to the expired window's end |
| `expired-end` | **8 / 10** | the earlier window's end date |
| `not-covered` | 3 / 10 | an unambiguous "no downtime is in effect" phrasing |
| `on-record` (count), `first-author`, `second-author`, `claims-covered` (forbidden) | **0 / 10** | — already solid every trial |

So the agent reliably made the right single tool call (`tool_calls=1.0` in 10/10),
reliably named both authors and both purposes, and reliably avoided the
"calendar must be right" trap. It lost ~all of its missing answer weight on
**converting timestamps** and on **phrasing the coverage verdict**.

### Root cause, read off the transcripts

Icinga returns all times as Unix epoch seconds. The agent has **no shell and no
date tool** (tool list is `query_icinga`, `fetch_github_file`,
`search_github_repo`), so it must convert epochs by hand — and it got them wrong
in essentially every trial, in a way that was *internally confident but numerically
off*. The same epochs were reported as, among others:

- `1794938400` → "2026-11-16 10:00", "2026-11-16 06:00", "2026-11-17 14:00",
  "2026-11-16 ~12:00" (truth: **2026-11-17 18:00 UTC**)
- `1795204800` → "2026-11-19 08:00", "2026-11-19 12:00", "2026-11-19 04:00"
  (truth: **2026-11-20 20:00 UTC**)

The dates drift by 1–2 days and the hours by up to 8, with no consistent bias —
the signature of eyeballing rather than dividing. Two of the three downstream
rubric items are *dates*, and the third (`hours-since-end`) is a subtraction from
those dates, so one upstream arithmetic error cost three items at once.

Crucially, the transcripts also showed what *fixes* it: in the minority of trials
where the agent wrote out an explicit anchored division ("anchor Nov 2026 =
1793491200; diff = …; floor(diff/86400) = …"), it landed on **2026-11-17 22:00**
and **11 hours 30 minutes** exactly. The good behavior already exists in the
policy's repertoire and is simply not reliably invoked — which is exactly the
profile of a flaky task, and what makes an explicit procedure the right lever.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Epoch timestamps converted by estimation, not arithmetic (costs every date item + any derived offset) | icinga-204-downtime-window-expired | Icinga returns epoch seconds; no shell/date tool; prompt never says to convert or how | KNOWLEDGE | add an explicit, verified conversion procedure + worked example to `icinga_agent.md` |
| 2 | "A downtime exists" conflated with "a downtime is in effect"; verdict phrased too weakly to read as an answer | icinga-204-downtime-window-expired | prompt's only downtime guidance assumes the in-downtime case; no rule for expired/future windows or for stating the negative verdict | BEHAVIORAL | add coverage-adjudication + premise-testing rules to `icinga_agent.md` |
| 3 | Direct state questions answered via the alert-triage template, so asked sub-questions get dropped | icinga-204-downtime-window-expired | `Output Format` offers only a triage shape | BEHAVIORAL | scope the template + require per-object coverage of each asked clause |

## Changes made this iteration

All three edits are in `icinga_agent.md` — the single domain file this task reads
(`task.toml` has `services=["icinga"]`; `orchestrator.md:84` routes it to
`investigate_icinga`). Nothing went into `shared_context.md`: epoch-seconds
timestamps and downtime-window semantics are Icinga-specific, and the other five
domain agents would only be diluted by them. `orchestrator.md` is untouched —
routing was correct in 10/10 trials.

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE (procedure + worked example) | `icinga_agent.md` → new "Timestamps — Icinga Returns Epoch Seconds, Always Convert Them" | Names every epoch-valued Icinga field, then gives a 4-step anchored conversion with a year-anchor table (2024–2030), a leap/non-leap cumulative-days table, a worked example, and a re-addition self-check. Also: treat a stated "now" as the clock, convert it to an epoch via the reverse formula, and report offsets in exact units. Applies to any Icinga field in any task, not just downtimes. | Yes — adds a method where there was none; changes no tool choice or action |
| 2 | BEHAVIORAL (decision rule) | `icinga_agent.md` → new subsections under Step 0 | Per-row coverage adjudication: read `is_in_effect` as authoritative, cross-check `start/end` vs now, treat `trigger_time == 0` as never-started, distinguish host-level (empty `service_name`) from service-level scope, and trust the flag over your own arithmetic. Plus: treat a user's "maintenance should be covering this" premise as a claim to test, lead with the explicit negative verdict, attribute the external claim, and account for every row returned. | Yes — the pre-existing "if in downtime, report it first" guidance is preserved verbatim; this adds the not-in-effect branches it never covered |
| 3 | CONTRACT (output scoping) | `icinga_agent.md` → preamble to `Output Format` | Direct state questions are answered in their own terms first rather than forced into the triage template; and every clause the user asked must be answered for every object reported. | Yes — triage template itself unchanged; only scoped |

## Verify-the-fix

- **Cluster 1 / `expired-end`, `future-start` (18 of 28 missed items).** I executed
  the exact procedure I wrote, in Python, against this task's real epochs: it
  yields `1794952800 → 2026-11-17 22:00 UTC` and `1795204800 → 2026-11-20 20:00
  UTC` — both rubric-matching. I then fuzzed the forward procedure over **60,000**
  random epochs spanning 2024–2030 against `datetime.fromtimestamp`: **0
  mismatches**. So an agent that follows the text lands on the right date, and the
  tables/anchors I published are arithmetically correct rather than plausible.
- **Cluster 1 / `hours-since-end` (10/10 missed).** Fuzzed the reverse
  (date → epoch) formula over 20,000 random datetimes: **0 mismatches**. It maps
  the stated now to `1794994200`, and `(1794994200 − 1794952800)/3600 = 11.5`
  exactly — the rubric value. The "carry a half hour as `.5`, don't round" rule
  targets the observed failure directly: trials that *did* reason about the gap
  wrote "~43 hours" / "two days ago" / "~15.5 hours", and the rubric accepts only
  exact half-hour forms.
- **Cluster 2 / `not-covered` (3/10 missed).** I checked the three failing trials
  against the rubric's accepted phrasings: all three had the reasoning right and
  lost the item purely on wording — "neither downtime is active at 09:30 UTC",
  "neither is currently in effect". The new rule tells the agent to lead with
  "no downtime is in effect" / "no active downtime", which are accepted forms.
  This is a phrasing-reliability fix, which is the correct shape for an item that
  fails 3/10 rather than 10/10.
- **Forbidden item `claims-covered` (0/10 hit) — protected, and deliberately so.**
  My premise-testing rule could in principle push the agent toward discussing the
  calendar's claim and tripping the forbidden phrases. The rubric exempts those
  phrases when attributed, so I wrote the attribution requirement explicitly
  ("the change calendar says …, but Icinga shows …") and an outright prohibition on
  asserting "is in maintenance" on calendar evidence. The instruction to trust
  `is_in_effect` over one's own arithmetic points the same way.

## Process & features used

- **Subagents / worktrees / parallel features used (or: "serial fallback because …"):**
  Serial, deliberately. The run-level guidance suggests one subagent per
  trajectory-group. I read all 10 trials directly instead: they are trials of a
  *single* task, the joined verifier detail showed one dominant mechanism
  (two rubric items missed in 10/10 and a third in 8/10, all downstream of the
  same arithmetic), and every edit lands in one file. Fanning out would have
  produced merge surface and parallel rediscovery of the same cause with no
  coverage gain. I did use scripted joins over the trial dirs to tally misses, and
  Python to *verify* every table and formula before publishing it.
- **Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md:** none exist —
  this is iteration 1/5. `rejected.jsonl` and `history.jsonl` are both
  absent/empty, `LEDGER.md` has only the baseline row, and `prior_iterations/` has
  not been created. Nothing to build on or avoid yet.

## Good things to PRESERVE (do not let a future iteration undo these)

- `tool_calls` scored **1.0 in 10/10** and `completion` **1.0 in 10/10** — the
  single `get_downtimes` call with the host filter is exactly right. Do not add
  guidance that encourages extra exploratory calls here.
- Authors, purposes/change refs, and the downtime **count** were never missed. The
  existing prose already gets those; don't churn it.
- The `claims-covered` forbidden item was never tripped. Any future edit touching
  the premise-testing language must keep the attribution requirement.
- The pre-existing "if the service is already in downtime, report this first" line
  is load-bearing for the in-downtime case — my edit adds branches around it
  rather than replacing it.

## Deliberately skipped (cluster + why)

- `orchestrator.md` — routing to `investigate_icinga` was correct in all 10 trials;
  no discriminating condition to add.
- `shared_context.md` — considered putting the epoch rule there, since other
  domains also surface timestamps, but rejected it: the concrete fields, the
  `is_in_effect` semantics, and the anchor tables are Icinga-specific, and the
  instructions are explicit that only genuinely domain-general rules belong there.
  If a future iteration sees the *same* estimated-timestamp failure in a non-Icinga
  domain, promoting the conversion procedure (not the Icinga field list) is the
  right follow-up.
- The other five domain agents — not read by this task.

## Escalation (capability gap, not fixable by prose)

The real fix for cluster 1 is a tool, not a prompt. The agent is asked to do exact
calendar arithmetic on epoch integers with no shell, no `date`, and no code
execution; the prompt can only supply a hand-division procedure and hope it is
followed. A one-line `epoch_to_utc` / `utc_to_epoch` helper — or simply having
`query_icinga` return ISO-8601 alongside each epoch field — would make this entire
failure class structurally impossible instead of probabilistically mitigated.
**Recorded here as the honest finding; this phase has no tools/code layer.** If a
later phase opens one up, do that instead of hardening this prose further.

---

# DIAGNOSIS.json

Written as `DIAGNOSIS.json` in this directory.
