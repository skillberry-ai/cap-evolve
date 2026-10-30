# PROCESS — what I did this iteration (explainability; REQUIRED)

## Where the reward actually leaks

The task is flaky at exactly one place. Across all 10 seed trials:
`completion=1.0` and `answer=1.0` **every time** — all 5 required facts hit, the
forbidden `wrong-cause` fact never hit. The entire 0.91 shortfall is `tool_calls`,
which is 0.5 on 6/10 trials and 1.0 on 4/10.

`tool_calls` is an **ordered-subsequence** match over two expected calls:
`query_aap2 get_job_log` then
`fetch_github_file(agnosticd/agnosticd-v2, ansible/roles/claims_warehouse_rds/tasks/main.yml)`.
Every trial makes the first call. The split is entirely about the second:

| trials | `unmatched_expected` | reward |
| --- | --- | --- |
| erYhnig, Bb5iLoz, oTjEWdt, YkGxYAc, Q9GWB7j, wfkxF47 | the `fetch_github_file` of the role task file | 0.85 |
| kNoeopX, TTo5hv7, LcvQuML, HYsByUb | `[]` | 1.0 |

So the agent reaches the right sub-agent, reads the log, and writes a correct report —
it just **does not reliably read the file it is reporting on**. The answer still scores
1.0 because the AWS error text in the log carries enough to state the facts; the agent
is passing the answer rubric partly without the evidence the contract wants.

## The mechanism (verified against agent.jsonl, not inferred)

The job log hands the agent the path outright:

```
task path: /runner/project/ansible/roles/claims_warehouse_rds/tasks/main.yml:3
```

