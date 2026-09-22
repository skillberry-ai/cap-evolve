# platform-004-events-then-config

<!-- BEGIN:auto -->

**task:** `platform-004-events-then-config`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-004-events-then-config/run_20260920_083427` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.733 |
| seed (val, v4_t2_e1) | val | 5 | 0.787 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.400 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.267

**T2 cost/time:** $15.88, 517,799 tokens, 2.05h (eval $1.22/357,549tok · optimizer $14.67/160,250tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-004-events-then-config/run_20260920_083427/report.md`, `.capevolve/v4_t2_e1_platform-004-events-then-config/run_20260920_083427/JOURNAL.md`

<!-- END:auto -->

## What this task is about

A cluster-provision job failed. The task that actually failed, and the role it belongs to, only show up in the job's *events*, not in the log alone, and a config file supplies how many retries the wait was allowed. The seed also includes a second, successful host, so naming the wrong host is a distinguishable mistake.

## What the optimizer tried

Two iterations, both resolving one rule conflict: four different rules told the agent not to make a second `query_aap2` call after `get_job_log` (a redundant-call ban, a round budget, two re-fetch echoes in `shared_context.md`), while only one narrow rule said to make it — and that one lived in a GUID-discovery flow this task never enters, since a separate tip routes a direct job ID straight to `get_job_log`. `cand_0001` rewrote `aap2_agent.md`, `shared_context.md`, and `orchestrator.md` to make all of those rules agree (redundant now means same action *and* same arguments; a new Critical Rule 5 requires `get_job_events(failed_only=true)` after a failed job's log, before any GitHub fetch) and also fixed a `Role` field the report template required but no log in this task's trials could source. `cand_0001` was rejected on paper (val 0.400), but JOURNAL.md's post-mortem — reading all 5 trials' raw records rather than the aggregate — found this was a LiteLLM gateway outage: 2 of 5 trials scored 1.0 with the byte-identical prompt, and the other 3 never received a model response at all (TLS handshake timeouts and a 600s request timeout, before any output was produced). `cand_0002` re-delivered the same behavioral contract in about a third of the diff size (no changes to `orchestrator.md`) and was accepted at val 1.0.

## Why the winning candidate won

JOURNAL.md's `reward-detail.json` reading shows all 5 baseline trials differ at exactly one decision point — whether a second `query_aap2` call happens after `get_job_log` — and that one skipped call costs both the `tool_calls` and `answer` components simultaneously (0.267 of reward). `cand_0002`'s conflict-resolved rules made that call fire consistently, moving val 0.787 → 1.0 (Δ+0.213) and fixing the task per the RESULT line. On the held-out test split, `report.md` records the baseline `seed` skills at 0.713 ± 0.008 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.287; the auto block's `delta vs JB` of 0.000 reflects that the single-trial JB baseline measurement already sat at reward 1.0, not that the optimizer made no difference against the team's own earlier (n=3) baseline of 0.733.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md's own account is a caveat on interpreting any single rejected candidate at face value: `cand_0001`'s val=0.400 looked like a regression but was actually 2 clean 1.0 trials plus 3 infrastructure failures (a gateway outage) that the eval layer scored as 0.0 — a distinction JOURNAL.md says the framework currently cannot make automatically (filed as a framework escalation).

<!-- BEGIN:diff -->

## What changed (seed → best)

2 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-004-events-then-config/best/`](../../../artifacts/v4/platform-004-events-then-config/best/):

<details>
<summary><code>aap2_agent.md</code> (+51/−10)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-004-events-then-config/best/aap2_agent.md
@@ -21,9 +21,33 @@
    failure and write the report. More fetching without analysis is worse than a
    report with some gaps.
 
-4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job
-   metadata or events, extract what you need (steps, playbook events, errors) from
-   the existing result. Do NOT make a redundant second call to the same job.
+4. **Reuse values you already hold — but a different `action` is not a re-fetch.**
+   A `query_aap2` call is redundant only when it repeats the **same `action` with the
+   same arguments**; read that from the existing result instead. Different actions on
+   one job are complementary: `get_job_log` returns the log text, `get_job_events`
+   returns the structured failed-task rows (`role`, `play`, `task`, `host`,
+   `error_msg`). Neither response contains the other's data, so "I already queried
+   this job" is never a reason to skip a different action on it.
+
+5. **A failed job needs the log AND the failed events.** When a job's status is
+   failed or error, call `get_job_events` with `failed_only=true` after `get_job_log`
+   and before any GitHub fetch — including when the user hands you the job ID and you
+   skip the GUID lookup. Pass `failed_only` as the boolean `true`, not the string
+   `"true"` and not `1`. The log gives you the failure *text*; only the events rows
+   carry the **`role`** that owns the failed task. These two calls are the minimum
+   evidence set, so Rule 3's budget does not apply to them — it governs exploratory
+   fetching. Do the events call even when the log looks self-explanatory: the log
+   telling you *what* failed is not the log telling you *which role* it was in.
+
+   Worked example — user asks "why did job 11111 on the `west` controller fail?":
+   ```
+   query_aap2(action="get_job_log",    controller="west", job_id="11111")
+   query_aap2(action="get_job_events", controller="west", job_id="11111", failed_only=true)
+   fetch_github_file(owner=…, repo=…, path=…)   # config trace, using the job's Project URL
+   ```
+   Two `query_aap2` calls, different actions, same job — correct, not a re-fetch. The
+   second one is what lets you name the role; without it the report has a hole you will
+   be tempted to fill by guessing.
 
 ## Available Tools
 
@@ -58,7 +82,8 @@
 3. Read `tower_jobs` from the AnarchySubject — contains controller hostname and job ID
 4. Call `query_aap2` with `get_job_log` using `towerHost` as controller and `deployerJob` as job_id.
    **Always use `get_job_log` instead of `get_job`.**
-5. If the job failed, also call `get_job_events` + `failed_only=true`
+5. If the job failed, also call `get_job_events` + `failed_only=true` (Critical Rule 5)
+   — do it here, before Step 6; the config trace cannot supply the failed task's `role`
 6. Continue to trace the config hierarchy via the "Investigate AAP2 Job Failures" workflow Steps 2+
 
 **If the AnarchySubject is gone**, use `query_aap2(action="find_jobs", template_name="<guid>")`
@@ -93,7 +118,9 @@
   ask the user to double-check the number before sweeping all controllers. If you do
   sweep, check all remaining controllers in a single batch — don't try them one at a time.
 - **When the user provides a specific job ID**, use `get_job_log` directly with that
-  ID — don't use `find_jobs` to search for it first.
+  ID — don't use `find_jobs` to search for it first. This shortcut skips the
+  GUID/Babylon *discovery* steps only; if the job failed, still make the
+  `get_job_events` call from Critical Rule 5.
 
 ### Job Not Found in Database
 
@@ -234,8 +261,13 @@
 
 | Project Pattern | Version | GitHub Owner | GitHub Repo |
 |----------------|---------|--------------|-------------|
-| `https://github.com/redhat-cop/agnosticd.git` | v1 | `redhat-cop` | `agnosticd` |
-| `https://github.com/rhpds/agnosticd-v2.git` | v2 | `rhpds` | `agnosticd-v2` |
+| `.../agnosticd.git` (legacy) | v1 | `redhat-cop` | `agnosticd` |
+| `.../agnosticd-v2.git` | v2 | `agnosticd` | `agnosticd-v2` |
+
+**Parse `owner`/`repo` out of the URL you were actually given** — the job's Project
+URL, a tool result, or the user's question — as `https://github.com/{owner}/{repo}.git`,
+and use exactly that. Fall back to this table only when you have no URL. An owner you
+guessed either 404s or silently returns a different repo's file.
 
 When fetching agnosticd files, use the `ref` parameter to get the correct code version:
 1. **If the job has a Revision SHA** — use it as `ref` to get the exact commit that ran.
@@ -276,7 +308,10 @@
 **Key sections to examine in the log:**
 1. **PLAY RECAP** — Summary of hosts and status
 2. **fatal** or **FAILED** tasks — Actual error messages
-3. **TASK [role_name : task_name]** — Identify which role/task failed
+3. **TASK [...]** — the failed task's name. The `role :` prefix is frequently absent
+   from a rendered log, so a bare `TASK [some name]` does **not** mean the task has no
+   role — that is a rendering detail, not a fact about the playbook. Take the role
+   from the `get_job_events` rows (Critical Rule 5), never from the log's silence.
 4. **Pod status details** — container states, waiting reasons, restart counts, exit codes
 5. **Timing** — how long did the failing operation take? Short = auth/config error. Long = timeout.
 
@@ -401,8 +436,14 @@
 - **Namespace:** `{namespace}` (if CNV)
 
 **Failure Analysis:**
-- **Failed Task:** `{role} : {task_name}`
-- **Host:** `{host}`
+- **Failed Task:** `{task_name}`
+- **Role:** `{role}` — copy the `role` field from the `get_job_events` row for the
+  failed task; that is its only source. If the events rows carry no role, write
+  `not reported in job events`. An `env_type`/config directory, the catalog item, the
+  repo path, and the `PLAY [...]` name are **not** the role — not even when the user's
+  own question handed you that string.
+- **Host:** `{host}` — the host the PLAY RECAP shows with `failed=1`, not the first
+  host mentioned in the log
 - **Error:** the actual error (not "pod failed" — the underlying cause)
 
 For pod/container failures, include:
```

</details>

<details>
<summary><code>shared_context.md</code> (+10/−4)</summary>

```diff
--- seed/shared_context.md
+++ platform-004-events-then-config/best/shared_context.md
@@ -184,7 +184,12 @@
   loosen JOINs, widen date range) before adding complexity back.
 - **Error results**: All tools return `{"error": "..."}` on failure. Report the error
   and suggest alternatives.
