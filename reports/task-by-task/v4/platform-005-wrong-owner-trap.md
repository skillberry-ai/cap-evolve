# platform-005-wrong-owner-trap

<!-- BEGIN:auto -->

**task:** `platform-005-wrong-owner-trap`  
**category:** platform  
**tranche:** regression  
**services:** github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719` (n_runs: 2)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.813 |
| seed (val, v4_t2_e1) | val | 5 | 0.320 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.608 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.916 |
| cand_0003 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.187

**T2 cost/time:** $13.65, 2,351,554 tokens, 1.55h (eval $7.26/2,303,144tok · optimizer $6.39/48,410tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/report.md`, `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Asks to look up a catalog item, find the AgnosticD content repository it points to, and read a workload role's defaults file from it. The trap is the single most common real mistake in the underlying trajectory corpus: fetching from the wrong repository owner (`rhpds/agnosticd-v2`, which doesn't exist) instead of the correct `agnosticd/agnosticd-v2`.

## What the optimizer tried

This task has two finalized runs (see `results/v4/summary.md`'s "Data-quality caveats"); `results.json` takes the one with the best held-out `test_reward`, which is this task's first attempt. All three of its candidates' JOURNAL.md entries are framework-synthesized "EMPTY HANDOVER" placeholders — the optimizer never wrote its own iteration entry for `cand_0001`, `cand_0002`, or `cand_0003`, because an unrelated infrastructure interruption hit each of the three optimizer subprocesses while it was composing its handover, so no rationale for what changed or why survives in this run's record. What is known is the measured outcome: val rose monotonically across all three candidates (seed 0.320 → cand_0001 0.608 → cand_0002 0.916 → cand_0003 1.000, the last one accepted as champion), with each RESULT line stamped `ACCEPTED (new champion)`.

## Why the winning candidate won

No content-based rationale is available for this task — better to say so than to invent one. JOURNAL.md contains no iteration entry for any of the three candidates (all three are framework-synthesized "empty handover" notes), so the only record of why `cand_0003` won is the reward progression itself: it reached val 1.0 with a paired Δ of +0.084 over `cand_0002`, and `report.md` records a held-out test score of 1.0 ± 0.0 for the optimized skills versus 0.774 ± 0.138 for the baseline `seed` skills (test improvement +0.226).

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). Beyond the usual caveats, this task's entire optimization record is a rewards-only trail — no JOURNAL.md entry explains what any of the three candidates' prompt edits actually were, only that each was measured and accepted. That is an infrastructure gap, not evidence the edits themselves were arbitrary or wrong — the monotonic val progression and the clean held-out test score argue the edits were real, just undocumented.

<!-- BEGIN:diff -->

## What changed (seed → best)

3 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-005-wrong-owner-trap/best/`](../../../artifacts/v4/platform-005-wrong-owner-trap/best/):

<details>
<summary><code>aap2_agent.md</code> (+47/−6)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-005-wrong-owner-trap/best/aap2_agent.md
@@ -15,11 +15,36 @@
    recommendations). If you have been calling tools, your next text block should be
    the report — not more narration.
 
-3. **Budget your rounds.** You have a limited number of tool calls. Do NOT
-   speculatively browse directories — use `search_github_repo` or `lookup_catalog_item`
-   to find paths in one call. Stop fetching when you have enough data to explain the
-   failure and write the report. More fetching without analysis is worse than a
-   report with some gaps.
+3. **Budget your rounds — running out silently destroys your answer.** You get a
+   limited number of rounds, and a "round" is ONE assistant turn, not one tool call:
+   a turn with four parallel tool calls costs the same single round as a turn with one.
+   When the rounds run out before you have written your findings, the user receives no
+   answer at all — your entire investigation is discarded and replaced with a prompt
+   asking whether to keep going. A partial answer always beats being cut off.
+
+   **Spend rounds like this:**
+   - **Batch every independent lookup into one round.** If two calls do not depend on
+     each other's output, issue them as parallel tool calls in the SAME turn. Probing
+     one search term per turn is the main way investigations run out of rounds.
+   - **Never spend a round re-asking a question a previous result already answered.**
+     Re-read the results already in your context first.
+   - **Do NOT speculatively browse directories** — use `search_github_repo` or
+     `lookup_catalog_item` to find paths in one call.
+   - **Stop and write as soon as you can answer.** The moment a tool result contains
+     the values the user asked for, your NEXT output MUST be the final answer — not
+     one more confirming call. Confirming a value you already have costs a round and
+     buys nothing.
+   - **Once you are two thirds through your rounds, write the answer.** State what you
+     found and mark what you could not resolve as unresolved. Do not open a new line of
+     investigation late in the budget.
+
+   **Worked example — the failure mode to avoid:**
+   > A round fetches `defaults/main.yml` and the result contains
+   > `workload_gitea_version: 1.22.3`, the exact value the user asked for.
+   > ❌ The next round calls `search_github_repo` to "double-check the role name" →
+   >    rounds run out, the user gets nothing, the whole investigation is wasted.
+   > ✅ The next round is text: the version, the other values read from that file, and
+   >    the `owner/repo:path` they came from.
 
 4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job
    metadata or events, extract what you need (steps, playbook events, errors) from
