# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I diagnosed (reusable — read this first next iteration)

`trajectories/*.json` in this working dir carry **no trace** (`"trace": null`,
`tool_calls: []`) — only a reward summary. The real evidence is reachable via
`rollout.metadata.trial_dir`, which points into the parsec harbor run tree:

```
<trial_dir>/<ts>/bench-*/verifier/reward-detail.json  # EXACTLY which rubric items missed
<trial_dir>/<ts>/bench-*/agent/agent.jsonl            # full transcript
```

`reward-detail.json` is the highest-value file in the run: it names the missed
rubric item ids, the forbidden phrases hit, and the unmatched expected tool
calls. It removed all guesswork about *which* of the six required facts was
lost. **Start there, not with the prompt files.** The task rubric itself is at
`_run/tasks/bench-v6-platform-153-.../tests/expected.json`.

Answer = 6 required facts + 1 citation + 2 forbidden checks; `answer` is 70% of
reward, `tool_calls` 30%. I tabulated all 10 seed trials rather than reading one.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **A — "cite the line" answered with the line's text, never its number** (missed in **10/10** trials; caps answer at 0.889) | platform-153-override-uses-removed-variable-name | Agent treats "cite the line" as satisfied by quoting the line verbatim. Nothing in any prompt file says a line citation requires a *numeric* line number, nor how to count one from `fetch_github_file`'s single `content` string. | KNOWLEDGE | output contract + worked example |
| 2 | **B — remediation heading echoes the requested value as an accomplished outcome** (forbidden `override-applies` hit in **6/10** trials; drops answer 0.889→0.778) | platform-153-override-uses-removed-variable-name | When reporting "your setting is not honoured, here is the fix", the agent titles the fix section with the *requested* value + a present-tense verb of attainment, which reads as the opposite of its own finding. | BEHAVIORAL | decision policy / wording contract |
| 3 | **C — pinned fetch issued without `ref`** (expected tool call unmatched in **3/10** trials; tool_calls 1.0→0.0, 30% of reward) | platform-153-override-uses-removed-variable-name | Agent reads the pinned revision from the consuming config, then fetches the dependency file with no `ref`, silently reading the default branch. Also burns calls searching already-confirmed repos/forks. | BEHAVIORAL | explicit tool-use rule |

Cluster A is the ceiling: even otherwise-perfect trials capped at 0.889 answer.
A+B together explain the entire 0.778-vs-0.889 spread; C explains the
0.694/0.772 outliers.

## Changes made this iteration

All three edits are in `shared_context.md`. **Placement rationale:** `task.toml`
has `services=["github"]`; the two tools used (`fetch_github_file`,
`search_github_repo`) appear only in `aap2_agent.md`, `babylon_agent.md`,
`icinga_agent.md`. Delegation is **not** recorded in `agent.jsonl`, so I could
not determine which sub-agent ran. `system_prompt.py` prepends
`shared_context.md` to every sub-agent and *not* to the orchestrator — so it is
the one file guaranteed to be read whichever candidate sub-agent handled this.
A domain-file edit had a real chance of landing in a file this task never reads.
Deliberate trade-off, not convenience.

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | KNOWLEDGE + output contract | `shared_context.md` → new `### Citing a Specific Line in a Fetched File` | "cite the line" means a *number*, not the line's text. Count from 1 over the newline split, counting blank and comment lines. Render a numbered excerpt block first, then read the number off it. Cite the value's own line; mention any explanatory comment span separately. Generalizes to every file-backed "where does this value come from" question. | Yes — adds a requirement to an answer shape that was previously silent; no existing rule is loosened or reworded. |
| B | BEHAVIORAL / wording contract | `shared_context.md` → new `## Reporting a Setting That Is Not In Effect` | Keep requested vs effective value from blurring: effective value in present tense, requested value only past-tense/imperative; never put the requested value in a remediation heading as an accomplished outcome; title the section by its action ("Required change"/"Fix"). Generalizes to any renamed/removed/overridden-setting finding. | Yes — constrains wording only in the case where a setting is NOT in effect, so correct-and-honoured answers are unaffected. |
| C | BEHAVIORAL / tool-use rule | `shared_context.md` → new `### Fetching a File at the Revision That Is Actually Deployed` | When a config pins a revision (`scm_ref`, a `version`, a `Revision` SHA), every later fetch of that repo MUST pass it as `ref`; re-fetch if the ref is learned late. Don't search for a path the question already gives; don't search other owners/forks of an already-confirmed repo. | Yes — the existing `ref` guidance in `aap2_agent.md` already says to use `scm_ref`; this makes it mandatory and available to all sub-agents, contradicting nothing. |

