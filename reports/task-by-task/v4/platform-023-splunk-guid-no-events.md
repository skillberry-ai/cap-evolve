# platform-023-splunk-guid-no-events

<!-- BEGIN:auto -->

**task:** `platform-023-splunk-guid-no-events`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.933 |
| seed (val, v4_t2_e1) | val | 5 | 0.960 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.067

**T2 cost/time:** $15.04, 522,733 tokens, 1.22h (eval $1.32/368,469tok · optimizer $13.72/154,264tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411/report.md`, `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411/JOURNAL.md`

<!-- END:auto -->

## What this task is about

A sandbox is reported as failing to provision, and the task asks Splunk to be searched for its GUID over a specific error window. The search legitimately returns nothing, and the task measures whether the agent treats that absence correctly -- as "no errors logged in this window," not as evidence the sandbox never started or was never provisioned.

## What the optimizer tried

Two iterations, both touching `orchestrator.md` and `shared_context.md`, plus `babylon_agent.md`/`aap2_agent.md` for domain-specific Splunk guidance (`cand_0001` also lightly touched `cost_agent.md`, `icinga_agent.md`, `ocpv_agent.md` and `security_agent.md`; `cand_0002` deliberately left those four alone because none of those agents run for this task). `cand_0001` diagnosed the entire 0.2 val loss as one forbidden clause — a seed trial's "the pod **never started** and therefore never emitted logs" tripped `expected.json`'s `inferred-from-silence` ban — and tried to fix it with a `### Reporting an Empty or Negative Result` contract in both `orchestrator.md` and `shared_context.md`: a 3-part shape (absence + scope → what it does/doesn't establish → next check) plus a Do-NOT-write/Write-instead table that named the banned phrasings explicitly, and matching guidance in `babylon_agent.md`/`aap2_agent.md` about what a zero-event Splunk result does and doesn't mean. `cand_0002` (the winner) removed that table and its enumeration entirely, replacing them with a new `### When a Search Comes Back Empty` section: a 4-part worked shape (Searched → `Result: no events — 0 results.` → what that establishes → what it does not tell us → Next checks) whose only forward-looking slot is a plain checklist of next checks, never framed as possible causes; a word-level vocabulary ban (the words "never" and "confirms"/"proves"/"shows" about what a result means, rather than a ban on specific phrases); and every open question forced into a fixed `whether`-form sentence.

## Why the winning candidate won

`cand_0001` was rejected: val fell from the 0.960 seed to 0.800 (Δ−0.160). JOURNAL.md's per-trial reconstruction shows the forbidden-hit rate went 1/5 → 4/5 because `cand_0001`'s own Do-NOT-write/Write-instead table printed the banned bigram "never started" and its neighbours 8+ times literally, and the checker does negation-blind substring matching — so a careful hedge like "does NOT establish ... that it never started" still contains the banned string and scores identically to the claim it was hedging against. `cand_0002` rewrote the rule rather than resizing it: it verified by grep that zero forbidden substrings from any of the 8 `none_of` entries remain anywhere in the 8 prompt files, removed the "does/does-not-establish" enumeration structure itself (rather than reframing it, since the enumeration was the slot the banned phrase kept finding a way into), and banned the trigger words at the word level so a hedge cannot satisfy the rule by negating a banned phrase. That combination took val from the 0.800 `cand_0001` low back up to 1.000, a net Δ+0.040 over the original 0.960 seed. Val and test move together on this task: `report.md` records the baseline `seed` skills at 0.96 ± 0.04 on the held-out test split — the same number as the val-seed score — and the optimized skills at 1.0 ± 0.0 on both splits, so the val delta (+0.04) and the test delta (+0.04) are, for this task, genuinely the same figure (confirmed from `report.md`'s explicit test lines, not assumed).

## Caveats

n=5 val trials is a small sample, and this was single-task tuning; with n=1 task, JOURNAL.md itself notes the gate's standard-error calculation falls back to a stricter comparison mode ("with n=1 task the gate reports SE=0 and warns it fell back to STRICT, so a 5-trial 0.8-vs-0.96 comparison is unarbitrated"), and even the accepted `cand_0002`'s own RESULT line is flagged `unresolved={platform-023-splunk-guid-no-events}` (its +0.040 move is below 2×SE of its own measurement). `cand_0001`'s rejected regression is itself the most useful artifact in this run: it demonstrates concretely that telling an agent what *not* to write, by printing the banned phrase in a Do-NOT-write table, is exactly the mechanism that produces the violation, because the reward's forbidden-substring check has no notion of negation or hedging.

<!-- BEGIN:diff -->

## What changed (seed → best)

4 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-023-splunk-guid-no-events/best/`](../../../artifacts/v4/platform-023-splunk-guid-no-events/best/):

<details>
<summary><code>aap2_agent.md</code> (+13/−0)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-023-splunk-guid-no-events/best/aap2_agent.md
@@ -416,6 +416,12 @@
 3. **Evidence:** how you determined this (timing analysis, error message, script trace)
 4. **Fix suggestions:** actionable next steps with specific commands or file paths
 
+Fill fields 1–3 from tool results only. If your searches came back empty and no
+result identifies a cause, write "not established — <what you searched> returned no
+events" in that field and put the check that would establish it under Fix
+suggestions. That is the correct report, not a failed one — do not fill the field
+with an inference about whether the job ran.
+
 **Relevant Files to Review:**
 - AgnosticV config: `{path_to_common.yaml}`
 - Component config (if used): `{component_item}/common.yaml`, `{component_item}/{stage}.yaml`
@@ -519,3 +525,10 @@
 2. Search AAP2 controller logs for server-side errors: `search_aap2_logs` with `errors_only=true`
 3. Search OCP pod logs for container-level failures: `search_by_guid` with `errors_only=true`
 4. If needed, broaden the search by removing `errors_only` or extending the time range
+5. **Zero events bounds the search, not the job.** A Splunk search covers only what
+   was shipped to that index, inside the window you asked for, at the severity you
+   filtered to. Report an empty result in the shape given under "When a Search Comes
+   Back Empty", then pivot to a source that records the job itself: `query_aap2` for
+   the job and its job events, `list_anarchy_subjects` for the AnarchySubject
+   lifecycle state, or the provisions DB for the provision record. Do not settle on
+   one explanation for the silence.
```

</details>

<details>
<summary><code>babylon_agent.md</code> (+8/−0)</summary>

```diff
--- seed/babylon_agent.md
+++ platform-023-splunk-guid-no-events/best/babylon_agent.md
@@ -38,6 +38,14 @@
 
 - **Time range**: Use `earliest=-7d` for stuck provisions — they may have been failing
   for days. Don't start with `-24h` for stuck/requested state investigations.
+
+- **Zero events bounds the search, not the provision.** `search_by_guid` returns only
+  what was shipped to the queried index, from namespaces whose name matched, inside
+  the window, at the severity you filtered to. Report an empty result in the shape
+  given under "When a Search Comes Back Empty", then pivot off Splunk: re-run without
+  `errors_only`, widen the window, then `list_anarchy_subjects` for the AnarchySubject
+  lifecycle state and its tower job references, or the provisions DB for the record.
+  Do not settle on one explanation for the silence.
 
 ### Missing AnarchySubject Investigation
 
```

</details>

<details>
<summary><code>orchestrator.md</code> (+55/−2)</summary>

```diff
--- seed/orchestrator.md
+++ platform-023-splunk-guid-no-events/best/orchestrator.md
@@ -18,12 +18,65 @@
 through your thought process. Just state the facts clearly and concisely.
 
 Use tables for structured data. Use bullet points for lists. Keep explanations
-short. If the user asks "why did this fail?", answer with the cause — not a
-walkthrough of how you figured it out.
+short. If the user asks "why did this fail?" and a tool result shows the cause,
+answer with the cause — not a walkthrough of how you figured it out. If no tool
+result shows it, say the cause is not established by the data you have and name the
+check that would establish it. "Not established yet, here is the check" is a
+complete answer; a plausible-sounding cause you did not read in a result is not.
 
 Be concise and data-driven. Show exact numbers and dates. Use markdown tables for
 tabular data. Stay measured and objective — present facts and let the investigator
 draw conclusions. Do NOT use alarming language unless the data clearly warrants it.
+
+### When a Search Comes Back Empty
+
+A search that returns zero rows is a real finding — report it. But it is evidence
+about the *search*, not about the system: it bounds what was indexed, in the window
+you asked for, at the severity you filtered to, and nothing more. An absence does
+not license any statement about what the system did or did not do.
+
+When the user asks what such a result does and does not let us conclude, answering
+that IS your job — it is not a re-synthesis of the sub-agent's findings. Answer it
+once, in this shape:
+
+> **Searched:** `<tool/action>` for `<identifier>`, `<window>`, `<filters applied>`.
+>
+> **Result: no events — 0 results.**
+>
+> **What that establishes:** nothing matching `<identifier>` was indexed in
+> `<index/source>` at that severity inside that window.
+>
+> **What it does not tell us:** whether the operation ran, whether it succeeded, or
+> why it failed. An empty result is not evidence for any of those, so no cause is
+> established here.
+>
+> **Next checks** — each named by the change to make and the data it would return:
+> - drop the error/severity filter and re-run → whether any lines at all exist for `<identifier>`
+> - widen the time window → lines outside the window first searched
+> - `<the authoritative record for the object itself>` → its recorded status and message
+
+Three rules the shape does not enforce on its own:
+
+1. **State the absence bare, then qualify it.** Write "the search returned no
+   events" (or "no results" / "0 results") as its own statement, then add the scope
+   separately. Fusing them — "no error-level entries for this identifier in this
+   index" — reads as a narrow technical caveat, and a reader skimming it misses that
+   the search came back with nothing at all.
+2. **List checks, not explanations.** Do not enumerate what might have happened: not
+   as a list of possible causes, not as a "does NOT establish" list, not in scare
+   quotes, and not as the thing a check would distinguish between. Name each check by
+   the parameter you would change and the data it would return. A reader keeps the
+   hypothesis and drops the hedge, so a hedged hypothesis is still a claim.
+3. **Vocabulary.** In an empty-result answer do not use the word *never*, and do not
+   use *confirms*, *proves* or *shows* about what the result means — each of them
+   asserts more than an absence can carry. Phrase every open question as `whether …`.
+
+Re-read the answer once before sending: is the bare absence in it, is the limit
+stated in words ("does not tell us" / "does not mean"), is a named next check in it,
+and is every sentence about the data rather than about what happened?
+
+This applies to every empty result, not only logs: no CloudTrail events, no cost
+rows, no monitoring history, no database rows.
 
 ### Source Citations
 
```

</details>

<details>
<summary><code>shared_context.md</code> (+63/−7)</summary>

```diff
--- seed/shared_context.md
+++ platform-023-splunk-guid-no-events/best/shared_context.md
@@ -7,8 +7,59 @@
 through your thought process. Just state the facts clearly and concisely.
 
 Use tables for structured data. Use bullet points for lists. Keep explanations
-short. If the user asks "why did this fail?", answer with the cause — not a
-walkthrough of how you figured it out.
+short. If the user asks "why did this fail?" and a tool result shows the cause,
+answer with the cause — not a walkthrough of how you figured it out. If no tool
+result shows it, say the cause is not established by the data you have and name the
+check that would establish it. "Not established yet, here is the check" is a
+complete answer; a plausible-sounding cause you did not read in a result is not.
+
+## When a Search Comes Back Empty
+
+A search that returns zero rows is a real finding — report it. But it is evidence
+about the *search*, not about the system: it bounds what was indexed or stored, in
+the window you asked for, at the severity or filter you applied, and nothing more.
+An absence does not license any statement about what the system did or did not do.
+
+Report it in this shape:
+
+> **Searched:** `<tool/action>` for `<identifier>`, `<window>`, `<filters applied>`.
+>
+> **Result: no events — 0 results.**
+>
+> **What that establishes:** nothing matching `<identifier>` was indexed in
+> `<index/source>` at that severity inside that window.
+>
+> **What it does not tell us:** whether the operation ran, whether it succeeded, or
+> why it failed. An empty result is not evidence for any of those, so no cause is
+> established here.
+>
+> **Next checks** — each named by the change to make and the data it would return:
+> - drop the error/severity filter and re-run → whether any lines at all exist for `<identifier>`
+> - widen the time window → lines outside the window first searched
+> - `<the authoritative record for the object itself>` → its recorded status and message
+
+Three rules the shape does not enforce on its own:
+
+1. **State the absence bare, then qualify it.** Write "the search returned no
+   events" (or "no results" / "0 results") as its own statement, then add the scope
+   separately. Fusing them — "no error-level entries for this identifier in this
+   index" — reads as a narrow technical caveat, and a reader skimming it misses that
+   the search came back with nothing at all.
+2. **List checks, not explanations.** Do not enumerate what might have happened: not
+   as a list of possible causes, not as a "does NOT establish" list, not in scare
+   quotes, and not as the thing a check would distinguish between. Name each check by
+   the parameter you would change and the data it would return. A reader keeps the
+   hypothesis and drops the hedge, so a hedged hypothesis is still a claim.
+3. **Vocabulary.** In an empty-result answer do not use the word *never*, and do not
+   use *confirms*, *proves* or *shows* about what the result means — each of them
+   asserts more than an absence can carry. Phrase every open question as `whether …`.
+
+Re-read the answer once before sending: is the bare absence in it, is the limit
+stated in words ("does not tell us" / "does not mean"), is a named next check in it,
+and is every sentence about the data rather than about what happened?
+
+This applies to every empty result, not only logs: no CloudTrail events, no cost
+rows, no monitoring history, no database rows.
 
 ## Provision Database
 
@@ -138,8 +189,11 @@
   rather than retrying the agent call.
 - **Batch GUID lookups:** When checking multiple GUIDs (e.g. retirement status),
   query them in a single `IN (...)` clause — not one tool call per GUID.
-- **Infer retired from absence:** If a GUID is missing from active results, treat
-  it as retired — do NOT re-run the same query to confirm.
+- **Missing from active results means retired:** the active-provision query returns
+  the complete active set, so a GUID absent from it is retired — do NOT re-run the
+  same query to confirm. This holds only because that query is complete by
+  construction. A log, event or cost *search* is not complete in that way, so an
+  empty one supports no equivalent inference (see "When a Search Comes Back Empty").
 - **Parallel independent lookups:** When you need both event context and user
   attribution (e.g. IAM key alerts), query CloudTrail and the provisions DB in
   parallel from the start.
@@ -179,9 +233,11 @@
 
 - **Truncated results** (`"truncated": true`): The query hit the limit. Narrow
   your query with tighter WHERE filters or date ranges.
-- **Empty results**: Say so clearly. Suggest alternatives. If a query returns
-  empty results, do NOT retry with the same SQL — simplify first (remove columns,
-  loosen JOINs, widen date range) before adding complexity back.
+- **Empty results**: Say so clearly, and report it in the shape given under "When a
+  Search Comes Back Empty" — the absence stated bare, what it does and does not tell
+  us, and the next check. If a query returns empty results, do NOT retry with the
+  same SQL — simplify first (remove columns, loosen JOINs, widen date range) before
+  adding complexity back.
 - **Error results**: All tools return `{"error": "..."}` on failure. Report the error
   and suggest alternatives.
 - **NEVER call the same tool with the same parameters twice in a conversation.**
```

</details>

<!-- END:diff -->
