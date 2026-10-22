# PROCESS — iteration 3 (cand_0003), parent cand_0002 (val 0.895)

## Starting position

cand_0002 scores 0.895 on val: **4 of 5 trials at reward 1.0, one at 0.475**
(`completion=1.0, tool_calls=1.0, answer=0.25`). The remaining loss is one trial.
Per iteration 1's INSIGHTS, I went straight to the cheap triage — *did the trial emit a
report at all?* — rather than looking for a reasoning defect.

It did not. The failing trial (seed-2) ends on the harness's `max_rounds` stub
(`agents.py:1109`), so it delivered **no report**. Same mechanism as iteration 1.

## The decisive new measurement

Iterations 1 and 2 both correctly identified "ran out of rounds before reporting" and both
added rules against it. Those rules **exist in the champion prompt and the failing trial
broke every one of them**:

| call | what it did | which existing rule it violated |
|---|---|---|
| 9 | `search_github_repo` for a registry hostname | Rule 4 (two-dead-calls) |
| 10 | `search_github_repo` for a credential variable name | Rule 4 |
| 11 | `fetch_github_file` on a directory | Rule 4 |
| 12 | `lookup_catalog_item` on the 2nd affected item | Rule 4's forbidden list, **verbatim** |
| 13 | `lookup_catalog_item` on the 3rd affected item | Rule 4's forbidden list, **verbatim** |

