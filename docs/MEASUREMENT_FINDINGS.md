# Three invisible confounds when optimizing an LLM agent against τ²-bench

Working notes toward a paper. Everything below is measured in this repository, with the
rollout files still on disk. Where a hypothesis of mine was disproved, that is recorded too —
several of the findings exist only because a plausible story failed its check.

**Setup.** τ²-bench `airline`, official split (train 30 used as val, test 20 sealed). Agent and
user simulator are both `aws/gpt-oss-120b` at temperature 0 through a LiteLLM gateway. The
optimizer is a Claude Code agent editing the domain's `policy.md` and `tools.py`. Reward is
τ²'s own, gated on the components listed in each task's `reward_basis`.

---

## 1. The instrument is the ceiling — and the cause is trial count, not the provider

Re-running **byte-identical code on identical seeds at temperature 0** does not reproduce. The
interesting part is what the magnitude turns out to be.

**Step one: the excess.** At concurrency 25, mean per-task movement between two identical arms was
**0.250**. Dropping to concurrency 8 cut it to **0.100**, and arm-level movement from 0.1167 to
0.0333. Five of twelve tasks became perfectly repeatable. So there is a real, load-dependent excess,
and it is removable.

**Step two: the floor underneath.** With that excess removed, the remaining spread matches plain
binomial arithmetic. Each rollout is pass/fail, so an arm mean over `m` tasks at `n` trials has
`SE = sqrt(Σ 2p(1-p)/n) / m`. Measured on 10 tasks at n=10 with p≈0.35:

| | value |
|---|--:|
| observed difference between two identical arms | 0.0778 |
| predicted binomial SE | 0.0615 |
| ratio | **1.27** |

Observed per-task movement was 0.0978 against a binomial prediction of 0.1445 — *less* than chance
requires. **Nothing remains to explain.**

One precision that matters for honesty: at temperature 0 with identical seeds a fully deterministic
system would return *identical* arms, so this is not sampling error in the textbook sense. The
defensible claim is that the variation is indistinguishable **in magnitude** from independent
per-rollout coin flips. Its physical cause is still unidentified — MoE batching nondeterminism,
seed non-honoring, a seed race, and set-ordering were each tested and disproved. The value of the
binomial framing is negative: no further mechanism needs positing, and the remedy is the same
either way.

**Step three: what this invalidates.** Four consecutive paired gate runs of one candidate against a
byte-identical control:

| seed block | candidate | control | paired Δ |
|---|--:|--:|--:|
| 0–4 | 0.7333 | 0.6467 | +0.0867 |
| 100–104 | 0.6867 | 0.6667 | +0.0200 |
| 200–204 | 0.7133 | 0.7067 | +0.0067 |
| 300–304 | 0.7067 | 0.7067 | 0.0000 |
| combined | | | **+0.0283 ± 0.0199, t = 1.42** |

Monotone decay to zero. The first block alone was reported as a +0.087 win, then withdrawn when a
second byte-identical control moved +0.0800 on its own.

**Step four: and the obvious fix is also wrong.** "Noise is high, so narrow to the hard tasks" is
backwards for judging an artifact, because a task at 1.00 adds signal with no variance:

| arm | rollouts/arm | SE of paired difference |
|---|--:|--:|
| 12 hard tasks, n=10 | 120 | **0.0496** |
| full val 30 tasks, n=10 | 300 | **0.0262** |

Full val at n=10 is nearly twice as precise as the hard subset. The prior gate rounds ran full val
at n=5 (SE 0.0371), so their task set was never the problem.

The two questions need **opposite** designs, and conflating them is the actual error: judge a
*mechanism* only on the tasks where it fires, at high `n`, with a per-task test — a mechanism firing
on two tasks is diluted to nothing in a thirty-task mean; judge an *artifact* on full val with both
arms in one batch.

**Claim.** Concurrency and trial count both belong in the experimental record of any agent-benchmark
result, next to temperature and seed, and a reported improvement should carry the SE its design can
actually achieve. Neither is currently reported by anyone, including τ²-bench itself. The
control variable for load is **total in-flight requests**, not any per-process concurrency flag —
so a fan-out of K evaluating optimizers is, by construction, the high-noise regime.

## 2. Verified per-task gains do not compose

Ten optimizer branches each independently verified a gain on its own task. Merged per-function with
all branches retained cleanly, the combined artifact measured **−0.0617** against seed-matched arms —
and the task whose own verified fix was in the merge fell 0.40 → 0.20.

