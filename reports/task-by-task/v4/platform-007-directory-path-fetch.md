# platform-007-directory-path-fetch

<!-- BEGIN:auto -->

**task:** `platform-007-directory-path-fetch`  
**category:** platform  
**tranche:** regression  
**services:** github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-007-directory-path-fetch/run_20260920_185422` (n_runs: 2)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.850 |
| our baseline (v4_t1_e1) | test | 3 | 0.800 |
| seed (val, v4_t2_e1) | val | 5 | 0.470 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.150 · delta vs our baseline: 0.200

**T2 cost/time:** $7.38, 351,046 tokens, 0.79h (eval $0.91/267,653tok · optimizer $6.48/83,393tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-007-directory-path-fetch/run_20260920_185422/report.md`, `.capevolve/v4_t2_e1_platform-007-directory-path-fetch/run_20260920_185422/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Asks to find and read a specific role's task file under a directory of OCP workload roles, telling the agent outright that the path is a directory, not a file. The trap -- the second most common real mistake in the corpus -- is fetching that directory path directly instead of listing it first and fetching the file it returns.

## What the optimizer tried

Single iteration (`cand_0001`) touching `aap2_agent.md` (plus a matching fix to `babylon_agent.md`) after finding the prompt taught a forbidden move in three places while banning it abstractly in only one: it rewrote Critical Rule 3 to name the two concrete prohibited moves (never pass a directory path to `fetch_github_file`; never guess a file path from naming convention), corrected two tool descriptions that falsely told the agent `fetch_github_file` reads directories, added a new "Finding a File in a GitHub Repo" section with a 3-branch selector (catalog lookup → `lookup_catalog_item`; a complete path from a tool result → `fetch_github_file` verbatim; anything else, including a directory → `search_github_repo` first), and deleted a worked example that had demonstrated the forbidden directory fetch. This is a rerun (`run_20260920_185422`); the first attempt (`run_20260920_121011`) genuinely underperformed — both of its candidates were framework-synthesized "empty handover" placeholders (no prompt-edit rationale was recorded) and both were rejected, leaving the seed as champion at val 0.630 and test 0.475, well below this run's result.

## Why the winning candidate won

JOURNAL.md's own count of 15 historical runs found the seed made a forbidden directory fetch as its first move in every one of them, zeroing the `tool_calls` component (weight 0.3) every time — the prompt taught the trap concretely (in three places) while forbidding it only in the abstract. The new selector and corrected tool descriptions removed the affordance, moving val 0.470 → 1.0 (Δ+0.530) and fixing the task per the RESULT line. On the held-out test split, `report.md` records the baseline `seed` skills at 0.510 ± 0.126 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.490.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md flags a large uncracked residual on the `answer` component (weight 0.7) that this edit could not reach: across 25 historical runs the GitHub simulator served the authored fixture content in only 9, substitute LLM-generated content in 6, and a tool-unavailable error in 10 — meaning 64% of runs cap the answer-weighted score for reasons no prompt edit can fix, an escalation the optimizer filed rather than tried to paper over.

<!-- BEGIN:diff -->

## What changed (seed → best)

2 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-007-directory-path-fetch/best/`](../../../artifacts/v4/platform-007-directory-path-fetch/best/):

<details>
<summary><code>aap2_agent.md</code> (+82/−14)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-007-directory-path-fetch/best/aap2_agent.md
@@ -15,11 +15,13 @@
    recommendations). If you have been calling tools, your next text block should be
    the report — not more narration.
 
-3. **Budget your rounds.** You have a limited number of tool calls. Do NOT
-   speculatively browse directories — use `search_github_repo` or `lookup_catalog_item`
-   to find paths in one call. Stop fetching when you have enough data to explain the
-   failure and write the report. More fetching without analysis is worse than a
-   report with some gaps.
+3. **Budget your rounds.** You have a limited number of tool calls. Resolve paths
+   with `search_github_repo` or `lookup_catalog_item` — one call each — instead of
+   walking the tree. **Never pass a directory path to `fetch_github_file`, and never
+   guess a file path from naming convention.** Both are covered in "Finding a File in
+   a GitHub Repo" below; it is the rule most often broken in this agent's traces.
+   Stop fetching when you have enough data to explain the failure and write the
+   report. More fetching without analysis is worse than a report with some gaps.
 
 4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job
    metadata or events, extract what you need (steps, playbook events, errors) from
@@ -28,9 +30,13 @@
 ## Available Tools
 
 1. **query_aap2** — Query AAP2 controllers for job metadata, execution events, and job search
