# PROCESS — cand_0002 (explainability; REQUIRED)

## Headline

The champion (cand_0001, val 0.922) has **exactly one scored loss left**, and it is
present in **5/5** trials: the answer rubric's forbidden check `override-applies`
fires on the heading `## 3. Required change to get 60 GiB`. Everything else is
already perfect — `required_missed=[]`, `citations_missed=[]`,
`unmatched_expected=[]`, `forbidden_violations=[]` in every trial. So this
iteration is a single-target edit, plus one latent-defect fix found while verifying.

Fixing this one phrase takes answer 0.889 → 1.0 and reward 0.922 → 1.0. There is no
other scored loss to chase.

## How I diagnosed (reusable)

`trajectories/*.json` in this working dir carry **no trace** (`"trace": null`,
`reward: None`) — iteration 1 recorded this and it still holds. The real evidence is
reachable via `rollout.metadata.trial_dir`:

```
<trial_dir>/<ts>/bench-*/verifier/reward-detail.json  # EXACTLY which rubric items missed
<trial_dir>/<ts>/bench-*/agent/agent.jsonl            # full transcript
_run/tasks/bench-v6-platform-153-.../tests/expected.json   # the rubric itself
```

Reward = `0.3·tool_calls + 0.7·answer`; answer = 6 required facts + 1 citation + 2
forbidden checks.

## What I did, in order

### 1. Re-measured the champion instead of inheriting iteration 1's cluster list

I aggregated per-item verdicts across all 5 champion trials. The cluster picture
**changed completely** from the seed:

| cluster (iter-1 naming) | seed | champion |
| --- | --- | --- |
| A — `line` item missed | 10/10 | **0/5 — FIXED** |
| B — `override-applies` forbidden hit | 6/10 | **5/5 — now the ONLY loss** |
| C — pinned fetch without `ref` | 3/10 | **0/5 — FIXED** |

Had I trusted iteration 1's ranking (A biggest, C flaky), I would have spent the
iteration re-fixing two solved clusters. B also got *worse in frequency* (6/10 →
5/5), which is the decisive signal that cand_0001's rule 2 did not work — not that
it needs to move to a different file.

### 2. Found the exact trigger, byte-for-byte

Grepped all 20 forbidden substrings against each trial's `agent.jsonl`. One hit per
trial, identical in all 5: `## 3. Required change to get 60 GiB`, matching the
forbidden substring `get 60 GiB`.

### 3. Diagnosed *why* cand_0001's rule 2 failed — the key insight

This is not a placement problem. cand_0001's rule 2 told the agent to title the
remediation section by its *action* and offered "Required change" as a model. **The
agent did exactly that** — it wrote "Required change" — then appended a purpose
clause, `to get 60 GiB`.

The rule failed because it was written as a *semantic* prohibition: it banned the
requested value as an "accomplished outcome". An infinitive of purpose ("to get X")
genuinely is not an outcome claim — the agent complied with the rule as written and
still tripped the verifier, which matches the literal substring regardless of
grammar. The rule and the grader disagreed about what counts as a violation.

Confirming the mechanism: the rubric's own `new-name`/`fix` items are annotated
`asked_by: "Exactly what to put in the catalog item to get 60 GiB"`, and the task
instruction's item 3 is phrased the same way. The agent is echoing the *question's*
wording into its heading — a natural move, and exactly what this check punishes.

**Fix: restate the rule as a mechanical, lexical constraint** — "does the requested
value appear anywhere on this heading/summary line? if yes, rewrite it" — and name
the purpose-infinitive form as explicitly forbidden, with a good/forbidden heading
list. This removes the judgement call that let a compliant agent still fail, and
suits the stated reader tier (strong, not frontier): an explicit lexical test beats
a semantic principle from which it must infer a grader's behavior.

### 4. Found and fixed a latent off-by-one (currently passing by luck)

While verifying the `line` item I counted the real file from the task's seed data.
The deciding assignment is on **line 13**. The champion's answer says:

- "The deciding line is **line 12**" ← wrong
- then a numbered block whose last row reads `13 | ...db_storage_size: 10Gi`
- then "is set to `10Gi` on **line 14**" and an anchor `...main.yml:14` ← wrong

Three different numbers for one assignment, two of them wrong. The item passes
**only** because the rubric happens to accept the literal `13 |` from inside the
block. A rubric accepting only `line 13` would score this zero.

Root cause is visible in the parent prompt: cand_0001's worked example ended
`12 | <variable>: <value>` — and the agent emitted "line 12", copying the example's
offset rather than counting the file. I de-numbered the example to relative
placeholders (`<n-2>/<n-1>/<n>`) so there is no concrete number to copy, and added a
self-consistency requirement.

I am **not** claiming a scored gain here; it is currently passing. I am removing a
fragility that would become a loss on any reseed or rubric variant.

## Edits

Both in `shared_context.md` — verified to be the right file (see Placement). No
other file touched.

| id | section | cluster | lever | class |
| --- | --- | --- | --- | --- |
| F1 | `## Reporting a Setting That Is Not In Effect`, rule 2 | B (5/5, the only scored loss) | CONTRACT | overconfident wording |
| F2 | `### Citing a Specific Line in a Fetched File` | latent (passing by luck) | CONTRACT | missing knowledge |

**F1** — rule 2 rewritten from semantic to lexical: bans the requested value anywhere
in a heading/summary line **including as a goal**; names the purpose-infinitive forms
("…to get X", "How to get X", "Getting X") as forbidden; supplies a mechanical
per-line test; gives a Good/Forbidden heading list; confines the requested value to
the concrete change (code block / assignment line); adds a pre-send re-read of own
headings.

