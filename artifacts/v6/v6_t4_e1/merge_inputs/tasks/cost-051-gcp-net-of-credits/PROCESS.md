# PROCESS — what I did this iteration (explainability; REQUIRED)


| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |


|---|---|---|---|

**The phrasing boundary** (this is the whole diagnosis — passing vs failing text differs *only* here):
- PASS t3/t4/t6/t9: "savings are **netted into the total already** — the tool **does not itemize them separately** … **not broken out by this tool**"
- PASS t2/t5/t7: "a discrete savings figure **cannot be isolated** from the available data"
- FAIL t0: "the export **returned no credit or discount line items**"
- FAIL t1: "the billing data … **contains no** credits or committed-use discount line items"
- FAIL t8: "**$0 in credits** … **no negative-cost line items were present**"


## Changes made this iteration (one row per edit)

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |

## Verify-the-fix (one line per change: the trace it targets → what it now does on those exact inputs)

- **Rubric executed, not eyeballed.** Ran my worked template through the real matcher in `tests/expected.json`: `REQUIRED satisfied by: ['not itemized', 'savings:** not', 'no separate credit', 'cannot give you that']` and `FORBIDDEN violations: []`. **Four independent** substring matches clear `no-separate-credits-figure`, so the agent can drift substantially in wording and still pass — which is the point, since wording drift *is* the failure mode. It trips none of the 1000+ `invented-credits-figure` patterns (all currency-anchored; the template attaches no figure to credits).
- **t8** ("returned **$0** in credits") → banned twice: `shared_context.md`'s "not even 0, ~0, or negligible" and `cost_agent.md`'s "do NOT write a dollar amount … not `$0`".
- **t0** ("returned **no credit or discount line items**") → `cost_agent.md` names this exact shape: "do NOT say the export/data 'returned no credits', 'contained no discount line items'".
- **t1** ("**contains no** credits or committed-use discount line items") → same clause, plus the "absence carries no information" sentence directly refutes the inference t1 made.
- **Non-overfitting** → restated without any task-specific noun: *"when a user asks for a quantity your tool's response schema has no field for, report that the tool does not break out that quantity instead of reporting it as zero or empty, and attach no figure to it."* No GUID, hostname, date, service name, provider, dollar amount, or count appears in either edit — "Vertex AI", "April 2026", "47463", "18764" appear nowhere in the prompts. `cost_agent.md` names *categories* of billing adjustment, which are standing cloud-billing concepts, not instances.

## Process & features used


## Good things to PRESERVE (do not let a future iteration undo these)

- **The "still answer every other part fully" clause** in the new `cost_agent.md` subsection. Without it, a strengthened unavailability rule could make the agent hedge the spend figures, which are the other two rubric items and currently flawless.
- **The absent-field vs empty-field distinction belongs in `shared_context.md`, not only in `cost_agent.md`** — it is the general mechanism; the cost file carries only the domain-specific inventory.

## Deliberately skipped (cluster + why)

- **The `Empty results` bullet itself** — not weakened, only narrowed. Genuinely empty result sets must still be reported clearly as findings.
- **`Confidence Markers` section** — tempting, since failing t1/t8 wrapped the wrong claim in `[confidence: medium]`. But that is the symptom, not the cause: passing t2/t7 used the same marker. A confidence marker does not launder a false assertion, so I fixed the assertion instead.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` in this directory.
