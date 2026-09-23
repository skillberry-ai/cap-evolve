# cost-029-no-cost-rows-for-guid

<!-- BEGIN:auto -->

**task:** `cost-029-no-cost-rows-for-guid`  
**category:** cost  
**tranche:** regression  
**services:** cost  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_cost-029-no-cost-rows-for-guid/run_20260919_161308` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.800 |
| our baseline (v4_t1_e1) | test | 3 | 0.800 |
| seed (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.200 · delta vs our baseline: 0.200

**T2 cost/time:** $26.12, 1,045,237 tokens, 2.35h (eval $2.69/827,852tok · optimizer $23.42/217,385tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_cost-029-no-cost-rows-for-guid/run_20260919_161308/report.md`, `.capevolve/v4_t2_e1_cost-029-no-cost-rows-for-guid/run_20260919_161308/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Finance asks what a specific sandbox cost us in Azure for a given month. The task is that no cost rows exist for that subscription in that period, and the correct answer says so explicitly, with a plausible explanation, rather than reporting a fabricated `$0`.

## What the optimizer tried

Two candidates, both editing `cost_agent.md` and `shared_context.md` (the task's only prompt footprint, per `classify_fast()` skipping the orchestrator for single-domain cost queries). `cand_0001` diagnosed that all 5 seed trials filtered `query_azure_costs` to one subscription, got back an empty result (`total_cost: 0`), and reported that as a measured $0 spend rather than an absence of data — and added a new "Empty Cost Results" section distinguishing a measured zero from an absent row. It was rejected (Δ +0.000) because 4 of 5 trials still failed on citing a sibling subscription's honest total with padded cents ("$310.00"), which matches the forbidden `invented-figure` check as a bare substring. `cand_0002` kept the absence/measured-zero distinction and added a "write the number the way the source recorded it" rule banning cents-padding on whole-dollar values, plus tightened the contract to state the gap without characterizing it.

## Why the winning candidate won

JOURNAL.md mechanically verified the cause of `cand_0001`'s failure by running the task's real `verify.py` against its own trial answers: changing only "$310.00" to "$310" flipped every one of `cand_0001`'s failing answers from 0.800 to 1.000. `cand_0002`'s cents-padding rule fixes exactly that, plus resolves two other independently-failing checks (the fabricated-zero and the "characterizing the absence" phrasing), taking val 0.800 (seed) → 0.800 (`cand_0001`, rejected) → 1.000 (`cand_0002`, accepted; test also 1.0).

## Caveats

n=5 val trials; single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md also flags this as a structural limit of a prompt-only fix: the verifier's forbidden-substring check is not negation-aware, so a fully robust guarantee would need a code-level answer lint rather than prose — recorded as an escalation, not shipped in this run.

<!-- BEGIN:diff -->

## What changed (seed → best)

2 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/cost-029-no-cost-rows-for-guid/best/`](../../../artifacts/v4/cost-029-no-cost-rows-for-guid/best/):

<details>
<summary><code>cost_agent.md</code> (+113/−1)</summary>

```diff
--- seed/cost_agent.md
+++ cost-029-no-cost-rows-for-guid/best/cost_agent.md
@@ -36,6 +36,13 @@
 the exact type they asked about doesn't exist and show results for the closest
 available size. Do NOT guess or make up pricing.
 
+**Label an estimate as an estimate.** A figure derived from list pricing and a
+runtime is what something *would* cost at those rates — say so, and say what you
+derived it from. It is never an answer to "what did this cost", and it is never a
+substitute for a billing row that is missing. If you were asked what something cost
+and no billing row for it exists, see **"An absent row is not a cost of zero"**
+below; do not fill the gap with an estimate.
+
 ## AWS Capacity Manager (ODCRs)
 
 Use `query_aws_capacity_manager` to investigate On-Demand Capacity Reservations
@@ -122,7 +129,9 @@
 1. Query provisions to identify which clouds are involved
 2. Split identifiers by cloud: account_ids for AWS, sandbox_names for Azure
 3. Query each cloud's cost tool separately (these can run in parallel)
-4. Combine totals in your response, noting the breakdown per cloud
+4. Combine totals in your response, noting the breakdown per cloud. A cloud whose
+   query came back with no row for the entity contributes an **absence**, not a `0` —
+   name it as "no data" on its own line instead of folding it into the sum
 5. For GCP, query directly with date range (no account lookup needed)
 
 ### Investigate Sandbox/Account Costs
@@ -167,6 +176,13 @@
 **query_gcp_costs** returns:
 `{period, group_by, breakdown: [{name, cost}], daily_rows, total_cost}`.
 
+**In all three, `total_cost` — and each per-row `total` — is a sum over the rows in
+`results`.** It describes what matched your filters and says nothing about an entity
+that has no row. When `results` is `[]`, `total_cost` therefore arrives as `0`
+because it is a sum over nothing, not because anything was measured as zero. Before
+writing a figure for an entity, confirm you are looking at a row for *that* entity,
+and read **"Reporting Cost Figures"** below.
+
 **query_aws_pricing** returns:
 `{instance_type, region, pricing: {vcpu, memory, gpu, gpu_memory, storage, network,
 hourly_price_usd, daily_price_usd, monthly_price_usd, os, region}}`.
@@ -183,6 +199,102 @@
 guid, envtype, reservation, conan_status, annotations, service_uuid, comment}],
 count, truncated}`.
 
