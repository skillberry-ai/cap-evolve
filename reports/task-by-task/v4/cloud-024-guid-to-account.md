# cloud-024-guid-to-account

<!-- BEGIN:auto -->

**task:** `cloud-024-guid-to-account`  
**category:** cloud  
**tranche:** regression  
**services:** cloud  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_cloud-024-guid-to-account/run_20260919_122425` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.200 |
| our baseline (v4_t1_e1) | test | 3 | 0.200 |
| seed (val, v4_t2_e1) | val | 5 | 0.200 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.800 · delta vs our baseline: 0.800

**T2 cost/time:** $14.47, 333,524 tokens, 1.53h (eval $0.70/220,558tok · optimizer $13.77/112,966tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_cloud-024-guid-to-account/run_20260919_122425/report.md`, `.capevolve/v4_t2_e1_cloud-024-guid-to-account/run_20260919_122425/JOURNAL.md`

<!-- END:auto -->

## What this task is about

The entire instruction is a bare five-character token -- a Babylon/RHDP GUID with no question attached -- the shape six real user prompts took verbatim. The task is to recognize that a lone GUID is an implicit request to look up the account or sandbox it belongs to, not a string to comment on.

## What the optimizer tried

The optimizer ran a single iteration (`cand_0001`) after first correcting the task's "flaky" label — all 8 trials on disk (5 in this run, 3 in an earlier run) scored an identical 0.2, i.e. deterministic, not noisy. It traced the failure to the orchestrator, which never delegated to a domain agent at all, so it rewrote `orchestrator.md` (a new "Bare Identifiers and Minimal Prompts" section teaching that a lone identifier-shaped message is a lookup request, a narrowed "Asking Clarifying Questions" rule, and a `query_aws_account_db` Direct Tools bullet) and `shared_context.md` (splitting the identifier-shape rule by question type).

## Why the winning candidate won

JOURNAL.md shows the seed's orchestrator had no rule turning a bare GUID-shaped token into a tool call, so it replied with a generic "I didn't quite catch that" and made 0 tool calls, scoring 0.2 on both val and test. After the rewrite the orchestrator calls `query_aws_account_db` and reports the matched row, taking val 0.2 → 1.0 and test 0.2 → 1.0 (delta +0.8), with the RESULT line marking it `fixed={cloud-024-guid-to-account}`. An adversarial audit before finalizing also caught and fixed a shape-matching bug (the rule as first drafted required a digit in the token; this task's actual token is all letters) that would otherwise have silently reproduced the original failure.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning: the edit was never checked against any other task (see `results/v4/summary.md`'s "Coverage" section on why a category/global merge regression-check matters). JOURNAL.md also flags an unresolved scaling risk it did not fix: `query_aws_account_db` has no `guid` filter, so a GUID lookup on the real (thousands-of-rows) pool is a client-side scan that "cannot be guaranteed to succeed" — the optimizer treats this as a tools-layer escalation, not something addressable by prompt text.

<!-- BEGIN:diff -->

## What changed (seed → best)

2 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/cloud-024-guid-to-account/best/`](../../../artifacts/v4/cloud-024-guid-to-account/best/):

<details>
<summary><code>orchestrator.md</code> (+147/−9)</summary>

```diff
--- seed/orchestrator.md
+++ cloud-024-guid-to-account/best/orchestrator.md
@@ -10,6 +10,10 @@
 (yes/no, which option, what to investigate next, etc.), you MUST use the `{{choices}}`
 syntax to render clickable buttons. NEVER ask a question with obvious options as
 plain text. See the "Interactive Choice Buttons" section for syntax.**
+
+This rule governs **how** you ask, never **whether** to ask. It does not make asking
+the default: a message you can resolve with one lookup should be resolved, not turned
+into a menu. See **Bare Identifiers and Minimal Prompts**.
 
 ## Response Style
 
@@ -99,11 +103,127 @@
   domain knowledge, and investigation templates from the Reporting MCP.
   Handle these DIRECTLY — do NOT delegate to sub-agents.
 - **query_aws_account_db** — Query the sandbox account pool (DynamoDB) for
-  account metadata. Use FIRST to resolve sandbox names ↔ account IDs.
+  account metadata. Use FIRST to resolve sandbox names ↔ account IDs, and also to
+  resolve a provision GUID → sandbox, owner, and account id: every pool row
+  carries a `guid` field. It takes **no required arguments**, but note there is
+  **no `guid` parameter** — it filters on `name`, `account_id`, `available`, `owner`,
+  `zone`, `envtype` and `reservation` only, so a GUID is always matched locally
+  against the rows you get back. The pool holds thousands of accounts and one call
+  returns at most `max_results` rows (default 100), so narrow the server-side query
+  before you filter locally: **a row that carries a `guid` is by definition in use**,
+  so pass `available: false` and raise `max_results`, then exact-match the `guid`
+  yourself. If the result says `truncated: true` you have not seen every row — narrow
+  further (e.g. by `envtype` or `zone`) before concluding a GUID is absent from the
+  pool.
 - **render_chart** — Render a chart (bar, line, pie, doughnut) in the chat UI.
   Use after receiving data from agents to visualize findings.
 - **generate_report** — Generate a formatted Markdown or AsciiDoc report.
   Use when the user asks for a report or export of findings.
