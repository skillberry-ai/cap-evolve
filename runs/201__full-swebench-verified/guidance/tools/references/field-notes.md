# Field notes — observations from real optimization runs

Evidence gathered while optimizing tool surfaces on specific harnesses and runners.
These are **observations, not rules**: the numbers belong to the runs that produced
them, and the harness details (Python docstrings, one framework's schema builder) are
that framework's, not this capability's. Read them for the *mechanism*, then verify the
equivalent on your own runtime.

Read before your first candidate on a new harness, and whenever an edit "verified"
green without an explanation you can point at.

## Contents
- [1. Not all of a tool's documentation reaches the model](#1-not-all-of-a-tools-documentation-reaches-the-model)
- [2. Enriching a return is a hypothesis, not a free win](#2-enriching-a-return-is-a-hypothesis-not-a-free-win)
- [3. A docstring header can break tool REGISTRATION](#3-a-docstring-header-can-break-tool-registration)
- [4. Changing a return SHAPE can corrupt the learning signal](#4-changing-a-return-shape-can-corrupt-the-learning-signal)

## 1. Not all of a tool's documentation reaches the model

A docstring is not the wire schema. One benchmark harness built each tool's schema
`description` from the docstring **summary plus the prose before `Args:`**, and dropped
the `Returns:` section entirely. Measured across a 14-tool toolset there: **5469 of
12929 docstring characters (42%) never reached the model**, and on the one tool whose
return had been documented most carefully it was **1791 of 1906 — 94% dropped**.
Rounds of behavioural guidance had been written into that void, and one edit credited
as "verified" turned out to work only because the return **VALUE** changed shape
(which the model does see at call time), not because anything documented it.

So on that harness there were three delivered surfaces — the summary and pre-`Args:`
prose, the per-parameter `Args:` descriptions, and the returned value itself — and one
that looked identical and did nothing. **Render the live toolset the way the runtime
builds it and count the delivered characters per candidate** rather than trusting the
file. Your runtime will have its own cut line; find it before you write into it.

## 2. Enriching a return is a hypothesis, not a free win

A tool return is re-read on every later turn, so adding to it is not free — measure it.
Measured on a multi-turn tool-use benchmark with a mid-tier runner: one round accepted
an edit that CONSTRAINED behaviour (in-code preconditions, val 0.5889 → 0.6778,
+8.9pp) while **four separate edits that ADDED information all landed at or below the
same parent**: richer docs + derived facts merged onto the winner **0.6444**, composite
tools **0.6556**, argument derivation **0.6666** (identical to that round's null
control), and a structural policy rewrite **0.5777** (also identical to the control).

Multi-turn rollouts have a step budget and the whole conversation is re-read each turn,
so verbose returns crowd out the signal they were meant to supply. Keep what the agent
ACTS on — amounts, eligibility, the corrective hint — and cut what it can read off the
object it already has. When in doubt, run the subtraction as its own gated candidate;
it is as legitimate a hypothesis as the addition, and here the additive ones lost.

## 3. A docstring header can break tool REGISTRATION

Observed: adding a worked example under an `Example:` / `Examples:` header made
`docstring_parser` return a `DocstringExample` object; that harness's `Tool` model
required `examples: list[str]`, so building the environment raised and **all 90
rollouts of that candidate died as `INFRASTRUCTURE_ERROR`** — an entire evaluation
spent on a parse error, not on the edit. Keep the example text, but put it under
ordinary prose (e.g. "A correct call looks like:").

**An import check is NOT a registration check** — the file imported fine; it was
registration that failed. Prove the toolset still builds the way the runtime builds it
before you spend rollouts. If the adapter exposes a render/validate helper, call that
and keep it in the loop. Otherwise construct it directly, substituting your own
runner's construction call for the last line, which is harness-specific:

```bash
python -c "import sys; sys.path.insert(0,'<project>/adapters'); from adapter import Adapter; \
from pathlib import Path; Adapter().apply(Path('<candidate_dir>')); \
tools = <your harness's get_tools() call>; \
print(len(tools), sorted(t.name for t in tools))"
```

The same render is what lets you count delivered characters (§1).

## 4. Changing a return SHAPE can corrupt the learning signal

This one is a caveat about the *measurement*, not about tool surfaces — keep it in mind
when a defect appears without a cause.

Optimizer-side code that parses tool returns to build feedback is written against the
PRISTINE shape, and a candidate is entitled to change it. Observed: a candidate that
nested summary objects under a list key the feedback code read as bare ids made that
code `str()` the dicts, so its feedback claimed the id was *"not among"* the held ids —
for calls whose id was perfectly valid. The reward was never affected (it came from the
harness's own DB/action checks, which never read a tool's return), but one optimizer
spent a whole iteration hunting a scoring bug that did not exist, and another concluded
the key name was capping its score.

Two lessons, in order: **audit the measurement before you believe a defect**, and make
return-parsing tolerant of shapes a candidate may legitimately introduce (extract ids
from `str` *or* `dict` entries) rather than forbidding the enrichment. The signal
degrades exactly when the candidate is most interesting.
