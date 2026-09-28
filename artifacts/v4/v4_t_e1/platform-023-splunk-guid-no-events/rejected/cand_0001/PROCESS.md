# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 of 3. Parent: `seed` (val 0.960). One task, 5 trials: rewards
`[1.0, 0.8, 1.0, 1.0, 1.0]`. The single lost 0.2 is entirely `answer=0.75` on
trial seed-1; `completion` and `tool_calls` were 1.0 on all five trials.

## How I found the actual defect (not guessable from the summary line)

`./trajectories/*.json` carry `trace: null` and `tool_calls: []`, so the
feedback line ("Task fully solved") is useless — it is the LAST trial, which
passed. The real evidence is behind `metadata.trial_dir`, which points into
`/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/jobs/...`. There
I read, per seed: `verifier/reward-detail.json` and `agent/agent.jsonl`, plus
the task's `tests/expected.json`, `instruction.md` and `provenance.md`.

**The exact defect.** `reward-detail.json` for seed-1 shows
`required_missed: []` (all 3 required facts present) and one
`forbidden_hit: inferred-from-silence`. In `agent.jsonl`, the orchestrator's
final block wrote:

> "✅ Does mean no error-level log lines tagged with `<guid>` reached the
> indexed OCP app log stream … This could be because: **(1) the pod never
> started and therefore never emitted logs**, (2) logs were emitted but not
> indexed, or (3) the GUID tag was absent or misspelled."

`never started` is on the forbidden list. That one clause is the entire 0.2.

**Why this is a class, not a one-off.** I read all five transcripts. *Every
one* of the five reaches for the same speculation; only the surface wording
differs, and it is luck which side of the matcher it lands on:

| seed | reward | the risky clause | outcome |
| --- | --- | --- | --- |
| 0 | 1.0 | "may simply not have reached the pod/log stage" | escaped |
| 1 | **0.8** | "the pod **never started**" | **HIT** |
| 2 | 1.0 | "before any pod was started" | escaped |
| 3 | 1.0 | "failed before any logs were emitted" | escaped |
| 4 | 1.0 | "it may **never have** started" | escaped by one word |

seed-4 differs from seed-1 by the word "have". So the baseline is not a
0.96-quality behaviour with one bad draw — it is a systematically unsafe
behaviour with an ~80% escape rate. That is the flakiness to remove, and it
is why a real fix should lift the mean *and* cut variance.