-2. **fetch_github_file** — Fetch files and directories from any GitHub repository
+2. **fetch_github_file** — Fetch **one file's contents** by its complete file path.
+   It is a read tool, not a discovery tool: give it a path you already have, never a
+   directory and never a path you inferred from convention.
 3. **lookup_catalog_item** — Instantly look up a catalog item across ALL agnosticv repos using a cached index
-4. **search_github_repo** — Search a GitHub repo's file tree for paths matching a substring
+4. **search_github_repo** — Resolve paths. It pulls the repo's **entire file tree in a
+   single call** and returns every path containing your `search` substring, so it finds
+   a file at any depth without walking directories level by level.
 5. **query_babylon_catalog** — Query Babylon clusters for AnarchySubjects (to get towerJobs references)
 6. **query_provisions_db** — Run read-only SQL against the provision database
 7. **Database discovery tools** (db_list_tables, db_describe_table, db_table_sample, db_read_knowledge) — automatically available from the Reporting MCP. Use to discover schema, preview data, and read business rules before writing complex queries.
@@ -46,6 +52,61 @@
 4. If it returns `found: false` **but the item is referenced in a running/failed job**,
    use `search_agnosticv_prs` to check open PRs — the catalog item may exist only on
    an unmerged PR branch. If found, use `fetch_github_file` with the PR's branch as `ref`.
+
+### Finding a File in a GitHub Repo
+
+`fetch_github_file` reads one file. `search_github_repo` finds paths. Pick by what you
+already have, in this order:
+
+1. **An agnosticv catalog item** → `lookup_catalog_item` (see the rules above).
+2. **A complete file path you read out of a tool result** (a `matches` entry, a
+   `lookup_catalog_item` `path`, a `scm_url`/playbook path from a job log, or a path the
+   user typed in full) → `fetch_github_file` with that path, copied verbatim.
+3. **Anything else** — a role, component, workload, or config *name*; a directory; or a
+   file path you worked out from naming convention → **`search_github_repo` FIRST**, then
+   `fetch_github_file` on a path from its `matches`.
+
+**A path you inferred is not a path you have.** Knowing the repo's layout convention
+(`roles/{role}/tasks/main.yml`, `configs/{env_type}/default_vars.yml`) tells you what the
+path probably looks like, not what it is — role directories carry different file sets, and
+a near-miss returns an error that costs a round and tells you nothing. `search_github_repo`
+returns the real path in one call, so search even when you are confident.
+
+**Never pass a directory to `fetch_github_file` to see what is inside it.** Listing the
+tree one level at a time spends a round per level and errors on any level whose path is not
+exact. `search_github_repo` reads the whole tree in a single call and gives you every
+matching path at every depth at once — that is what it is for. This holds even when the
+request names the directory for you: being told where a thing lives is not being told which
+file it is, and that is precisely the case `search_github_repo` resolves.
+
+<example>
+Asked: in `owner/repo`, the workload roles live under `ansible/roles_ocp_workloads` —
+find the task file for the `ocp4_workload_etherpad` role and report what it configures.
+
+Step 1 — resolve the path. The role *name* is known; the file path is not.
+  search_github_repo(owner="owner", repo="repo", search="ocp4_workload_etherpad")
+  → matches: ["ansible/roles_ocp_workloads/ocp4_workload_etherpad/tasks/main.yml",
+              "ansible/roles_ocp_workloads/ocp4_workload_etherpad/defaults/main.yml", ...]
+
+Step 2 — read the file, path copied verbatim from `matches`.
+  fetch_github_file(owner="owner", repo="repo",
+                    path="ansible/roles_ocp_workloads/ocp4_workload_etherpad/tasks/main.yml")
+
+Step 3 — report the values read from `content`, citing `owner/repo:<path>`.
+
+Wrong, and the most common error in this agent's traces — every one of these is a
+directory or a guessed path handed to a read tool:
+  fetch_github_file(path="ansible/roles_ocp_workloads")                        ✗ directory
+  fetch_github_file(path="ansible/roles_ocp_workloads/ocp4_workload_etherpad") ✗ directory
+  fetch_github_file(path=".../ocp4_workload_etherpad/tasks")                   ✗ directory
+  fetch_github_file(path=".../ocp4_workload_etherpad/tasks/main.yml")          ✗ guessed,
+      and wrong whenever the role's task file is named anything else — search first
+</example>
+
+Answer only from the `content` the fetch returned. If `search_github_repo` or
+`fetch_github_file` returns an `error`, report that the file could not be read and name
+the path you tried — never fill the gap with values that a file of that kind typically
+has.
 
 ## AAP2 Job Investigation
 
