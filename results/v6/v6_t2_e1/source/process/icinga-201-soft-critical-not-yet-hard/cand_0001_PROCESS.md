# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I got a real diagnosis

`./trajectories/*.json` carry only reward summaries (`trace: null`, `tool_calls: []`),
so they cannot tell you *why* a trial lost points. The actual evidence is under each
trial's `metadata.trial_dir`:

- `…/verifier/reward-detail.json` — the per-rubric breakdown (`required_missed`,
  `forbidden_hit`, `counts_missed`), including the rubric's own `rationale` strings
- `…/agent/agent.jsonl` — the full tool calls and the final answer text

I swept all 28 available reward-detail files for this task and joined them to the
answer text, grepping each forbidden literal to see the exact sentence that tripped it.
That turns "answer=0.833" into a named rubric item and a quoted phrase.

## The measured failure distribution (28 trials)

| outcome | n | cause |
|---|---|---|
| reward 1.0 | 17 | — |
| 0.883 | 6 | `forbidden_hit: claims-hard-or-paged` |
| 0.883 | 3 | `required_missed: not-notified` |
| 0.767 | 1 | both of the above |
| 0.533 | 1 | tool unavailable → infra noise, not a prompt bug |

`tool_calls` scored 1.0 in every single trial. Tool selection is already correct;
**100% of the recoverable loss is in the answer's wording.** Two mechanisms:

### Cluster A — `claims-hard-or-paged` (6/28, the single largest cause)
The rubric forbids `"hard critical"`, `"confirmed critical"`, `"is hard"`,
`"already notified/paged"`, `"15 minutes"`. Every hit was the *same syntactic
accident*: the agent correctly understood the state was SOFT, then wrote the
prospective state as the glued bigram **"HARD CRITICAL"**:

- seed-2: "Only on transition to **HARD CRITICAL** does Icinga send the first notification"
- seed-4: "Icinga transitions to **HARD CRITICAL** and fires the notification itself"
- seed-6: "It will transition to a **HARD CRITICAL** state"

These are *semantically right* — note the future tense — but the literal string
asserts a confirmed problem to anyone skimming, which is exactly the operational
hazard the rubric is guarding. The rubric's `attributed_to` list confirms it: it only
fires the penalty when the surrounding text *also* shows correct understanding, i.e.
it is scoring the phrasing, not the reasoning.

### Cluster B — `not-notified` (4/28)
The agent described SOFT state, attempt counts, and time-to-HARD accurately, but
never wrote the plain sentence "no notification has been sent." It left the reader to
infer the notification consequence from `state_type | SOFT` in a table. seed-7 and
seed-8 are the clearest: thorough, correct reports that never answer the question the
user actually asked ("has it sent out a notification already?"). seed-150001 also
dumped ~20 lines of epoch-conversion scratch work *above* the answer.

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | A: asserts confirmed/notified state while SOFT | icinga-201-soft-critical-not-yet-hard (6/28 trials) | Prompt teaches the SOFT/HARD *distinction* but gives no guidance on how to *word* a prospective HARD transition; agent reaches for the glued severity bigram | KNOWLEDGE (output discipline) | domain-file rule + worked contrast example |
| 2 | B: omits the direct answer to the question asked | same task (4/28 trials) | Output contract is a fixed report skeleton with no "answer the question first" slot; notification consequence is never an explicit required element | KNOWLEDGE (output contract) | new output-contract section + explicit rule |
| 3 | (infra) tool timeout | same task (1/28) | `query_icinga` unavailable | — | skipped, see below |

## Changes made this iteration
All edits are in `icinga_agent.md` — the single domain file this task reads. Nothing
went into `shared_context.md`: the SOFT/HARD state machine is Icinga-specific, and
putting it in the shared prefix would push it onto five unrelated domain agents.

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A + B | KNOWLEDGE | `icinga_agent.md` — new `### SOFT vs HARD` section after the State Model | Field-semantics table (`state` vs `state_type` vs `last_hard_state`, `retry_interval` vs `check_interval`) + 4 numbered rules for the SOFT-and-non-OK case: (1) state the notification consequence in plain words, (2) remaining = max − attempt and they must all fail consecutively, (3) use `retry_interval` not `check_interval` for the estimate, (4) don't use wording that asserts confirmation already happened. Closes with the inverted HARD case. | Yes — every rule is gated on `state_type` SOFT + non-OK `state`; HARD-state answers are explicitly told to invert |
| A | BEHAVIORAL | same, rule 4 | Prohibition stated *structurally* ("the word HARD glued onto the severity word, in either order"; "any 'already'-form of notified/paged/alerted") plus a Wrong/Right contrast pair, and a prescribed safe alternative ("a HARD state" / "`state_type` = HARD", severity kept in its own clause) | Yes — a pure phrasing constraint; does not change which facts are reported |
| A | BEHAVIORAL | same — `Step 1: Triage` | Rewrote the line that itself conflated the axes. It previously read "Hard failure (service down) vs. Soft failure (threshold breach)" — a genuinely **wrong** gloss: SOFT/HARD is retry-confirmation, not severity. Replaced with two separate bullets (severity axis, confirmation axis) stating that CRITICAL can be SOFT and WARNING can be HARD. | Yes — corrects a factual error; strictly more accurate for any alert |
| B | CONTRACT | same — new `### Answer the question that was asked, first` in Output Format | Requires a short direct-answer paragraph before the report skeleton, with three worked question→answer-shape mappings (notification status → yes/no sentence, not a table row; escalate? → recommendation; how long? → number with arithmetic), a rule to answer every part of a multi-part question, and a ban on scratch work above the answer | Yes — additive; the existing skeleton is unchanged and now explicitly framed as supporting evidence |

