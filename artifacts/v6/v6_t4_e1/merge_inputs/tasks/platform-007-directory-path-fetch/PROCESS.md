# PROCESS — what I did this iteration (explainability; REQUIRED)

## Headline

The trajectory JSONs carry no transcripts (`trace: null`, `tool_calls: []`), so I
could not read what the agent did. Instead I **reconstructed the failure from the
is entirely in the `tool_calls` component; `answer` and `completion` are already

## How I localized the failure without a transcript


| --- | --- | --- |


  and skipped the search leg, so 1 of 2 expected calls matched.
  down* the directory tree. `expected.json` lists exactly those three directory
  paths as `forbidden`, and any forbidden hit **zeroes** the whole component.

So the two failure modes are the two halves of one mechanism: **the agent treats
`fetch_github_file` as a directory browser, and treats path discovery as
optional.** The task instruction even warns "That is a directory, not a file" —
the agent still mishandled it, which says the prompt, not the request, is at fault.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 2 | No routing rule covers "read a file from a source repo" with no failed job | same task | `orchestrator.md` routes GitHub work only via *job failure* / *catalog item* framings, and has no GitHub tools itself. A plain "find and read this role's task file" matches no rule. | BEHAVIORAL (routing) | discriminating routing condition |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE / contract | `shared_context.md` | New **"GitHub Path Discovery — `search_github_repo` Before `fetch_github_file`"** section: states the 2-step order, forbids passing a directory, gives a *file-vs-directory* test (last segment has an extension / ends in `/`), and a RIGHT/WRONG worked example with placeholder nouns only. | Yes — adds a step, never removes one. Verified below. |
| 1 | KNOWLEDGE | `aap2_agent.md`, `babylon_agent.md` | Deleted the two false affordances: tool blurb "files **and directories**" → "ONE file … a directory path returns an error"; response-shape line `{entries: [{name,type}]}` for dirs → `{error}` for dirs, plus the real `search_github_repo` shape incl. `total_matches`/`truncated`. Also listed `search_github_repo` in babylon's tool list (it *has* the tool but never mentioned it) and renumbered. | Yes — corrects docs to match the actual API contract. |
| 1 | BEHAVIORAL | `aap2_agent.md` | The "Fetch the setup automation files" example no longer fetches `"setup-automation/"`; it searches instead. | Yes — the directory fetch it taught returns an error. |
| 1 (guard) | BEHAVIORAL | `shared_context.md` | Added: `owner`/`repo`/`ref` are **carried, never guessed — on the search call too**, because a wrong-owner search returns zero matches that read like "file does not exist". | **This protects passing tasks** — see regression note. |
| 2 | BEHAVIORAL / routing | `orchestrator.md` | New "Reading source-repo files when there is no failed job" rule. Discriminates by **which repo is being read** (monitoring-* → icinga; catalog items → babylon; code/role/playbook in a deployer repo → aap2), not by the word "GitHub". Also states the orchestrator has no GitHub tools, so it must never answer file contents from memory. | Yes — adds a case that previously matched no rule; does not alter existing rules. |

## Verify-the-fix

Ran the task's real verifier over reconstructed sequences (not plausibility — actual scoring):


## Process & features used

- **Serial, not fanned out.** The run brief suggests fanning out one subagent per trajectory group, but there is exactly **one** task with one failure mechanism and the trajectories contain no transcripts. Parallel diagnosis subagents would have had the same empty inputs. The leverage was in executing the verifier, which is cheap and serial. I used background grep for one slow repo-wide search.
- Cross-referenced `task.toml` (`services = ["github"]`) against the live parsec source (`tool_definitions.py: get_aap2_tools/get_babylon_tools/get_icinga_tools`) to confirm which agents actually hold `search_github_repo` — all three do, which is why the core rule went in `shared_context.md` rather than one domain file. Also read the `parsec-github` simulation SKILL.md, which **confirms at the contract level** that a directory path returns the in-band `{error}` shape and that `search_github_repo` is the only path-discovery operation.

## Good things to PRESERVE


## Deliberately skipped


## Escalation (no code lever available this phase)

Not needed for this task — the fix is genuinely a prose fix. Worth recording for the
framework, though: `fetch_github_file`'s own **tool description** (in
`tool_definitions.py`, outside this phase's edit space) already says "If you don't
know the exact path, use search_github_repo first — do NOT list directories one by
one", yet still advertises itself as fetching "a file **or directory listing**".
That self-contradiction sits in the tool layer where no prompt edit can reach it. If
a later phase opens the tools capability, the honest fix is to make a directory path

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` alongside this file.