A later round reproduced this with a properly powered per-mechanism measurement on one side of it,
which removes the obvious objection that the per-task "verifications" were never real:

| mechanism | measured alone, n=40 | in the 6-mechanism merge, full val (2 blocks) |
|---|--:|--:|
| preview tool, task 10 | +0.516 (z +4.68) | **+0.80 / +0.40** — survives |
| argrepair, task 20 | +0.220 (z +2.35) | **−0.14 / −0.40** — inverts |

Both were resolvable at |z| ≥ 2 in isolation. One survived integration and one inverted. The merged
artifact's own gate: pooled **−0.0146 ± 0.0181**, blocks disagreeing in sign, with **two** replicated
per-task gains against **seven** replicated losses — four of the damaged tasks being high scorers
that no mechanism targeted and no canary protected.

So the phenomenon is not "the per-task gains were fake." It is that a per-task gain is measured
holding everything else fixed, and an artifact changes everything at once. The fix is sequential
accumulation with a measurement after each step, canaries drawn from the *whole* suite rather than
from the tasks the mechanisms aim at, and any step below the measured noise floor recorded as
provisional rather than as a gain.

**A caveat this round is well placed to state**, having been caught by it: at n=10 per task, six of
the moving tasks flipped sign between the two blocks. A single block's per-task table will supply a
mechanism story on demand — an apparent −0.50 interference on one task read +0.20 in the second
block. Per-task attribution needs n≈40; per-task tables at n=10 are for generating hypotheses, never
for concluding.

## 3. The simulated user ends episodes it intends to continue

Across 600 rollouts, user messages containing leaked `<reasoning>` skew **32 failures : 7
passes**. In **21–22** episodes the simulator emitted `###STOP###` in the same message as
reasoning that explicitly planned to continue:

> `<reasoning>` … After third agent message, we need to ask about other upcoming flights and
> total cost. So we must wait for agent's third message. **Continue.** `</reasoning>###STOP###`

The agent is scored zero on a turn it was never given. Task 7 scores **0.00 in 40/40 rollouts**
and 15 of its 27 observed failures carry a reasoning leak.

**A hypothesis I had and disproved.** τ²'s `is_stop()` is a bare substring test on message
content, so leaked reasoning discussing the stop token would end the episode spuriously — an
attractive, fixable harness bug. Measured: **only 1 of 26 cases has the token inside the
reasoning block**; 25 are after `</reasoning>`. So it is the simulator model genuinely stopping,
not a parsing defect, and it must not be patched away.

**Consequence.** ~25/600 = 4.2% of rollouts are lost this way, capping the achievable score at
about **0.958**. Any claim near or above that is measuring something other than agent skill.

---

## 4. Supporting facts that reshape where effort goes

- **Reward is strictly binary.** 430 passes, 170 failures, **zero partial** across 600 rollouts.
  A task's "rate" is a pass probability, so per-task evidence needs binomial thinking, and
  n = 5 cannot separate 0.4 from 0.6.
- **95% of failures are wrong database writes** (162/170); 65% name a wrong argument value, 42% a
  required write never made. Communication misses are 24%. Effort spent on phrasing is
  mostly misdirected.
- **Failing episodes run longer** (median 24 messages vs 16) while only 1 of 170 failures hit the
  step cap. The agent does not run out of steps — the user stops. **Turns are a scarce currency**,
  which is why a tool that repairs a recoverable argument slip can beat one that refuses it.
- **Tool guards are net positive**: rollouts with a guard refusal pass at 0.767 vs 0.702 without.
  But a refusal that names no valid alternative can push the agent into an unauthorized
  workaround — observed: a chronology guard rejected an itinerary and the agent silently moved
  the *user's requested date* to satisfy it. Prefer "refuse **and** name a valid option".
- **Tool descriptions are silently truncated on delivery.** 42% of docstring text never reached
  the model (94% for one tool); a `Returns:` section is stripped entirely. Nested object
  parameters typed `List[FlightInfo | dict]` serialize to an `anyOf` whose second branch is
  `{"additionalProperties": true}` — any object validates — while the prose names no keys.
  (`$defs` *are* delivered and *do* contain the right names: I checked, expecting a dangling
  `$ref`, and was wrong.)

---

## 4b. A taxonomy of silent tool-surface defects

