# PROCESS — what I did this iteration (explainability; REQUIRED)

## TL;DR

The flakiness is **not** reasoning, routing, or tool use. All 28 available
trials make the correct single tool call and retrieve the correct data. The
only thing that ever fails is one answer-contract check, `lon-is-up`, and it
fails for a **presentation** reason: the agent writes a decorative status icon
**between** an entity's name and its status word (`| host | ✅ UP |`), which
breaks the name↔status adjacency that every `lon-is-up` form requires.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | A: status icon splits entity name from its status word | icinga-045-hosts-search-filter (4/28 trials lose `lon-is-up`) | Agent renders state as `\| name \| ✅ UP \|`. The decorative glyph sits between the name and the status word, so no name↔status pairing form matches. Substance is correct in all 28 trials; only the rendering varies, which is exactly why it is intermittent rather than deterministic. | BEHAVIORAL (output-contract / formatting reflex) | Output-contract rule in `shared_context.md` + reinforcement at the state-rendering decision point in `icinga_agent.md` |
| 2 | B (latent, 0 observed failures): multi-row answers may drop healthy rows / paraphrase check output | same task | The contract's third required check exists to catch an agent that reports only problem rows and leaves healthy matches unaccounted for; a sibling check defends against paraphrasing a check output into a generic guess. Not observed failing, but one icon-free mention of the healthy host is the *only* thing saving 4 more trials — the habit is one step from failing. | BEHAVIORAL (completeness / fidelity) | Explicit multi-row reporting procedure in `icinga_agent.md` |

No routing cluster: `task.toml` has `services = ["icinga"]` and routing is
correct in 28/28 trials. No capability gap: the one tool call needed exists
and is used correctly every time.

## How I diagnosed it (in order)

1. **`trajectories/*.json` were insufficient** — all 10 have `trace: null`
   and `tool_calls: []`. But the metric breakdown was already decisive:
   `completion=1.0, tool_calls=1.0` in **every** trial; only `answer` moves
   (1.0 in 6, 0.75 in 4). So the defect is purely in answer text, and no
   routing or tool edit could help.
2. **Found the real transcripts** via the `trial_dir` in each trajectory's
   metadata, plus `verifier/reward-detail.json`. 28 trials across two runs.
3. **Isolated the failing check** — every 0.75 trial has
   `required_missed = ["lon-is-up"]`, the same single check, never another.
   The other two required checks always pass; the forbidden check is never
   hit. (0.8 × 2/3 + 0.2 = 0.75 answer → 0.8 reward.)
4. **Ran the real verifier** (`tests/verify.py`) against each trial's actual
   answer text instead of guessing. This reproduced the pass/fail split
   exactly, so I could test hypotheses mechanically.
5. **Found the discriminator.** Failing and passing answers look nearly
   identical to a human (seed-4 fail and seed-5 pass are near-copies). The
   difference is one character class. Regex for "glyph interposed between
   hostname and state word":

   | any_of passes | glyph interposed | trials |
   |---|---|---|
   | yes | no  | 20 |
   | yes | yes |  4 |
   | no  | yes |  4 |

   **Every** failing trial has the glyph interposed; no trial fails without
   it. The 4 pass-with-glyph trials had a second, glyph-free mention of the
   host elsewhere that satisfied the check — the source of the intermittency.
   Failing rows: `| x | ✅ UP |`, `| x | 🟢 UP |`, `| x | ✅ **UP** — …`.
   Note `_strip_markup` is **not** active here (`fold_markup` unset), but
   `**UP**` forms are enumerated in `any_of`; the emoji is not, and nothing
   folds it.
6. **Verified mechanically before writing prose.** Stripping only decorative
   glyphs from the 4 failing answers and re-scoring:
   fully-clean trials **24/28 → 28/28**, forbidden hits **0 → 0**. No passing
   trial changes — upside-only on all observed data.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | CONTRACT (output format) | `shared_context.md` — new "Keep each entity adjacent to its status" subsection beside the existing formatting rules | Status word must directly follow the name with only ordinary punctuation between; no icon between name and status; an icon must never replace the status word; icons allowed *after* the status or in their own column. Includes a good/bad worked example. Generalizes because "entity followed by its status" is domain-general — hosts, services, jobs, accounts, clusters, provisions all render this way, and the icon habit is a model-wide formatting reflex, not Icinga-specific. This is the one rule that belongs in the shared file. | Yes — constrains *where* an icon may go; does not forbid icons, tables, or bold. Cannot change any tool call. The 24 passing trials already comply. |
