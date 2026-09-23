# PROCESS — cand_0001 (iteration 1/3)

Task: `platform-031-helm-url-not-a-timeout`, baseline val **0.441** (flaky, 3 scored
trials). Capability: `system-prompt`. All edits landed in **one file**, `aap2_agent.md`.

## 0. How I diagnosed (order of work)

1. Read `INSTRUCTIONS.md`, `LEDGER.md`, `JOURNAL.md`, `RUNMAP.md`, `INSIGHTS.md`,
   `META_INSIGHTS.md`. No prior iterations, empty `rejected.jsonl` / `history.jsonl` —
   nothing refuted yet, so the whole edit space was open.
2. Read the task definition: `instruction.md`, `tests/expected.json`, `golden.json`,
   `task.toml`, `provenance.md`, `verify.py`. **`verify.py` was the decisive read** — it
   gave me the exact arithmetic of a point (below), which is what let me rank issues by
   measured value rather than by vibe.
3. `trajectories/*.json` were useless (`trace: null`, `tool_calls: []`). Followed
   `metadata.trial_dir` to the real transcripts:
   `_run/jobs/v4_t2_e1/platform-031-helm-url-not-a-timeout/seed-{0,1,2}/**/agent/agent.jsonl`
   plus `verifier/reward-detail.json`. Three usable rollouts (seed-3/4 have no
   `agent.jsonl`).
4. Cross-referenced `task.toml` `services=["platform","github"]` against
   `orchestrator.md`'s routing text → agent #2 `investigate_aap2_job`. **Routing is
   already correct** in all 3 rollouts, so `orchestrator.md` needed no change.
5. Fanned out one read-only subagent to profile `aap2_agent.md` structurally (section map,
   verbatim quotes by topic, zero-hit gap list, house style) while I read the file myself.
   Its report confirmed every line number and surfaced two gaps I had missed
   (`search_terms` and `latest` appear nowhere in the file; `query_splunk`'s actions are
   never attributed to their parent tool).

### Scoring arithmetic (from `verify.py`) — used to rank everything below

- `weights = {answer: 0.7, tool_calls: 0.3}`; tool calls matched as an **ordered LCS
  subsequence** with **subset arg matching** (extra args fine, order matters).
- Answer denominator = required(4) + counts(1) + citations(0) + verdict(1) + forbidden(2)
  = **8**. So **one answer fact = 0.0875** of final reward; **one tool call = 0.06**.
- Gate is `completion {nonempty_answer, status: ok}`. **A timeout ⇒ reward 0.0**,
  regardless of how much was learned.
- `_forbidden_violated` splits the answer on `(?<=[.!?])\s+|\n+` — newlines count, so
  markdown bullets are separate "sentences". Neither forbidden item declares
  `attributed_to`, so *any* occurrence anywhere violates.

## 1. Ranked issues

| # | Issue | Trials | Prompt text that caused it (pre-edit line) | Est. value |
|---|---|---|---|---|
| 1 | **Timed out with NO answer** → completion gate 0 → reward **0.0**, after 17 calls and zero text | 1/3 (seed-2) | Critical Rule 3 "Budget your rounds" — no numeric cap, no answer reserve, no anti-re-fetch rule (`:18-22`) | **~+0.23** |
| 2 | **`mirror-serving` fact missed 3/3** and **`query_splunk search_by_guid` never matched 3/3** | 3/3 | `:498-500` "Splunk is a supplementary data source. Only use it when the primary tools … don't provide enough signal"; `:511`/`:520` prescribe `errors_only=true` | **~+0.147** |
| 3 | **Wrong GitHub owner + wrong role path** → `var-root-url` missed, 3 tool calls unmatched, 1 fabricated variable name | 2/3 (seed-1, seed-2) | `:238` says owner `rhpds` for agnosticd-v2 while `:204`/`:456` say `agnosticd` — a **direct self-contradiction**; `:248` says `ansible/roles/`, real v2 workload layout is `ansible/roles_ocp_workloads/` (**0 hits** in all 8 files) | **~+0.09** |
| 4 | **Forbidden `transient` hit** — "Transient external CDN / network read timeout", "Re-trigger the provision" | 2/3 | `:281` "Long = timeout"; `:294` `\| timeout \| Resource provisioning timeout \|`; `:444` "Increase timeout…"; no root-cause category vocabulary or confidence slot anywhere in the file | **~+0.058** |

Issue 2 is the task's designed trap — `provenance.md`: *"The agent failure it exposes is
accepting the symptom's own explanation."* The prompt did not merely fail to prevent it;
it **actively taught it** (issue 4) and **forbade the one call that refutes it** (issue 2).

## 2. Every edit, with its class

All in `aap2_agent.md`. Classes per `guidance/system-prompt/SKILL.md`.

