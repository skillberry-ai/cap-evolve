---
name: mechanism-probe
description: Force a proposal to name its mechanism before it is written. Use when you are at the ideation step of an optimization iteration — after diagnosing failure clusters, before editing any file. Counters the failure mode where the optimizer skips analysis and ships a plausible one-line knob tweak — restating a rule the agent already ignores, retuning a threshold, or rewording a docstring — instead of changing what the system can structurally do. Produces the three-field proposal declaration (mechanism, hypothesis, expected observable) that cap-evolve records per candidate.
component: reasoning
argument-hint: "[--process PROCESS.md]"
allowed-tools: Read, Bash
sources: [arbor]
---

# mechanism-probe — declare the mechanism before you edit

**The failure mode this counters.** An optimization iteration is expensive: one
proposal, one full-val evaluation, one accept/reject. The recurring waste is not a bad
idea — it is a *skipped step*. The optimizer reads a few traces, recognizes a familiar
shape, and ships the first plausible edit: another prose rule, a retuned number, a
reworded docstring. It scores net-zero, the gate rejects it, and the iteration is gone.
Prior runs in this repo lost iterations exactly this way (see any run's `LEDGER.md`).

The probe is one question asked *before* the edit exists, when it is still cheap to
throw away:

> **Could this whole proposal be replaced by changing one existing value or restating one
> existing rule? If yes, it is a knob. Find the mechanism instead.**

## Knob vs mechanism

A **knob** leaves the system's behaviour space unchanged. It adjusts a dial the agent
already has, or repeats an instruction it already had and already skipped:

- another prose rule for a rule the traces show the agent *knows* and *skips*
- a retuned threshold, temperature, retry count, or budget
- a reworded tool description or docstring, same semantics
- a longer preamble telling the agent to be more careful

A **mechanism** changes what is structurally possible or impossible:

- an in-body guard or validation in the tool the rule governs, raising an actionable
  error on exactly the violating condition — the rule can no longer be skipped
- a computation moved out of the agent's head and into code (a total, a date, a unit
  conversion it kept getting wrong)
- a new or composite tool that performs a whole action atomically, so a multi-step
  sequence the agent kept getting out of order becomes one call
- a **narrowed decision rule**: replacing "usually do X" with the discriminating
  condition the traces reveal, so the agent stops guessing
- removing a tool or option that the traces show is mis-selected

The test is not size. A one-line in-body guard is a mechanism; a fifty-line prompt
section restating known rules is a knob.

## The three-field declaration

Write these into `./PROCESS.md` under **Proposal declaration** before you edit. Each has
a job; the middle one is where knobs get caught.

| field | the question it answers | fails when |
| --- | --- | --- |
| `Mechanism:` | What now behaves differently, and why does that change the outcome? | the answer is "the prompt now says X" for an X it already said |
| `Hypothesis:` | Which failure cluster does this fix, and why does it generalize past the exact failing inputs? | it only explains the specific inputs you read |
| `Expected observable:` | What will be different in the NEXT iteration's trajectories if this is right? | you cannot name anything a reader could check |

The observable field is the honest one. If you cannot state what would look different —
which tool call now appears, which error no longer does, which computed value is now
right — you do not have a hypothesis, you have a hope, and there is nothing to learn
from the result either way.

## Worked example

Traces show four tasks failing because the agent answered a total from memory instead of
calling the pricing tool, each off by the tax line.

**Knob version** — prompt gains "ALWAYS call `get_total` before quoting a price." The
agent already had "call `get_total` to compute totals" and skipped it four times; a
louder restatement of a skipped rule changes nothing. Mechanism field would read "the
prompt now says it more forcefully", which is the tell.

**Mechanism version** — `quote_price` gains an in-body check: if the caller passes a
total that does not match `get_total`'s result for those line items, it raises
`"total mismatch: expected {computed}, got {given} — call get_total first"`. The
behaviour is no longer optional.

- `Mechanism:` `quote_price` now recomputes the total in-body and refuses a mismatched
  one with an actionable error, so answering from memory becomes impossible rather than
  discouraged.
- `Hypothesis:` the four tax-line failures share one root cause — the total is derived
  by the agent instead of by code. Any task whose total includes a line the agent must
  remember hits the same path, so the fix generalizes beyond these four.
- `Expected observable:` next iteration's trajectories show a `get_total` call preceding
  every `quote_price` on these tasks, and no "expected N got M" scoring feedback on the
  tax line.

Blast radius: the guard fires only on the mismatch condition, so passing tasks (which
already agreed with `get_total`) take an unchanged path.

## How this is judged — advisory, not enforcing

cap-evolve **records** your declaration as a `proposal_quality` event alongside the
candidate. It does **not** reject on it. A missing declaration does not reject your
edit, and a beautifully-worded one does not get it accepted — the val significance gate
remains the only thing that accepts or rejects a candidate.

That split is deliberate. "Is this a mechanism or a knob?" is a judgement no regex can
make: a heuristic strict enough to reject knobs would also reject real one-line
mechanism fixes, and a false rejection throws away a genuine improvement *invisibly* —
nobody sees the gain that never happened. So the bar lives here, in the prompt, where it
shapes the proposal, and the hard decision stays where it can be made honestly: on the
val split, against the noise bar.

Declare it anyway. The declaration is the cheapest part of the iteration and the part
that makes the expensive part legible: whether the candidate is accepted or rejected,
the next iteration reads what you predicted and whether it happened.

## Checking your own declaration

```bash
python skills/reasoning/mechanism-probe/scripts/run.py --process ./PROCESS.md
```

Prints which of the three fields are present and which are still empty or placeholders.
Presence is all it can check — it cannot tell a mechanism from a knob, which is exactly
why the gate is advisory.