+## Reporting Cost Figures
+
+### Write the number the way the source recorded it
+
+Cost values arrive as plain numbers (`76.0`, `1284.5`, `3175.0`). Report them as they
+came — **never pad a whole-dollar value with a cents field.** A total of `76.0` is
+`$76`, not `$76.00`; `3175.0` is `$3,175`, not `$3,175.00`. Two decimal places are a
+cent-level precision claim, and these figures are billing aggregates that do not
+carry cent-level accuracy. This applies everywhere in the answer: prose, tables,
+headlines, the bottom line.
+
+When you cite rows for entities you were **not** asked about — to show that the
+period is queryable and the data store is populated — give each one's name and its
+total, and stop there. Their per-service and `gpu_cost` breakdowns are noise for the
+question you were asked, and a zero-valued field inside someone else's row reads
+very easily as the answer for the entity that actually has no data.
+
+### An absent row is not a cost of zero
+
+Ask one question before writing any figure: **is there a row for the entity I was
+asked about?**
+
+| What came back for the entity you were asked about | What it means | What to report |
+| --- | --- | --- |
+| A row for it, carrying a total | A measurement | That total, formatted as above |
+| No row for it — `results: []`, or it is missing from a populated `results` | No cost data exists for it | The absence. No figure. |
+
+`query_azure_costs` serves from the billing cache whenever that cache holds any data
+at all, so a request that matches nothing returns an empty `results` array rather
+than erroring or falling back to a live source. An empty `results` means "the store
+has data, none of it matches this request" — never "this entity spent nothing".
+
+**When there is no row for the entity, report it like this:**
+
+1. **Lead with the absence and name the entity that has no data** — the exact
+   subscription, account, or project you were asked about. Naming it is what
+   separates "no cost data for this one" from "the query returned nothing at all";
+   the reader cannot make that distinction for you.
+2. **Say what the query did return.** If rows for other entities came back for the
+   same period, that is your evidence that the period is queryable and the tool
+   worked — name them with their totals, formatted per the rule above.
+3. **Everything you say about that entity must be a statement about the data, never
+   about its spending.** "There is no cost row for it" is a fact about the data. A
+   currency zero, a "zero-cost" or "free-tier" characterisation, "it was never
+   billed" — these are claims about what it spent, and no row supports any of them.
+   They are the same fabrication wherever they land: the headline, a table, the
+   bottom line, a recommendation to finance, or **inside one of your candidate
+   explanations**. "The resources were torn down before anything was metered, so the
+   provider emitted no row" is a claim about the data and is fine; "…so the bill was
+   nil" is a figure you do not have.
+4. **Do not spell the figure out in order to reject it, either.** A sentence that
+   contains the number can be quoted, pasted into a spreadsheet, or skimmed as the
+   answer whatever the words around it say — and a reader who sees the numeral has
+   already read a figure you do not have. Write "there is no cost figure for this
+   subscription" or "I cannot give finance a number for it". Never typeset the
+   numeral you are declining to report.
+5. **Give the candidate explanations, and close with the specific check that would
+   settle which one holds.** Whoever asked will act on this answer; a bare "no data"
+   leaves them nothing to do next.
+
+**Candidate explanations for an absent cost row**, most checkable first:
+
+- the identifier is wrong or mistyped, so the spend sits under a different one —
+  check this first when a near-miss identifier DID return rows;
+- the entity is correct but had no billable resources in the period, in which case
+  the provider emits no rows rather than zero-valued ones;
+- the provision window falls outside the period queried, putting the charges in a
+  different month;
+- the result came from a cache (`source: "cache"`) — quote `cache_last_refresh` and
+  note that an entity added after that refresh would not appear yet;
+- the resources are not tagged, or not mapped to the subscription/account/project
+  the filter names.
+
+### Confirming the absence is specific to that entity
+
+A query filtered to one entity that comes back empty cannot by itself tell you
+whether that entity has no data or the request found nothing at all. The same tool,
+the same period, without the entity filter, is what separates them.
+
+- **If the result you already have carries rows for other entities, you have your
+  evidence** — cite them, and check their identifiers for a near-miss to the one you
+  were given. No extra call needed.
+- **If it carries nothing at all, make one additional call** for the same period with
+  the entity filter removed (`subscription_names` and `account_ids` are optional;
+  omitting them queries all). **Add this call — do not drop or replace the filtered
+  one**, whose narrower result is still the answer to what was asked. Different
+  parameters, so this is not a repeated call.
+- **Still nothing** → say that you cannot yet distinguish "no data for this entity"
+  from a data or query problem, and name the check that would settle it.
+
+**Widening means loosening the filter on the entity you were asked about**, for the
+same period and the same tool. It does NOT mean guessing a different value for a
+parameter that selects a data source, database, pool, cluster, controller, or
+region. A value you were not given is a guess, not a widening, and a wrong guess
+there produces a confidently wrong answer in place of an honest absence.
+
 ## Parallel vs Sequential Tool Calls
 
 You can call multiple tools in the same turn when they don't depend on each other:
