# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Absent schema field reported as a measured zero/empty** (3 of 10 trials: t0, t1, t8) | cost-051-gcp-net-of-credits | The user asks for a quantity (credits / committed-use savings) for which the cost tool's response schema has **no field at all**. The agent narrates that silence as a *finding about the world* — "the export returned no credit line items", "$0 in credits" — instead of as a *limit of the tool*. `shared_context.md`'s only applicable rule ("**Empty results**: Say so clearly") actively pushes it there; nothing distinguishes "field exists and is empty" from "there is no such field". The rubric's own rationale confirms the gap: *"parsec's prompts never tell the agent so."* | KNOWLEDGE (+ a BEHAVIORAL rule that misfires) | prose rule in `shared_context.md` (general discipline) + absent-field inventory & worked answer template in `cost_agent.md` |
| — | *no second cluster exists* | — | `completion=1.0` and `tool_calls=1.0` in **10/10** trials; the single `query_gcp_costs(2026-04-01..2026-04-30, SERVICE)` call and both spend figures are correct every time. 100% of the lost reward is the one `answer` rubric item above. Routing (`services=["cost"]` → `investigate_costs`) is correct 10/10. | — | — |

Per-trial evidence (`verifier/reward-detail.json` under the harness job dir):

| seed | reward | answer | missed rubric item |
|---|---|---|---|
| t0 | 0.84 | 0.8 | `no-separate-credits-figure` |
| t1 | 0.84 | 0.8 | `no-separate-credits-figure` |
| t8 | 0.68 | 0.6 | `no-separate-credits-figure` (also attached a literal `$0`) |
| t2 t3 t4 t5 t6 t7 t9 | 1.0 | 1.0 | — |

**The phrasing boundary** (this is the whole diagnosis — passing vs failing text differs *only* here):
- PASS t3/t4/t6/t9: "savings are **netted into the total already** — the tool **does not itemize them separately** … **not broken out by this tool**"
- PASS t2/t5/t7: "a discrete savings figure **cannot be isolated** from the available data"
- FAIL t0: "the export **returned no credit or discount line items**"
- FAIL t1: "the billing data … **contains no** credits or committed-use discount line items"
- FAIL t8: "**$0 in credits** … **no negative-cost line items were present**"

Passing trials describe a **schema limit**; failing trials assert a **measurement**. It passes 7/10 by luck of wording — so the fix is to make the correct framing the prescribed one rather than the lucky one.

## Changes made this iteration (one row per edit)

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE + narrowing a misfiring BEHAVIORAL rule | `shared_context.md` → "Tool Result Handling", inserted directly after the `Empty results` bullet it must override | New bullet: **"'No field for it' is NOT 'it measured zero or empty.'"** Three cases — (a) schema *has* the field, came back empty → a measured finding, report as a value; (b) schema has **no** field → the tool is silent, you have **no measurement**, say it does not report / does not itemize / does not break out that quantity; (c) never attach a currency amount, count, or percentage to an absent-field quantity, "not even 0, ~0, or negligible". Explicitly bans the four paraphrases the failing trials produced ("the data returned none", "no such line items were present", "$0", "none were found"). Generalizes because **every** domain agent here has a "Tool Response Formats" block and can be asked for a quantity its schema omits; the rule cross-references that per-agent block instead of naming any tool, so it carries no cost/GCP-specific content. | YES — narrows `Empty results` with a condition rather than loosening it; genuinely empty result *sets* must still be reported as findings. The 7 passing trials' wording is exactly what this now prescribes. |
| 1 | KNOWLEDGE + worked example (output contract) | `cost_agent.md` → new subsection "What the cost tools do NOT return" under "Tool Response Formats" | The general rule says *how to reason*; the agent still needs to know *which* billing quantities are unreported, because a field list alone cannot tell you whether a missing `credits` key means "no credits" or "not reported". Adds: (1) an **absent-field inventory** spanning the class — credits/promotional/free-tier, committed-use + reserved + savings-plan + sustained-use + enterprise discounts, gross/list/pre-discount cost and the discount delta, refunds/credit memos/tax/support, blended-vs-unblended and amortized-vs-unamortized; (2) the **trigger phrasings** for "as its own number" ("broken out separately", "kept apart from the spend", "how much did X save us", "gross before credits"); (3) the **key non-inference**: a result with no credit rows is *not* evidence that no credits applied, since these tools never emit such rows for *any* period, so the absence carries zero information; (4) a **worked answer template** (reader is `claude-sonnet-4-6`; guidance calls for a worked example on tricky output contracts — handing over the sentence removes the phrasing lottery); (5) four rules on that answer. Generalizes across providers: fires for an AWS RI-savings or Azure gross-cost question too. | YES — rule 3 of the subsection explicitly says *"still answer every other part of the request fully and precisely; a missing adjustment figure is one unavailable item, not a reason to hedge the spend numbers you do have"*, guarding the `total-cost` / `top-service` / `top-service-cost` items that are 10/10 today. |

