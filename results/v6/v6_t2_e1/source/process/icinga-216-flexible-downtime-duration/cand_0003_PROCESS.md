# PROCESS — cand_0003

## Headline

Two facts reframe this iteration, and both came from reading the artifacts rather than the reward number:

1. **The accepted champion `cand_0002` is byte-identical to `seed`.** I diffed all 8 files:
   no differences. The ACCEPT at Δ=+0.012 was the gate's `SE=0 → STRICT fallback, n=1`
   path firing on an empty edit. So the real baseline this candidate must beat is the
   **seed prompt**, and the +0.012 in the LEDGER is measurement noise, not a prior gain.
2. **The lost reward has a single, exactly-identified cause, and it is NOT what
   `cand_0001` targeted.** In all 5 champion trials the only missed rubric item is
   `window-start` (`"22:00"`). `window-end` ("06:00") is *hit* in 5/5 — the earlier
   iteration's claim that both endpoints were missed does not hold for these trials.

## The mechanism (verified, not inferred)

Ground truth: `start_time` 1795298400 = 2026-11-21 **22:00** UTC, `end_time` 1795327200 =
2026-11-22 **06:00** UTC. The window **crosses midnight** (`end mod 86400` = 21600 <
`start mod 86400` = 79200).

In 5/5 champion trials the agent answered "window 06:00 → 14:00 UTC on 2026-11-22".
Decomposing that:

- `06:00` is the true time-of-day of **`end_time`**, re-labelled as the *start*.
- `14:00` = 06:00 + 8 h, i.e. the end was **derived by adding the span**, not converted.
- It scores `window-end` by accident: the rubric matches the bare substring `"06:00"`
  anywhere, and the agent prints 06:00 — as the wrong endpoint. Only `window-start`
  (`"22:00"`) is missed, which is exactly the 0.833 answer / 0.883 reward seen.

So the error is **not** faulty mod/div arithmetic. It is: convert *one* endpoint, then
place the other by adding the interval, and slide both onto a single date because an
overnight window "looks wrong". I verified with Python that this reproduces the observed
answer exactly.

**Why `cand_0001` could not have worked, and measurably didn't.** Its central guard was a
span cross-check, `(end-start)/3600 == converted end − converted start`. The agent's wrong
answer has a span of exactly 8 h, and the true span is exactly 8 h. The check is
**silent** on the only failure present. Confirming this: cand_0001's 5 trials produced
`missed: ['window-start']` and near-identical prose — its large `shared_context.md` block
changed the output essentially not at all. That is a refutation of the *diagnosis*, not
just of the wording, so this iteration deliberately does not re-word that procedure.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Derived-endpoint epoch conversion | icinga-216-flexible-downtime-duration | One timestamp converted, the other obtained by adding the interval; an overnight window (`end mod 86400 < start mod 86400`) then normalised onto one date. Span stays self-consistent, so a span check cannot see it. | KNOWLEDGE / BEHAVIORAL | domain-file procedure + a day-count check that actually fires |
| 2 | Downtime field semantics undocumented | icinga-216-flexible-downtime-duration | `icinga_agent.md` documents state codes but never downtime `attrs`; `fixed`/`duration` are ungrounded. Latent — `flexible`, the 5 h count and the author are correct in 5/5 — so this is a regression guard. | KNOWLEDGE | field table + fixed-vs-flexible rule |
| 3 | No epoch→UTC tool (escalation) | icinga-216-flexible-downtime-duration | Structural; no prose fix. | CAPABILITY-GAP | escalated, not patched |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE + BEHAVIORAL | `icinga_agent.md` → new "Converting Downtime Epochs to UTC Wall-Clock" | Bans deriving one endpoint from another ("convert every timestamp independently, straight from its own epoch"); states that `end mod 86400 < start mod 86400` is a **legitimate overnight window** to report as-is, not to normalise; adds the day-count check (count distinct `epoch div 86400`; if two endpoints have different `day` but you wrote one date, the conversion is wrong); says explicitly that a matching span is **not** evidence of correctness. Generalizes to any epoch pair where the interval is recoverable but the absolute placement is not. | Yes — purely additive; no existing rule altered or loosened. |
| 2 | KNOWLEDGE | `icinga_agent.md` → new "Downtime Objects: Field Semantics" | `attrs` table; fixed ⇒ mute = window length, flexible ⇒ mute = `duration/3600`; select-the-right-row rule (a host-filtered call returns unrelated rows — true here, there is a second fixed host downtime); keeps window span and mute length attached to separate nouns. | Yes — the file previously had **no** downtime documentation, so nothing to conflict with. |
| 1 | KNOWLEDGE | `shared_context.md` → 1 bullet in "Tool Result Handling" | The domain-general half only: convert each epoch from its own value, never by adding the interval. 9 lines, placed in an existing list. | Yes — additive bullet. |

Deliberate sizing choice: cand_0001 put a ~75-line block in `shared_context.md` and it
moved the behaviour not at all. This candidate puts the detailed procedure in
`icinga_agent.md` — the most specific file this task actually reads — and leaves only the
genuinely cross-domain sentence in `shared_context.md`.

## Verify-the-fix (against the exact point each trace went wrong)

- **Day-count check, on the observed wrong answer.** Reconstructing the agent's claim:
  `2026-11-22 06:00` → epoch 1795327200, but the field it labelled `start_time` is
  1795298400 → mismatch; `2026-11-22 14:00` → 1795356000 vs `end_time` 1795327200 →
  mismatch. Distinct `div 86400` values across the two true epochs = 2 (20778, 20779),
  while the agent's answer uses **one** date. The check **fires**. On the true answer
  (22:00 Nov-21 → 06:00 Nov-22) both reconstructions match and the day count is 2 against
  two dates: the check **passes**, so it raises no false alarm. Both verified in Python.