Every scored fact was already in context at call 8. Rule 6 ("a source that tells you the
data is unavailable has answered you") also applied — the config fetched at call 8 literally
says the value *"cannot be inspected from here"*.

So the lever for this iteration could NOT be "add another stop rule" — that is what the last
two iterations did, and the rules did not bind. I asked instead: *why* don't they bind?

### Root cause 1 (NEW, and the real prize): a tool-contract fact nothing states

`search_github_repo` matches **file paths only**. From `tools/github_files.py:313`:

```python
matches = [entry["path"] for entry in tree if search_lower in entry["path"].lower()]
```

It substring-matches the git tree's *paths*. It never opens a file. **Nothing in
`aap2_agent.md` says this.**

Measured across every trial of every iteration of this task:

> **18 `search_github_repo` calls. 18 returned `total_matches: 0`. 0 ever returned a match.**

And every one searched for a *content* string — a variable name, a registry hostname, an
include-path fragment read out of a fetched file. The agent is using a filename finder as a
grep, so it is **guaranteed** to get zero, then reads that zero as "not here, try elsewhere"
and keeps hunting. This is what *generates* the dead calls that the stop rules then have to
catch. Iterations 1–2 were treating the symptom; this is the source.

### Root cause 2: the stop rules are framed as recognition tasks

Rules 4/5/6 all ask the agent to introspect over conversation state — "was the previous
result dead?", "am I certain enough yet?". That is the fragile kind of judgement for this
reader. A rule keyed to **possession of named facts** is checkable in one glance at context;
a rule keyed to **counting recent failures** is not.

### Also verified: the real round budget is ~10, not 20

`AGENTS["aap2"].max_rounds = 20`, but `config.yaml` / `config.local.yaml` set
`anthropic.max_tool_rounds: 10`. Observed: the 9 reporting trials finish at 9–11 calls; the
two cutoff trials die at 11 and 13. Also confirms cand_0002's "you get NO warning" claim is
right **in effect** — `_maybe_inject_budget_warning` fires at `remaining==2` computed off
20, i.e. round 17, never reached. Grep: 0 occurrences of "rounds remaining" in any trial.
I did **not** revert that cand_0002 text; I made it quantitative instead.

## Ranked issues and the edit for each

| rank | issue | class | edit |
|---|---|---|---|
| 1 | `search_github_repo` used as a content grep; 18/18 zero results, misread as "look elsewhere" | **KNOWLEDGE (tool contract)** | New Critical Rule 4: path-only, with an explicit never-search list + worked example |
| 2 | Stop rules keyed to recognising failure, which didn't bind | **BEHAVIORAL (reframe)** | Rule 6 rewritten as a 5-box *possession* checklist run before every call past the 5th |
| 3 | Sibling-item lookups (2 of the 5 wasted calls) felt like diligence | **BEHAVIORAL (emphasis)** | Explicit paragraph in Rule 5 on why one item's config + others' job rows already suffices |
| 4 | Directory fetches not in the forbidden list | **BEHAVIORAL** | Added bullet to Rule 5 |
| 5 | Budget stated vaguely ("a limited number") | **KNOWLEDGE** | Rule 6 states ~10, and that 3 job logs + 1 config already spends 5–6 |

All edits are in **`aap2_agent.md`** — the single domain file this task reads
(`services=["platform","github"]`; `orchestrator.md` routed to the aap2 agent correctly in
11/11 trials). Nothing went into `shared_context.md`: the path-only fact is specific to a
tool only some agents hold, and the checklist is failure-investigation-shaped.
I also added the path-only contract to the "Available Tools" line and the "Tool Response
Formats" section, so it is present where the agent looks up tool behaviour, not only in the
rules preamble.

## Verify-the-fix (replay against the exact failure point)

Facts held after call 8 of seed-2: failing task + error text (calls 1–4), affected count = 3
(call 2 returned `total: 3`), shared secret name and its include path (call 8), registry
answered-and-rejected (call 1 log). **All five checklist boxes ticked at call 8.**

- **call 9** — blocked by new Rule 4 (hostname = content string), *and* new Rule 6's
  checklist is already complete → write the report. **Outcome changes here**, 5 calls before
  the cutoff.
- **call 10** — new Rule 4 again; this is the worked example almost verbatim.
- **call 11** — new Rule 5 bullet (directory fetch).
- **calls 12, 13** — Rule 5's forbidden list plus the new emphasis paragraph.

Every wasted call is now blocked by a rule keyed to something checkable in one glance, and
the earliest block fires with all required facts in hand. Replayed as `answer` 0.25 → 1.0.

### Why this cannot regress the 4 passing trials — the strongest evidence here

`search_github_repo` returned a match **0 times in 18 calls across every trial**. So
forbidding content-searches **cannot remove a fact from any report**: there is no fact in any
passing report that came from that tool. The passing trials all end with 2–3 consecutive
zero-match searches *immediately before* writing their report — the new rules delete exactly
those calls and leave the report untouched, which also buys back 2–3 rounds of headroom.

The checklist can only make a trial write its report *sooner* than it already did, and only
once all five facts (which are the rubric's required items) are in hand.

Honest limit: this is trace replay, not execution — I cannot re-run the sims from here (they
need the five seeded MCP services). I verified the agent would have both the data and the
instruction to report at the point it instead got cut off.

## Non-overfitting check

My first draft of the worked example used this task's literal credential name and registry
hostname. I replaced them with `<SECRET_VAR>` / `<some-credential-name>` /
`<some.registry.host>` placeholders. Grepped the added lines for every task-specific literal
(credential name, hostname, catalog item names, account prefix, job IDs, the count 3):
**zero hits.** Restating the rules without task-specific nouns: *"a path-matching search tool
cannot find file contents"* and *"stop when you hold the facts your report requires, not when
you notice you are failing."* Both are task-independent.

## Process & features used

**No subagents or worktrees — serial by choice**, same call as iteration 1 and for the same
reason, now with evidence behind it: there is one task, one failing trial, and one root
cause. The brief encourages fan-out "one subagent per trajectory-group", but there is only
one trajectory group and fanning out would have spent budget rediscovering a single fact.
META_INSIGHTS already recorded this; this iteration confirms it.

What actually produced the win was **reading the tool's source** rather than the transcript.
Two iterations read the transcript and saw "the agent keeps searching and failing", and both
inferred a discipline problem. One `grep` of `github_files.py` showed the searches were
*incapable* of succeeding — a knowledge gap, not a discipline gap. Then the 18/18
aggregation across trials turned that from a plausible story into a measurement.

## Escalation (unchanged from iteration 1, still real, now with a second item)

1. `lookup_catalog_item` returns a `files` list whose entries are not individually fetchable
   at the returned ref — the guessed-sibling 404 that starts the dead-end hunt. Tool-layer
   fix: return only fetchable paths, or mark which are.
2. **NEW:** `search_github_repo`'s own description tells the model *"If it returns zero
   matches, the item does NOT exist"* (`tool_definitions.py:828`). For a content query that
   statement is **false and actively misleading** — zero means the tool never looked. The
   durable fix is in the tool description (say "paths only"), or give the agent a real
   content-grep. I can only counteract it from the prompt side, which is what Rule 4 does.
3. `_maybe_inject_budget_warning` computes `remaining` from `AGENTS[...].max_rounds` (20)
   while the live loop is bounded by `anthropic.max_tool_rounds` (10), so **the budget
   warning is dead code on this path** and never fires. Fixing that one line would likely
   solve this task's flakiness outright, with no prompt change at all.

## What to preserve

- cand_0002's "no warning before cutoff" framing — verified correct in effect; keep.
- Rule 5's bounded one-call exception — iteration 1 proved the unbounded stop rule is
  harmful (loses the credential name on trials that hit dead calls before the config fetch).
- Rule 7's "unavailable data is an answer" and Step 7's shared-cause / auth-vs-outage content:
  these cover rubric items directly.

## What I skipped

- Re-tightening the dead-call threshold (iteration 1's suggested fallback). The failing trial
  violated the existing threshold rule five times; making the same rule stricter would not
  have bound either. Reframing to possession-based was the structurally different move.
- Any `orchestrator.md` or `shared_context.md` edit — routing is correct in 11/11 trials.