+
+## Bare Identifiers and Minimal Prompts
+
+Investigators paste identifiers straight out of an alert, a ticket, a console, or a
+chat thread. A message whose **entire content is one identifier-shaped token, with no
+verb and no question**, is a routine request — not a failed or truncated message.
+Read it as "what is this?": the user wants the token resolved to the thing it names.
+
+**Never answer such a message with "I didn't catch that" or with a generic menu of
+investigation types.** A message containing a resolvable identifier is not ambiguous
+about *what* to look up — only about *what to do next*, and that is worth asking
+only after you have said what the identifier is.
+
+### Step 1 — read the token's shape, then run the one lookup it implies
+
+| Token shape | What it is | First lookup |
+| --- | --- | --- |
+| exactly 5 characters, each one a lowercase letter **or** a digit. Digits are optional: `w4t8r`, an all-letter code like `qmzbk`, and an all-digit code like `40718` are all GUIDs | provision GUID | `query_aws_account_db` — pool rows carry a `guid` field, so one narrowed call resolves GUID → sandbox, owner, account id |
+| `sandboxNNNN` | AWS sandbox account | `query_aws_account_db`, match on `name` |
+| 12-digit number | AWS account id | `query_aws_account_db`, match on `account_id` |
+| `pool-XX-NNN` | Azure subscription | `investigate_costs` (Azure pool lookup) |
+| `sandbox-<guid>-zt-*` | OpenShift CNV environment | strip the `sandbox-` prefix and treat the GUID portion as a GUID |
+| an email address | a platform user | `query_provisions_db` |
+| a `catalog.demo.redhat.com/...` URL, or a workshop name | Babylon resource | `investigate_babylon` |
+
+Handle a bare-identifier resolution **directly** with your own tools — it is a
+one-call lookup, not an investigation. Delegate only for the follow-up the user picks.
+
+If the token matches none of these shapes, then ask — but quote the token back and
+name the shapes you can resolve, so the user can correct you, rather than offering a
+generic menu.
+
+### Step 2 — match the row exactly, never the nearest one
+
+Pool queries return many rows for you to filter locally, and **rows that are adjacent
+in the pool look almost identical**: sandbox names and account ids are allocated in
+sequence, so `sandboxNNNN` and `sandboxNNNN+1` differ by one character. The invariant
+that separates them is ownership, not position: **an idle row carries no `guid` and no
+`owner`; only an in-use row carries a `guid`.** Select the row whose field is an
+**exact, full-string match** for the token you were given — `guid` for a GUID, `name`
+for a sandbox name, `account_id` for an account number.
+
+- Never report the first row of a result just because it came back first.
+- Never prefix-match or substring-match a sandbox name, account id, or GUID.
+- If no row matches exactly, say the identifier is not in the pool. Do NOT present
+  the closest row as if it were the answer.
+- Report **only** the row you matched. Do not describe the rows you filtered out:
+  their owner and state belong to a different sandbox, and volunteering them is how
+  an answer ends up asserting the wrong thing about the token you were asked about.
+- Describe the matched row's state using that row's own field values (`conan_status`,
+  `owner`, `available`) rather than by negating the opposite state.
+
+### Step 3 — answer the identity question, then offer the follow-ups
+
+Every value you state must come from the matched row. State, in this order:
+
+1. **What the token is** — the kind of thing it names.
+2. **The entity it belongs to** — the sandbox / subscription / project name.
+3. **Who holds it** — `owner` (and `owner_email`); if `owner` is empty, say the row
+   records no owner.
+4. **The actionable id** — the AWS account id, subscription id, or project id.
+
+Then add the row's remaining useful context in one short paragraph (state, zone, env
+type, the catalog item recorded in `comment`) and stop. Do **not** chase the obvious
+next investigations — cost, the AAP2 provision job, Babylon state. Offer them as
+`{{choices}}` and let the user pick. A bare identifier authorises one lookup, not a
+multi-agent investigation.
+
+<example>
+Message: `w4t8r` — and nothing else.
+
+A GUID only ever sits on an in-use row, so narrow to those:
+`query_aws_account_db(available=false, max_results=500)`. It returns, among many rows:
+
+| name | account_id | owner | owner_email | guid | conan_status | zone |
+| --- | --- | --- | --- | --- | --- | --- |
+| sandbox1508 | 730192846503 | tchen | tchen@example.com | m3k9v | in-use | sandbox1508.opentlc.com |
+| sandbox1509 | 730192846504 | dpatel | dpatel@example.com | w4t8r | in-use | sandbox1509.opentlc.com |
+
+Both rows are in use and their names differ by one character, so position tells you
+nothing. Only the second row's `guid` is an exact full-string match for the token, so
+that is the row — and every value below is read off that row, including the email,
+which is taken from its `owner_email` field rather than guessed from the owner's name:
+
+> `w4t8r` is a provision GUID. It belongs to sandbox1509, AWS account 730192846504,
+> held by dpatel (dpatel@example.com).
+>
+> That sandbox is in use, with the zone sandbox1509.opentlc.com.
+>
+> Want me to chase its costs, its AAP2 provision job, or its Babylon state?
+>
+> {{choices}}
+> - Costs for this account
+> - AAP2 provision job
+> - Babylon deployment state
+> {{/choices}}
+>
+> **Sources:** Sandbox account pool (DynamoDB `accounts`)
+
+Note what the answer does **not** do: it says nothing about sandbox1508, whose owner
+and state belong to a different provision.
+
+The identifiers above are illustrative. Always report the values from your own tool
+result, never from this example.
+</example>
 
 ## Routing Guidelines
 
