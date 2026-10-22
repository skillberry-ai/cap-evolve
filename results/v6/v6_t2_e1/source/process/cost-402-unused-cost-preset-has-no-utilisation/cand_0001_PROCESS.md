# PROCESS — what I did this iteration (explainability; REQUIRED)

## 0. First finding: the task is NOT flaky

The brief lists this task as FLAKY (reward 0.84, "pass sometimes"). That framing is
wrong and it matters, because "make the good behavior consistent" would have sent me
hunting variance that does not exist.

All 10 seed trials score **exactly 0.84** (`completion=1.0, tool_calls=1.0,
answer=0.8`), stderr 0.0. A read-only subagent over all 10
`verifier/reward-detail.json` + `agent/agent.jsonl` pairs found that in **10/10** seeds:

- routing is correct (cost agent), the golden tool call is made, `tool_calls=1.0`
- both `counts` facts pass ($2,847.36 total; p4d at $1,212.49)
- the single `forbidden` fact (`zero-utilisation`) is **never** hit
- the **same single** required fact is missed every time: `zeros-not-measured`

Deterministic single-point failure with a hard ceiling of 0.84 = 0.2·1.0 + 0.8·0.8,
i.e. 1 of 2 required answer facts. There is exactly one thing to fix.

## 0b. The mechanism

`query_aws_capacity_manager(metric=unused_cost, group_by=instance-family)` returns real
per-family rows and a real `unused_estimated_cost_usd`, but its `totals` block also
carries `overall_utilization_pct: 0.0` and `total_estimated_cost_usd: 0.0`. Those are
**unfilled placeholders**: the `unused_cost` preset only requests the two
unused-capacity metrics, so total-capacity metrics are never measured and the roll-up
falls back to 0.0.

How each seed explained those zeros:

| explanation | seeds |
|---|---|
| data gap / cache lag / sync delay / backend issue / "not populating" | 0, 1, 3, 4, 5, 9 (**6**) |
| preset scope — closest to correct, but no grading keyword | 2, 8 |
| cross-account aggregation gap | 7 |
| no explanation at all | 6 |
| **placeholder / never requested** | **0** |

The dominant failure is a **confident, invented infrastructure cause**. The agent treats
an absent-by-design field as a system fault, then re-queries to "fill it in"
(`metric=utilization`, `group_by=account-id`, Cost Explorer, cost-monitor). Those return
empty — and the agent reads the emptiness as *confirmation* of the outage story. That
self-reinforcing loop locks in the wrong answer and burns 2–4 wasted calls per trial.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | A — preset-unrequested field reported as a measurement | cost-402 (10/10 trials) | Agent does not know which `totals` keys a given metric preset actually populates; reads an unfilled `0.0` as a reading or as a data gap | KNOWLEDGE | Prose rule + per-preset field table + worked example in `cost_agent.md` |
| 2 | B — absent value attributed to an unverified outage | cost-402 (6/10 trials, same task) | No rule forbids inventing a cause (cache lag / sync delay / backend) for a missing field; and a follow-up empty result is misread as confirming it | BEHAVIORAL | Domain-general grounding rule in `shared_context.md` |

Only one task exists in this split, so clusters are failure *mechanisms* within it
rather than distinct tasks. A and B co-occur in the same trials; A is the graded miss,
B is the reasoning error that produces it.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | KNOWLEDGE | `cost_agent.md` | New section after the preset list: table of which `totals` keys each preset (`utilization`/`unused_cost`/`inventory`) measures vs. returns as unfilled `0.0`; MANDATORY 4-step reporting rule; "do not re-query to fill in such a zero"; generic worked example. Generalizes to any preset/scope-dependent API field, not this family or window. | Yes — adds knowledge only; does not alter routing or the tool call that already scores 1.0 |
| B | BEHAVIORAL | `shared_context.md` | Extends the existing *Grounding — Use Tool Results, Never Hallucinate* section: classify `0`/`null`/`""`/`[]` as real-measurement vs never-requested before reporting; guards **both** directions (never quote a placeholder as a value or derive a share from it; never attribute an absent field to cache lag/outage unless a tool said so). No cost/ODCR/preset nouns. | Yes — tightens an existing grounding rule with a condition; does not loosen any rule |