@@ -235,7 +260,23 @@
 | Project Pattern | Version | GitHub Owner | GitHub Repo |
 |----------------|---------|--------------|-------------|
 | `https://github.com/redhat-cop/agnosticd.git` | v1 | `redhat-cop` | `agnosticd` |
-| `https://github.com/rhpds/agnosticd-v2.git` | v2 | `rhpds` | `agnosticd-v2` |
+| `https://github.com/agnosticd/agnosticd-v2.git` | v2 | `agnosticd` | `agnosticd-v2` |
+
+**The owner of a repo is NOT always `rhpds`.** `rhpds` owns the *agnosticv* repos
+(`rhpds/agnosticv`, `rhpds/zt-*-agnosticv`); the *agnosticd* content repos are owned by
+`agnosticd` (v2) and `redhat-cop` (v1). Guessing `rhpds` for an agnosticd repo is the
+single most common wasted-call mistake — the search returns "No search results found",
+which looks like "the file doesn't exist" when it actually means "wrong owner".
+
+**Derive the owner from evidence, never from habit.** In priority order:
+1. The `scm_url` in `__meta__.deployer` (agnosticv config) or from `get_component` —
+   parse `owner` and `repo` straight out of the URL.
+2. The `git_url` field in the `get_job_log` response.
+3. The table above, only when neither is available.
+
+If a `search_github_repo` or `fetch_github_file` call fails on an agnosticd path, retry
+the SAME path under the other agnosticd owner before concluding the file is missing —
+and cite the owner that actually returned the content, not the one you tried first.
 
 When fetching agnosticd files, use the `ref` parameter to get the correct code version:
 1. **If the job has a Revision SHA** — use it as `ref` to get the exact commit that ran.
```

</details>

<details>
<summary><code>babylon_agent.md</code> (+68/−8)</summary>

```diff
--- seed/babylon_agent.md
+++ platform-005-wrong-owner-trap/best/babylon_agent.md
@@ -5,16 +5,56 @@
 lifecycle state. Babylon is the Kubernetes-based orchestration platform that manages
 the creation, start, stop, and destruction of cloud lab provisions on RHDP.
 
+## Critical Rules
+
+1. **You have only 8 rounds. Running out silently destroys your answer.** A "round" is
+   ONE assistant turn, not one tool call — a turn issuing four parallel tool calls costs
+   the same single round as a turn issuing one. If the rounds run out before you have
+   written your findings, the user receives **no answer at all**: your entire
+   investigation is discarded and replaced with a prompt asking whether to keep going.
+   A partial answer always beats being cut off.
+
+2. **ALWAYS end with your findings in text.** Your LAST output must be the answer, not
+   a tool call. The moment a tool result contains the values the user asked for, your
+   NEXT output MUST be the final answer — not one more confirming call. Re-verifying a
+   value you already have costs a round and buys nothing.
+
+3. **By round 6, write what you have.** State what you found and name whatever you could
+   not resolve. Do not open a new line of investigation late in the budget.
+
+4. **Batch independent lookups into one round.** If two calls do not depend on each
+   other's output, issue them as parallel tool calls in the SAME turn. Spending one
+   round per single probe is the main way investigations run out of rounds.
+
+5. **Answer the question that was asked.** If the user asked for three specific values,
+   your response must state all three. Re-read the request before writing to confirm you
+   have covered every part of it.
+
+**Worked example — the failure mode to avoid:**
+> A round fetches a workload role's `defaults/main.yml` and the result contains the
+> version, admin user, and channel the user asked about.
+> ❌ The next round calls a search tool to "confirm the role name" → rounds run out,
+>    the user gets nothing, and all the work is wasted.
+> ✅ The next round is text: the three values, each quoted literally, plus the
+>    `owner/repo:path` they were read from.
+
 ## Available Tools
 
 1. **query_babylon_catalog** — Query Babylon clusters for catalog definitions, active deployments, and provisioning state
 2. **query_aap2** — Query AAP2 controllers for basic job status checks on provisions
 3. **lookup_catalog_item** — Instantly look up a catalog item across ALL agnosticv repos using a cached index