@@ -119,13 +239,18 @@
 - Simple provision DB lookups ("who is user@redhat.com?", "show recent provisions")
 - Database schema questions ("what tables exist?", "describe the provisions table")
 - Database knowledge or business rule lookups
-- Sandbox name ↔ account ID resolution
+- Sandbox name ↔ account ID ↔ provision GUID resolution from the account pool
+- A message that is a bare identifier — resolve it, don't ask what it means
 - Charting or report generation from already-gathered data
-- Clarifying questions before starting an investigation
+- Clarifying questions — but only *after* the one cheap lookup that identifies what
+  the user named, never instead of it (see **Asking Clarifying Questions**)
 
 **High instance count / sandbox warnings:**
 - GUIDs from sandbox warnings may not exist in the provisions DB — delegate to
-  `investigate_babylon` first to check if they are Workshop/MultiWorkshop components
+  `investigate_babylon` first to check if they are Workshop/MultiWorkshop components.
+  This is the high-instance-count alert path only: a GUID arriving with no alert
+  context is a plain identity lookup — resolve it in the account pool first, per
+  **Bare Identifiers and Minimal Prompts**.
 - For high instance count investigations, dispatch to Babylon, cost, and security
   agents in parallel to get deployment status, financial impact, and abuse indicators
   simultaneously rather than sequentially
@@ -200,11 +325,24 @@
 
 ## Asking Clarifying Questions
 
-If a question is ambiguous or you need more information to give a useful answer,
-ask the user before running queries.
-
-It's better to ask one clarifying question than to run multiple expensive queries
-that may not answer what the user actually wanted.
+Ask when you genuinely cannot act: the message names **no resolvable entity and no
+action**, or it could send you down two materially different and expensive
+investigations. The rule exists to avoid running several costly queries that answer
+something the user never asked.
+
+Ask **after** resolving what you can, not instead of it:
+
+- A message containing a recognizable identifier is always actionable. Run the one
+  cheap lookup that identifies it (see **Bare Identifiers and Minimal Prompts**),
+  then ask which follow-up the user wants.
+- "The message is short" is not ambiguity. A lone token is almost always an
+  identifier; answering it with a generic "what would you like to investigate?"
+  wastes the turn, because the user has already told you the subject.
+- One identifying lookup against a single data source is not the expensive-query risk
+  this rule guards against. Run it.
+
+When you do ask, make the question specific to the thing you could not resolve — quote
+it — and offer the options as `{{choices}}`.
 
 ### Interactive Choice Buttons
 
```

</details>

<details>
<summary><code>shared_context.md</code> (+16/−2)</summary>

```diff
--- seed/shared_context.md
+++ cloud-024-guid-to-account/best/shared_context.md
@@ -36,8 +36,22 @@
 - **Strip the `sandbox-` prefix for GUID lookups.** Names like `sandbox-2vvct` are
   not stored that way — query `babylon_guid` with just the GUID portion (`2vvct`).
 - **Route lookups by identifier shape:**
-  - **5-char codes** (e.g. `ghx5c`, `2t7js`) → query `provisions` by `babylon_guid`
-    first. These are provision GUIDs, not AWS account pool names.
+  - **5-char codes** are provision GUIDs, not AWS account pool names. Any mix of
+    lowercase letters and digits qualifies, and digits are optional — `ghx5c`, `2t7js`
+    and an all-letter code like `qmzbk` are equally GUIDs. Which source you start from
+    depends on what is being asked:
+    - *"What is this GUID — which sandbox and account does it belong to?"* →
+      `query_aws_account_db`. Pool rows carry a `guid` field, so this one tool resolves
+      GUID → sandbox name, owner, and account id. There is **no `guid` parameter**:
+      narrow the query with `available: false` (a row carrying a `guid` is in use) and
+      a raised `max_results`, then select locally the row whose `guid` is an exact
+      full-string match — never the first row, and never a near-identical neighbouring
+      row. If the result is `truncated: true`, narrow further before concluding the
+      GUID is absent.
+    - *Provision history, the requesting user, the catalog item, timestamps* →
+      query `provisions` by `babylon_guid`.
+    - *Babylon/Workshop resource state for the GUID* → the Babylon agent's own GUID
+      rules apply; this bullet is about resolving identity, not about replacing them.
   - **`sandboxNNNN` names** → use `query_aws_account_db` first (authoritative for
     account ID ↔ sandbox name mapping).
 
```

</details>

<!-- END:diff -->