The most useful thing this round produced is not a score but a class of bug: **defects in the
tool surface that cost reward without producing any error**. Each was found by diffing a passing
rollout against a failing one of the same task and isolating a single differing field; each is
verifiable deterministically, without spending a single rollout on statistics.

| defect | measured incidence | how it costs reward |
|---|---|---|
| a tool omits its own input from its output | **942 / 942** flight objects returned by `search_direct_flight` carried `date: null` | the agent must remember which date each result set was for, across turns and several searches; on a two-date round trip it writes the wrong one |
| an argument's meaning is ambiguous and undocumented | **8 / 76** round-trip bookings set `destination == origin`; **8 in failures, 0 in passes** | `destination` means the turnaround city, not the airport you return to; the description says only "the IATA code for the destination city such as 'JFK'" |
| a normalizer covers some aliases but not all | `method_id` used 6 times, not in the alias list | the call is rejected outright, costing a scarce turn |
| a normalizer normalizes the key but not the value | `amount` omitted → `None` → `ValidationError` | same: a wasted turn on a recoverable slip |
| a nested object schema is delivered but not described | `List[FlightInfo \| dict]` serializes to an `anyOf` whose second branch is `{"additionalProperties": true}`; **691 / 693** flight objects carried extra keys | mostly harmless — extras are ignored — which is itself the lesson |
| docstring text is silently truncated on delivery | 42% of characters dropped; `Returns:` stripped entirely | guidance the author believes is delivered never arrives |

Two things make this a result rather than a bug list.

**First, incidence does not predict impact.** The extra-keys defect fires on 99.7% of flight
objects and is very likely worth nothing, because the extra keys are silently ignored. The
`destination` defect fires on 10% of round-trip bookings and discriminates outcome perfectly in
the observed data. A frequency count without a model of the *consequence* predicts nothing — and
frequency is what an optimizer naturally measures.

**Second, these are invisible to every signal the loop normally uses.** No exception is raised;
the conversation reads as a success; the simulated user *confirms* the wrong action. On one task the
agent tabulated three reservations, asked "shall I cancel these three?", received "yes, please", and
cancelled the wrong subset. The simulated user cannot check the choice either. **Only the database
check catches it**, and it reports a mismatch, not a cause.

A correction belongs here, because I got this one wrong first, and the way I got it wrong is itself
the finding. I initially recorded that task as a *fabricated read* — the agent inventing routes and
dates it had never fetched. It was not. `get_user_details` returns two top-level keys: `user`, whose
`.reservations` field is a bare id list, and `reservations`, a list of full summary cards carrying
route, cabin, passenger count and every dated segment. I inspected the first, saw only ids, and
concluded the data could not have been read. Checked against the cards, the agent's table is
**exact**. The real defect is choosing the wrong subset from correctly-read data — a judgement error
with no tool-level fix, on the task holding the single largest block of headroom.

The lesson generalises past this incident. When the grader says only "final state does not match",
a *plausible mechanism* is far cheaper to construct than to verify, and a partial read of the trace
will supply one on demand. Every mechanism in this taxonomy survived because it had a deterministic
replay behind it; the one that did not survive was the one I had only argued for.

That suggests a concrete claim: for agents whose actions are graded on end state, the highest-yield
audit is not of the model's reasoning but of the *fidelity of its tool surface* — whether every
tool's output is self-describing, whether every argument's meaning is unambiguous, and whether the
text the author wrote is the text the model receives. All three are checkable offline, with no
rollouts, and all three were violated here in code that four prior optimization runs had already
been over.

## 5. What this says about optimizing agents

The order of operations that follows from the above, and which contradicts how all four prior
runs here were conducted:

1. **Calibrate the instrument before trusting any verdict.** Two byte-identical arms, same seeds,
   at the load you intend to gate at. That number is the bar. Cheap, and it invalidates most
   small accepts.
2. **Explore fast, gate slow.** Exploration can run hot because its product should be a
   *mechanism verified from a trace* — the guard fired, the next action changed — not a rate.
3. **Integrate sequentially.** One branch at a time, measured, canaries in the objective.
4. **Know your ceiling.** Quantify the harness's own losses first, or you will spend the budget
   chasing points that are not on the table.

The honest headline for this run: val ≈ **0.717**, no candidate yet demonstrated above the
noise floor, ceiling ≈ **0.958**, and the reason the previous four rounds found nothing is now
measured rather than guessed.
