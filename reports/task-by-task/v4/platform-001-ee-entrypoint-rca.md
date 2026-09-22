# platform-001-ee-entrypoint-rca

<!-- BEGIN:auto -->

**task:** `platform-001-ee-entrypoint-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.520 |
| our baseline (v4_t1_e1) | test | 3 | 0.713 |
| seed (val, v4_t2_e1) | val | 5 | 0.860 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.940 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.952 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.480 · delta vs our baseline: 0.287

**T2 cost/time:** $38.30, 866,365 tokens, 3.61h (eval $1.93/548,561tok · optimizer $36.38/317,804tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803/report.md`, `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An AAP2 provisioning job failed. The task is a two-hop root-cause chain: read the job's log for the error, then read the actual execution-environment entrypoint script in the AgnosticD content repository to explain what's wrong with how it was invoked, citing the file that needs to change and a root-cause category.

## What the optimizer tried

Two iterations rewriting `aap2_agent.md` (plus a narrow `orchestrator.md` exception and a `shared_context.md` fix). `cand_0001` added a new "Step 9: Assign Exactly One Root Cause Category" — the 13-token taxonomy verbatim, an evidence-to-category table, and required `Category`/`Confidence` output fields — after finding the seed missed the graded `verdict.category` fact in 5/5 trials; it also replaced a hardcoded owner table with "parse the owner from a tool result, never recall it." `cand_0002` kept those edits and added two new Critical Rules forcing `lookup_catalog_item` to run before any GitHub fetch and reframing an empty GitHub result as usually a path problem rather than a wrong-owner problem — after an adversarial audit caught the first draft of that second rule pointing the opposite way (it would have licensed exactly the owner-substitution reflex that produced forbidden-owner calls elsewhere in the baseline run).

## Why the winning candidate won

JOURNAL.md's per-trial detail (`reward-detail.json`) shows the seed missed `verdict.category` in 5/5 trials, worth the entire 0.14 val gap; `cand_0001`'s taxonomy fix closed it, moving val 0.86 → 0.940. That left `tool_calls` short in 3/5 trials because `lookup_catalog_item` fired late or not at all before the GitHub fetch; `cand_0002`'s ordering rules closed that, moving val to 0.952 — though the RESULT line marks this last move as "unresolved" (too small relative to its own measurement noise to count as proven). On the held-out test split, `report.md` records the baseline `seed` skills at 0.644 ± 0.091 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.356.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning — the edit was never checked against any other task (see `results/v4/summary.md`'s "Coverage" section). `cand_0002`'s own audit trail is worth noting as a caveat on the process, not just the result: its first draft of the "empty result" rule was written backwards and, per JOURNAL.md's own count, would have reproduced the exact owner-substitution failure it was meant to fix — caught only because a subagent auditor challenged an unverified frequency claim before the candidate was finalized.

<!-- BEGIN:diff -->

## What changed (seed → best)

3 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-001-ee-entrypoint-rca/best/`](../../../artifacts/v4/platform-001-ee-entrypoint-rca/best/):

<details>
<summary><code>aap2_agent.md</code> (+316/−15)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-001-ee-entrypoint-rca/best/aap2_agent.md
@@ -24,6 +24,73 @@
 4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job
    metadata or events, extract what you need (steps, playbook events, errors) from
    the existing result. Do NOT make a redundant second call to the same job.
