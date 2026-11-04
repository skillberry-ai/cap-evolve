# PROCESS — cand_0003


## Headline

sentence is a **near-verbatim echo of a negative example written inside the prompt's own
rule**. The fix is not a new rule; it is removing the forbidden strings the prompt itself
plants, and replacing a soft style preference with a hard, mechanically-grounded ban.



| --- | --- | --- | --- | --- | --- |

and cand_0002's edits are fully saturated and were preserved untouched. Exactly one item,

**I built an oracle before editing anything.** Importing the task's real `verify.py` and

## 2. The exact failing string, and the mechanism

t2's offending sentence:

> "…the automation was still running when the controller terminated it; **it did not fail
> because of a bad playbook, a cloud API error, or a configuration issue.**"

isolated why by probing the real matcher:

```
"It was not an API error."                                             violated=False
"It was not a bad playbook or an API error."                           violated=False
"It was not a bad playbook, a bad credential, or an API error."        violated=True
"it did not fail because of a bad playbook, a cloud API error, …"      violated=True
```

**`_negated_in_clause` only reaches `_NEGATION_WINDOW = 6` polarity tokens, and a comma is a
clause break.** So a *single* denial is safe and an *enumeration* is not: by the third item
the negator no longer covers the noun, and the occurrence reads as asserted. Prior iterations
knew "don't coin a failure mode to deny it" but **not** that list length is the
discriminator — which is why the existing prose rule did not prevent this.

Deleting exactly that one clause, changing nothing else:

```
```

## 3. The root cause: the prompt was planting its own forbidden strings

The decisive finding. I swept **every line** of the parent's two files through the real
`_forbidden_violated` for this task's own contract. The parent plants the forbidden form on
**9 lines** — 6 in `shared_context.md`, 3 in `aap2_agent.md`:

```
shared_context.md:290  'credential, or a cloud API error" introduces three failure modes…'
shared_context.md:298  '…rather than naming "a failed task", "a fatal'
shared_context.md:299  'error" or "an API error" so you can put a "not" in front of it.'
shared_context.md:301  'task events" and "zero API errors" name the mode just as surely…'
shared_context.md:308  '…without welding a verb to a noun ("task failed",'
shared_context.md:309  '"failed task") that reads as an assertion when quoted out of context.'
aap2_agent.md:82       '…one row per failed task, carrying'
aap2_agent.md:382      '3. **TASK […]** — Identify which role/task failed'
aap2_agent.md:507      '- **Failed Task:** `{role} : {task_name}`'
```

Line 290's example — *"it wasn't a code bug, a bad credential, or a cloud API error"* — is a
**three-item ruled-out list in exactly the illicit form**, and t2's failing sentence is that
example with the nouns swapped. The rule taught the behaviour it was trying to forbid: a
prohibition illustrated by a verbatim specimen of the banned output hands the reader a
mandated report template *orders* the agent to emit a line containing "Failed Task" on every
AAP2 investigation.

**My candidate plants it on 0 lines (down from 9).**

## 4. Edits (4 in `aap2_agent.md`, 3 in `shared_context.md`)

Class per the INSTRUCTIONS taxonomy.

| # | File | Edit | Class |
| --- | --- | --- | --- |
| E1 | `shared_context.md` | Rewrote "Name the cause you found" — **hard ban on lists of ruled-out causes**, with the negation-decay reason stated; removed every forbidden specimen from the rule's own examples; "delete the ruled-out **clause**, not the sentence". | overconfident → narrowed |
| E2 | `shared_context.md` | **Carve-out**: a cause the *user* or a given document named must still be answered, as a single denial, never as a list item. | guard on E1 |
| E3 | `shared_context.md` | Zero-count rule: **put the noun immediately after the word of absence**; never a bare "None." | missing knowledge |
| E4 | `aap2_agent.md` | Report template: `Failed Task:` → `Erroring task:`, and the task/host/error triple made **conditional** on a tool having reported an error; replaced by `Ending condition:` + `Last step reached:`. | right domain, wrong action |
| E5 | `aap2_agent.md` | Step 7 "you MUST trace deeper" gets an **exception** for externally-ended runs: the metadata *is* the root cause, stop digging, name no task/host/role. | overconfident → narrowed |
| E6 | `aap2_agent.md` | `get_job_events` description: "one row per **erroring** task"; empty result is an absence, not a zero count. | missing knowledge |
| E7 | `aap2_agent.md` | Log-parsing step 3: "which role/task **failed**" → "the role/task that **reported the error**". | de-planting |

`orchestrator.md` and the other five domain files are untouched — the task routes to AAP2.

## 5. Verify the fix

**(a) Would it have changed behaviour at the exact point of failure?** Yes. t2's sentence is
the banned construction, and the rule it obeyed previously *modelled* that construction.
E1 removes the model and bans the form explicitly; E4/E5/E6/E7 remove the remaining sources
of the same strings.

prescribe:

```
```

the rules already in the file, not only against the trace.

**(c) Suite-wide safety (two parallel read-only subagents over all 200 contracts):**

- **0** tasks require the literal "failed task"/"task failed"; **0** require "fatal" or
  "api error". **3** tasks *forbid* them. So de-planting costs nothing and helps three tasks.
- Stripping contrastive tails from all 200 golden answers: **77 answers change, 0 lose
  **clause**, not sentence. That measurement shaped the wording.
  instruction *asks* whether a suspected cause explains it → **E2 is the carve-out for that**,
  added because of the sweep.
  `"no <noun> were recorded"` ✓, `"zero <noun>"` ✓, but `"no **matching** <noun>"` ✗ and bare
  `"None."` ✗ → **E3**. Without E3, Rule 2 would have cost `cloud-306` a point.
- E4 changes no golden answer (none uses the template lines); `platform-008` needs the last
  task named when the log reaches one → **the `Last step reached:` line covers it.**

**(d) Non-overfitting.** No GUID, hostname, job id, template name, count, or service name
appears in any edit. Every rule restates without a task-specific noun: *a negated enumeration
asserts its tail items; a count of zero is an absence; a report label for a thing that did not
happen must be conditional; when a run is ended externally its metadata is the root cause.*

## 6. What to preserve

rule, the headroom subtraction, and the read-only contract. All four are saturated.

## 7. What I skipped, and the escalation

  inside the 900 s cap. E5 should incidentally shorten it. I declined to perturb passing
- **Escalation (no prose fix exists):** `_negated_in_clause`'s 6-token window makes the
  verifier's forbidden check **sensitive to list length rather than to polarity** — a
  agent can be steered around it, but the contract is measuring sentence shape, not
  truthfulness. Related: `"rather than X"` and `"instead of X"` **always** trip, because
  `_CLAUSE_BREAK_RE` treats `rather`/`instead` as clause breaks and cuts the phrase before
  `_NEGATING_PHRASE_RE` can excuse it. Both are verifier defects, not agent defects.

## 8. Process / features used

a full-file plant sweep that found the self-inflicted cause, plus **2 parallel read-only
subagents** over all 200 contracts for blast radius. Three of my seven edits (E2, E3, and the
`Last step reached:` line in E4) exist **only** because the sweeps measured a cost I had not
predicted — the fan-out changed the edit, it did not merely bless it.