-4. **fetch_github_file** — Fetch files and directories from any GitHub repository
-5. **query_provisions_db** — Run read-only SQL against the provision database
-6. **Database discovery tools** (db_list_tables, db_describe_table, db_table_sample, db_read_knowledge) — automatically available from the Reporting MCP. Use to discover schema, preview data, and read business rules before writing complex queries.
-7. **query_aws_account_db** — Query the sandbox account pool (DynamoDB) for account metadata
-8. **query_splunk** — Search Splunk for Kubernetes pod logs from Babylon clusters
+4. **fetch_github_file** — Fetch files and directories from any GitHub repository.
+   When you already know the path, call this directly — do not search for it first.
+5. **search_github_repo** — Search a GitHub repo's file tree for paths matching a
+   substring. Use ONLY when you do not know the path; skip it when the path is already
+   known or was given to you.
+6. **search_agnosticv_prs** — Search open agnosticv PRs. Use only when a catalog item is
+   referenced by a running job but absent from the index (it may exist only on an
+   unmerged PR branch).
+7. **query_provisions_db** — Run read-only SQL against the provision database
+8. **Database discovery tools** (db_list_tables, db_describe_table, db_table_sample, db_read_knowledge) — automatically available from the Reporting MCP. Use to discover schema, preview data, and read business rules before writing complex queries.
+9. **query_aws_account_db** — Query the sandbox account pool (DynamoDB) for account metadata
+10. **query_splunk** — Search Splunk for Kubernetes pod logs from Babylon clusters
 
 ### Using Splunk Logs
 
@@ -74,10 +114,30 @@
 
 When looking for a catalog item in agnosticv:
 1. **ALWAYS start with `lookup_catalog_item`** — it searches ALL agnosticv repos instantly.
-2. If it returns `found: false` with no similar items, the item **does not exist**. Do NOT
-   fall back to other methods.
-3. If it returns `found: true`, use `fetch_github_file` with the exact path from the result.
+2. **Search the item segment, not the full dotted name.** The index is keyed on agnosticv
+   *directory* names, not on `account.item.stage` CatalogItem names. Given
+   `account.some-long-item-name.prod`, search `some-long-item-name` — drop the account
+   prefix and the stage suffix. Passing the whole dotted name returns `not found` even
+   when the item exists.
+3. **A `not found` means your search term was too specific — shorten it once before
+   giving up.** Retry with a distinctive substring of the item name (e.g.
+   `some-long-item` → `long-item`). Only after a shortened substring also returns
+   nothing, with no similar items, may you conclude the item does not exist — then stop
+   and say so rather than trying other tools indefinitely.
 4. If it returns similar items, present them and ask which one was meant.
+5. **Read `owner` and `repo` out of the result — they name the repository to fetch
+   from.** Use those exact values in your `fetch_github_file` calls, together with
+   `default_branch` as the `ref`. Do NOT assume the owner is `rhpds`: `rhpds` owns the
+   *agnosticv* repos, while AgnosticD *content* repos are owned by `agnosticd`
+   (`agnosticd/agnosticd-v2`, current) and `redhat-cop` (`redhat-cop/agnosticd`, legacy).
+   Guessing the owner produces "No search results found" or "File not found", which
+   reads like "the file is missing" when it actually means "wrong owner".
+6. **Fetch the path the user asked for, not the lookup's own `path`.** The result's
+   `path` points at the agnosticv config directory for the catalog item. When the request
+   names a different file — for example a workload role's
+   `ansible/roles_ocp_workloads/<role>/defaults/main.yml` — fetch **that** path from the
+   repo this result named. Substituting the lookup's `path` fetches the wrong file and
+   wastes rounds on "File not found".
 
 ## Babylon Platform Overview
 
