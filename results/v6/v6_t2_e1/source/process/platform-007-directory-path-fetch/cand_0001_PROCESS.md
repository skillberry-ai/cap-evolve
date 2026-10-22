# PROCESS — what I did this iteration (explainability; REQUIRED)

## Headline

The trajectory JSONs carry no transcripts (`trace: null`, `tool_calls: []`), so I
could not read what the agent did. Instead I **reconstructed the failure from the
reward arithmetic** by running the task's own verifier against candidate call
sequences, and found an exact match for both observed reward levels. The failure
is entirely in the `tool_calls` component; `answer` and `completion` are already
1.0 on every one of the 10 trials.

## How I localized the failure without a transcript

`tests/expected.json` + `tests/verify.py` give `weights = {tool_calls: 0.3,
answer: 0.7}` and 2 expected calls, so `tool_calls` can only be 0.0 / 0.5 / 1.0:

| tool_calls | reward | observed in trials |
| --- | --- | --- |
| 1.0 | 1.000 | **never** (0/10) |
| 0.5 | 0.850 | 5/10 |
| 0.0 | 0.700 | 5/10 |

Mean = 0.775 = the reported val reward. I then confirmed each level by executing
the real verifier (`verify.compute_reward`) on reconstructed call lists:

- `[search, fetch(leaf)]` → **1.000** ← what the fix must produce
- `[fetch(leaf)]` only → **0.850** — the agent guessed the conventional leaf path
  and skipped the search leg, so 1 of 2 expected calls matched.
- `[fetch(dir), fetch(dir), fetch(leaf)]` → **0.700** — the agent tried to *walk
  down* the directory tree. `expected.json` lists exactly those three directory
  paths as `forbidden`, and any forbidden hit **zeroes** the whole component.

So the two failure modes are the two halves of one mechanism: **the agent treats
`fetch_github_file` as a directory browser, and treats path discovery as
optional.** The task instruction even warns "That is a directory, not a file" —
the agent still mishandled it, which says the prompt, not the request, is at fault.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | `fetch_github_file` used as a directory browser; path-discovery leg skipped | platform-007-directory-path-fetch (all 10 trials) | Prompts actively teach the wrong model: they describe the tool as fetching "files **and directories**", document a `{entries: [...]}` directory-listing response that the API never returns, and give a worked example that fetches `"setup-automation/"` to "list the directory". Nothing states the search→fetch order. | KNOWLEDGE (false affordance) | prose rule + delete the false affordances |
| 2 | No routing rule covers "read a file from a source repo" with no failed job | same task | `orchestrator.md` routes GitHub work only via *job failure* / *catalog item* framings, and has no GitHub tools itself. A plain "find and read this role's task file" matches no rule. | BEHAVIORAL (routing) | discriminating routing condition |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE / contract | `shared_context.md` | New **"GitHub Path Discovery — `search_github_repo` Before `fetch_github_file`"** section: states the 2-step order, forbids passing a directory, gives a *file-vs-directory* test (last segment has an extension / ends in `/`), and a RIGHT/WRONG worked example with placeholder nouns only. | Yes — adds a step, never removes one. Verified below. |
| 1 | KNOWLEDGE | `aap2_agent.md`, `babylon_agent.md` | Deleted the two false affordances: tool blurb "files **and directories**" → "ONE file … a directory path returns an error"; response-shape line `{entries: [{name,type}]}` for dirs → `{error}` for dirs, plus the real `search_github_repo` shape incl. `total_matches`/`truncated`. Also listed `search_github_repo` in babylon's tool list (it *has* the tool but never mentioned it) and renumbered. | Yes — corrects docs to match the actual API contract. |
| 1 | BEHAVIORAL | `aap2_agent.md` | The "Fetch the setup automation files" example no longer fetches `"setup-automation/"`; it searches instead. | Yes — the directory fetch it taught returns an error. |
| 1 | BEHAVIORAL | `aap2_agent.md` | "Budget your rounds" now says the budget is **not** a reason to skip path discovery — economize on redundant *fetches*, never on the locating search. | Yes — removes a read that justified skipping the search (the 0.850 mode). |
| 1 (guard) | BEHAVIORAL | `shared_context.md` | Added: `owner`/`repo`/`ref` are **carried, never guessed — on the search call too**, because a wrong-owner search returns zero matches that read like "file does not exist". | **This protects passing tasks** — see regression note. |
| 2 | BEHAVIORAL / routing | `orchestrator.md` | New "Reading source-repo files when there is no failed job" rule. Discriminates by **which repo is being read** (monitoring-* → icinga; catalog items → babylon; code/role/playbook in a deployer repo → aap2), not by the word "GitHub". Also states the orchestrator has no GitHub tools, so it must never answer file contents from memory. | Yes — adds a case that previously matched no rule; does not alter existing rules. |

