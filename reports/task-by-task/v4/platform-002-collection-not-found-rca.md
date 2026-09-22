# platform-002-collection-not-found-rca

<!-- BEGIN:auto -->

**task:** `platform-002-collection-not-found-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-002-collection-not-found-rca/run_20260920_034433` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.883 |
| our baseline (v4_t1_e1) | test | 3 | 0.783 |
| seed (val, v4_t2_e1) | val | 5 | 0.907 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.117 · delta vs our baseline: 0.217

**T2 cost/time:** $8.30, 482,431 tokens, 1.95h (eval $1.34/393,252tok · optimizer $6.97/89,179tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-002-collection-not-found-rca/run_20260920_034433/report.md`, `.capevolve/v4_t2_e1_platform-002-collection-not-found-rca/run_20260920_034433/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Same two-hop RCA shape as platform-001, on a different failure: a missing Ansible role or collection whose cause is only visible in the execution environment's own `ansible.cfg`, not in the job log alone.

## What the optimizer tried

Single iteration (`cand_0001`) touching `aap2_agent.md`, `shared_context.md`, and `orchestrator.md`. It added a "Root Cause Category and Confidence" section (the taxonomy verbatim, a 10-row evidence-to-category table, two boundary rules for `dependency` vs `configuration`/`timeout_failure`), grew the AAP2 output contract from 4 to 6 required items so a verbatim category and confidence are always stated, added a new "Step 7d: Missing Collection or Role" pattern for stating what a fetched value does not include, and rewrote the Step 6 owner table to stop teaching a hardcoded (and forbidden) owner/repo pair.

## Why the winning candidate won

JOURNAL.md's `reward-detail.json` reading shows `completion` and `tool_calls` were already 1.0 in all 5 seed trials; the entire 0.093 val gap was one missing `verdict.category` fact, missed in 3/5 trials (seeds 0, 1, 3) because the RCA taxonomy vocabulary appeared in none of the 8 prompt files — the seed wrote correct-sounding but non-taxonomy descriptions. The new taxonomy section and required output fields closed that gap, moving val 0.907 → 1.0 (Δ+0.093), with the RESULT line marking the task `fixed`. On the held-out test split, `report.md` records the baseline `seed` skills at 0.573 ± 0.055 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.427.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning — never checked against any other task (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md flags one live hazard the edit did not fix: `verify.py`'s exclusivity rule fails the verdict if a second taxonomy category token appears anywhere in the answer, so a thorough answer that rules out an alternative category by name would score zero — a risk the optimizer chose to leave as a hazard rather than address structurally this iteration.

<!-- BEGIN:diff -->

## What changed (seed → best)

3 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-002-collection-not-found-rca/best/`](../../../artifacts/v4/platform-002-collection-not-found-rca/best/):

<details>
<summary><code>aap2_agent.md</code> (+133/−6)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-002-collection-not-found-rca/best/aap2_agent.md
@@ -232,10 +232,20 @@
 
 #### Step 6: Determine AgnosticD Version and Fetch Config
 
-| Project Pattern | Version | GitHub Owner | GitHub Repo |
-|----------------|---------|--------------|-------------|
-| `https://github.com/redhat-cop/agnosticd.git` | v1 | `redhat-cop` | `agnosticd` |
-| `https://github.com/rhpds/agnosticd-v2.git` | v2 | `rhpds` | `agnosticd-v2` |
+Read the version off the job's Project URL — v1 and v2 have different repo layouts:
+
+| Project URL ends with | Version |
+|----------------------|---------|
+| `/agnosticd.git` | v1 |
+| `/agnosticd-v2.git` | v2 |
+
+**Take `owner` and `repo` from the data, never from memory.** Parse them out of the
+Project URL you actually observed (`https://github.com/{owner}/{repo}.git`), or use the
+`owner` and `repo` that `lookup_catalog_item` returned for this catalog item. The
+organization owning the agnosticd repos is **not** fixed — it differs between v1 and v2
+and has moved between orgs. An owner you assumed rather than read is the single most
+common error in these investigations: it sends every later fetch to a repository that
+does not exist, and the whole config trace then rests on nothing.
 
 When fetching agnosticd files, use the `ref` parameter to get the correct code version:
 1. **If the job has a Revision SHA** — use it as `ref` to get the exact commit that ran.
@@ -287,6 +297,7 @@
 | `FAILED! => {"msg": "..."}` | Task failure with error message |
 | `fatal: [host]: UNREACHABLE!` | SSH/connectivity issues |
 | `CrashLoopBackOff` / init container failed | Container startup failure — trace the container (Step 7b) |
+| `ERROR! the role '...' was not found` | A role or collection the play needs is not on the search path — trace `collections_path` / `roles_path` in the EE's `ansible.cfg` (Step 7d) |
 | `ERROR! No inventory` | Inventory generation failed |
 | `Unable to resolve DNS` | DNS or network issues |
 | `cloud_provider error` | Cloud API quota/limits/credentials |
@@ -362,6 +373,40 @@
 
 6. **Include the content repo files in your sources** — link directly to the
    failing script on GitHub.
+
+#### Step 7d: Missing Collection or Role ("was not found")
+
+When the log says a role or collection **was not found**, the log names *what* was
+missing but never *why*. The why is in the Ansible configuration the execution
+environment actually uses — `ansible.cfg` at the root of the agnosticd repo the job ran
+against. Fetch that file and read its search paths before you write the report; the log
+alone cannot support a root cause here. Take the `owner` and `repo` for that fetch from
+what `lookup_catalog_item` returned — do not assume the owner from the repo name.
+
+1. **Decide which search path governs.** A dotted, fully-qualified name
+   (`namespace.collection.role`) is resolved through `collections_path`. A bare role
+   name is resolved through `roles_path` and the play's own `roles/` directory. Naming
+   the wrong one of these two is a wrong root cause.
+
+2. **Quote the setting's actual value** from the `ansible.cfg` you fetched — not a
+   remembered default.
+
+3. **Work out what that value leaves out.** This is the step that turns a quoted setting
+   into an explanation, and it is the one most often skipped. In an AAP2 execution
+   environment:
+   - the project checkout is at `/runner/project`;
+   - collections installed dynamically for the run from a `requirements.yml` land in
+     `/runner/requirements_collections`;
+   - collections baked into the EE image sit on Ansible's system defaults
+     (`/usr/share/ansible/collections`, `~/.ansible/collections`).
+
+   Setting `collections_path` at all **replaces** Ansible's defaults rather than adding
+   to them, so a value naming only one of these locations silently excludes the rest.
+
+4. **Write both halves in the report.** Quoting the setting is half an answer; state
+   explicitly that it **does not include** the location where the collection actually
+   lives, so that location is never searched and the role resolves to nothing. "The
+   path is too narrow" is not an explanation — name the excluded location.
 
 #### Step 8: Cross-Reference with Parsec Data
 
@@ -413,8 +458,12 @@
 **Root Cause & Recommendations:**
 1. **Immediate cause:** what directly failed (the specific command, script, or operation)
 2. **Root cause:** underlying reason (expired token, missing image, bad config, etc.)
-3. **Evidence:** how you determined this (timing analysis, error message, script trace)
-4. **Fix suggestions:** actionable next steps with specific commands or file paths
+3. **Root cause category:** exactly one member of the fixed taxonomy, written verbatim
+   — see "Root Cause Category and Confidence" below
+4. **Confidence:** `high`, `medium`, or `low` — state it every time, including when it
+   is high
+5. **Evidence:** how you determined this (timing analysis, error message, script trace)
+6. **Fix suggestions:** actionable next steps with specific commands or file paths
 
 **Relevant Files to Review:**
 - AgnosticV config: `{path_to_common.yaml}`
@@ -422,6 +471,84 @@
 - AgnosticD env_type: `ansible/configs/{env_type}/`
 - Failed role: `ansible/roles/{role_name}/`
 - Content repo scripts (if showroom): `{content_repo}/setup-automation/`
+
+#### Root Cause Category and Confidence
+
+Every failure analysis ends with **exactly one** category from this fixed taxonomy, plus
+a stated confidence. Write the category **verbatim** from the lists below — lowercase,
+underscores included. A label you compose yourself ("Misconfiguration", "Missing
+collection", "debug override left in production") is not a category and does not satisfy
+this contract, however well it describes the failure. Compose your prose freely; the
+category value itself is a fixed vocabulary.
+
+**Prefer the operational set:**
+`platform_failure` · `connectivity_failure` · `authentication_failure` ·
+`resource_failure` · `timeout_failure` · `automation_failure` ·
+`infrastructure_failure`
+
+**Fall back to these when no operational member fits the failure:**
+`configuration` · `infrastructure` · `application_bug` · `secrets` · `resource` ·
+`dependency`
+
+The fallback list exists for real failure classes the operational set does not name, and
+a missing dependency is the standard example. When a fallback member is the closest fit,
+it *is* the right answer — do not force a failure into an operational member just
+because that set is listed first.
+
+**Choose by what the evidence shows:**
+
+| What the evidence shows | Category |
+|---|---|
+| Something the play needed could not be found, resolved, or installed — a collection, role, Galaxy requirement, package, container image, chart, or a remote artifact URL that no longer serves it | `dependency` |
+| The playbook, role, or template logic is itself wrong — bad filter or expression, wrong data type, undefined variable, malformed template | `application_bug` |
+| The automation harness never got as far as running the play content — EE entrypoint, runner invocation, or inventory generation failed | `automation_failure` |
+| Credentials, tokens, or vault secrets were absent | `secrets` |
+| A platform rejected credentials that were presented | `authentication_failure` |
+| Cloud quota, capacity, or service limits exhausted | `resource_failure` |
+| An operation that would otherwise have succeeded exceeded its time budget | `timeout_failure` |
+| SSH, DNS, or the network could not reach a host that exists | `connectivity_failure` |
+| The AAP2 controller or the underlying platform itself errored | `platform_failure` |
+| A setting names a target that exists and is reachable, but its value makes the run behave wrongly | `configuration` |
+
+**Two boundaries that are easy to get wrong:**
+
+- **`dependency`, not `configuration`** — classify by *what was missing*, not by *which
+  file contained the mistake*. If the run failed because something it needed could not
+  be found, the category is `dependency` even when the reason it could not be found is a
+  wrong path, a narrowed search path, or a commented-out requirement in a config file.
+  Reserve `configuration` for a setting whose target exists and is reachable, where the
+  value merely makes the run behave wrongly.
+- **`dependency`, not `timeout_failure` or `connectivity_failure`** — a fetch that hangs
+  or times out against an artifact that no longer exists is still `dependency`; the
+  timeout is the symptom. Use `timeout_failure` or `connectivity_failure` only when the
+  target exists and the clock or the network is the actual fault.
+
+**Name one category and only one.** The category line carries your verdict, so it must
+not also carry the ones you ruled out. Do NOT list the taxonomy in your report, do NOT
+write "not a `timeout_failure`", and do NOT hedge across two members. The discriminators
+above are for you to decide with, not to reproduce in the report — a report naming two
+categories has not produced a verdict.
+
+**Worked example** — a play that failed because a collection it needed was not on the
+search path. Correct:
+
+<example>
+- **Root cause category:** `dependency`
+- **Confidence:** high
+</example>
+
+Wrong, for that same failure — a composed label, and a second category dragged in from
+the reasoning:
+
+<example>
+- **Root cause category:** Misconfiguration — collections_path debug override left in
+  production (not a timeout_failure)
+- **Confidence:** high
+</example>
+
+`high` is the right confidence when the log and the configuration files you fetched
+directly support the verdict; `medium` when you are extrapolating from partial data;
+`low` when a needed source was unavailable.
 
 #### Source Link Construction
 
```

</details>

<details>
<summary><code>orchestrator.md</code> (+6/−0)</summary>

```diff
--- seed/orchestrator.md
+++ platform-002-collection-not-found-rca/best/orchestrator.md
@@ -164,6 +164,12 @@
 introduces errors (wrong links, missing config trace), and wastes the user's time
 re-reading what they already saw.
 
+**If you do restate any part of a sub-agent's verdict** — a root cause category, a
+confidence level, a citation, or an error string — copy it **verbatim** from what the
+agent reported. Never rephrase a category into your own words, never substitute a
+description for it, and never add a category the agent did not name. A rephrased verdict
+contradicts the agent's, and the reader cannot tell which one to trust.
+
 ## Stay Focused on the Current Investigation
 
 **CRITICAL: When investigating a specific sandbox, account, or user, ONLY
```

</details>

<details>
<summary><code>shared_context.md</code> (+6/−1)</summary>

```diff
--- seed/shared_context.md
+++ platform-002-collection-not-found-rca/best/shared_context.md
@@ -159,7 +159,7 @@
 **Example:**
 > **Sources:** Provision DB (provisions + users), AWS Cost Explorer (us-east-1),
 > [agnosticv config](https://github.com/rhpds/agnosticv/blob/master/sandboxes-gpte/EXAMPLE/prod.yaml),
-> [agnosticd env_type defaults](https://github.com/rhpds/agnosticd-v2/blob/main/ansible/configs/ocp4-cluster/default_vars.yml),
+> [agnosticd env_type defaults](https://github.com/redhat-cop/agnosticd/blob/development/ansible/configs/ocp4-cluster/default_vars.yml),
 > [AAP2 job #12345](https://aap2-prod-us-east-2.aap.infra.demo.redhat.com/#/jobs/playbook/12345)
 
 When you fetch files from GitHub (agnosticv or agnosticd repos), always include
@@ -230,6 +230,11 @@
 
 **When NOT to include:**
 - When all tool results directly support your conclusions (high confidence is the default)
+
+  This exemption is about the `[confidence: ...]` marker for shaky inferences — it is
+  **not** about a root-cause verdict. When your report states a root cause, it always
+  states its own confidence (`high`, `medium`, or `low`) explicitly as part of that
+  verdict, even when the confidence is high and no marker is needed.
 - When empty results are themselves the answer (e.g., "no provisions found for this user"
   is a factual finding, not a data gap)
 - When tools you didn't call weren't relevant to the question
```

</details>

<!-- END:diff -->