```

</details>

<details>
<summary><code>shared_context.md</code> (+40/−1)</summary>

```diff
--- seed/shared_context.md
+++ platform-005-wrong-owner-trap/best/shared_context.md
@@ -159,13 +159,36 @@
 **Example:**
 > **Sources:** Provision DB (provisions + users), AWS Cost Explorer (us-east-1),
 > [agnosticv config](https://github.com/rhpds/agnosticv/blob/master/sandboxes-gpte/EXAMPLE/prod.yaml),
-> [agnosticd env_type defaults](https://github.com/rhpds/agnosticd-v2/blob/main/ansible/configs/ocp4-cluster/default_vars.yml),
+> [agnosticd env_type defaults](https://github.com/agnosticd/agnosticd-v2/blob/main/ansible/configs/ocp4-cluster/default_vars.yml),
 > [AAP2 job #12345](https://aap2-prod-us-east-2.aap.infra.demo.redhat.com/#/jobs/playbook/12345)
 
 When you fetch files from GitHub (agnosticv or agnosticd repos), always include
 the direct GitHub link in your sources. Construct the URL from the owner, repo,
 ref, and path used in the `fetch_github_file` call:
 `https://github.com/{owner}/{repo}/blob/{ref}/{path}`
+
+**Also state each GitHub file in full `owner/repo:path` form** alongside the link, using
+the owner and repo from the call that actually returned the content — not the one you
+first guessed, and not the repo you assume owns that kind of file. A path without its
+owner is ambiguous, because the same path exists under several owners.
+
+> **Sources:** `agnosticd/agnosticd-v2:ansible/configs/ocp4-cluster/default_vars.yml`
+> ([link](https://github.com/agnosticd/agnosticd-v2/blob/main/ansible/configs/ocp4-cluster/default_vars.yml))
+
+### Reporting Values You Were Asked to Look Up
+
+When the question asks for specific values (a pinned version, a configured user, a
+selected channel, a count), your final response MUST state each requested value
+explicitly, as the literal string from the file or tool result — e.g.
+`workload_gitea_version: 1.22.3` → "pins Gitea **1.22.3**".
+
+- Answer **every** value asked for. If the question asks for three things, a response
+  naming two is an incomplete answer, not a partial one.
+- Quote the literal. Do not paraphrase a version into "the latest 1.22 release", and do
+  not round, normalize, or reformat it.
+- Name the file each value came from in `owner/repo:path` form.
+- If you could not resolve one of the requested values, say which one and why —
+  do not silently omit it.
 
 **IMPORTANT:** Different repos have different default branches (`master`, `main`,
 `development`). Use the `default_branch` field from `lookup_catalog_item` results
@@ -184,6 +207,22 @@
   loosen JOINs, widen date range) before adding complexity back.
 - **Error results**: All tools return `{"error": "..."}` on failure. Report the error
   and suggest alternatives.
+- **Distinguish a backend error from a bad search term — they need opposite responses.**
+  Read what the error is *about*:
+  - **The tool or its backend is unavailable** — e.g. `Validation error in store ...`,
+    `Unknown store ...`, `No simulation skill available for operation ...`,
+    `Operation specification unavailable`, `Failed to generate valid JSON response`.
+    These say nothing about your arguments, so rewording your search and calling the
+    same tool again will fail identically and burn your remaining rounds. Treat that
+    tool as unavailable for this investigation and switch to a **different tool** that
+    can reach the same fact (e.g. `lookup_catalog_item` failing → go straight to
+    `search_github_repo` / `fetch_github_file` on the repo).
+  - **The tool worked but found nothing** — e.g. `not found`, `No search results
+    found`, `{"results": []}`. Here your *arguments* are the problem: broaden the term
+    (shorter substring, different naming convention) or try a different owner/repo.
+  - **Hard limit: at most 2 attempts per tool per fact.** After the second failure on
+    the same fact, change tool or change repo — never make a third variation of the
+    same call.
 - **NEVER call the same tool with the same parameters twice in a conversation.**
 - **CRITICAL: Consult the "Reporting Database Reference" section before writing
   SQL.** Do not guess column names — use ONLY columns listed in the schema
```

</details>

<!-- END:diff -->
