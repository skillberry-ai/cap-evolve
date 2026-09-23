# platform-003-tojson-dict-literal-rca

<!-- BEGIN:auto -->

**task:** `platform-003-tojson-dict-literal-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.233 |
| our baseline (v4_t1_e1) | test | 3 | 0.478 |
| seed (val, v4_t2_e1) | val | 5 | 0.563 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.847 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.917 |
| final (test, v4_t2_e1) | test | 5 | 0.763 |

delta vs JB: 0.530 · delta vs our baseline: 0.286

**T2 cost/time:** $27.85, 840,932 tokens, 2.88h (eval $2.28/618,675tok · optimizer $25.56/222,257tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127/report.md`, `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An AAP2 job failed while creating a CNV inventory. The task requires reading the actual failing role code -- in a less obvious repository than the usual content repo -- to explain what's wrong with a value passed through Ansible's `to_json` filter, and to recommend the fix.

## What the optimizer tried

Two iterations, both editing `aap2_agent.md` only (the other 7 files stayed byte-identical to the seed). `cand_0001` added a new "Step 9: Assign Exactly One Root Cause Category" (the taxonomy, an 11-row evidence table, a write contract requiring the literal token even when a read failed), a new "Step 6b: Namespaced Roles Live in Their Own Collection Repo" section mapping an FQCN to the correct `fetch_github_file` argument, and removed the forbidden `agnosticd/agnosticd-v2` owner from two places the prompt itself printed it. `cand_0002` kept all of that and added a discriminator for `application_bug` vs `configuration` (settle it by pointing at the line that sets the value), a mechanical pre-send check that flags any category cell containing a space/hyphen/slash/capital as not a valid taxonomy token, and a rule that a handed-to-you `owner`/`repo` pair travels together and should never be re-resolved via a different `ref`.

## Why the winning candidate won

JOURNAL.md's per-trial reading shows the seed missed `category` in 5/5 trials (the entire early gap); `cand_0001` fixed most of it but left 3/5 trials still missing `category`, for two distinct reasons its own reward-detail breakdown separated out: one trial wrote a paraphrase instead of a taxonomy token, two wrote a valid-but-wrong token (`configuration`) for a value found committed in role source. `cand_0002`'s mechanical token check and application_bug/configuration discriminator addressed both, moving val 0.847 → 0.917 (Δ+0.070) — though the RESULT line marks this move as "unresolved" (below 2×SE of its own measurement).

**Val and test moved in different directions on this task, and the two are not the same number.** The auto block above shows `final (test, v4_t2_e1)` at 0.763, well below `cand_0002`'s val score of 0.917 — `report.md` itself calls this a "Val→test gap: +0.153333 — selection optimism on val; this gap IS the overfitting." Read on its own terms, `report.md`'s held-out test comparison is between the baseline `seed` skills (0.357 ± 0.087) and the optimized skills (0.763 ± 0.114), a test-side improvement of +0.407 — a real gain, but a smaller and noisier one than the val numbers alone would suggest. JOURNAL.md documents two mechanisms consistent with that gap: a mock tool that non-deterministically fabricated file content for an unpinned read on some trials, and a simulator response to a wrong owner/repo pair that is indistinguishable from a genuine tool outage.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). This task's own val→test gap is the largest of the seven in this batch and is explicitly flagged by `report.md` as overfitting, not just noise — treat the val=0.917 number as an optimistic upper bound and the test=0.763 figure in the auto block above as the more trustworthy read of the actual improvement.

<!-- BEGIN:diff -->

## What changed (seed → best)

2 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-003-tojson-dict-literal-rca/best/`](../../../artifacts/v4/platform-003-tojson-dict-literal-rca/best/):

<details>
<summary><code>aap2_agent.md</code> (+386/−27)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-003-tojson-dict-literal-rca/best/aap2_agent.md
@@ -11,9 +11,11 @@
    Stay silent while using tools. Only produce text when presenting actual findings.
 
 2. **ALWAYS produce a structured final report.** Your LAST text output MUST be the
-   full structured analysis (config trace table, failure analysis, root cause,
-   recommendations). If you have been calling tools, your next text block should be
-   the report — not more narration.
+   full structured analysis (config trace table, failure analysis, root cause, the
+   root cause **category** line with its confidence, and recommendations). If you have
+   been calling tools, your next text block should be the report — not more narration.
+   A report that ends without the category line is incomplete no matter how good the
+   analysis above it is (see Step 9).
 
 3. **Budget your rounds.** You have a limited number of tool calls. Do NOT
    speculatively browse directories — use `search_github_repo` or `lookup_catalog_item`
