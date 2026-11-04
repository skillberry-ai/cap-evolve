# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I diagnosed (not from the trajectory stubs — read this first)

`./trajectories/*.json` carry only reward summaries — `trace: null`, `tool_calls: []`. The
real signal is in the `metadata.trial_dir` each stub points at. Under
`…/_run/jobs/v6_g2_e1/icinga-206-stale-ok-check/seed-*/…` each trial has
`verifier/reward-detail.json` (exactly which required facts were missed) and
`agent/agent.jsonl` (full transcript incl. final answer). I aggregated per-fact misses
across **all 29 trials** rather than reasoning from the single `feedback` line.
**Future iterations: do this first — it is the whole diagnosis.**

Measured miss distribution (n=29):

| count | missed facts |
|---|---|
| 18 | *(none — scored 1.0)* |
| 8 | `last-check-date` **and** `days-stale` |
| 3 | `last-check-date` only |

`tool_calls` = 1.0 and `completion` = 1.0 in **every** trial. 100% of lost reward is the
`answer` metric, concentrated in one mechanism.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **A — epoch timestamp never converted to a calendar date** (11/29 trials) | icinga-206-stale-ok-check | `last_check` comes back as 10-digit epoch seconds. The agent has no clock and no conversion procedure, so it *eyeballs* a date off the integer's magnitude. Guesses scatter in both directions by up to 20× ("~22 hours", "~18.6 hours", "31 days", "2026-11-05", "2026-11-15"; truth `2026-11-09 02:15 UTC` / 9 days). Misses the date fact and, usually, the derived day-count. | CAPABILITY-GAP (arithmetic, not reasoning) | KNOWLEDGE + worked example: anchor-and-difference recipe in domain file |
| 2 | **B — freshness fields absent from the extraction contract** (enabler for A) | icinga-206-stale-ok-check | Step 0's "extract from the service object" list omits `last_check`, `execution_end`, `enable_active_checks`, `check_interval`. Agent had to notice the freshness angle unprompted, and the report template had no slot to put it in. | KNOWLEDGE | CONTRACT: extend extraction list + output-format header line |
| 3 | **C — risk of ratifying the user's stated premise** (0/29 observed; latent) | icinga-206-stale-ok-check | `kind = "trap"`: user opens "I'm planning to report backups OK". No trial tripped the forbidden phrase, so this is **not** a measured failure — guarded only because it is the task's designed trap and cheap to state domain-generally. | BEHAVIORAL | BEHAVIORAL rule in shared_context |

**Key framing for cluster A:** this is *not* a reasoning failure. All 29 trials — including
every failing one — named the staleness, named `enable_active_checks: false`, and avoided
the `backup-ok` forbidden phrase. The agent fully understands the trap; it just cannot do
the arithmetic reliably. The one passing trial I read did long-hand epoch math, **got it
wrong on the first attempt** ("435th day past Sep 1 — that overshoots"), noticed, re-anchored,
and landed correctly. So the capability is present but unguided, and the task's flakiness is
the variance of an ad-hoc calculation. Making that calculation deterministic is the lever.

## Changes made this iteration (one row per edit — aim for MULTIPLE classes, incl. a NEW tool when a cluster needs one)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | KNOWLEDGE + worked example | `icinga_agent.md` → new **Step 0.05 "Date the Result Before You Trust It"** | 5-point freshness protocol (convert → age → compare vs `check_interval` → check `enable_active_checks` → sibling services as control) plus an **anchor-and-difference** conversion recipe: take the freshest `last_check` in the payload as the ≈now anchor, difference the epochs, then `//86400`, `%86400//3600`, `%3600//60`, and subtract whole days from the anchor's calendar date. Generalizes to any "is this state current?" question — never names a host, service or backup. | Yes — adds no action name; anchor data comes from the *same* `get_services`+`host` call already expected, so no extra/forbidden call |
| A | KNOWLEDGE (worked example) | `icinga_agent.md` same step | Fully worked numeric example on **invented** timestamps (`1772614020`/`1772233920`, March 2026), unrelated to this task's values. Arithmetic verified internally correct so the reader does not learn from a wrong example. Reader tier is `sonnet-4-6` — guidance says add a worked example for tricky formats. | Yes |
| B | CONTRACT | `icinga_agent.md` Step 0 list, Step 1 Triage, Output Format | Added `last_check`/`execution_end`, `enable_active_checks`, `check_interval` to the extraction list; added a "Date the State" triage bullet; added a **Last checked / Active checks** line to the report header, and "lead the summary with staleness, not the state word" when stale. Failing trials all *produced* a report — the fact needs a slot or it stays optional. | Yes — output additions only |
| C | BEHAVIORAL | `shared_context.md` → "Grounding" | Two domain-general rules: (1) **every record has an as-of time** — when the question names a window, convert the record's timestamp and confirm it falls inside, else say the data cannot confirm it; derive ages by differencing, never report an uncomputed estimate. (2) **do not ratify the user's stated conclusion without evidence.** Both apply to AAP2 `finished`, Babylon `modified`, cost report periods — every domain serves timestamped records against windowed questions. | Yes — no existing rule loosened |