`/runner/project/` is the repo checkout root, so the repo-relative path is a pure
substring of the log (provenance.md confirms: "the path is a substring of the log's
`task path:` lines. No exemption is needed").

**All 10 trials — passing and failing — ignore that and open with
`search_github_repo` instead.** In this environment that tool returns
`{"matches": [], "total_matches": 0}` for every query, and directory listings return
`"No such file or directory at the requested ref."`, while a *direct*
`fetch_github_file` on the log-derived path returns the file perfectly. The agent reads
the empty search as evidence the role is absent and starts hunting — other search
terms, then other owners (`rhpds`, `redhat-cop`), then other refs, then Splunk. The
round budget runs out. 6/10 never fetch the path at all; the 4 that pass are the ones
that happen to give up searching and fetch directly, and they only get there on tool
call #18–21.

That is the flakiness: **nothing distinguishes the passing trials except whether a
random exploration order reached the direct fetch before the budget ran out.** Making
the direct fetch the *first* GitHub move removes the dice roll.

A rule in `aap2_agent.md` actively pushed the wrong way:

> **Budget your rounds.** […] Do NOT speculatively browse directories — use
> `search_github_repo` or `lookup_catalog_item` to find paths in one call.

Correct advice against blind browsing, but it names search as *the* way to find a path,
with no carve-out for a path the log already gave. Under round pressure the agent obeys
it literally. A second rule contributed: the Step 6 owner/repo table maps v2 to
`rhpds/agnosticd-v2`, while this job's `git_url` is `agnosticd/agnosticd-v2` — several
trials burn calls on `rhpds` because the table outranked the job row in their reading.

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Log-derived file path discarded in favour of search | platform-137 (6/10 trials lose 0.5 tool_calls) | Agent searches for a path the log's `task path:` line already states; prompt names search as the path-finding method with no exception for log-supplied paths | BEHAVIORAL | Decision rule + worked example in `aap2_agent.md` |
| 2 | Empty search / failed listing read as "file absent" | same trials | `search_github_repo` 0 matches and dir-listing errors are treated as proof of absence, triggering owner/repo/ref hunting that exhausts the budget | KNOWLEDGE | Negative-evidence rule in `aap2_agent.md` |
| 3 | Owner/repo taken from the version table, not the job's `git_url` | erYhnig, LcvQuML, wfkxF47 and others (wasted calls on `rhpds`/`redhat-cop`) | Step 6 table presents the two common repos as authoritative; job row's `git_url` is the real source | KNOWLEDGE | Precedence rule in `aap2_agent.md` |

All three are one failure chain, so all three are fixed in the one file the task
actually reads for this domain. Nothing went into `shared_context.md`: these rules are
specific to tracing an Ansible job failure into its source repo, not domain-general.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BEHAVIORAL (decision rule) | `aap2_agent.md` — "Budget your rounds" | Adds the carve-out: when the log names the file, fetch it; search is only for paths you do *not* have. Fixes the rule that caused the misbehavior rather than appending a competing instruction. | Yes — passing trials also fetched this path, just later. Reordering can only help them. |
| 1 | BEHAVIORAL (worked example) | `aap2_agent.md` — new "Deriving the failing file's path from the log" under Step 6 | Shows the `task path:` → strip `/runner/project/` → `fetch_github_file` derivation on a generic `some_role`, and requires reading that line before any GitHub call. Any Ansible job log has these lines, so this applies to every job-failure trace. | Yes — adds a cheaper first move; removes no capability. |
| 1 | BEHAVIORAL | same section, rule 4 | Also fetch the *preceding* task's file when the failing task consumes a value it produced, noting a `no_log: true` task's value can only be understood from the file. Generic statement of "the log censors it, so read the source". | Yes |
| 2 | KNOWLEDGE (negative evidence) | same section, closing paragraph | `total_matches: 0` and `"No such file or directory"` are not proof of absence; a direct fetch on the log-derived path is the authoritative test; never report a role missing on a failed search alone. Generalizes to any unindexed repo. | Yes — stops a false-negative conclusion, enables nothing new. |
| 3 | KNOWLEDGE (precedence) | same section, opening paragraph | Owner/repo come from the job's `git_url`; the Step 6 table is the common case, the job row is authoritative. Applies to any job whose repo is served from a non-default org. | Yes — passing trials used `git_url` already. |

## Verify-the-fix
- **Trials Bb5iLoz / erYhnig / YkGxYAc / Q9GWB7j / oTjEWdt / wfkxF47 (0.85).** Verified
  from `agent.jsonl`: each one's *first* GitHub call is
  `search_github_repo(agnosticd/agnosticd-v2, "claims_warehouse_rds")` → 0 matches, and
  none of the six ever calls `fetch_github_file` on the log-derived path. The new rule
  fires strictly before that call ("read the `task path:` line before any GitHub call",
  and "when the log already names the file, do NOT search for it — fetch it"), and the
  worked example gives the exact derivation for the path the log contains. The negative-
  evidence paragraph removes the reason the six kept hunting after the empty search.
  This is the one call the subsequence is missing, so supplying it takes `tool_calls`
  0.5 → 1.0.
- **Trials kNoeopX / TTo5hv7 / LcvQuML / HYsByUb (1.0).** Each already fetched the path,
  at call #18–21 after the same wasted search phase. The edits move that fetch earlier
  and forbid nothing they did, so they stay at 1.0 — and should get there with fewer calls.
- **Answer rubric.** No edit touches how the report is written, and I added no text about
  passwords, character sets, randomness or RDS. `answer=1.0` on all 10 trials is
  therefore undisturbed, and the forbidden `wrong-cause` fact stays unreachable (nothing
  I wrote suggests a transient provider fault). The fix raises evidence quality, so if
  anything it makes the correct answer better grounded.

## Non-overfitting check
No rule names a value from this task. The added text's only identifiers are the generic
`some_role` / `some_task_name` placeholders and `/runner/project/`, which is Ansible
Runner's fixed checkout root for every AAP2 job, not a fact about this scenario. No
GUID, job id, controller, role, repo, owner, or character-set detail from this task
appears anywhere in the diff. Restated task-independently: *"when a job log states the
failing file's path, fetch that path directly; take owner/repo from the job's own git
URL; and do not treat an empty search or a failed directory listing as proof the file
is absent."* All three hold for any job-failure trace.

## Process & features used
- **Serial, no subagents or worktrees.** The brief suggests fanning out one diagnostic
  subagent per trajectory-group, but there is exactly one task and one failure mode, and
  `reward-detail.json` localised it to a single missing tool call within the first few
  minutes. Fanning out would have cost budget to re-derive one already-certain finding.
  All three edits land in one file and one section, so parallel edit-agents would have
  conflicted on the same hunk for no gain.
- **What made the diagnosis cheap:** the `trajectories/*.json` shown in the working dir
  have `"trace": null` and `"tool_calls": []`, so they cannot explain the failure. The
  real evidence is under each trial's `metadata.trial_dir` —
  `verifier/reward-detail.json` (gives `unmatched_expected` outright) and
  `agent/agent.jsonl` (full call sequence with results). Note each seed dir holds **two**
  runs; I matched on the `trial_result.task_id` suffix rather than taking the first hit,
  which initially mismatched passing and failing trials.
- **Prior iterations:** none — `RUNMAP.md`, `LEDGER.md`, `rejected.jsonl` and
  `history.jsonl` are all empty at iteration 1/5, so nothing to build on or avoid.

## Good things to PRESERVE
- Fetching the role task file at the **log-derived path** as the first GitHub move. This
  is the one call the grader's subsequence needs and the only difference between the
  0.85 and 1.0 trials.
- The negative-evidence rule. In this environment `search_github_repo` returns 0 matches
  and directory listings error for a repo that serves files fine; without the rule the
  agent re-derives "the role is missing" every run.
- Owner/repo from `git_url` taking precedence over the Step 6 table.
- Do not "fix" the answer section — it is already 1.0 on every trial and the forbidden
  fact is never hit. Spend future iterations on `tool_calls` only.

## Deliberately skipped
- **The answer rubric** — 5/5 required facts and 0 forbidden hits on all 10 trials.
  Nothing to win, and edits there risk the forbidden `wrong-cause`.
- **`shared_context.md` / `orchestrator.md`** — routing is correct every trial
  (`investigate_aap2_job`), and the fix is specific to source-tracing an Ansible failure,
  so putting it in shared context would widen blast radius for no benefit.
- **The censored-`no_log` reasoning** — the agent already derives randomness and the
  character set correctly once it reads the file; this was an evidence-gathering failure,
  not a reasoning one.

## Escalation (no prose fix exists)
`search_github_repo` returning `total_matches: 0` for a repo whose files
`fetch_github_file` serves correctly is a **tool-layer defect**, not a prompt problem.
My edits route around it by making the direct fetch primary and telling the agent not to
trust the empty result, but the honest fix is for the search tool to index these repos
(or to signal "not indexed" distinctly from "no matches" — the two are indistinguishable
to the agent today). Same for directory listings, which return
`"No such file or directory at the requested ref."` for paths that exist. Out of scope
in this phase (no tools/code layer); recorded here as a real finding.

---

# DIAGNOSIS.json — see sibling file `DIAGNOSIS.json`.