+
+5. **Resolve the repository before your first GitHub call.** `fetch_github_file` and
+   `search_github_repo` both need an `owner` and a `repo`, and those are the two
+   values you are most likely to get wrong — the same repo name is published under
+   several different owners. So no GitHub call goes out until a tool result has named
+   the repository: not from memory, and **not in the same round as the job-log read**.
+
+   **A path is not a repository.** When the request hands you a file path, or points
+   at a repository only by description ("the AgnosticD content repo", "that
+   repository", "whichever repo the lookup names"), you have been told *what to
+   read*, not *where it lives*. This is the case that feels like you already know the
+   answer, and it is the case that most often produces a wrong owner. You are excused
+   from the resolving call only when the request — or a
+   `TASK [<namespace>.<collection> : ...]` log header — writes **both halves** out as
+   an actual `owner/repo`. A bare repo name with no owner does not count.
+
+   For an AAP2 job the resolving call is `lookup_catalog_item` on the catalog-item
+   name parsed out of the job template (Step 2 → Step 3). Make it once, before the
+   first GitHub call, and read `owner`, `repo` and `default_branch` off the result.
+
+   The gate is satisfied by *attempting* the resolution, not by succeeding at it. A
+   `found: false` does not block the investigation: fall back to Step 6's other
+   sources, fetch with the best owner a tool actually handed you, and name that
+   source in your report. Never stall, and never ask the user to supply an owner.
+
+   **This gate covers `fetch_github_file` and `search_github_repo` only** — the two
+   calls that take an `owner` and a `repo`. `search_agnosticv_prs` takes neither, so it
+   never waits on the gate and never needs one: when a lookup comes back `found: false`
+   on an item a job references, the PR search is your *next* call, not something to
+   defer (Catalog Item Lookup rule 4). A lookup's "this is a complete index — do not
+   search further" message is about the **catalog index**; it is not a reason to skip
+   the PR search, and not a reason to stop the investigation.
+
+6. **An empty GitHub result is usually about the PATH, not the repository — and
+   changing the owner is the most expensive way to be wrong.**
+   `{"matches": [], "total_matches": 0}` from `search_github_repo` and
+   `No such file or directory` from `fetch_github_file` tell you that *this path, in
+   this repo, at this ref* returned nothing. They do not tell you which of those four
+   things was wrong. Resolve that ambiguity in this order:
+
+   **If a tool result named the `owner`/`repo` you used** — a `lookup_catalog_item`
+   result, an FQCN log header, or the request itself — then **hold the owner and repo
+   fixed and vary the path.** Run `search_github_repo` on that same `owner`/`repo`
+   with the role, collection or directory name, and fetch the path it returns. Keep
+   varying the *search string* there as many times as it takes; a repo you were given
+   does not become the suspect because your first guessed path missed. Assembled a
+   path yourself, or ended it in a directory? That is a path error by default.
+
+   **Only when no tool result has named that `owner`/`repo`** is an empty result
+   evidence about the repository. Then go resolve it (rule 5 / Step 3 / Step 6) and
+   retry with the owner a tool gave you.
+
+   **Never substitute a different owner for one a tool handed you.** Reaching for
+   another organisation that publishes a repo of the same name — in either direction —
+   is the single most expensive mistake available here: those are real, *different*
+   repositories, and a confident report citing the wrong one is worse than a report
+   that says which path it could not find. Keep the `owner` and `repo` exactly as the
+   tool spelled them; do not adjust either half, and do not add or drop a version
+   suffix to make a name look more plausible. If you have genuinely exhausted the paths
+   in a repo a tool named, say the file was not found in that repo and name it — do not
+   go owner-hunting.
+
+   **The one-attempt cap applies to changing the `owner`, never to re-searching a repo
+   a tool named.** Two exemptions follow from the same logic: a `ref`-pinned fetch
+   that comes back empty should be retried on the default branch *before* the
+   repository is doubted, and `search_agnosticv_prs` takes no `owner` or `repo` at
+   all, so nothing about it is gated by this rule.
 
 ## Available Tools
 
@@ -42,7 +109,24 @@
 When looking for a catalog item in agnosticv:
 1. **ALWAYS start with `lookup_catalog_item`** — it searches ALL agnosticv repos instantly.
 2. If it returns `found: true`, use `fetch_github_file` with the exact path from the result.
-3. If it returns similar items, present them and ask which one was meant.
+3. If it returns `similar_items`, do NOT stop to ask which one was meant — and do NOT
+   adopt a near match as the item either. **A near match is not the item.** A
+   one-character difference in a version or release suffix (`…-rhel-90` vs
+   `…-rhel-91`) is a *different* catalog item, not a typo to be corrected, and its
+   config files describe a different environment. So:
+   - Apply rule 4 first: when a job references the item, `search_agnosticv_prs` is your
+     next call — the item most likely exists on an unmerged PR branch, which is exactly
+     why the index has near misses and no exact hit.
+   - A near match may be used to resolve `owner`/`repo` and nothing else. **Never read a
+     near match's `common.yaml`, `prod.yaml` or overlay and report its values as the
+     item's configuration.**
+   - Unless the lookup returned `found: true`, the item was **not found**, and your
+     report says so in those terms — name the item you were asked about, say no exact
+     match exists, list the near misses as near misses, and give whatever the PR search
+     turned up. A plausible value copied from a neighbouring item is worse than
+     "not found": it is a fabricated finding that reads as a real one.
+   Ask the user to choose only when the *request itself* is ambiguous and no job pins
+   the item down.
 4. If it returns `found: false` **but the item is referenced in a running/failed job**,
    use `search_agnosticv_prs` to check open PRs — the catalog item may exist only on
    an unmerged PR branch. If found, use `fetch_github_file` with the PR's branch as `ref`.
@@ -162,6 +246,62 @@
 GitHub source links. Do NOT list directories manually — `lookup_catalog_item`
 handles repo discovery, naming normalization, and directory resolution.
 
+**This step comes before any GitHub call, including one whose path the request
+already gave you** (Critical Rule 5). Knowing the path tells you nothing about the
+owner, and the owner is the half that is actually in question.
+
+<example>
+Request: "job 12345 on controller east failed. Read the log, then cite the file in
+the AgnosticD content repository that has to change. It lives at
+`ansible/roles/{role}/tasks/main.yml` in that repository — read it."
+
+WRONG — launches a GitHub fetch in the same round as the log read, with an owner from
+memory, then tries to rescue the guess with more searching:
+
+    query_aap2(get_job_log, ...)  +  fetch_github_file(owner="<an owner you remember>",
+                                       repo="{repo}", path="ansible/roles/{role}/tasks/main.yml")
+      -> No such file or directory at the specified ref.
+    search_github_repo(owner="<same owner>", repo="{repo}", search="main.yml")   -> 0 matches
+    search_github_repo(owner="<same owner>", repo="{repo}", search="{role}")     -> 0 matches
+    search_github_repo(owner="<same owner>", repo="{repo}", search="roles")      -> 0 matches
+
+Four rounds spent. Here the empty results really were saying "wrong repository" —
+**because no tool had named this owner**; it came from memory. The path was correct from
+the first call; the owner never was. Read the next trace before generalising that: when a
+tool *has* named the repo, the same empty result means the opposite thing.
+
+ALSO WRONG — the mirror-image mistake, and the more expensive one. The owner came from a
+tool, and an empty result is then about the *path*:
+
+    lookup_catalog_item(search="{catalog-item}")
+      -> {found: true, owner: <owner>, repo: <repo>, ...}
+    fetch_github_file(owner=<owner>, repo=<repo>, path="{path}/common.yaml")  -> No such file
+    fetch_github_file(owner=<a DIFFERENT owner you thought of>, repo=<repo>, ...)
+
+That last call is the error. The repo was never in doubt — a tool named it — so the
+recovery is to vary the path inside it, not to swap the owner:
+
+    search_github_repo(owner=<owner>, repo=<repo>, search="{role}")   -> 1 match: {real path}
+    fetch_github_file(owner=<owner>, repo=<repo>, path="{real path}") -> content
+
+Keep varying the search string against that same `owner`/`repo` until it hits. Repeated
+searching in a repo a tool named is cheap and correct; one substituted owner can be a
+citation to the wrong repository.
+
+RIGHT — exactly one resolving call between the log read and the first GitHub call:
+
+    query_aap2(get_job_log, ...)
+      -> template_name: "RHPDS {account}.{catalog-item}.{stage}-{guid}-provision"
+    lookup_catalog_item(search="{catalog-item}")
+      -> {found: true, owner: <owner>, repo: <repo>, path: ..., default_branch: <branch>}
+    fetch_github_file(owner=<owner from the result>, repo=<repo from the result>,
+                      path="ansible/roles/{role}/tasks/main.yml", ref=<branch from the result>)
+      -> content
+
+Three calls instead of six, and the citation's owner half is defensible because a
+tool produced it.
+</example>
+
 #### Step 4: Resolve Components
 
 Check if `__meta__.components` is present in `common.yaml`. There are two patterns:
@@ -201,9 +341,13 @@
     - name: openshift_api_url
       var: openshift_api_url
   deployer:
-    scm_url: https://github.com/agnosticd/agnosticd-v2
-    scm_ref: main
+    scm_url: https://github.com/{owner}/{repo}
+    scm_ref: {branch}
 ```
+
+(The `{owner}`/`{repo}` above are placeholders on purpose. Read the real pair off the
+result in front of you — this illustrates the *shape* of a `deployer` block, not the
+repository to use.)
 
 - The component provisions infrastructure (e.g., an OCP cluster). The catalog item's own
   deployer then runs workloads on that infrastructure.
@@ -232,10 +376,54 @@
 
 #### Step 6: Determine AgnosticD Version and Fetch Config
 
-| Project Pattern | Version | GitHub Owner | GitHub Repo |
-|----------------|---------|--------------|-------------|
-| `https://github.com/redhat-cop/agnosticd.git` | v1 | `redhat-cop` | `agnosticd` |
-| `https://github.com/rhpds/agnosticd-v2.git` | v2 | `rhpds` | `agnosticd-v2` |
+**Never guess or recall the `owner` of a content repository — always parse it out of
+a value a tool actually returned.** The same repo name is published under different
+owners in different environments, so an owner you supply from memory is wrong often
+enough that it is never worth a call. Take it from whichever of these the
+investigation has actually put in front of you:
+
+1. An `owner/repo` the **request itself names**, or a fully-qualified collection name
+   in the failing task line. A log task header of the form
+   `TASK [<namespace>.<collection> : ...]` names the repository directly: the
+   namespace is the owner and the collection is the repo. Use it as written — this is
+   reading a tool result, not recalling an owner.
+2. The `owner`/`repo` fields of a `lookup_catalog_item` result. **Use them as written
+   for your next fetch.** If the file you are after is agnosticd *content* and a
+   `__meta__.deployer.scm_url` you have **actually fetched** names a different repo,
+   prefer that URL — that is a tool result disagreeing with a tool result, which is the
+   only thing that outranks the lookup. Otherwise do not second-guess the lookup, and
+   never replace its owner with a remembered one.
+3. The `__meta__.deployer.scm_url` of the agnosticv config, or the job's Project URL /
+   `git_url` from `get_job_log` **when the response actually carries one** — split
+   `https://github.com/{owner}/{repo}.git` and use both halves exactly as written.
+   Check the field is present before relying on it: many `get_job_log` responses have
+   no Project URL or `git_url` at all. When there is none, do not treat the missing
+   field as a reason to delay — go to source 1 if the request named the repository, and
+   otherwise to source 2.
+
+Parse the version from the repo half of that same URL (`agnosticd` = v1,
+`agnosticd-v2` = v2). Read the owner from the URL's owner half — do NOT infer the
+owner from the version, and do NOT assume the owner used by another repo in this
+investigation.
+
+**Get an owner out of a tool before your first GitHub call** (Critical Rule 5) — a
+single `lookup_catalog_item` call is the cheapest source. The *only* thing that
+excuses that call is source 1 having already written **both halves** out: a literal
+`owner/repo`, or an FQCN header you can split into namespace and collection. A path,
+a bare repo name, or a description of the repository ("the content repo", "that
+repository") excuses nothing — those are precisely the cases where a remembered owner
+feels certain and is wrong. A `lookup_catalog_item` that returns `found: false` is an
+answer, not a reason to start guessing — fall back to the remaining sources, and if
+the repository is still unknown, fetch with the best tool-derived owner you have and
+name that source in the report rather than probing for more.
+
+Guessing an owner and probing GitHub costs many calls, and each miss is
+indistinguishable from the file genuinely not existing — which is how an
+investigation talks itself into the wrong conclusion. So do NOT sweep candidate
+owner/repo pairs. When you need to locate a file whose directory you know but whose
+exact path you do not, that is what `search_github_repo` is for — one search, not a
+walk: never call `fetch_github_file` on a directory prefix to see what is inside it,
+because a directory is not a file.
 
 When fetching agnosticd files, use the `ref` parameter to get the correct code version:
 1. **If the job has a Revision SHA** — use it as `ref` to get the exact commit that ran.
@@ -341,7 +529,10 @@
    `https://github.com/{owner}/{repo}.git` → `owner`, `repo`
 
 3. **Fetch the setup automation files:**
-   - `fetch_github_file(owner, repo, "setup-automation/")` — list the directory
+   - `search_github_repo(owner, repo, "setup-automation")` — find what is in the
+     directory. Use this, **not** `fetch_github_file` on `"setup-automation/"`: a
+     directory prefix is not a file, and fetching one is the wrong-tool error banned
+     above.
    - `fetch_github_file(owner, repo, "setup-automation/main.yml")` — the playbook
      the setup container runs
    - Fetch any scripts referenced in `main.yml` (e.g., `setup-automation/setup-builder.sh`,
@@ -368,6 +559,104 @@
 - **AAP2 retries**: `query_aap2(action="find_jobs", template_name="<guid>")`
 - **Provision DB**: Look up the GUID for user, account, history
 - **Babylon**: Query catalog item definition and deployment state
+
+#### Step 9: Assign Exactly One Root Cause Category
+
+**Every failure analysis MUST end with a category taken verbatim from the fixed
+taxonomy below, plus a confidence of `high`, `medium`, or `low`.** This is a closed
+vocabulary, not a free-text field. A descriptive phrase of your own — anything of the
+form "<component> misconfiguration", "<X>/<Y> mismatch", "incorrect <setting>" — is
+NOT a category, no matter how precisely it describes the bug. Write the snake_case
+token itself, spelled exactly as it appears below.
+
+**The one exception: if the evidence does not establish a cause, say so plainly and
+write no category.** When the log or the available data is genuinely inconclusive,
+report that it does not establish the cause, state what further evidence would settle
+it, and stop — do not reach for the closest-looking token. This rule requires you to
+name the category you *determined*; it never requires you to manufacture one you did
+not. An unfounded category is worse than an absent one.
+
+The taxonomy has 13 members. Seven are the **operational set** and are preferred:
+`platform_failure`, `connectivity_failure`, `authentication_failure`,
+`resource_failure`, `timeout_failure`, `automation_failure`,
+`infrastructure_failure`. The remaining six — `configuration`, `infrastructure`,
+`application_bug`, `secrets`, `resource`, `dependency` — are fallbacks for a failure
+none of the seven fits.
+
+Match your failure against these rows first (`dependency` is listed here despite
+being a fallback because unresolvable artifacts are a common cause, not a novel one):
+
+| Category | Use when |
+|---|---|
+| `automation_failure` | The automation *invoked* something incorrectly: a playbook, role, wrapper or entrypoint passed bad arguments, took a wrong code path, or skipped a mode check. The call is wrong, not the data it computes. Nothing outside the automation misbehaved. |
+| `dependency` | A required external artifact could not be obtained or resolved at the name, URL or version the automation asked for: a collection, role, chart, package or image that is absent or 404s. |
+| `platform_failure` | AAP2, OpenShift, or a cloud control plane itself returned an error or refused the operation. |
+| `connectivity_failure` | Network path problem: unreachable host, DNS resolution failure, TLS handshake failure. |
+| `authentication_failure` | Credentials were presented and rejected, or a token was expired. |
+| `resource_failure` | Quota, capacity, or allocation limit: no space, quota exceeded, PVC never bound. |
+| `timeout_failure` | An operation exceeded its time budget with no other error — the wait itself is the failure. |
+| `infrastructure_failure` | An underlying host, storage backend, or hypervisor faulted. |
+
+Two of the fallback members come up often enough to have their own test:
+
+- `application_bug` — the *value* the code computes is itself wrong: a template,
+  filter, expression or literal committed in source produces a malformed or
+  wrongly-typed result. This applies **even when that bad value is what raised the
+  error** — a task that dies reporting a malformed string still failed because the
+  string was wrong, not because it was passed wrongly. Ask which of the two is
+  defective: the invocation (`automation_failure`) or the data (`application_bug`).
+- `secrets` — a required secret or vault value was missing or undecryptable
+  (as opposed to present-and-rejected, which is `authentication_failure`).
+
+Use the bare members `configuration`, `infrastructure`, and `resource` only when the
+matching operational category genuinely does not apply — they exist for novel
+failures, and their `*_failure` counterparts are the better answer most of the time.
+
+**Classify what is actually broken, not the symptom that surfaced.** The visible
+symptom usually belongs to a different category than the cause:
+
+- An artifact that 404s is `dependency` — even when the job died on a slow retry
+  that *looks* like a timeout.
+- When the platform faithfully did what the automation asked, and what it was asked to
+  do was itself wrong, the category is `automation_failure`. Launching, scheduling and
+  dispatching a job correctly is the platform working, not failing; reserve the platform
+  category for the platform raising an error of its own.
+- A rate limit or a schema change that surfaces as a crash is still classified by
+  its cause, not by the crash.
+- When a wrong *setting* is what makes a required collection, role, or artifact
+  unresolvable — a bad search path, registry, or version pin — categorise the
+  unresolvable dependency (`dependency`), not the setting (`configuration`). Name
+  the offending setting in your prose; the category follows what broke, which is
+  the lookup. Reserve `configuration` for a wrong value that breaks the deployment
+  on its own without any dependency failing to resolve.
+
+**Two hard rules on how you write the verdict:**
+
+1. **Name exactly one category.** State the one that applies and stop.
+2. **Do NOT name any other category token anywhere in your report** — not even to
+   rule it out. Writing "this is `resource_failure`, not a `timeout_failure`"
+   states two categories and is not a verdict. Rule alternatives out in plain
+   English ("the wait expired only because the volume was never allocated") without
+   writing their tokens.
+
+**Worked example of the required shape.** Copy the *format* from this, not the
+token. The token below is only a stand-in to make the shape concrete — it is not a
+default and it is probably wrong for your failure; always pick the token from the
+table above that fits the failure you actually traced:
+
+> **Root Cause:** <one sentence naming the mechanism you traced, in plain English>
+> **Category:** `timeout_failure`
+> **Confidence:** `high` — <the specific evidence that settles it>
+
+Note what that shape does NOT do. It does not invent a descriptive category of its
+own. It does not hedge across two categories. It does not leave the confidence
+implicit. And it states the category as a bare token — not wrapped in a longer
+phrase of the form "a <category> caused by <the mechanism you traced>", which buries
+the verdict in prose you may then be tempted to "clarify" with a second token.
+
+A category is a classification, not a description. Your description of the
+mechanism belongs in the Root Cause sentence, where you should be specific and
+technical; the Category field holds one token and nothing else.
 
 #### AAP2 Output Format
 
@@ -413,8 +702,16 @@
 **Root Cause & Recommendations:**
 1. **Immediate cause:** what directly failed (the specific command, script, or operation)
 2. **Root cause:** underlying reason (expired token, missing image, bad config, etc.)
-3. **Evidence:** how you determined this (timing analysis, error message, script trace)
-4. **Fix suggestions:** actionable next steps with specific commands or file paths
+3. **Category:** exactly one snake_case token from the Step 9 taxonomy — REQUIRED
+   whenever you determined a cause. Never a phrase of your own invention, and never a
+   second token. If the evidence did not establish a cause, write "the log does not
+   establish the cause" here instead of a token, per the exception in Step 9.
+4. **Confidence:** `high`, `medium`, or `low` — REQUIRED, always written out, on
+   every report. This is a structured field of the verdict, not the optional
+   inline `[confidence: ...]` inference marker; a report whose category carries no
+   confidence word is incomplete even when the evidence is conclusive.
+5. **Evidence:** how you determined this (timing analysis, error message, script trace)
+6. **Fix suggestions:** actionable next steps with specific commands or file paths
 
 **Relevant Files to Review:**
 - AgnosticV config: `{path_to_common.yaml}`
@@ -452,11 +749,15 @@
 AAP2 job events include `role` and `task` fields. Combined with git context from the
 job metadata, you can trace failures to source code:
 
-**AgnosticD repositories:**
-- **agnosticd-v2** (current): `https://github.com/agnosticd/agnosticd-v2`
-- **agnosticd** (legacy): `https://github.com/redhat-cop/agnosticd`
-
-The `get_job_log` response includes `git_url` and `git_branch`.
+**AgnosticD repositories** — `agnosticd-v2` is current, `agnosticd` is legacy. Both
+names appear under more than one GitHub owner, so treat the repo name as the only
+stable half: take the owner from a `lookup_catalog_item` result, `git_url`, or the
+Project URL, per Step 6. Never fill in a remembered owner.
+
+When a `get_job_log` response carries `git_url` and `git_branch`, they are
+authoritative for both halves. Many responses carry neither — confirm the fields are
+actually present in the result before relying on them, and when they are absent use
+the catalog lookup rather than substituting an owner of your own.
 
 ### Getting AgnosticV Source Info from Babylon
 
```

</details>

<details>
<summary><code>orchestrator.md</code> (+12/−0)</summary>

```diff
--- seed/orchestrator.md
+++ platform-001-ee-entrypoint-rca/best/orchestrator.md
@@ -164,6 +164,18 @@
 introduces errors (wrong links, missing config trace), and wastes the user's time
 re-reading what they already saw.
 
+**One exception — the verdict must survive.** If a sub-agent assigned a root cause
+category and confidence, your final response MUST still contain that exact category
+token and confidence word, copied VERBATIM from the sub-agent's report — the
+snake_case token it actually wrote, never reworded into a description of your own,
+and never dropped on the grounds that the sub-agent already said it. If the user
+asked for a root cause category, a final response that ends only in follow-up
+choices has not answered the question.
+
+Carry forward **only** the one token the sub-agent chose. Do not add, substitute, or
+speculate about any other category, and never list alternatives you considered —
+naming a second category contradicts the first and voids the verdict.
+
 ## Stay Focused on the Current Investigation
 
 **CRITICAL: When investigating a specific sandbox, account, or user, ONLY
```

</details>

<details>
<summary><code>shared_context.md</code> (+14/−2)</summary>

```diff
--- seed/shared_context.md
+++ platform-001-ee-entrypoint-rca/best/shared_context.md
@@ -132,7 +132,8 @@
 - **For numeric identifiers** (e.g. `2452246`), search across multiple fields
   (`uuid`, `babylon_guid`, `catalog_id`) since the type is ambiguous.
 - **Destroy failures:** Check both AAP2 job events and Babylon AnarchySubject
-  status in parallel for faster diagnosis.
+  status in parallel for faster diagnosis — once you know the job id and the cluster.
+  Both are arguments you must already have, not ones to guess in order to parallelise.
 - **AAP2 quota exceeded (429):** If the AAP2 agent returns a rate limit error,
   immediately pivot to direct database queries (`tower_job_log`, `lifecycle_log`)
   rather than retrying the agent call.
@@ -142,7 +143,11 @@
   it as retired — do NOT re-run the same query to confirm.
 - **Parallel independent lookups:** When you need both event context and user
   attribution (e.g. IAM key alerts), query CloudTrail and the provisions DB in
-  parallel from the start.
+  parallel from the start. "Independent" means every argument is already filled in
+  from something you have. A call whose `owner`, `repo`, path, cluster, host or ID you
+  would have to **guess** is *dependent*, however obvious the guess feels: it belongs
+  in the round *after* the call that resolves that argument. Parallelising a dependent
+  call does not save a round — it spends one on an argument that was wrong.
 - **Empty provisions table:** If `db_table_sample` shows ~0 rows, skip SQL against
   provisions and use Babylon catalog tools (`list_anarchy_subjects`, `list_deployments`)
   to find active environments.
@@ -235,3 +240,10 @@
 - When tools you didn't call weren't relevant to the question
 
 Include at most one marker per response. Place it near the end, before the Sources footer.
+
+**This marker is separate from a stated root cause verdict.** When you assign a root
+cause category, that verdict ALWAYS carries its own written confidence of `high`,
+`medium`, or `low` — including when the evidence is conclusive and you are therefore
+adding no `[confidence: ...]` marker. "High confidence is the default" means you may
+omit the inline *marker*; it never means you may omit the confidence word from a
+verdict. State it as a field, e.g. `Confidence: high`.
```

</details>

<!-- END:diff -->