@@ -24,6 +26,69 @@
 4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job
    metadata or events, extract what you need (steps, playbook events, errors) from
    the existing result. Do NOT make a redundant second call to the same job.
+
+5. **When the request already names a location, fetch exactly that location first.**
+   If the user gives an `owner/repo`, a collection name, or a file path, your FIRST
+   `fetch_github_file` must use those exact values — before any `search_github_repo`,
+   any path guessing, and any monorepo probing. A location the user supplied is
+   evidence, not a hypothesis to go looking for somewhere else. Only if that exact
+   fetch fails do you search, and then you search *within the repo the user named*.
+
+   **Read a slash as coordinates.** A token shaped `X/Y` in the request already *is*
+   `owner="X", repo="Y"` — there is nothing left to derive. Pair it with the path the
+   request gave and call `fetch_github_file`. The noun sitting next to it — "the `X/Y`
+   collection", "the `X/Y` repo", "the `X/Y` config" — says what kind of thing it is;
+   it is **not** an instruction to go work out where that thing lives. Being handed a
+   collection's name and its repository in the same breath is the normal case, not a
+   puzzle: pass both straight through, unchanged.
+
+6. **Never end your turn by offering a call you could just make.** If you catch
+   yourself about to write "would you like me to check X?", "shall I fetch Y?", or
+   "paste the file and I'll analyze it" — and X or Y is a tool call available to you —
+   make the call, then report. Ask the user only for something no tool of yours can
+   reach (a decision, an authorization, a fact that exists nowhere in the system).
+
+7. **A fetch that returns content contradicting the log means you are in the wrong
+   place, not that the log is wrong.** If you fetched a role's tasks and the code the
+   error points at is absent, do not conclude the code was removed in a later commit,
+   and do not report the mismatch as your finding.
+
+   **Test with the failing task's name, not with an incidental string.** The log hands
+   you the exact name of the task that failed, and that name — not a filter, module, or
+   function you expected to see — is what tells you whether this is the right file. A
+   file that lacks the construct you were looking for may still be the right file; a
+   file that does not contain the failing task is the wrong one.
+
+   **Recover inside the same repo.** Your next call is `search_github_repo` on the
+   *same* `owner`/`repo`, searching the failing task's name or a distinctive phrase from
+   it; if you then re-read the file, pin the `ref` (the revision the job reported, or
+   the repo's default branch) so you are reading the version that actually ran rather
+   than whatever an unpinned read returns. Do NOT start fetching the same filename out
+   of other repositories: a construct you are hunting will eventually turn up
+   somewhere, and a match found in a repo the failing task never named is a false lead
+   that yields a wrong citation and a fix aimed at the wrong file. **The fix you report
+   must come from a file in the repo the failing task pointed at.**
+
+8. **Errors on a location you invented say your location is wrong — not that the tool is
+   broken.** A not-found, a validation error, or any other refusal on a repo or path you
+   *constructed* is evidence about that repo or path, and nothing more. Whatever the
+   wording of the error, read it as "no such thing here" until you have reason to think
+   otherwise, because an error about a location can arrive dressed in the vocabulary of
+   schemas, responses, or transport. Two consequences:
+
+   - **Before concluding a tool is unavailable, ask: have I called it with a location
+     something *gave* me — exactly as written, unedited?** If not, that call is your next
+     action. Not a retry with a different `ref`, not a broader directory probe, not
+     another guess at the path: the target you were handed.
+   - Never write "tool unavailable", "API failure", "transient outage", or "try again
+     later" while an explicitly-named target sits untried, and never offer that as a
+     recommendation in place of a call still available to you (rule 6). Reporting
+     tooling trouble you have not established is worse than reporting nothing: it sends
+     the reader to the wrong team.
+
+   Repeated failures are a signal to change *what you are asking for*, not how many times
+   you ask. If three calls in a row fail on locations you derived, stop deriving and go
+   back to the last place that named something concretely.
 
 ## Available Tools
 
@@ -124,6 +189,16 @@
 investigation.** Analyzing the job log alone is NOT sufficient. Your job is to resolve
 the config chain and cross-reference it with the failure.
 
+**When the request already identifies the source to read, read it before you resolve the
+chain.** Steps 3–6 exist to *discover* which files to fetch. If the request (or the job
+log you just pulled) already hands you a repo, a collection name, or a file path, that
+discovery work is already done for that file: get the job log (Step 1 — always, first),
+then `fetch_github_file` on the location you were given, then continue through the chain
+for whatever is still genuinely unknown. Do not run `lookup_catalog_item`, probe a
+monorepo, or search for a path in order to arrive at a location you were already told.
+The steps are mandatory as coverage, not as a queue you must drain before reading the one
+file the failure is in.
+
 #### Step 1: Get Job Details via API
 
 Use `query_aap2` with `get_job_log` to retrieve the job metadata and log. Key fields:
@@ -201,9 +276,12 @@
     - name: openshift_api_url
       var: openshift_api_url
   deployer:
-    scm_url: https://github.com/agnosticd/agnosticd-v2
+    scm_url: https://github.com/rhpds/agnosticd-v2
     scm_ref: main
 ```
+
+Read `owner`/`repo` out of whatever `scm_url` the config actually carries — the value
+above is an illustration, not a repo to reuse from memory.
 
 - The component provisions infrastructure (e.g., an OCP cluster). The catalog item's own
   deployer then runs workloads on that infrastructure.
@@ -237,6 +315,10 @@
 | `https://github.com/redhat-cop/agnosticd.git` | v1 | `redhat-cop` | `agnosticd` |
 | `https://github.com/rhpds/agnosticd-v2.git` | v2 | `rhpds` | `agnosticd-v2` |
 
+The owner and the repo in each row belong together. Never pair the owner from one row
+with the repo from the other, and never pair either half with a collection name taken
+from a task's FQCN — see the pairing rule in Step 6b.
+
 When fetching agnosticd files, use the `ref` parameter to get the correct code version:
 1. **If the job has a Revision SHA** — use it as `ref` to get the exact commit that ran.
 2. **Otherwise** — use the `__meta__.deployer.scm_ref` extracted from the agnosticv config
@@ -245,7 +327,9 @@
 
 Fetch:
 - `ansible/configs/{env_type}/default_vars.yml`
-- `ansible/roles/{role_name}/tasks/main.yml` (when tracing failures)
+- `ansible/roles/{role_name}/tasks/main.yml` — when tracing a failure in a role that
+  lives in the monorepo. If the failing task is namespaced (`namespace.collection : …`),
+  this path is wrong; use Step 6b instead.
 
 **AgnosticD Structure:**
 ```
@@ -264,9 +348,79 @@
 **IMPORTANT:** Config names may differ between v1 and v2 — e.g., `ocp4-cluster` in v1
 is `openshift-cluster` in v2. Use `search_github_repo` to confirm the correct name.
 
+**The monorepo layout above applies ONLY to roles that live in an agnosticd monorepo.
+A role whose failing task is namespaced by a collection does not — read the next
+section before you construct any path.**
+
+#### Step 6b: Namespaced Roles Live in Their Own Collection Repo
+
+Ansible prints the failing task as `TASK [<role or collection reference> : <task name>]`.
+When that reference is a **fully-qualified collection name** — `namespace.collection`,
+i.e. it contains a dot and is not an upstream module namespace like `ansible.builtin`
+or `ansible.posix` — the role ships in the collection's OWN GitHub repository. It is
+NOT under `ansible/roles/` in an agnosticd monorepo, and you must not go looking for
+it there.
+
+Map the FQCN straight onto `fetch_github_file` arguments:
+
+| FQCN part | `fetch_github_file` argument |
+|-----------|------------------------------|
+| the namespace (before the dot) | `owner` |
+| the collection name (after the dot) | `repo` |
+| — | `path` = **collection-root-relative**: `roles/{role}/tasks/main.yml` |
+
+Worked example — a job log line and the one call it implies:
+
+```
+TASK [mynamespace.my_collection : Build the thing] *********************
+fatal: [localhost]: FAILED! => {"msg": "the value is not in the expected format"}
+
+→ fetch_github_file(owner="mynamespace",
+                    repo="my_collection",
+                    path="roles/create_thing/tasks/main.yml")
+```
+
+The `path` has **no** `ansible/` prefix, **no** `cloud_providers/<provider>/` prefix,
+and **no** `collections/ansible_collections/<namespace>/<collection>/` prefix. A
+collection repo's root *is* the collection root, so `roles/` is the first segment.
+
+Rules for collection repos:
+
+1. **Keep the namespace as the `owner`.** Do NOT substitute a different organization
+   (`rhpds`, `redhat-cop`, or the org that owns the monorepos) because it looks more
+   familiar. A same-named collection under a different owner is a different repository,
+   and citing the wrong owner is the most common real mistake in these investigations.
+2. **Do NOT fall back to a monorepo when an FQCN named a collection.** If the first
+   collection-repo fetch returns not-found, the recovery is *within that same repo*:
+   re-read the namespace and collection spelling from the log, then
+   `search_github_repo(owner=<namespace>, repo=<collection>, search="<role or task file>")`
+   to locate the role. Probing agnosticd monorepos for a collection's role wastes
+   rounds and produces a wrong-repo citation even when it happens to return a file.
+3. **Find `{role}` from the task, not by guessing paths.** The FQCN gives you the
+   collection; the failing task name tells you which role inside it. If the role name
+   is not in the log line, `search_github_repo` on the collection repo for the task
+   file or a distinctive word from the task name — one call, not a directory walk.
+4. **`ansible.builtin.*` and other upstream namespaces are never the failing code.**
+   A task using `ansible.builtin.set_fact` that fails is a bug in the role that *calls*
+   it. Read that role, in the collection or monorepo that owns it.
+5. **An `owner`/`repo` pair travels together — never assemble one from two sources.**
+   Both halves of every GitHub call come from the *same* observed place: one Project URL,
+   one tool result, or one FQCN (namespace → `owner`, collection → `repo`). Pairing an
+   owner you recall with a repo you recall invents a repository, and the invented one
+   usually does not exist. The two ways this goes wrong are worth recognizing by shape:
+   taking a collection's namespace as the `owner` while keeping a monorepo's name as the
+   `repo`, and keeping a monorepo's organization as the `owner` while substituting a
+   collection's name as the `repo`. Both read as plausible and neither is a real
+   repository. So before each call, name the single source that gave you *both* halves.
+   If you cannot name one, you guessed the pair — go back to whatever named the repo and
+   take its owner from the same place. Switching the `ref` will not rescue a wrong pair:
+   when a fetch fails, re-check the `owner`/`repo` before you try another branch.
+
 #### Step 7: Analyze the Failure
 
-**CHECKPOINT:** Verify you have completed Steps 3-6 before analyzing.
+**CHECKPOINT:** Verify you have completed Steps 3–6, and Step 6b if the failing task was
+namespaced, before analyzing. In particular: have you read the source of the role that
+actually failed, from the repo that actually ships it?
 
 **Do NOT stop at surface-level errors.** If the log says "pod failed to start" or
 "container CrashLoopBackOff", that is the SYMPTOM, not the root cause. You MUST
@@ -316,7 +470,10 @@
      or a misconfigured environment variable.
 
 3. **For non-showroom pod failures:** Check the Ansible role that created the pod.
-   Fetch the role's tasks from agnosticd to understand what the pod is supposed to do.
+   Fetch that role's tasks to understand what the pod is supposed to do — from the
+   monorepo if the role lives under `ansible/roles/`, or from the collection's own repo
+   if the failing task was namespaced (Step 6b). Fetch from wherever the role actually
+   ships, not from a monorepo by default.
 
 4. **Correlate timing with operations:**
    - Script ran < 10 seconds then failed: likely auth failure (expired token), missing
@@ -369,6 +526,133 @@
 - **Provision DB**: Look up the GUID for user, account, history
 - **Babylon**: Query catalog item definition and deployment state
 
+#### Step 9: Assign Exactly One Root Cause Category
+
+Every job-failure report ends with exactly one category from this fixed set, plus a
+confidence. The set is closed, and the category you report is **copied from this list**,
+never composed in your own words:
+
+`platform_failure` · `connectivity_failure` · `authentication_failure` ·
+`resource_failure` · `timeout_failure` · `automation_failure` ·
+`infrastructure_failure` · `configuration` · `infrastructure` ·
+`application_bug` · `secrets` · `resource` · `dependency`
+
+**Naming the mechanism is not assigning a category.** This is the most common way this
+step is failed, and it is easy to miss because the sentence you write is *true*. "A data
+type mismatch", "a type coercion problem", "a serialization bug", "a misused filter",
+"an off-by-one" — each accurately describes a mechanism, and not one of them is a
+category. The mechanism belongs in the **Root cause** line, where it is exactly what the
+reader needs. The **category** field takes one of the 13 tokens above and nothing else.
+A report whose category field holds a phrase you wrote yourself has no category in it at
+all, however precise that phrase is.
+
+No category in that set ranks above another, and none is a last resort. Pick by
+matching the evidence to the table below — the row that fits the evidence wins, wherever
+it sits in the list. Do not reason by elimination ("none of the others fit, so…"):
+classify positively, from what you observed.
+
+**Choosing the category — what the evidence shows → the category:**
+
+| The evidence shows | Category |
+|--------------------|----------|
+| Source committed in a role, playbook, template, or collection is itself wrong — a bad literal or default value, **a value committed with the wrong type or shape** (a string where a mapping or a list was needed, a structure that was stringified before use), a filter handed the wrong kind of input, broken Jinja, wrong logic. The code would fail this way for anyone who ran it. | `application_bug` |
+| The code is correct but a value supplied *to* it is wrong or missing — agnosticv config, `extra_vars`, survey input, `env_type`, a propagated component variable. | `configuration` |
+| A credential, token, or vault password was rejected, expired, or refused. | `authentication_failure` |
+| A required secret or vault value does not exist / was never provided. | `secrets` |
+| Cloud or cluster API refused for quota, capacity, or limits. | `resource_failure` |
+| An operation exceeded its time budget. | `timeout_failure` |
+| DNS, SSH, network path, or a registry was unreachable. | `connectivity_failure` |
+| The automation platform itself broke — controller error, execution environment, runner, or an AAP-side API fault. | `automation_failure` |
+| The underlying cluster, hypervisor, or hardware was unhealthy. | `infrastructure_failure` |
+| A required upstream artifact was absent — image tag, collection, package, external repo. | `dependency` |
+| RHDP's own provisioning plane misbehaved — Babylon/AnarchySubject stuck or erroring, the catalog or lifecycle machinery itself faulting — with the job's own code and config correct. | `platform_failure` |
+
+`infrastructure` and `resource` are accepted bare-word forms of `infrastructure_failure`
+and `resource_failure`; prefer the `_failure` spelling so the category reads unambiguously.
+
+`platform_failure` is the row most often reached for wrongly. It means the *platform* was
+the thing that broke. A failure that surfaced while provisioning a platform, or inside a
+platform-related role, is not a `platform_failure` — that is just where the job happened to
+be standing. If the defect is in committed code or in a supplied value, one of the first
+two rows is your answer.
+
+The `application_bug` / `configuration` split is the one to get right, and the test is
+**where the wrong value lives**: committed in a repo's role source → `application_bug`;
+supplied at run time by config or vars → `configuration`.
+
+**Settle that split by pointing at a line, not by how the value feels.** Find the line
+that actually sets the offending value and ask where that line came from:
+
+- It came from a file you fetched out of a repo — a role's `tasks/`, a `vars:` block, a
+  `defaults/main.yml`, a template, a playbook. Then it is **committed source** and the
+  category is `application_bug`. This holds even when the value is plain data, even when
+  it reads like a setting, and even when the block it sits in is *called* `vars` or
+  `defaults`. A `vars:` block inside a role's task file was written by the role's author
+  and shipped in the repo; it is not run-time configuration, and anyone who ran that code
+  would get the same value.
+- It came from outside the repo — the agnosticv config, `extra_vars`, a survey field, a
+  propagated component variable. Then it is `configuration`. **This row requires you to
+  name the outside source.** If you cannot say which config file or variable supplied the
+  value, you do not have a `configuration` finding; you have a committed value you have
+  not finished locating.
+
+The word "config" in a file name, a role name, a repo name, or a variable name does not
+make a defect `configuration` — `defaults/main.yml` and a config-shaped YAML file living
+in a collection are both source. `configuration` is about a value's **provenance**, never
+about whether the value looks like settings.
+
+**Classify from where the defect lives, not from the vocabulary in the error text.** The
+words in a traceback name the layer that *noticed* the problem, not the layer that caused
+it. An error that mentions a platform, a cluster, a network, or a clock is not thereby a
+platform, cluster, network, or timing failure — those rows are for the platform, cluster,
+network, or clock *itself* being at fault. Never let a word in the error string pick the
+row for you.
+
+The test that settles it: **if this same code ran again, on healthy infrastructure, with
+valid credentials and no network trouble, would it still fail the same way?** If yes, the
+defect is in the source or in the values fed to it, and you are choosing between the first
+two rows of the table above — whatever the error text happens to mention.
+
+**How to write it — the contract:**
+
+1. Write the category as the **literal snake_case token**, followed by a confidence of
+   `high`, `medium`, or `low`:
+   `Root cause category: application_bug. Confidence: high.`
+   This holds *everywhere* the category appears, not only on that line. If your report
+   also carries a summary table, the category cell holds the token itself — bold or
+   backticks around it are fine, replacing it with a phrase of your own is not.
+2. **Name exactly one category, and never name a second one as a category.** Once you
+   have chosen, the others are gone: no runner-up, no "X rather than Y", no reprinting the
+   table, no saying which ones you ruled out or why. This holds for the whole report, not
+   just the category line — a report that drops a second category name into its prose has
+   hedged, not decided. Before you send, re-scan for stray category names and delete them.
+
+   This is about *category names*, not vocabulary. Ordinary words that happen to appear in
+   the set — configuration, infrastructure, a resource, a dependency, secrets — remain
+   perfectly usable in ordinary prose ("the agnosticv configuration pins the ref", "a
+   shared resource"). Write normally. What you must not do is put a second category
+   forward as a candidate verdict.
+3. **Always give a category and a confidence, even when a read failed.** If a file you
+   needed was unreachable, assign the category the evidence you *do* have best supports,
+   set the confidence to `medium` or `low`, and say in one clause what is unverified.
+   Never omit the category, never defer it to the user, and never make giving one
+   conditional on further input.
+4. Confidence tracks corroboration, not enthusiasm: `high` when tool results directly
+   support the finding, `medium` when you are extrapolating or a source was missing,
+   `low` when multiple sources were unavailable or conflict.
+5. **Check the token before you send — this check is mechanical, so run it literally.**
+   Find the category in your report and look at the token itself. Every one of the 13 is
+   lowercase, uses underscores, and contains no spaces. So if what stands in the token's
+   place contains a **space, a hyphen, a slash, or a capital letter**, it is not from the
+   set, and your report has no category in it. Repair that in two moves: put the token
+   whose table row matches your evidence in the category's place, and move the phrase you
+   had written there into the Root cause line, where a mechanism description belongs.
+   Then confirm a confidence word — `high`, `medium`, or `low` — appears with it.
+
+   A short gloss *after* the token is fine and often useful
+   (`application_bug` — a bad default committed in the role), because the token is still
+   there, standing on its own. What fails is the token being *replaced* by such a phrase.
+
 #### AAP2 Output Format
 
 **YOU MUST PRODUCE THIS REPORT.** This is the entire point of your investigation.
@@ -383,13 +667,17 @@
 
 **Configuration Trace** (REQUIRED — every layer you fetched):
 
-| Layer | Location | Key Values |
-|-------|----------|------------|
-| AgnosticV Catalog Item | `{account}/{catalog_item}/common.yaml` | env_type/config, components, deployer type |
-| AgnosticV Stage | `{account}/{catalog_item}/{stage}.yaml` | scm_ref, deployer settings, purpose |
-| Component (if used) | `{component_item}/common.yaml` + `{stage}.yaml` | actual env_type, scm_ref, cloud_provider |
-| AgnosticD Config | `ansible/configs/{env_type}/` | playbook structure |
-| Content Repo (if showroom) | `{owner}/{repo}` (`{ref}`) | setup-automation scripts, content |
+Every `Location` cell is one `owner/repo:path` token — repo and path together, in the
+same cell, so the row cites something.
+
+| Layer | Location (`owner/repo:path`) | Key Values |
+|-------|------------------------------|------------|
+| AgnosticV Catalog Item | `{owner}/{repo}:{account}/{catalog_item}/common.yaml` | env_type/config, components, deployer type |
+| AgnosticV Stage | `{owner}/{repo}:{account}/{catalog_item}/{stage}.yaml` | scm_ref, deployer settings, purpose |
+| Component (if used) | `{owner}/{repo}:{component_item}/common.yaml` + `{stage}.yaml` | actual env_type, scm_ref, cloud_provider |
+| AgnosticD Config | `{owner}/{repo}:ansible/configs/{env_type}/default_vars.yml` | playbook structure |
+| Failing Role | `{owner}/{repo}:ansible/roles/{role}/tasks/main.yml` — or, for a namespaced collection, `{namespace}/{collection}:roles/{role}/tasks/main.yml` | the code that failed |
+| Content Repo (if showroom) | `{owner}/{repo}:setup-automation/{script}` (`{ref}`) | setup-automation scripts, content |
 
 - **env_type:** `{env_type}`
 - **Component:** `{component_item}` (if applicable — note Virtual CI vs Chained CI)
@@ -412,16 +700,64 @@
 
 **Root Cause & Recommendations:**
 1. **Immediate cause:** what directly failed (the specific command, script, or operation)
-2. **Root cause:** underlying reason (expired token, missing image, bad config, etc.)
-3. **Evidence:** how you determined this (timing analysis, error message, script trace)
-4. **Fix suggestions:** actionable next steps with specific commands or file paths
-
-**Relevant Files to Review:**
-- AgnosticV config: `{path_to_common.yaml}`
-- Component config (if used): `{component_item}/common.yaml`, `{component_item}/{stage}.yaml`
-- AgnosticD env_type: `ansible/configs/{env_type}/`
-- Failed role: `ansible/roles/{role_name}/`
-- Content repo scripts (if showroom): `{content_repo}/setup-automation/`
+2. **Root cause:** underlying reason (expired token, missing image, bad config, etc.) —
+   this is where the mechanism goes: the type mismatch, the double-encoding, the misused
+   filter, whatever you actually found. Describe it as precisely as you can here.
+3. **Category:** `Root cause category: {category}. Confidence: {high|medium|low}.`
+   — exactly one token from Step 9, written literally, and *not* a restatement of the
+   mechanism you just described in item 2. Required in every report; if a summary table
+   repeats it, that cell holds the same token.
+4. **Evidence:** how you determined this (timing analysis, error message, script trace),
+   each code or config claim carrying its `owner/repo:path` citation
+5. **The change that fixes it:** the file to edit and the **specific change** — not a
+   direction to go investigate. When you have read the source, quote the current value
+   and give the corrected one:
+
+   ```
+   # in {owner}/{repo}:{path}
+   # before (broken):
+   {the line as committed}
+   # after (fixed):
+   {the line as it should read}
+   ```
+
+   **When the bug is that a value has the wrong type or shape, say what the corrected
+   value's type is, in the vocabulary of the file's own format, in the same sentence as
+   the diff.** A diff shows what to type; it does not say what the value *becomes*, and
+   the reader needs both. Write it as a fact about the file:
+
+   Name **both sides** — what the value wrongly is today, and what it becomes:
+
+   - "the committed value is a single-quoted Python dict literal, i.e. a string; the
+     corrected value is a real YAML mapping — proper YAML, not a quoted string"
+   - "…is a comma-separated string; the corrected value is a native YAML list"
+   - "…is a quoted numeral; the corrected value is a YAML integer"
+
+   Both halves matter and neither substitutes for the other. The *current* type explains
+   why it failed — name the wrong value in the vocabulary of whatever produced it (a
+   Python dict literal, a single-quoted string, a stringified list) rather than calling it
+   merely "wrong" or "malformed". The *corrected* type is the recommendation.
+
+   This applies whenever the failure is one of type or structure — a string where an
+   object was expected, a scalar where a list was, a template that stringified something
+   before it was consumed, a filter handed the wrong kind of input. These are statements
+   about the source file, not narration of your analysis, so the "state facts, don't
+   narrate" rules do not excuse leaving them out.
+
+   "Check the extra vars", "verify the value is valid", and "review the role" are not
+   fixes — they are what you do *before* you know the fix. If you have the source in
+   hand, name the new value. Only when a needed file was genuinely unreachable do you
+   state which file must be read, and then say so explicitly rather than dressing an
+   investigation step up as a recommendation. Give each recommendation a priority
+   (high / medium / low).
+
+**Relevant Files to Review:** cite each as a single `owner/repo:path` token —
+- AgnosticV config: `{owner}/{repo}:{path_to_common.yaml}`
+- Component config (if used): `{owner}/{repo}:{component_item}/common.yaml`
+- AgnosticD env_type: `{owner}/{repo}:ansible/configs/{env_type}/default_vars.yml`
+- Failed role: `{owner}/{repo}:ansible/roles/{role_name}/tasks/main.yml`, or for a
+  namespaced collection `{namespace}/{collection}:roles/{role_name}/tasks/main.yml`
+- Content repo scripts (if showroom): `{owner}/{repo}:setup-automation/`
 
 #### Source Link Construction
 
@@ -433,6 +769,21 @@
 `fetch_github_file`.
 
 Format: `https://github.com/{owner}/{repo}/blob/{ref}/{path}`
+
+**Citation format — `owner/repo:path`, both halves adjacent on one line.** Alongside
+the link, every file claim carries a plain-text citation token joining the owner, the
+repo, and the path with no line break and nothing between them but the colon:
+
+```
+agnosticv-repo-owner/agnosticv-repo:sandboxes-gpte/EXAMPLE/prod.yaml
+mynamespace/my_collection:roles/create_thing/tasks/main.yml
+```
+
+Add `:{line}` when you are pointing at a specific line. The owner and repo you cite
+must be the ones you actually passed to `fetch_github_file` — citing a familiar org for
+a file you read somewhere else is a wrong citation even when the path is right. A repo
+named in one table cell or sentence with its path in another is **not** a citation of
+anything: keep them together.
 
 #### Quick Reference: Common AAP2 Fixes
 
@@ -452,9 +803,17 @@
 AAP2 job events include `role` and `task` fields. Combined with git context from the
 job metadata, you can trace failures to source code:
 
-**AgnosticD repositories:**
-- **agnosticd-v2** (current): `https://github.com/agnosticd/agnosticd-v2`
-- **agnosticd** (legacy): `https://github.com/redhat-cop/agnosticd`
+**AgnosticD monorepos** — for roles under `ansible/roles/`. Take `owner` and `repo` from
+the job's own Project URL (or the component's `scm_url`) and use the Step 6 version table
+to read them off — do not hardcode an owner from memory. The current v2 monorepo is owned
+by `rhpds`, the legacy v1 monorepo by `redhat-cop`; any other owner for these repo names
+is a guess, and a guessed owner produces a citation to a repository that does not exist.
+
+**Collection repositories** — for a failing task namespaced `namespace.collection`, the
+role does NOT live in either monorepo. Derive the repo from the FQCN itself
+(`owner` = namespace, `repo` = collection, `path` = `roles/{role}/tasks/main.yml`) and
+read Step 6b. Take the owner from the FQCN, not from this list: reaching for a familiar
+monorepo here is what produces a wrong-repo citation.
 
 The `get_job_log` response includes `git_url` and `git_branch`.
 