## Verify-the-fix (one line per change: the trace it targets → what it now does on those exact inputs)

- **Rubric executed, not eyeballed.** Ran my worked template through the real matcher in `tests/expected.json`: `REQUIRED satisfied by: ['not itemized', 'savings:** not', 'no separate credit', 'cannot give you that']` and `FORBIDDEN violations: []`. **Four independent** substring matches clear `no-separate-credits-figure`, so the agent can drift substantially in wording and still pass — which is the point, since wording drift *is* the failure mode. It trips none of the 1000+ `invented-credits-figure` patterns (all currency-anchored; the template attaches no figure to credits).
- **t8** ("returned **$0** in credits") → banned twice: `shared_context.md`'s "not even 0, ~0, or negligible" and `cost_agent.md`'s "do NOT write a dollar amount … not `$0`".
- **t0** ("returned **no credit or discount line items**") → `cost_agent.md` names this exact shape: "do NOT say the export/data 'returned no credits', 'contained no discount line items'".
- **t1** ("**contains no** credits or committed-use discount line items") → same clause, plus the "absence carries no information" sentence directly refutes the inference t1 made.
- **Regression check on the 7 passers** → their winning phrasing ("does not itemize them separately", "not broken out by this tool", "cannot be isolated") is precisely what both edits now prescribe. The edits **ratify the passing behavior and ban only the losing behavior**, so there is no mechanism by which a currently-passing trial regresses. Expected move: 0.904 → ~1.0.
- **Non-overfitting** → restated without any task-specific noun: *"when a user asks for a quantity your tool's response schema has no field for, report that the tool does not break out that quantity instead of reporting it as zero or empty, and attach no figure to it."* No GUID, hostname, date, service name, provider, dollar amount, or count appears in either edit — "Vertex AI", "April 2026", "47463", "18764" appear nowhere in the prompts. `cost_agent.md` names *categories* of billing adjustment, which are standing cloud-billing concepts, not instances.

## Process & features used

- **Serial, no fan-out — deliberately.** The focus set is one task with one flaky rubric item, i.e. exactly one cluster and no independent work to parallelize; a subagent fan-out would have paid coordination cost for a single diagnosis. The leverage came from three other moves: (a) reading the **per-trial `verifier/reward-detail.json` + `agent/agent.jsonl` under the harness job dir** — the local `trajectories/*.json` have `trace: null` and `tool_calls: []`, so they cannot identify the failing rubric item at all and the local files alone are insufficient to diagnose this task; (b) **diffing passing against failing answer text** to isolate the phrasing boundary; (c) **executing the rubric's own matcher against the proposed template** before committing. Move (c) is the one worth repeating every iteration — it converts "plausible fix" into a checked one.
- **Prior iterations read:** none exist — `RUNMAP.md` and `LEDGER.md` are empty (iteration 1, seed is the only candidate), and `rejected.jsonl`/`history.jsonl` are absent, so nothing is refuted yet and this proposal cannot be a repeat.

## Good things to PRESERVE (do not let a future iteration undo these)

- **Tool use is already perfect — do not touch it.** `tool_calls=1.0` and `completion=1.0` in 10/10 trials: one `query_gcp_costs` call with the right window and `group_by=SERVICE`. Any future edit that adds cost-tool call guidance risks turning a 1.0 into a loss for no available gain.
- **Routing is correct 10/10** — leave `orchestrator.md`'s `investigate_costs` rule alone.
- **The "still answer every other part fully" clause** in the new `cost_agent.md` subsection. Without it, a strengthened unavailability rule could make the agent hedge the spend figures, which are the other two rubric items and currently flawless.
- **The absent-field vs empty-field distinction belongs in `shared_context.md`, not only in `cost_agent.md`** — it is the general mechanism; the cost file carries only the domain-specific inventory.

## Deliberately skipped (cluster + why)

- **`orchestrator.md`** — routing correct in 10/10 trials; nothing to fix.
- **The `Empty results` bullet itself** — not weakened, only narrowed. Genuinely empty result sets must still be reported clearly as findings.
- **`Confidence Markers` section** — tempting, since failing t1/t8 wrapped the wrong claim in `[confidence: medium]`. But that is the symptom, not the cause: passing t2/t7 used the same marker. A confidence marker does not launder a false assertion, so I fixed the assertion instead.
- **ESCALATION (genuine capability gap, out of scope for this prose-only phase).** For the task *as scored*, no new tool is needed — the rubric wants the agent to say the figure is unavailable, which prose achieves. But `query_gcp_costs` / `query_aws_costs` / `query_azure_costs` genuinely **cannot** answer "how much did credits and committed-use discounts save us," a routine finance-close question. The honest ceiling of any prose fix is a well-phrased refusal. If that question matters, the tools need a credits/adjustments dimension — GCP's billing export does carry `credits[]` records, and AWS CE exposes `AmortizedCost`/`NetAmortizedCost` metrics plus a `RECORD_TYPE` dimension that separates credits and refunds. Recorded as the escalation this phase cannot fix.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` in this directory.