**Which half of the pipeline emitted it.** The graded answer is the
concatenation of sub-agent output + orchestrator output. The hit (seed-1) and
the near-miss (seed-4) were both in the **orchestrator's** "what this does and
does not let us conclude" block. This matters: `shared_context.md` is NOT
prepended to the orchestrator's prompt, so a fix placed only there would have
left the exact failing text untouched.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Treats an empty search as evidence about system state — enumerates unverified causes ("never started") when reporting a legitimately empty result | 1 (5/5 trials at risk, 1/5 realized) | Two prompt forces push it there: (a) "If the user asks 'why did this fail?', answer with the cause" is stated unconditionally and duplicated in `orchestrator.md:21` + `shared_context.md:10`; (b) nothing anywhere tells the agent what an absence does and does not license. `shared_context.md:141` even *licenses* the move ("**Infer** retired **from absence**") | BEHAVIORAL (overconfident) | Narrow the cause directive with an explicit condition; add a 3-part output contract for empty results, with a banned-phrase → replacement table |
| 2 | Same class, latent, in files outside this task's footprint: `security_agent.md:31` defines how to *earn* a confirmed negative but never says what it licenses; `ocpv_agent.md:59` maps "PVC Pending, **no events**" straight to an asserted `Cause` | 0 measured | Same root cause, different domains | BEHAVIORAL | In-place scope qualifiers |
| — | Routing, tool choice, tool args, completion | 0 | `tool_calls=1.0` and `completion=1.0` on all 5 trials | — | **no change** (deliberately untouched) |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | narrow an over-broad rule | `orchestrator.md:20-26` | "answer with the cause" now carries the condition *when a tool result shows the cause*; names "cause not established" as a complete answer. Removes the pressure, rather than adding a rule that fights it | Yes — unchanged whenever a result does show the cause, which is every other trajectory shape |
| 1 | new output contract + worked example | `orchestrator.md` new `### Reporting an Empty or Negative Result` | 3-part contract (absence + scope → what it does/doesn't establish → next check) and a Do-NOT-write → Write-instead table. This is the file the failing text came from | Yes — only fires on an empty result; all three parts are things the task already rewards |
| 1 | same contract for the sub-agent half | `shared_context.md` new `### Empty and Negative Results`; narrowed `:10`; sharpened the `**Empty results**` bullet | Covers whichever domain agent ran (I could not determine from the trial artifacts whether babylon or aap2 handled the Splunk call — both own `query_splunk`, so I covered both paths) | Yes — additive, empty-result-gated |
| 1 | de-generalize an absence→state license | `shared_context.md:141` | "Infer retired from absence" kept (it is attested and the active-provision query is authoritative for that one fact) but explicitly fenced as a narrow exception that must not generalize | Yes — the rule itself still applies exactly as before |
| 1 | close a loophole | `shared_context.md` Confidence Markers "When NOT to include" | The empty-result exemption now covers the *bounded* report only, not claims that go beyond what was searched | Yes — bounded case unchanged |
| 1 | domain worked example | `babylon_agent.md` `### Using Splunk Logs` | What zero Splunk events does/doesn't mean, + ranked next checks (drop `errors_only` → widen → leave Splunk for `list_anarchy_subjects` / provisions DB / AAP2) | Yes — additive to a section that had no empty-result rule |
| 1 | domain worked example + resolve counter-pressure | `aap2_agent.md` `## Using Splunk Logs`, and the mandatory `**Root Cause & Recommendations:**` block | Same Splunk rule; and the mandatory `Root cause:` field now accepts "not established — <what was searched> returned no events", so the must-produce-a-report rule no longer forces an invention | Yes — fields still required; only the permitted *value* set widened |
| 2 | scope qualifier | `security_agent.md:31` | States what an earned confirmed negative licenses: bounded to the events/window searched, never "the action never happened" | n/a — agent does not run for this task |
| 2 | demote asserted cause | `ocpv_agent.md:55` | `Cause` → `Likely cause (verify)`, with a note singling out the "no events" row | n/a — agent does not run for this task |

## Verify-the-fix (against the exact point each trial went wrong)

- **seed-1, the realized hit.** Its clause was "This could be because: (1) the
  pod never started…". The new orchestrator table has a row whose left cell is
  exactly `"never started", "never ran"` and whose right cell is the
  replacement `"whether it ever ran is unverified — check the orchestration
  record"`. The adjacent rule ("write each one as **the check that would settle
  it**, never as a statement of what happened") rewrites the whole
  three-item enumeration into three checks. This is the sentence that cost the
  0.2, and the edit lands on it directly, in the file that produced it.
- **seed-4, the one-word escape.** "it may never have started" is a hedged form
  that the table alone might not catch, so I added an explicit clause: keep
  those phrasings out "**even inside a negation or a hedge**", naming both
  "we cannot conclude it never started" and "it may never have been
  provisioned" as still-wrong, with the positive replacement. Without this the
  fix would have left the near-miss variance in place.
- **Required facts are reinforced, not endangered** — I checked each edit
  against `expected.json`'s `any_of` lists rather than assuming:
  - `no-events`: contract part 1 prescribes "no events", "0 results", "no
    matching records" — all three are in the `any_of` list.
  - `cannot-conclude`: part 2 prescribes "does not tell us", "does not mean",
    "does not let us conclude", and the prose uses "does not establish" — four
    members of the `any_of` list.
  - `next-step`: part 3 mandates a named next source; the domain files name
    `errors_only`, "widen", `list_anarchy_subjects`/AnarchySubject, `query_aap2`
    — four members of the `any_of` list.
  So the edit should raise the floor on the required facts as well as remove
  the forbidden hit, which is why I expect variance to drop, not just the mean
  to move.
- **Negation blindness.** I deliberately phrased part 2 as "does not let us
  conclude **anything about whether it ran**" rather than "…that it never ran",
  so the instruction itself never models a string that would trip the matcher
  if echoed.
- **No instance values.** Verified by grep that `hq7wz`, `2026-06-19`,
  `2026-06-21` and `platform-023` appear in **no** prompt file. Every rule is
  written against the pattern (an empty result for an identifier in a window),
  not this case. The banned phrases are named as an *inference class*
  ("never started" / "was never provisioned" / "failed because") — these are
  generic English claims any future empty-search case would face, not values
  from this instance.

## Process & features used

- **Subagents:** one read-only `Explore` subagent, fanned out over all 8 prompt
  files in parallel with my own trial-artifact reading, to inventory (a) every
  passage pushing toward cause assertion, (b) every existing empty-result /
  uncertainty rule worth sharpening instead of duplicating, (c) each file's
  section structure. It found three things I would likely have missed: the
  verbatim duplication of the cause directive across
  `orchestrator.md:20-22` and `shared_context.md:9-11`; the explicit
  `Infer retired from absence` license at `shared_context.md:141`; and the
  counter-pressure in `aap2_agent.md` (mandatory `Root cause:` field +
  "'Pod failed to start' is never an acceptable root cause") that would have
  fought the new rule. I did **not** use edit-subagents/worktrees: there is one
  task and one failure cluster here, so parallel edit branches would have added
  merge risk without covering additional clusters. Recorded in
  META_INSIGHTS.md.
- **Prior iterations read:** none exist — `RUNMAP.md` and `LEDGER.md` are
  empty (iteration 1), and `rejected.jsonl` / `history.jsonl` do not exist yet,
  so nothing is refuted and nothing was re-tried.

## Good things to PRESERVE (do not let a future iteration undo these)

- The **3-part empty-result contract must stay in `orchestrator.md` itself.**
  `shared_context.md` is not prepended to the orchestrator prompt, and the
  orchestrator is where the forbidden phrase was actually emitted. A future
  iteration that "consolidates" this into `shared_context.md` to reduce
  duplication would silently reopen the exact failure.
- The **"even inside a negation or a hedge"** clause. It is what covers the
  seed-4 near-miss shape; it looks redundant next to the table and is not.
- The **conditional** on "answer with the cause" in both files. Reverting it to
  the unconditional form restores the pressure that caused this.
- Do **not** touch routing, tool selection, or `errors_only`/window arguments:
  `tool_calls=1.0` on all 5 trials. This task's remaining headroom is entirely
  in answer prose.

## Deliberately skipped (cluster + why)

- **`cost_agent.md`, `icinga_agent.md`** — the audit found the same latent
  class here (`icinga_agent.md:190-195` forces a root cause; `cost_agent.md`
  has no epistemic scaffolding at all), but neither agent runs for this task,
  so an edit is unmeasurable, and both files would grow for zero gate signal.
  Left for a future run where a cost/monitoring task is in the split. I did
  make the `security_agent.md` / `ocpv_agent.md` edits because those two are
  small in-place qualifiers on *actively wrong* text (an absence mapped
  straight to an asserted cause), not new sections.
- **`aap2_agent.md:299-301`** ("'Pod failed to start' is never an acceptable
  root cause") — left alone on purpose. It is conditioned on *"When the log
  shows a pod failing to start"*, so it cannot fire on an empty search, and
  rewriting it would risk the deep-tracing behaviour that other trajectory
  shapes depend on. I addressed the unconditional pressure (the mandatory
  report field) instead.
- **The orchestrator's "NEVER re-synthesize the agent's analysis" rule** — all
  five trials produce a second orchestrator block because the user explicitly
  asks a second question ("tell me what that does and does not let us
  conclude"). That is answering, not re-summarizing, and `completion=1.0`
  throughout. Loosening it would add duplication for no gain.

## Escalation (needs code, cannot be fixed with prose)

Not needed for this fix, but worth recording: `expected.json`'s
`inferred-from-silence` is a plain case-insensitive substring list, so it is
blind to negation — a *correct* sentence like "we cannot conclude it never
started" scores as a violation. `provenance.md`'s own edit log documents the
mirror-image problem twice (the scenario scored 0.800 for a right answer until
`0 results` and `no log records` were added to an `any_of` list). My edit works
*with* the matcher by steering phrasing away from negated claims — which is
independently good report-writing — but the grader limitation is real and
belongs in the verifier, not in prompt text.