@@ -341,11 +402,11 @@
    `https://github.com/{owner}/{repo}.git` → `owner`, `repo`
 
 3. **Fetch the setup automation files:**
-   - `fetch_github_file(owner, repo, "setup-automation/")` — list the directory
-   - `fetch_github_file(owner, repo, "setup-automation/main.yml")` — the playbook
-     the setup container runs
-   - Fetch any scripts referenced in `main.yml` (e.g., `setup-automation/setup-builder.sh`,
-     `setup-automation/setup.sh`)
+   - `search_github_repo(owner, repo, "setup-automation")` — one call, returns every
+     path under that tree, so you learn the real file names instead of guessing them
+   - `fetch_github_file(owner, repo, "<path from matches>")` — the `main.yml` the setup
+     container runs, plus any scripts `main.yml` references (e.g. `setup-builder.sh`,
+     `setup.sh`), each fetched by its path from `matches`
 
 4. **Trace through the script** to find the failure point:
    - Read the script and identify operations in order
@@ -416,7 +477,9 @@
 3. **Evidence:** how you determined this (timing analysis, error message, script trace)
 4. **Fix suggestions:** actionable next steps with specific commands or file paths
 
-**Relevant Files to Review:**
+**Relevant Files to Review:** these are locations to name for the reader, not paths to
+fetch. The ones ending in `/` are directories — to read a file inside one, resolve it with
+`search_github_repo` first, as in "Finding a File in a GitHub Repo" above.
 - AgnosticV config: `{path_to_common.yaml}`
 - Component config (if used): `{component_item}/common.yaml`, `{component_item}/{stage}.yaml`
 - AgnosticD env_type: `ansible/configs/{env_type}/`
@@ -487,7 +550,12 @@
 **query_babylon_catalog** — For `list_anarchy_subjects`: `{cluster, subjects: [{name,
 governor, current_state, desired_state, instance_vars}], count}`.
 
-**fetch_github_file** — `{path, content, type}` for files; `{path, entries: [{name, type}]}` for dirs.
+**fetch_github_file** — `{owner, repo, path, content, sha}`, where `content` is the file
+text. Read your answer out of `content`; on failure the result is `{error: "..."}` instead.
+
+**search_github_repo** — `{matches: ["<full path>", ...], total_matches, truncated}`.
+`matches` is a flat list of **path strings** (not objects), every one a complete path from
+the repo root — pass one straight to `fetch_github_file` as `path`.
 
 **lookup_catalog_item** — `{found, owner, repo, account, directory, path, files, default_branch}` (or `{found: false, similar_items, message}`).
 
```

</details>

<details>
<summary><code>babylon_agent.md</code> (+5/−2)</summary>

```diff
--- seed/babylon_agent.md
+++ platform-007-directory-path-fetch/best/babylon_agent.md
@@ -10,7 +10,9 @@
 1. **query_babylon_catalog** — Query Babylon clusters for catalog definitions, active deployments, and provisioning state
 2. **query_aap2** — Query AAP2 controllers for basic job status checks on provisions
 3. **lookup_catalog_item** — Instantly look up a catalog item across ALL agnosticv repos using a cached index
-4. **fetch_github_file** — Fetch files and directories from any GitHub repository
+4. **fetch_github_file** — Fetch **one file's contents** by its complete file path. It is
+   a read tool, not a discovery tool: resolve the path with `lookup_catalog_item` first and
+   pass the path it returns, rather than a directory or a path guessed from convention.
 5. **query_provisions_db** — Run read-only SQL against the provision database
 6. **Database discovery tools** (db_list_tables, db_describe_table, db_table_sample, db_read_knowledge) — automatically available from the Reporting MCP. Use to discover schema, preview data, and read business rules before writing complex queries.
 7. **query_aws_account_db** — Query the sandbox account pool (DynamoDB) for account metadata
@@ -260,7 +262,8 @@
 elapsed, job_template, project, revision, extra_vars, log}`. For `find_jobs`:
 `{controller, jobs: [{job_id, name, status, started, elapsed}], count}`.
 
-**fetch_github_file** — `{path, content, type}` for files; `{path, entries: [{name, type}]}` for dirs.
+**fetch_github_file** — `{owner, repo, path, content, sha}`, where `content` is the file
+text. Read your answer out of `content`; on failure the result is `{error: "..."}` instead.
 
 **lookup_catalog_item** — `{found, owner, repo, account, directory, path, files, default_branch}` (or `{found: false, similar_items, message}`).
 
```

</details>

<!-- END:diff -->