## Verify-the-fix

Ran the task's real verifier over reconstructed sequences (not plausibility — actual scoring):

- **Target behavior now scores 1.000.** `[search_github_repo(owner,repo,search=<role name>), fetch_github_file(path=<leaf from matches>)]` → `reward 1.000, tool_calls 1.00`.
- **Both observed failures reproduce exactly** (0.850 and 0.700), which is what makes me confident the diagnosis is the real mechanism and not a plausible story.
- **Would the edit have changed behavior at the exact point of failure?** Yes, at both points. The 0.700 mode fetches `ansible/roles_ocp_workloads` first — the new rule names that exact move as forbidden *and* supplies the file-vs-directory test that classifies it (no extension in the last segment). The 0.850 mode guesses the leaf path and skips the search — the rule's "Do the search step even when you can guess the path" clause addresses precisely that, and the budget clause removes the competing incentive.
- **Regression sweep: zero regressions.** For all **61** tasks in the v6 suite whose golden tool_calls touch `fetch_github_file`/`search_github_repo`, I scored the golden sequence and then the same sequence with a *correct* extra `search_github_repo` prepended (what my rule adds). All 61 stayed at 1.00. Four tasks (001, 002, 005, 006) do forbid a `search_github_repo` — but only with the **wrong** `owner`/`ref`, never the right one. That is the specific risk my rule's extra search volume creates, which is why I added the carry-never-guess `owner`/`repo`/`ref` guard rather than leaving it implicit.

## Process & features used

- **Serial, not fanned out.** The run brief suggests fanning out one subagent per trajectory group, but there is exactly **one** task with one failure mechanism and the trajectories contain no transcripts. Parallel diagnosis subagents would have had the same empty inputs. The leverage was in executing the verifier, which is cheap and serial. I used background grep for one slow repo-wide search.
- **Prior iterations read:** none exist — `LEDGER.md`, `RUNMAP.md`, `rejected.jsonl` and `history.jsonl` are all empty (iteration 1/5, baseline only). Nothing to build on or avoid re-proposing yet.
- Cross-referenced `task.toml` (`services = ["github"]`) against the live parsec source (`tool_definitions.py: get_aap2_tools/get_babylon_tools/get_icinga_tools`) to confirm which agents actually hold `search_github_repo` — all three do, which is why the core rule went in `shared_context.md` rather than one domain file. Also read the `parsec-github` simulation SKILL.md, which **confirms at the contract level** that a directory path returns the in-band `{error}` shape and that `search_github_repo` is the only path-discovery operation.

## Good things to PRESERVE

- The two-step search→fetch order, and the explicit statement that a directory path returns an **error, not a listing**. The old `{entries: [...]}` text was a documented return value that the API never produces — do not let it come back.
- The `owner`/`repo`/`ref` carry-never-guess guard. It is what keeps the added search volume from walking into the wrong-owner traps in tasks 001/002/005/006.
- The "budget is not a reason to skip path discovery" clause — without it, the round-budget rule argues for the 0.850 failure mode.

## Deliberately skipped

- **`answer` and `completion` components** — already 1.0 on all 10 trials. No headroom; touching the answer contract would be risk with no upside.
- **Hardcoding anything task-specific.** No rule I added names the repo, the role, the directory, or the counts 40/15. The worked example uses `<owner>`, `<repo>`, `<some/dir>`, `<name>` placeholders. Restated generally: *"when a request quotes a container directory and an item inside it, search for the item name and fetch the leaf path the search returns."*

## Escalation (no code lever available this phase)

Not needed for this task — the fix is genuinely a prose fix. Worth recording for the
framework, though: `fetch_github_file`'s own **tool description** (in
`tool_definitions.py`, outside this phase's edit space) already says "If you don't
know the exact path, use search_github_repo first — do NOT list directories one by
one", yet still advertises itself as fetching "a file **or directory listing**".
That self-contradiction sits in the tool layer where no prompt edit can reach it. If
a later phase opens the tools capability, the honest fix is to make a directory path
a hard validation error there.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` alongside this file.