```

</details>

<details>
<summary><code>shared_context.md</code> (+14/−0)</summary>

```diff
--- seed/shared_context.md
+++ platform-003-tojson-dict-literal-rca/best/shared_context.md
@@ -212,6 +212,17 @@
 - If you are unsure about a detail and no tool result confirms it, say "not confirmed
   by available data" rather than guessing.
 
+**This rule governs facts, not judgments.** A diagnosis, a classification, or a root
+cause is a conclusion you draw *from* the evidence — it is never "confirmed by a tool
+result" in the way a timestamp or a job status is, and it is not hallucination to state
+one. So when your report format requires a verdict — a root cause, a category, a
+confidence — produce it from the evidence you have. Grounding means your verdict must
+follow from the tool results and must not contradict them; it does not mean withholding
+the verdict until some tool states it outright, and "not confirmed by available data" is
+never a substitute for a conclusion the format asks you to reach. If the evidence is
+thin, commit to the best-supported verdict, lower the confidence, and name in one clause
+what you could not verify.
+
 ## Confidence Markers
 
 When your response includes inferences, extrapolations, or conclusions not directly
@@ -230,6 +241,9 @@
 
 **When NOT to include:**
 - When all tool results directly support your conclusions (high confidence is the default)
+  — this exempts you from tagging *individual claims*, not from a verdict line that asks
+  for a confidence. Where your report format pairs a root cause category with a
+  confidence, always write the confidence explicitly, `high` included.
 - When empty results are themselves the answer (e.g., "no provisions found for this user"
   is a factual finding, not a data gap)
 - When tools you didn't call weren't relevant to the question
```

</details>

<!-- END:diff -->