| # | Edit | Class | Targets |
|---|---|---|---|
| A | Critical Rule 3 → numeric budget: hard report checkpoint at **call 12**, max **4 calls to locate one file**, never re-fetch one logical path across owner/repo/ref, "a report with a named gap beats no report". Rule 2 gains "a run that ends while still calling tools is scored a total failure". | tighten decision policy | 1 |
| B | `## Using Splunk Logs` rewritten: dropped "supplementary / only use it when…"; Splunk is now **MANDATORY before naming a root cause** when the failing op targeted anything outside the job. Actions attributed to `query_splunk`. | resolve conflict + strengthen mandate | 2 |
| C | New `### Searching FOR contrast, not for the error you already have`: never `errors_only=true` / never the failure's own terms in `search_terms` when asking "what else happened" — the rows that answer it are `INFO` successes. Unfiltered first, narrow only if truncated. **Worked WRONG/RIGHT example.** Plus GUID-extraction fallback when the API omits the field, and "inconclusive ≠ nothing was running". | worked example + decision rule | 2 |
| D | New `#### Step 7a: Timeouts, Retries and Dead Dependencies`: 3 ordered questions (exact target → did anything else reach the host → is the ref floating), with the `dependency` / `connectivity` / inconclusive split; "**exhausted retries are evidence AGAINST transience**"; transience requires *positive* evidence, else say **undetermined**. Includes "`find_jobs` does NOT answer this — it is job-granularity, not log lines". | new decision rule | 2, 4 |
| E | Generalized "Do NOT stop at surface-level errors" past pods: errors that *sound self-explanatory* ("read operation timed out", "gave up after N attempts") name a symptom while sounding like a diagnosis — **the error text is the hypothesis to test, never the finding to report**. | sharpen existing rule | 4 |
| F | `:281` timing rule: "Long = timeout" → "Long = it spent that time *waiting on something*; that tells you where to look, not that the cause is 'a timeout'". | correct wrong guidance | 4 |
| G | `:294` table row and `:444` fix row rewritten; added a "download/fetch failed on a URL" fix row pointing at Step 6b and ref-pinning. | correct wrong guidance | 4 |
| H | Step 6 owner table `rhpds` → `agnosticd`, **plus** "never type an owner/repo from memory" with a 3-step resolution order (`scm_url`/`git_url` → `lookup_catalog_item` → account prefix confirms *version* not *owner*), a corroborate-the-file-against-the-log rule, and an explicit ban on re-fetching one path across orgs. | resolve conflict + new rule | 3, 1 |
| I | Step 6 fetch list gains the role's **`defaults/main.yml`** as first-class ("the variables it does it WITH"); "don't type role paths from memory — `search_github_repo` them"; structure tree gains `roles_ocp_workloads/` and the `defaults/` vs `tasks/` split. | missing knowledge | 3 |
| J | New `#### Step 6b: Compose the Failing Value from Its Variables`: name each variable from the file (never invent a plausible name), quote the composition comment, check the precedence chain, report names **and** composed result, flag floating segments. | new decision rule | 3 |
| K | Output contract: added **root cause category** (7-label vocabulary table with use/don't-use columns), **confidence**, **ruled out**, and an external-target block (target requested / composed from / retry attempts / other traffic in window). Plus "write ruled-out items as evidence, not label denials", with good/weak examples. | tighten output contract | 2, 3, 4 |
| L | `MANDATORY fetch_github_file` block and the Steps 3-6 CHECKPOINT extended to also require Step 6b + the unfiltered Splunk search for external-target failures. | strengthen mandate | 2, 3 |

`orchestrator.md`, `shared_context.md` and the other 5 domain files: **untouched.** Routing
was already correct in 3/3 rollouts, and every rule above is AAP2-investigation-specific,
so per `INSTRUCTIONS.md` it belongs in the domain file, not in `shared_context.md`.

## 3. Verify the fix — each edit against the exact point it went wrong

Re-extracted the full tool-call sequence of all 3 rollouts *after* editing, and checked
the edited text against the precise call where behaviour diverged. Not "plausibly helps":

- **Seed-2, calls 11 / 14-17 → edit A + H.** Call 11 re-fetches the *same* path at
  `ref: development`; calls 14-17 re-fetch the *same two* paths from a third org
  (`rhpds`). Edit A's "never re-fetch one logical path across owner/repo/ref" and H's
  "do NOT re-fetch from a second and third org — each copy looks plausible" name exactly
  this. Edit A's call-12 checkpoint fires **before calls 13-17**, forcing a report where
  seed-2 produced none. This alone converts a 0.0 into a partial score.
- **Seed-2, calls 8/9/10/12 → edit A.** Four consecutive `search_github_repo` hunting one
  file on the wrong owner. "Never spend more than 4 calls locating one file" binds at 10-12.
- **Seed-1, call 4 (`rhpds/agnosticd-v2`) and calls 10-12 (`ansible/roles/…` on
  `redhat-cop`) → edits H + I.** Call 4 is the `:238` table row verbatim — the row I
  corrected. Calls 10-12 are the `:248` layout verbatim. The fabricated variable
  (`…_helm_base_url`, invented from a mismatched file) is what J's "never invent a
  plausible-looking name" and H's corroborate-against-the-log rule forbid.
- **Seed-1, call 14 → edit C.** `search_by_guid` with
  `search_terms: "<host> helm timeout"` — over-narrowing the one call that had the answer,
  filtering out the `INFO` success rows it needed. Edit C's WRONG example is structurally
  this call; the RIGHT example is the fix.
- **Seed-0, calls 5 & 9 → edit D.** `find_jobs` used to answer "what else was downloading",
  concluding "only this job matched in the ±2h window, so this was not a shared-bandwidth
  event." D's "`find_jobs` does NOT answer this — job granularity, not log lines" and the
  Step 8 discriminator target exactly this substitution.
- **Seeds 0 & 2 never called `query_splunk` at all → edits B + L.** Both had already
  formed an explanation from the job log + GitHub, which under `:498-500` made Splunk
  *by the rule* unnecessary. B removes the gate and makes the call mandatory for
  external-target failures; L adds it to the mandate block and the checkpoint.
- **Seeds 0 & 1's "transient / re-trigger" conclusion → edits D + E + F + G + K.** F and
  G remove the text that licensed it ("Long = timeout", "Increase timeout"); D inverts the
  retry inference and requires positive evidence for transience; K forces a category from
  a vocabulary where the `dependency`/`connectivity` split is decided by the Splunk
  evidence rather than by the error wording.

**Coverage check:** 0/3 rollouts ever issued an unfiltered `search_by_guid`; 2/3 never
called `query_splunk`; 3/3 missed `mirror-serving`. That is the dominant, fully
reproducible failure and edits B/C/D/L hit it head-on.

## 4. Non-overfitting

Automated scan of the 3 touched-or-adjacent files for every instance-specific token —
`t7fkq`, `90431`, `ocp4_workload_showroom_tools_root_url`, `..._helm_version`,
`mirror.openshift.com`, `cnv-roadshow`, `helm-linux`, `openshift-client`, `odo-linux`,
`agd-v2.cnv` — **all zero.** The worked example in edit C uses invented placeholders
(`artifacts.example.com`, `toolA`/`toolB`) with a different shape from the real case. No
rule names the answer; every rule states a *procedure* (search unfiltered, corroborate the
file against the log, require positive evidence for transience) or a *discriminator*
(host reachable ⇒ `dependency`, nothing reached it ⇒ `connectivity`) that an unrelated
failure would match equally. Nothing tells the agent to avoid a word — edit D constrains
when a transience *claim* is warranted, which is the honest version of that rule and is
what the rollouts actually got wrong.

I deliberately did **not** add "never say transient" or any grader-shaped instruction.

## 5. Preserved deliberately

- All security constraints in `shared_context.md` (no user-supplied SQL; SELECT-only tool;
  don't reveal raw SQL/credentials/internal infra) — that file is untouched.
- The no-narration rule, the mandatory-report rule, `Source Link Construction`'s
  exact-coordinates requirement, the `[confidence: …]` marker format in
  `shared_context.md`, and the existing Step 1-8 skeleton and house style (bold all-caps
  directives, pipe tables, numbered rules, ~88-col wrap).
- `orchestrator.md` routing: unchanged, because it was already right 3/3.

## 6. Skipped, with reasons

- **`search_agnosticv_prs` (`:47`) is referenced but not in the Available Tools list.** A
  real defect, but no rollout called it — unevidenced, so out of scope this iteration per
  "Verify the fix".
- **`shared_context.md` hardening of the grounding rule.** The fabricated variable name is
  a grounding violation, but the specific fix (read `defaults/main.yml`, corroborate
  against the log) is AAP2-domain, so it went in the domain file.
- **Splunk row in the Configuration Trace table.** Would be tidy; the evidence already has
  a home in the new external-target block, and I did not want a second place to put it.

## 7. Escalation (needs code, cannot be fixed with prose)

In the live simulation, `get_job_log` returned only `{job_id, controller, log}` — **no
`guid` and no `display_name`** — and `lookup_catalog_item` returned `{"result": []}` or a
hard error in **every** trial. The gold 4-hop chain
(`display_name` → catalog item → owner/repo) is therefore **broken in this environment**;
the expected `lookup_catalog_item` call cannot succeed on its merits. My edits route around
it (derive the GUID by parsing the template name / bastion hostname; resolve owner from
`scm_url`/`git_url` first), which is the honest prose fix, but the tool/sim defect itself
needs a code-layer fix and caps the achievable score. Also logged to
`FRAMEWORK_IMPROVEMENTS.md`.

## 8. Subagents / features used

One read-only `Explore`-style subagent to profile `aap2_agent.md` (section map, verbatim
quotes by topic, zero-hit gap inventory, house-style notes) in parallel with my own read;
its independent line numbers matched mine and it found the `search_terms` / `latest`
zero-hits. Diagnosis of the 3 rollouts I did directly — with only 3 transcripts and one
target file, per-trajectory edit-subagents in separate worktrees would have cost more
merge risk than the parallelism was worth. Post-edit integrity + overfitting scan
automated in Python.