| A | BEHAVIORAL (reinforce at decision point) | `icinga_agent.md` — appended to "Icinga State Model" | Always translate numeric `attrs.state` into its word and put that word immediately after the name — never a bare number, never an icon between. Placed directly under the `0 = UP, 1 = DOWN` table, i.e. the exact moment the agent decides how to render a state. | Yes — same rendering the passing trials already produce. |
| B | BEHAVIORAL (completeness + fidelity) | `icinga_agent.md` — new "Reporting a multi-host / multi-service result" subsection | For a query returning several rows: (1) answer the question and quote `last_check_result.output` **verbatim**, (2) list *every remaining matched row* by name with its own state word, (3) give the total count. Generalizes: "report the problems, drop the rest" is a general multi-row-answer failure mode, and the verbatim clause defends the separate hazard of paraphrasing a check output into a generic guess. | Yes — codifies what the passing trials already do; adds no tool calls. |

## Verify-the-fix (the trace → what the edited text now does on those exact inputs)
- **Cluster A, seeds 4/5/6/8** (the table cell where the icon was emitted): re-scored rule-compliant renderings with the real verifier —
  compliant table `| host | DOWN |` → **1.00**; compliant with icon *after* status (`DOWN 🔴`) → **1.00**; compliant prose (`host is DOWN; host2 is UP`) → **1.00**; old violating style `| host | ✅ UP |` → **0.67, missed `lon-is-up`**. The last row reproduces the observed failure and all three forms the new rule permits score 1.00 — the rule is sufficient, not merely plausible.
- **Glyph-strip simulation over all 28 trials**: fully-clean 24/28 → 28/28, forbidden 0 → 0 (no passing trial perturbed).
- **Cluster B**: no observed failure to replay; the rule is preventive and matches what all 28 trials already do substantively, so it cannot regress them.

## Non-overfitting check
`grep` confirms **no** task literal (`ledger`, `-fra`, `-lon`, `10.61.4.22`,
`time to live`) appears anywhere in the edited files — examples use `web-01` /
`host-x` placeholders. Restating both rules without task-specific nouns:
*"put a named thing's status word right after its name, with no icon in
between"* and *"when a query returns many rows, give every row's state and
quote outputs verbatim."* Neither names a host, service, or value.

## Process & features used
- **Subagents / worktrees / parallel features used:** none — serial, deliberately. The guidance suggests one subagent per trajectory-group, but there is exactly **one** task, **one** failing check, and **one** mechanism, and the real verifier was available to test hypotheses directly and cheaply. Fanning out would have multiplied cost without adding coverage. The high-leverage move here was running `verify.py` against real answer text, not parallelism. Recorded in `META_INSIGHTS.md`.
- **Prior iterations read from ./prior_iterations/ + ./RUNMAP.md:** none exist — this is iteration 1 (RUNMAP has only the "no prior iterations yet" row, LEDGER only the baseline). `rejected.jsonl` / `history.jsonl` are absent, so no refuted approach to avoid.

## Good things to PRESERVE (do not let a future iteration undo these)
- The seed already gets routing, tool choice (one `get_hosts` with `search` + `detailed=true`), and the substantive content right in **28/28** trials. Do **not** add tool-use, routing, or investigation-depth rules for this task — there is no headroom there, and extra tool-use prose risks breaking the clean single-call pattern that scores `tool_calls=1.0` every time.
- The measured headroom was *presentation only*. Keep the name↔status adjacency rule.

## Deliberately skipped (cluster + why)
- **`orchestrator.md` edit** — `services = ["icinga"]`; routing correct in every trial. No discriminating condition to add.
- **Prose telling the agent to match verifier phrasings** — that overfits to the grader instead of fixing a mechanism.
- **Any new-tool proposal** — no capability gap; this phase has no tools layer anyway.

## Escalation (honest scope note)
None blocking — this is genuinely fixable in prose. Worth recording: the
`lon-is-up` check passes/fails on whether an emoji sits between two tokens,
while the agent's *substance* (which host is down, why, and the other host's
state) is identical in all 28 trials. 4/28 trials lose 0.2 reward for a
cosmetic choice. `any_of` enumerates `**UP**` but not `✅ UP`, and nothing
folds leading glyphs the way `_strip_markup` folds markup. I fixed it on the
agent side because that is this phase's edit space, and because "status word
adjacent to the name" is defensible formatting advice on its own merits — but
a contract that folded leading glyphs would erase this flake class for every
task at once. Logged in `FRAMEWORK_IMPROVEMENTS.md`.
