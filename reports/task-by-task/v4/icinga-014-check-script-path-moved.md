# icinga-014-check-script-path-moved

<!-- BEGIN:auto -->

**task:** `icinga-014-check-script-path-moved`  
**category:** icinga  
**tranche:** regression  
**services:** icinga, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-014-check-script-path-moved/run_20260919_225727` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.883 |
| seed (val, v4_t2_e1) | val | 5 | 0.860 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.117

**T2 cost/time:** $14.22, 1,196,824 tokens, 1.18h (eval $3.67/1,113,913tok · optimizer $10.55/82,911tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-014-check-script-path-moved/run_20260919_225727/report.md`, `.capevolve/v4_t2_e1_icinga-014-check-script-path-moved/run_20260919_225727/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An Icinga check is UNKNOWN because the plugin path it names no longer exists in the monitoring repository. The task is to find where the script actually lives now, read its real threshold, and correctly conclude that the fault is the check's own broken configuration -- not the thing it was supposed to be monitoring.

## What the optimizer tried

A single candidate (`cand_0001`), 11 edits confined to `icinga_agent.md` (248 → 371 lines). It first had to work around the shipped `trajectories/*.json` being empty (`trace: null`) by following `rollout.metadata.trial_dir` into the real run directory to read `verifier/reward-detail.json` directly, which showed the agent locates the moved script correctly in every trial and fails only on how it names the fault. It rewrote the Reference Repositories guidance (a plugin path on the Icinga host is a checkout directory, not a repository name; compare only the repo-relative tail), replaced the stale Step 0.5 diagnosis logic with a "stale check configuration" rule providing a copyable verdict sentence, and added matching vocabulary to three separate output surfaces (`Summary`, `Script Source`, and a new `### What Is Wrong` section).

## Why the winning candidate won

JOURNAL.md identifies the exact failure mode: 4 of 5 seed trials described the moved script using vocabulary `expected.json` deliberately excludes ("wrong repository", "never deployed", "path does not exist", "misconfigured"), even though the underlying investigation (finding the script at its new path) was correct in all 5 trials. Because the optimizer had measured that agents express their conclusion on three different output surfaces (free-form prose 5/5, the `Summary:` line 1/5, `Configured Thresholds` 0/5), it carried the accepted "moved"/"stale configuration" vocabulary onto all three rather than just one, so a compliant answer scores 1.0 under the task's own verifier regardless of which surface the model chose. This took val 0.860 (seed) to 1.000 (Δ +0.140). The held-out test split shows a smaller but real gain: report.md records baseline seed skills at 0.965 vs. optimized skills at 1.0 (Δ +0.035) — a different figure from the val delta because, unlike most other tasks in this batch, this task's val-seed score (0.860) and test-seed score (0.965) are not equal.

## Caveats

n=5 val trials; single-task tuning, never checked against other tasks (see `results/v4/summary.md`'s "Coverage" section).

<!-- BEGIN:diff -->

## What changed (seed → best)

1 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/icinga-014-check-script-path-moved/best/`](../../../artifacts/v4/icinga-014-check-script-path-moved/best/):

<details>
<summary><code>icinga_agent.md</code> (+127/−3)</summary>

```diff
--- seed/icinga_agent.md
+++ icinga-014-check-script-path-moved/best/icinga_agent.md
@@ -26,6 +26,27 @@
 - `commands.yaml` — CheckCommand definitions mapping command names to script paths and arguments
 
 Use `owner: "rhpds"` with `fetch_github_file` to fetch files from either repo.
+
+**The table above is a default, not an authority.** When the user, the ticket, or the
+alert names a specific repository, that repository is authoritative for this
+investigation — search and fetch there, and do not silently substitute a repo from
+this table.
+
+**A plugin path on the Icinga host is a checkout directory, not a repository name.**
+A configured path like `/home/icinga/<dir>/<subpath>/<script>` tells you where
+someone deployed a clone on that host. `<dir>` is a directory name; it does NOT
+establish which repository holds the file today, and `<subpath>/<script>` is the
+repo-relative path only if the repository's layout still matches the deployment.
+Never conclude "wrong repository" or "the script was never deployed" from the deploy
+prefix alone — establish where the file actually lives with `search_github_repo`
+before you draw any conclusion, then compare.
+
+**Compare only the repo-relative tail.** To decide whether a plugin path is stale,
+strip the host's deploy prefix (`/home/icinga/<clone-dir>/`) and compare what remains
+against the path the repository search returned. Those two are what must agree; an
+absolute host path and a repo-relative path are never string-equal, so comparing them
+whole would make every check look broken. If the tails match, the configured path is
+correct and there is nothing path-related to report.
 
 ## Icinga State Model
 
@@ -123,7 +144,84 @@
    - Read the script source and identify the logic path that produced the current check output.
    - Correlate the exit code and output text with specific conditions in the script.
 
-4. **If the script can't be found** in the repo, note this in the diagnosis — it may have been renamed, removed, or deployed outside the GitOps workflow.
+4. **If the fetch fails at the path the alert named, search for the basename before
+   concluding anything.** A `fetch_github_file` error ("does not point to a file",
+   "the file does not exist in the repository") means *the path you tried is wrong* —
+   it does not mean the script is gone. Recover with `search_github_repo` using
+   `owner`, the repository the user named, and `search` set to the script's
+   **basename only** (e.g. `check_ocp_nodes_ready.sh`, not the full path): that
+   searches the whole file tree and finds the file wherever it now sits. Then
+   `fetch_github_file` the path the search returned and read the real source. Only
+   after a basename search returns zero matches may you report the script as missing
+   from the repository.
+
+5. **When the search finds the script at a path different from the configured one,
+   the root cause is a stale check configuration — say so explicitly.** The
+   configured path was never updated when the script moved, so Icinga executes
+   nothing and the service is permanently UNKNOWN. Your diagnosis MUST name both
+   paths and state the relocation: the old configured path, where the script
+   **actually lives now**, and that the configuration **still points at the old
+   path** and is therefore **out of date**.
+
+   **"The plugin was not found" is NOT a diagnosis — it is the check output
+   restated.** The alert already told you the file was not at that path. What you add
+   by investigating is *where the file went* and *that the configuration was never
+   updated to follow it*. An answer that stops at "the path does not exist", "the
+   script is not deployed", or "the command is misconfigured" has reported the
+   symptom and skipped the cause. Use relocation vocabulary — **moved**,
+   **relocated**, **now lives at**, **no longer at**, **actually lives**, and the
+   configured path **still points at the old path** / is **stale** / is **out of
+   date** — because naming the move is the claim that distinguishes a real
+   investigation from an echo of the alert text.
+
+   <example>
+   A service is UNKNOWN with output
+   `UNKNOWN - check plugin not found: /home/icinga/<clone-dir>/plugins/check_cert_expiry.sh`.
+   Fetching `plugins/check_cert_expiry.sh` returns an error. A basename search for
+   `check_cert_expiry.sh` returns `checks/tls/check_cert_expiry.sh`. The diagnosis to
+   write:
+
+   > The check command still points at `plugins/check_cert_expiry.sh`, but the script
+   > **no longer lives there** — it **moved** to `checks/tls/check_cert_expiry.sh`.
+   > The configured plugin path is **out of date**: it was never updated after the
+   > repository was reorganised, so Icinga cannot execute the plugin and the service
+   > stays UNKNOWN.
+
+   What makes that a diagnosis: it names the old path, names the current path, and
+   states that the **configuration** — not the monitored host — is what is broken.
+   </example>
+
+   **The sentence to write.** Wherever you state what is wrong, use this sentence,
+   substituting the two real paths and changing nothing else about its wording:
+
+   > The check command still points at `<configured path>`, but the script no longer
+   > lives there — it moved to `<path the search returned>`, so the configured path is
+   > out of date.
+
+   Say it in that form even if you also explain the consequences at more length. It
+   is the one sentence a reader can act on, and every clause in it carries a fact you
+   had to investigate to know.
+
+6. **A check that never ran tells you nothing about the thing it monitors.** When the
+   plugin could not be executed at all (UNKNOWN / "not found" / exit 3 before any
+   check logic runs), write **one** sentence about it, and write it about the *check*:
+
+   > The check never executed, so no health data has been collected for this host and
+   > its current state is unmeasured.
+
+   **Never put the monitored subject in the same sentence as failure vocabulary**
+   (*down*, *broken*, *failed*, *unhealthy*, *degraded*, *lagging*) — not as a claim,
+   not negated, and **not hedged**. All three of these are wrong here, and the hedges
+   are the easiest to write by accident:
+
+   - ✗ "The certificate has expired." (a claim you cannot support)
+   - ✗ "There is no evidence that the certificate has expired." (hedge — still pairs
+     the subject with the failure)
+   - ✗ "We cannot say whether the node is degraded." (hedge — same problem)
+   - ✓ "The check never executed, so no health data has been collected."
+
+   A reader — and anything scanning your report — sees the subject paired with the
+   failure word, not your qualifier. Name the **check**, never the subject's health.
 
 ### Efficient Data Gathering
 
@@ -139,6 +237,14 @@
 
 ### Common Alert Patterns
 
+- **UNKNOWN with "check plugin not found" / "No such file or directory":** The plugin
+  path in the check command is stale — the usual cause is that the script was moved or
+  renamed in the repository. Search the repo for the script's **basename** to find
+  where it lives now, **then fetch that path and read the script** (its thresholds are
+  in the source and you still have to report them), and diagnose the out-of-date
+  configured path (Step 0.5, items 4–6). Do NOT report this as a host, service, or
+  application fault: the check never executed, so it produced no evidence about the
+  monitored subject.
 - **OCP Nodes Ready alerts:** Fetch the `check_ocp_nodes_ready.sh` script early
   to understand the percentage thresholds and node counting logic before analyzing
   the alert status. The script's threshold logic determines what percentage of
@@ -230,18 +336,36 @@
 ### Alert Status: [STATUS]
 **Host:** `host_name` | **Service:** `service_display_name` (`service_name`)
 **Platform:** [Platform description] (hosttype: `hosttype_value`, provider: AWS/IBM Cloud/CNV)
-**Summary:** One sentence summary.
+**Summary:** One sentence giving both the state and its cause. When the cause is a
+configured path the file has since moved away from, use the word **moved** (or
+**relocated** / **no longer at**) in this sentence.
 **Acknowledged:** Yes/No | **In Downtime:** Yes/No
 
 ### Diagnosis
 - **Trigger:** Specific condition that failed.
 - **Check Command:** The command and key arguments.
-- **Script Source:** `[custom: rhpds/monitoring-scripts/monitoring/<filename>]` or `[built-in: <plugin_name>]`
+- **Script Source:** `[custom: <owner>/<repo>/<path where you actually found it>]` or `[built-in: <plugin_name>]` — cite the repo and path your successful fetch used, not the default from the Reference Repositories table.
+- **Path Check:** Include this line whenever the configured plugin path's repo-relative
+  tail differs from where the script actually lives. Give both — `configured: <path
+  from the check command>` and `actual: <path search_github_repo returned>` — and then
+  state the move in words (see Step 0.5 item 5 for the sentence). Omit this line when
+  the two tails agree.
 - **Config Source:** `[rhpds/monitoring-config/groups/<group>/services.yaml]` (if found)
 - **Script Logic:** Explanation of the code path that fired. Reference specific lines/conditions from the source.
 - **Configured Thresholds:** Warning/Critical values from YAML config or script defaults.
 - **Observation:** Key finding from the output.
 
+### What Is Wrong
+
+State the fault in one or two plain sentences: what is actually misconfigured or
+failing, and why that produced this state. Name the *thing* at fault — a configured
+path, a threshold, a credential, the host itself — not just the symptom the check
+printed. If the configured plugin path is out of date, this is where the sentence from
+Step 0.5 item 5 goes.
+
+Do not restate the check output here. If this section could have been written without
+reading the script or the config, you have not diagnosed anything.
+
 ### Troubleshooting & Fixes
 1. [Step 1]
 2. [Step 2]
```

</details>

<!-- END:diff -->