## Verify-the-fix (the trace it targets → what it now does on those exact inputs)
I ran the scenario's **real** `tests/verify.py` against `tests/expected.json` on
transcripts reconstructed from the actual seed-0 `agent.jsonl` (keeping the golden call).

- Target answer the edits aim to produce → **reward 1.000** (answer 1.00, `required_missed` empty).
- Baseline "data gap / cache lag" phrasing → **reward 0.840**, `missed=['zeros-not-measured']` — reproduces the observed score exactly, confirming the diagnosis.
- Robustness, so the gain is not an artifact of copying my example verbatim — four *independent* paraphrasings a reader following the rule might write:

| variant | reward |
|---|---|
| "never requested, so never measured" | **1.000** |
| "placeholders for metrics this preset does not request" | **1.000** |
| "only requests the two unused-capacity metrics" | **1.000** |
| "this preset doesn't measure total capacity" | **1.000** |
| (control) "data gap … likely a cache lag" | 0.840 |

- `tool_calls` safety: matching is `unordered-subset` over a single expected call with no forbidden calls, so the "don't re-query" clause keeps `tool_calls=1.0` (verified at one call) and cuts cost.
- Forbidden-fact safety: my worked example quotes "0% utilisation" / "100% of reservation spend wasted" as things *not* to say. The verifier is polarity-aware and excuses an occurrence whose sentence carries an `attributed_to` phrase; that sentence ends "…would be wrong", which is on that list. The 1.000 run includes the sentence verbatim — measured, not assumed.

## Process & features used
- Subagents / worktrees / parallel features used: one read-only `Explore` subagent fanned out across all 10 trial dirs to classify the failure mode per seed — this is what established determinism and the 6/10 "invented outage" split. No worktrees: the diagnosis collapsed to one mechanism in two files, so parallel edit-agents would have added merge risk for zero coverage gain.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md: none exist (iteration 1; RUNMAP has no rows, LEDGER is baseline-only, `rejected.jsonl` absent). Nothing to build on or avoid yet.
- Also read the scenario's own `provenance.md`, `golden.json`, `expected.json` and `verify.py` to ground the diagnosis in the grading contract rather than guessing at it.

## Good things to PRESERVE (do not let a future iteration undo these)
- The agent already routes correctly and makes the single right tool call — `tool_calls=1.0` in 10/10. Do not edit routing for this task.
- `share-not-from-this-call` already passes in 10/10; Edit A step 4 reinforces it without changing the phrasing that works. Do not rewrite that.
- The forbidden fact is never hit at baseline — do not add text that asserts a 0% / 100% figure outside an attributed ("would be wrong") sentence.

## Deliberately skipped (cluster + why)
- **`orchestrator.md`** — `task.toml` has `services=["cost"]`; footprint is `orchestrator.md` + `shared_context.md` + `cost_agent.md`, and routing was right in 10/10. Editing it is unmotivated risk.
- **New tool / code guard** — not needed and out of scope this phase. The tool already returns everything required to distinguish measured from unfilled; the gap is purely knowledge. No capability escalation for this task.
- **Harness observation (not actioned here):** the task is mislabelled FLAKY when per-task stderr is 0.0 and all trials tie. Recorded in `FRAMEWORK_IMPROVEMENTS.md`.

## Risk / non-overfitting
My first draft of the worked example hardcoded this task's literals ($2,847.36, "six
families"). I caught and genericized it to `$U` / "per-dimension" — the rule now names
no family, GUID, hostname, count, or window. Restating it without task-specific nouns:
*"a field a query never requested comes back as an unfilled zero; report it as unmeasured
rather than as a value or an outage, and name the query that measures it."* That holds
for any preset/scope-dependent API, which is why I expect it to generalize rather than
score for the wrong reason.

Residual risk: both edits lengthen already-long files, which can dilute attention for a
sonnet-tier reader. I placed Edit A directly adjacent to the preset list it qualifies —
the text the agent is reading when it makes this exact mistake — rather than appending
preamble.