- **Contrast with cand_0001's span check** on the same inputs: agent span 8 h, true span
  8 h → silent. This is the concrete reason the lever changed rather than the wording.
- **Derive-by-adding ban** hits the exact step that produced `14:00` (= 06:00 + 8 h).
- **Overnight-window sentence** hits the exact reason 22:00 → 06:00 was rejected by the
  agent as mis-ordered and normalised forward.
- **Worked example** verified with assertions against `datetime.fromtimestamp(..., UTC)`:
  epochs 1773176400 → 21:00 and 1773203400 → 04:30 next day, `day` 20522/20523, and the
  stated "now" 2026-03-10 09:00 does have `day` 20522. It crosses midnight on purpose, so
  it demonstrates the failure shape — on an unrelated invented date, no task literals.
- **Non-overfitting check, run mechanically:** grepped both edited files for every task
  literal (all three epochs, 18000, host, service, author, change number, downtime GUID,
  and the graded strings `22:00` / `06:00`) → **0 hits** for each.
- **Rubric-trap check, run mechanically:** tested all 14 `forbidden.none_of` substrings
  from `tests/expected.json` case-insensitively against both edited files → **no hits**.
  (The matcher is a bare substring test, so prose that *denies* the window-as-duration
  reading can score against itself; the text keeps the span and the mute figure on
  separate nouns and never negates one into the other.)

## Process & features used

- **Serial, not fanned out** — despite the brief suggesting subagent fan-out. One task,
  one tool call per trial, 5 short transcripts, each with a machine-readable
  `reward-detail.json` naming the missed item. Fan-out would have added summarization
  loss over text I could read in full, with no coverage to gain. Recorded honestly rather
  than using parallelism for its own sake.
- **Read the real transcripts, not the trajectory stubs.** `./trajectories/*.json` have
  `trace: null` and `tool_calls: []`; the actual agent output is at
  `metadata.trial_dir` → `*/agent/agent.jsonl`, and the graded verdict at
  `*/verifier/reward-detail.json`.
- **Diffed `candidates/cand_0002` against `candidates/seed`** — this is what exposed the
  empty champion, and it is the step I would most recommend to the next iteration.
- **Read the rejected candidate's trials** (`trajectories/rejected/`, cand_0001's 5
  transcripts) and confirmed its edit left the answers unchanged.
- **Prior iterations read:** `prior_iterations/cand_0001/{PROCESS.md,diff.patch}` (the
  patch contains only `DIAGNOSIS.json`, so I recovered the real prompt edit by diffing
  `candidates/cand_0001` against `candidates/seed`), `prior_iterations/cand_0002/PROCESS.md`
  (an unfilled template), plus `LEDGER.md`, `JOURNAL.md`, `INSIGHTS.md`,
  `META_INSIGHTS.md`, `RUNMAP.md`, `rejected.jsonl`, `history.jsonl`.
- **Read the task bundle**: `task.toml` (`services=["icinga"]` → footprint is
  `orchestrator.md` + `shared_context.md` + `icinga_agent.md`), `instruction.md`,
  `tests/expected.json`, `provenance.md`, `seeds/icinga.json`.

## Good things to PRESERVE

- The corrected diagnosis: the failure is **derived-endpoint placement on a
  midnight-crossing window**, not mod/div arithmetic. `window-end` passes in 5/5 and does
  so *coincidentally*, because the agent prints 06:00 as the wrong endpoint — do not read
  it as a working conversion.
- **A span cross-check cannot detect this failure** (both spans are 8 h). Refuted by
  measurement; never re-propose it.
- The day-count check (`distinct epoch div 86400`) and the reconstruct-and-compare idea
  both fire on the wrong answer and stay silent on the right one.
- The forbidden-fact matcher is a bare case-insensitive substring test with no polarity
  guard. Always re-run the substring check before shipping prose about the mute duration.
- `cand_0002 == seed`. Any future Δ should be measured against the seed.

## Deliberately skipped

- **`orchestrator.md` routing** — `tool_calls=1.0` in 5/5 and the call is exactly the
  expected one. No defect; editing it is unscored blast radius.
- **Re-wording cand_0001's `shared_context.md` conversion block** — its 5 trials show it
  changed nothing. The diagnosis was wrong, so re-wording it is the trap the JOURNAL
  warns about.
- **Flakiness / variance work** — the task is mislabelled flaky: 5/5 trials scored
  *exactly* 0.883333 and missed *exactly* the same item. The outcome is deterministic.
- **The 5 other domain files** (aap2, babylon, cost, ocpv, security) — outside this task's
  prompt footprint.

## Escalation (real capability gap; cannot be fixed in this phase)

No tool converts an epoch to a UTC timestamp, and there is no code layer in this phase, so
the agent is structurally forced into mental date arithmetic. Every tool call in every
trial is correct; only the conversion fails. A deterministic epoch → ISO-8601 helper, or
`query_icinga` returning a derived `start_time_utc` / `end_time_utc` alongside each epoch,
would make this entire failure class impossible instead of merely discouraged. That is the
actual fix; this candidate is the best available prose proxy. Carried forward from
cand_0001, and strengthened: we now have measured evidence that one round of prose on this
exact class moved the behaviour by zero.