-- **NEVER call the same tool with the same parameters twice in a conversation.**
+- **Never repeat an identical call — same tool, same parameters — in a conversation.**
+  If a prior result already holds the value you need, read it from that result instead
+  of calling again. This bans repeating a *call*, not touching a *resource* twice: a
+  different tool, or the same tool with different parameters (a different `action`, a
+  different filter), returns data the first call did not, so it is not a re-fetch and
+  is not redundant.
 - **CRITICAL: Consult the "Reporting Database Reference" section before writing
   SQL.** Do not guess column names — use ONLY columns listed in the schema
   reference. If unsure, call `db_describe_table` to check. Common mistakes:
@@ -195,9 +200,10 @@
   - `tower_job_log` column names are snake_case (`deployer_job`, not `deployerJob`)
   - `provision_cost` is partitioned — always include a `month_ts` filter to avoid full partition scans
   - When joining tables with shared column names (e.g. `category`), always use table aliases to avoid ambiguous column errors
-- **Don't re-fetch data already in context.** If a prior tool call returned data
-  (e.g., job details, provision records), extract what you need from the existing
-  result before making another call.
+- **Reuse values already in context.** If a prior tool call returned the value you
+  need (job details, provision records), read it from that result rather than calling
+  again — but see the identical-call rule above: a *different* action or filter on the
+  same resource returns new data and is not a re-fetch.
 
 ## Grounding — Use Tool Results, Never Hallucinate
 
```

</details>

<!-- END:diff -->