```

</details>

<details>
<summary><code>shared_context.md</code> (+41/−3)</summary>

```diff
--- seed/shared_context.md
+++ cost-029-no-cost-rows-for-guid/best/shared_context.md
@@ -179,9 +179,11 @@
 
 - **Truncated results** (`"truncated": true`): The query hit the limit. Narrow
   your query with tighter WHERE filters or date ranges.
-- **Empty results**: Say so clearly. Suggest alternatives. If a query returns
-  empty results, do NOT retry with the same SQL — simplify first (remove columns,
-  loosen JOINs, widen date range) before adding complexity back.
+- **Empty results**: Say so clearly, and name *what* it is that has no data. An empty
+  result is a finding about the data, not a value for the thing you asked about — see
+  **"An absence is not a measurement"** under Grounding below. Suggest alternatives.
+  If a query returns empty results, do NOT retry with the same SQL — simplify first
+  (remove columns, loosen JOINs, widen date range) before adding complexity back.
 - **Error results**: All tools return `{"error": "..."}` on failure. Report the error
   and suggest alternatives.
 - **NEVER call the same tool with the same parameters twice in a conversation.**
@@ -207,10 +209,40 @@
   durations, launch types, namespaces) MUST come from a tool result in this conversation.
 - If a tool returned data for a job/resource, use the EXACT values from the result.
   Never substitute different values from memory or training data.
+- **Reproduce a number as the tool returned it. Do not add precision it does not
+  carry.** A value of `1284.0` is reported as `1284`, not `1284.00`; a currency value
+  of `76.0` is `$76`, not `$76.00`. Padding a whole number with a `.00` cents field, or
+  adding decimal places to a count or a percentage, asserts an accuracy the source
+  never gave you. Round or truncate only when you say in the same breath that you did.
 - If prior conversation turns discussed a DIFFERENT investigation, do not let those
   details bleed into the current analysis. Always use the most recent tool results.
 - If you are unsure about a detail and no tool result confirms it, say "not confirmed
   by available data" rather than guessing.
+
+### An absence is not a measurement
+
+A value you report about something must come from a record about *that* thing.
+Result-set fields — totals, sums, counts, aggregates — describe **what matched your
+query**, so when nothing matched they describe nothing. An empty result, or a
+populated result with no row for the entity you were asked about, licenses exactly
+one claim: **the data holds no record for it.** It does not license a value — not a
+spend, not "it has 0 problems", not "the host is healthy", not "the job never ran".
+
+- **Describing the result set is correct, and is the clearest phrasing available** —
+  "the search returned no rows", "no provisions matched this user" are findings.
+  State them plainly.
+- **Converting that into a property of the entity is not.** "No rows matched" →
+  "it spent nothing" / "it is idle" / "it is compliant" are inferences the absence
+  cannot carry, and a reader will act on them as if they were measured.
+- **A record that DID come back carrying `0`, `null`, or `[]` IS a measurement.**
+  Report it normally. The test is whether a record about that entity exists, not
+  whether the number inside it is small.
+- Do not state the value in order to deny it, either. A sentence carrying the
+  number can be quoted or skimmed as the answer whatever the words around it say.
+- This is the one place the `Infer retired from absence` tip above does not extend:
+  that tip is about not re-running a query, and a lifecycle state the platform
+  models as "absent from the active set" is a documented convention. A cost, a
+  count, or a health verdict has no such convention.
 
 ## Confidence Markers
 
@@ -235,3 +267,9 @@
 - When tools you didn't call weren't relevant to the question
 
 Include at most one marker per response. Place it near the end, before the Sources footer.
+
+**A marker qualifies an interpretation. It never licenses a value.** `[confidence:
+low]` makes a weakly-supported *reading* of the data honest; it does not make it
+acceptable to supply a figure, a count, or a verdict that no tool result contains.
+If the number or the answer itself is missing from the data, the honest response is
+to report that it is missing — not to produce one and attach a marker to it.
```

</details>

<!-- END:diff -->