**F2** — example block de-numbered to `<n-2>/<n-1>/<n>`; explicit "never carry a line
number over from an example, a similar file, or a previous answer"; new "state one
number, and state it consistently" requirement covering prose + block + `path:N`
anchor; clarified that descriptive comment lines are counted but never cited as
deciding.

## Verify the fix (against the exact failing point)

**F1.** The failure point is the literal `## 3. Required change to get 60 GiB`. Under
the new rule the agent applies one test to that line: *does the requested value
appear on it?* It does. The rule then requires a rewrite, and lists this precise
shape — action title + "to get <value>" — under **Forbidden**, with "Required change"
alone as the Good form. The agent already chose "Required change" as its stem in all
5 trials, so only the trailing clause must go: the minimal change from observed
behavior. Required facts `new-name` and `fix` are satisfied from the code block,
which the rule explicitly preserves as the one place the value belongs — so removing
the heading clause cannot drop a required item.

**F2.** At the point the agent wrote "line 12" it was reproducing the parent
example's `12 |` offset; that number no longer exists in the prompt. At the points it
wrote "line 14" and `:14`, the new consistency check requires reconciling against the
block it had already rendered (`13 |`), which is correct.

Both rules fire for *any* task with the same mechanism (a configured value not in
effect; a file-backed "which line" question) and name no value from this task.
Restated without task-specific nouns: *when reporting that a requested value is not
the effective one, keep the requested value out of headings and summary lines,
including as a stated goal* / *when citing a line, state one number and keep every
mention of it consistent*.

## Placement — verified, not assumed

cand_0001 left this open and pre-registered "if B stays flat, move rule B to
`orchestrator.md`". **I checked, and that contingency does not apply:**

- `orchestrator.md:154-164` instructs the orchestrator **not** to re-summarize or
  re-synthesize a sub-agent's findings — the sub-agent's text is what the user sees.
- The answer carries the exact numbered-excerpt shape cand_0001 added *only* to
  `shared_context.md`, and clusters A and C — both fixed by `shared_context.md`-only
  edits — went to 0/5. `shared_context.md` is demonstrably reaching the author.

So B is not flat-because-unread; it is flat because the wording let a compliant agent
emit the forbidden substring. Moving it to `orchestrator.md` would have been wrong.
`shared_context.md` is also correct on merit: both rules concern reporting
file-backed config findings, domain-general here (the github tools appear in three
domain files and delegation is still not logged).

## What to preserve

- Everything cand_0001 added for clusters A and C — both at 0/5, must not be
  disturbed. F2 edits A's section but only de-numbers the example and *adds* a
  consistency requirement; the numeric-citation requirement, the counting procedure,
  and the cite-the-assignment-not-the-comment clause are intact.
- The `ref`-on-pinned-fetch rule (C): `unmatched_expected=[]` and
  `forbidden_violations=[]` in 5/5. Untouched.
- Rule 1 of the not-in-effect section (tense discipline). Untouched.

## What I skipped, and why

- **Duplicating rule B into `orchestrator.md`** — disproved above; would add a rule
  to a file that does not produce the failing text.
- **Re-fixing clusters A and C** — both 0/5; the measurement says neither is needed.
- **Parallel subagents / worktrees** — INSTRUCTIONS.md encourages fanning out; I did
  not. One task, one trajectory group, and after aggregation exactly **one** scored
  loss with a single known trigger string. Fanning out would have produced
  speculative edits to already-passing behavior, which on a hill-climb gate is
  downside-only. I spent the effort on measurement instead. Deliberate, not an
  oversight.
- **Any new-tool / capability-gap escalation** — none needed, and none to report:
  every graded fact is answerable from the two `fetch_github_file` results the agent
  already makes correctly, and the remaining loss is purely wording.

## Self-check performed

Scanned the final `shared_context.md` against all 28 forbidden substrings from both
forbidden checks and against task literals (`netbox`, `agnosticd`, `agnosticv`,
`v2.12.0`, `10Gi`, `60Gi`, `60 GiB`, `rhpds`, `db_storage`, `ipam`, `line 13/12/14`):
**no forbidden substring present**; the only literal hits (`agnosticd`, `agnosticv`,
`rhpds`) are pre-existing domain vocabulary, unchanged in count (4 before, 4 after)
and not introduced by my edits. Diffed against `candidates/cand_0001/` rather than
`git diff` (the `work/` tree is gitignored, so `git diff` silently returns empty);
confirmed the other 7 files are byte-identical.

## Risk

Low. One file, two sections, both reached only by this answer shape. F1 is strictly
more restrictive on a line the agent currently gets wrong 5/5 times, and cannot
affect answers about settings that *are* in effect (the section is scoped to the
not-in-effect case). F2 removes a copyable number and adds a consistency check.

Honest residual risk on F1: the agent must still state the requested value in the
code block for required items `new-name`/`fix`. The rule says so explicitly ("belongs
in exactly one place: inside the concrete change"), but a reader that over-applies
"keep the value out" could strip it everywhere and lose two required items. I judged
this acceptable because the scope is stated twice (headings / bold lead-ins / summary
sentences only) and the code-block carve-out is affirmative rather than merely
permitted. **This is the thing to check in the RESULT:** if `new-name` or `fix`
appears in `required_missed`, F1 over-fired and the carve-out needs strengthening
rather than the ban loosening.