I deliberately did **not** put the epoch arithmetic in `shared_context.md`: epoch-seconds
`last_check` is an Icinga-payload convention, so it belongs in the domain file.

## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)
- **Cluster A/B (the 11 failing trials):** running my own recipe literally against the real seed values — anchor `1794988260` (freshest sibling `last_check`) − stale `1794190500` = `797760`s → `797760//86400 = 9 days`, 5h36m; anchor calendar date `2026-11-18` − 9 days = **`2026-11-09`** (exact `02:15 UTC`, matches golden). Both missed facts (`last-check-date`, `days-stale`) fall out of subtraction and integer division alone. The `days-stale` count wants `9` within a 4-token window of "days", which "**9 days** 5h36m stale" satisfies.
- **Tool-call protection:** grepped both edited files to confirm neither now mentions the forbidden `get_check_results` / `get_last_check`; no new action name introduced. The sibling-anchor rule consumes the other services already returned by the expected single `get_services`+`host` call.
- **Near-miss I caught:** my first draft said to "re-enable/reschedule the check", which risked nudging a `reschedule_check` **write** call and breaking the clean 1.0 tool_calls score in all 29 trials. Reworded to recommend in text only and defer to the existing Write Operations rule.
- **Cluster C:** not verifiable against a failing trace (0/29 tripped it) — stated as a latent guard, not a claimed fix. If val does not move, this edit is the one with no evidence behind it.

## Process & features used
- Subagents / worktrees / parallel features used (or: "serial fallback because …"): **Serial, deliberately.** The fan-out guidance targets many clusters across many trajectory groups; here the split is a single task and the measured misses collapse to one mechanism in one file. Per-trajectory diagnostic subagents would have re-derived the same two facts 29 times. The leverage was instead in aggregating `reward-detail.json` across all trials programmatically (one script, exact per-fact counts) rather than reading traces in parallel.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md (which, and what I learned): **None exist** — this is iteration 1/5, RUNMAP's table is empty, `rejected.jsonl`/`history.jsonl` absent. Nothing to build on or avoid yet.

## Good things to PRESERVE (do not let a future iteration undo these)
- **The clean tool-call score.** `tool_calls` = 1.0 in 29/29: a single `get_services` with `host`, no forbidden actions, no write calls. Any future edit that encourages extra verification calls, a recheck, or "re-enable active checks" as an *action* can break this. Recommend writes in prose only.
- **The staleness / active-checks / cannot-confirm reasoning already hits 29/29.** Do not spend prompt budget re-arguing it; it is not broken.
- **The anchor-and-difference framing specifically** (relative difference against an in-payload timestamp), not "convert the epoch". The agent has no clock and the scenario date postdates its training, so absolute epoch→date is the operation it cannot self-check; the relative one needs only arithmetic and yields the day-count as a by-product.

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- **Routing.** `task.toml` `services=["icinga"]`; all 29 trials reached the icinga agent with the correct call. `orchestrator.md` untouched — no routing defect exists to fix.
- **The staleness / `enable_active_checks` / "cannot confirm" facts.** Hit in 29/29 trials. Only reinforced structurally (an output slot), with no new argument.
- **Any rule keyed to backups, snapshots, restic, or this host.** Overfitting; the mechanism is "a state field reported without its timestamp", which is host- and service-agnostic.

## Escalation (tooling gap, outside this phase's edit space)
No tool converts epoch→wall-clock and the agent has no clock. The prose recipe is a genuine
workaround, not the structural fix: a `now()`/time-formatting helper, or an MCP layer that
renders `last_check` as ISO-8601 alongside the raw epoch, would make this failure class
impossible rather than dependent on the model doing long division correctly. **Recommend for
the tools phase.** Residual risk my edit cannot remove: the one trial that got the date right
still needed two attempts at the arithmetic.

---

# DIAGNOSIS.json — see sibling file `DIAGNOSIS.json` in this directory.