## Verify-the-fix
Checked each edit against the exact sentence that lost the point, not just for plausibility:

- **seed-2 / 4 / 6 (cluster A)** — each hit is the bigram "HARD CRITICAL" in a
  future-tense clause. Rule 4 names that exact construction structurally and supplies
  the replacement the Right example models. The three cited sentences all rewrite
  cleanly under it without losing any content.
- **seed-7 / 8 (cluster B)** — both reports contain `state_type | SOFT` in a table and
  nothing else about notification. Rule 1 and the new output-contract section both
  require the plain sentence, and the contract explicitly says a table row is not an
  answer — which is precisely what those two transcripts did.
- **Rubric-string check (scripted).** The phrasings my edits prescribe
  (`"no notification has been sent"`, `"the on-call has not been paged yet"`) each
  match an entry in the rubric's `not-notified` `any_of` list, and my Right example
  contains zero forbidden literals. So following the rule satisfies A and B together.
- **Self-contamination check (scripted, and this caught a real bug).** My first draft
  spelled the banned literals out inside the prohibition itself — priming the reader to
  echo the very strings being banned. I rewrote the prohibition structurally and
  re-grepped: the file now contains **none** of the 8 forbidden literals. Also grepped
  for task-specific nouns (hostname, service name, the counts 2/5/188/200, the "15
  minutes" rate): none present.
- **seed-150001** — the epoch scratch work above the answer is now explicitly banned by
  the contract's last line.

## Why the mechanism generalizes
Nothing added is conditioned on this scenario. The triggers are field-value patterns
(`state_type` = 0 with non-OK `state`) and question shapes ("has anyone been paged",
"should I escalate", "how long until"), all of which recur across Icinga triage. The
`retry_interval` vs `check_interval` rule in particular fixes a latent trap no trial
happened to hit but the rubric explicitly guards (`"15 minutes"` = this task's
`check_interval` of 300 s misapplied): it is an unexploded version of the same bug.
Restating the rules without any task-specific noun is possible — they are written that
way.

## Process & features used
- Serial, not fanned out. The instructions suggest one subagent per trajectory-group,
  but this task is a single task and the sweep showed exactly **two** wording
  mechanisms in **one** file. Parallel edit-subagents in separate worktrees would all
  have been editing the same ~60 lines of `icinga_agent.md` and then needed conflict
  resolution — more process than signal. I used scripted analysis over all 28
  reward-detail files instead, which is what actually produced the diagnosis.
- Prior iterations: none. `RUNMAP.md` and `LEDGER.md` are empty (iteration 1/5),
  `rejected.jsonl` and `history.jsonl` do not exist yet. Nothing to build on or avoid.

## Good things to PRESERVE
- `tool_calls` scored **1.0 in all 28 trials**. The tool-selection guidance in
  `icinga_agent.md` (exact action names, `detailed=true` on follow-ups, the
  downtimes/comments follow-ups) is already optimal for this task — do not churn it.
- Keep the SOFT/HARD rules in `icinga_agent.md`, not `shared_context.md`. They are
  domain-specific; the shared prefix is read by five agents that do not need them.
- Keep rule 4's prohibition **structural**. Spelling the banned strings out primes the
  reader to emit them.

## Deliberately skipped
- **seed-120003 (reward 0.533), `query_icinga` timed out after 240 s.** Infra noise, not
  a prompt bug. Worth noting the agent's degraded answer was actually well-judged — it
  said what it couldn't determine and named the fields it would need. No edit.
- **`shared_context.md` and `orchestrator.md`.** Routing was correct in all 28 trials
  (the Icinga agent was always reached and always called the right tools), so neither
  file is implicated.

## Escalation (no new tools possible this phase — recording as a finding)
The `not-notified` and `claims-hard-or-paged` rubric items are both pure
*string-level* output constraints on a fact the agent already has in hand. Prose can
raise the hit rate but cannot guarantee it — the baseline already reasoned correctly in
every cluster-A trial and still lost the point on phrasing alone. A durable fix is a
code-level post-check: when a returned service object has `state_type == 0` and
`state != 0`, assert the answer contains an explicit no-notification statement and
none of the confirmed-state bigrams. That needs the tools/code layer, which this phase
excludes.

---

# DIAGNOSIS.json
See `DIAGNOSIS.json` alongside this file.