## Verify-the-fix

- **A** → seed-0 `agent.jsonl` ends with a fenced quote of the deciding line and
  no number, while the instruction says "Cite the line in the role's defaults
  that decides it". New rule states quoting is not an answer and mandates the
  number — fires exactly there. I hand-counted the fetched content: the deciding
  assignment is the 13th line under precisely this counting rule, and the
  explanatory comments occupy lines 10–12, which is why the "cite the value's
  line, not the comment" clause is needed to land on 13 rather than 11/12.
  Cross-check: trials from *later* prompt versions that pass this item emit a
  numbered block then "line 13" — I prescribed the shape that empirically works.
- **B** → the hit substring sits in a heading the agent wrote while describing
  the fix ("What to put in the catalog item to get 60 GiB"). Rule 2 forbids that
  heading shape and supplies action-titled replacements.
- **C** → in the failing seeds the agent had already read the pinned revision
  before fetching the dependency. The rule makes passing `ref` mandatory at that
  step, and tells it to re-fetch if the ref was learned late.

## Non-overfitting

Mechanically checked the added lines for `netbox`, `ipam`, `60Gi`, `10Gi`,
`v2.12`, `db_storage`, `network_bu`, `rhpds`, `agnosticd`, `line 13` — clean.

Two honest corrections during the work: my first draft of edit B leaked `10Gi`
and `60 GiB` into examples (now `<effective value>` / `<requested value>`
placeholders), and it spelled out "still takes effect", which is itself one of
the rubric's forbidden substrings — removed, since I did not want the prompt
seeding an echo of a phrase the grader penalizes. An early leak-check of mine
was run against `git diff` and returned empty because `work/` is gitignored;
the real check diffs against `candidates/seed/`. Worth knowing next iteration.

Each rule restates with no task-specific noun: "cite a line → give its number",
"don't claim a requested value is in force", "fetch at the pinned revision".

## Process & features used
- Subagents / worktrees / parallel features used: **none — serial fallback.**
  One task, one trajectory group, three small non-conflicting edits in a single
  file. Fan-out would have added coordination cost with nothing to parallelize
  over. The leverage here came from `reward-detail.json` aggregation across all
  10 trials, not from parallelism.
- Prior iterations read from `./prior_iterations/` + `./RUNMAP.md`: **none exist**
  — this is iteration 1. `rejected.jsonl`/`history.jsonl` are absent (no prior
  candidates), so there was nothing to avoid re-proposing.

## Good things to PRESERVE (do not let a future iteration undo these)
- The **numbered-excerpt-block procedure** in the line-citation rule. It is the
  method the empirically-passing trials used; a terser "give the line number"
  invites off-by-one against a rubric that accepts only 13.
- The **`<placeholder>` style** in all three sections. These rules are one
  careless edit away from being task-specific.
- The rule-B instruction to **title remediation sections by action**. The
  forbidden-phrase hit arises from heading wording, not from analysis errors —
  the analysis was already correct in all 10 trials.

## Deliberately skipped (cluster + why)
- **No orchestrator or domain-file edits.** Cluster B is arguably an orchestrator
  output-contract concern (it synthesizes the final answer), but
  `shared_context.md` is not loaded for the orchestrator. If the next RESULT
  shows B unfixed while A and C improve, the honest conclusion is that the final
  wording is produced by the orchestrator and rule B should be duplicated into
  `orchestrator.md`. That is the most informative follow-up this iteration sets up.
- **No new-tool / capability-gap edit.** This phase has no tools layer, and none
  of the three clusters needs one — all three are answerable with the existing
  `fetch_github_file` result.
- **Escalation (framework, not task):** `trajectories/*.json` ship no trace, and
  delegation events are absent from `agent.jsonl`. Not knowing which sub-agent
  ran forced the conservative `shared_context.md` placement. Logging the chosen
  agent type would let a future iteration target the specific domain file.
  Recorded in `FRAMEWORK_IMPROVEMENTS.md`.

## Risk
Cluster A is the only loss present in all 10 trials, so fixing it alone should
move val from ~0.83 toward ~0.92; B and C are needed for 1.0. Main risk is an
off-by-one on the line number (the rubric accepts only 13 or ranges ending at
13) — mitigated by the numbered-block instruction. Secondary cost:
`shared_context.md` grows 237 → 326 lines in a prompt already carrying a large
DB schema reference; worth watching if a later iteration sees altitude problems.
