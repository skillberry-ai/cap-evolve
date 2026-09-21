# PROCESS — what I did this iteration (explainability; REQUIRED)

Candidate `cand_0002`, iteration 2/3. Parent: `cand_0001` (val **0.721**, per-seed
0.893 / 0.571 / 0.464 / 0.679 / 1.000). Single task
`platform-033-schema-change-not-the-oom` (train == val == test).
Reward = 0.25·tool_calls + 0.75·answer. Significance bar ≈ 2·SE ≈ **0.199**
(per-seed sd 0.2223 over 5 trials).

Files changed: **`babylon_agent.md`** and **`shared_context.md`** only — the two files the
fast-path actually loads (footprint re-confirmed, see cand_0001's PROCESS).
`babylon_agent.md` 475 → 595 lines, `shared_context.md` 258 → 266.

## WHERE THE 0.279 OF REMAINING LOSS ACTUALLY IS

I measured this before designing anything, from the five `reward-detail.json` files found
via each trajectory's own `rollout.metadata.trial_dir` (my first attempt globbed
`-name reward-detail.json` and silently read the **baseline** 04:1x runs instead of the
champion's 05:0x–05:2x runs — each `seed-N/` holds both).

**`completion` = 1.0 on 5/5. `tool_calls` = 1.0 on 5/5. Both forbidden facts clean on
5/5.** cand_0001's contributing-factor guard works and must be preserved. **100% of the
remaining loss is the `answer` metric: 13 missed fact-checks out of 35** (5 required ×
5 seeds + 2 forbidden × 5 seeds, all forbidden passing). answer mean = 22/35 = 0.6286.

Ranked by (seed, fact) pairs explained:

| # | cluster | pairs | share |
|---|---|---|---|
| 1 | **Round exhaustion → no report → facts already in hand never written** | 7 | 54% |
| 2 | **`new-field` never discovered by any trial** | 4 | 31% |
| 3 | **Splunk `search_terms` that returned `[]`** | 2 | 15% |

Cluster 1: 3 of 5 champion runs hit `max_rounds=8` and fell through. Confirmed two ways —
`grep "used all my planned tool calls"` (seed-1/2/3) and `parsec-live.log`
"`exhausted max rounds: 9 / 10 / 9 tool calls`". `governor-unchanged` sat in tool call #3
of 9–10 in **every single run**, with the grader's exact `any_of` phrases ("still reads",
"nothing in this file changed") verbatim in the fetched file body — and all three
report-less runs dropped it. seed-2 passed `19034` as a *tool argument* and wrote
"That's the PR." without the number. seed-2 also dropped `old-field`, which was in call #1.

Cluster 2: genuinely absent from every tool result in all four non-winning runs. All four
burned 4–5 `search_agnosticv_prs` calls guessing replacement tokens (**17 calls across the
four, every one `[]`**) while `includes/ansible_control_plane.yaml` — same owner, same
repo, adjacent directory, named in the PR's own `files` list, seeded at both `HEAD` and
`main` — was one `fetch_github_file` away. **No run, including the 1.000 winner, ever
fetched it. It is the only place in the entire seed set where either `new-field` token
appears, and its header comment also names the PR number.** Highest-value unexploited read
in the task.

Monotonic across all five trials: fewer tool calls → higher reward (8 → 1.000; 9 + report
→ 0.893; 9–10 + fall-through → 0.464–0.679).

## THE DIVERGENCE POINT — identical in all four non-winning runs

Every run opens the same way and the first three calls are already correct:

```
1. query_aap2(get_job_log)                                   ← graded leg 1 ✓
2. search_agnosticv_prs(<variable name>, state="all") → []   ← graded leg 2 ✓
3. fetch_github_file(rhpds/agnosticv, roles/<role>/defaults/main.yaml) ← graded leg 3 ✓
4. ***** search_agnosticv_prs(<another guess>) → [] *****     ← EVERY RUN LOSES IT HERE
```

seed-0 `secret` · seed-1 `<var>.credential` · seed-2 `secret` · seed-3 `<role>` ·
seed-4 `control_plane`. From call 4 on, the four non-winners spend 5–7 further calls
guessing search terms; three of them never reach a report. The winner's call 5
(`<role>` as the term) happened to hit — 1 of 5 observations of that same string.

So the edit target is not "search better". It is: **make call 4 a direct path lookup, and
make the report mandatory before the cap.**

## THE EDITS (7, all in the two loaded files)

| # | file | section | class | what changed |
|---|---|---|---|---|
| A | babylon | Critical Rule 1 | BEHAVIORAL + OUTPUT CONTRACT | Soft "about six tool calls" → hard ledger: "Count your tool calls. Six is your ceiling: your seventh response contains no tool calls and is the report." Plus **"A fact you hold and do not write down scores zero"** + "state each value the moment you learn it". |
| B | babylon | Critical Rule 2 | BEHAVIORAL + KNOWLEDGE | Blanket "never re-issue with a new keyword" (ignored by 5/5) → "One attempt per keyword search, then get the fact from a **different tool**", with the index mechanics: matches title **or changed file path**, substring, never the body ⇒ prefer a **path component** term. Two-empties-per-tool hard cap. Old "last two calls empty" stop trigger folded in here, not dropped. |
| C | babylon | A Config Change Broke Everything At Once | KNOWLEDGE + WORKED CHAIN | 4-step chain that dead-ended on the PR search → **5-call chain that terminates**, with the new step 4: a failing `{{ <parent>.<field> }}` has **two sides in two files**; in AgnosticV the definition is `includes/<parent>.yaml`, same owner/repo, and its header comment names the change. Independent of the PR search. |
| D | babylon | Using Splunk Logs | KNOWLEDGE | "`search_terms` is one literal phrase, not a set of words" — a composed description matches nothing. Pass an **identifier** (`pr-<number>`, a check name) or **no `search_terms` at all**. Added: don't set `errors_only` (merge/override rows are `INFO`). |
| E | babylon | Report Format | OUTPUT CONTRACT | 4-row "must name" table → **5-line fill-in block with angle-bracket slots**, plus the 5th line for the tests/checks role, pre-labelled "Contributing factor". Names the two failure modes: describing instead of naming, and promoting the contributing factor. |
| F | babylon | **new** `### Before You Send the Report` | OUTPUT CONTRACT | ask → first source → **second source if the first came back empty**, one row per graded fact. This is the table Rules 1 and 2 point at instead of licensing another search. |
| G | shared_context | Tool Result Handling | BEHAVIORAL | "change ONE thing" bullet legitimised the search loop. Narrowed: **at most ONE retry, and it is a widened filter, never a new term** — and none at all if the first call already used the widest filters. Then "switch to a direct lookup". |

Reconciled with the reader tier (`claude-sonnet-4-6`, strong but not frontier): every rule
is an explicit numbered step or a fill-in template, not an inference. Edit E is a literal
block to copy because the graded values are exactly the ones agents describe instead of
naming.

## VERIFY THE FIX — replayed against all five champion transcripts

Not "plausible"; walked call-by-call. Under the edited prompt the chain is
`get_job_log` → `search_prs` (one attempt, path-component term) → `fetch(consumer)` →
`fetch(includes/<parent>.yaml)` → `splunk(pr-<number>)` → report = **5 calls, ≤6 rounds**.

- **seed-1 (0.571, exhausted):** calls 1–3 unchanged. Call 4 (`<var>.credential` → `[]`)
  is now the include fetch ⇒ `new-field` + PR number. Calls 5, 7, 8 (two composed splunk
  phrases, one more PR guess) are eliminated by B and D. Reports at call 6 with all five
  facts. Its 7–8 (`'ansible_control_plane merge'`, `'secret credential required check'`)
  are exactly what D forbids and `'required check'`/`pr-<n>` are what D prescribes.
- **seed-2 (0.464, exhausted, 10 calls):** same call-4 substitution; calls 5, 6, 7
  (`control_plane`, `credential`, `search_github_repo`) die on B's two-empties cap. Its
  `19034`-as-tool-argument-never-written is precisely what A's "a field name you passed as
  a parameter is invisible to them" targets.
- **seed-3 (0.679, exhausted):** call 4 substitution; 5–6 eliminated by B; 8
  (`'merged PR'` → `[]`) eliminated by D. Note seed-3's `tests-role` credit was
  **spurious** — it matched "no result" inside its own sentence "returning no results
  across multiple search terms" — so the real gap vs seed-1 is nil. Both now report.
- **seed-0 (0.893, reported):** its only miss was `new-field`; its calls 4, 5, 8 were all
  empty PR searches. Call 4 → include fetch closes it. → 1.0.
- **seed-4 (1.000, reported) — regression check:** becomes 5 calls instead of 8. Ordered
  subsequence `get_job_log` → `search_agnosticv_prs` → `fetch_github_file(<consumer>)`
  is positions 1–3 of the chain, so `tool_calls` stays 1.0. And the term that *won* for
  seed-4 at its call 5 (the role name, a **changed-path** match) is now what Rule 2 tells
  it to try **first**. Held at 1.0 with three rounds of margin.

`tool_calls` protection was a near-miss I caught by reading `tests/expected.json`: `match`
is **`ordered-subsequence`**, so an earlier draft that moved the PR search after both file
fetches would have dropped `tool_calls` 1.0 → 0.667 (−0.083 reward). The chain therefore
pins the PR search at position 2 and says to send it **alone in its own response**, before
any file fetch, so parallel emission can't reorder the subsequence.

Arithmetic: closing `new-field` (4) + `pr` (3) + `governor-unchanged` (3) = 10 of 13
misses ⇒ answer ≈ 32/35 = 0.914 ⇒ reward ≈ 0.936, **Δ ≈ +0.215 vs the 0.199 bar**. Thin
but real; no wording tweak could clear it, which is why the whole candidate is aimed at
clusters 1 and 2 rather than spread over all three.

## A HYPOTHESIS I HELD AND DROPPED (cost: 0 edits, saved: 1 iteration)

I had drafted a "PR-search retry ladder" (try term X, then Y, then Z) plus a matching
`shared_context.md` loosening, on the theory that the flakiness came from a **conflict**
between `shared_context.md`'s "change ONE thing" and Rule 2's "never re-issue". Subagent
evidence refuted it: the losing runs each made **4–5** PR searches, so Rule 2 was not
blocking anything, and `search_agnosticv_prs` is **non-deterministic in the simulator** —
17 calls across the four losers returned `[]`, *including the exact arguments that
returned the PR for the winner* (`<role>`: `[]` in 4 observations, the PR in 1; one run got
**fabricated** PRs; another got `{"error": "Unknown store …"}`). A ladder would have
*increased* round burn, which is the dominant failure. Dropped before writing.

**Design consequence, and the most transferable thing in this iteration: no graded fact
may depend on that tool.** The PR search stays in the chain because `tool_calls` requires
it, but the PR *number* now has two other sources (the definition file's header comment,
the controller log) and the new field name has one deterministic source (the definition
file). The flaky tool is kept for credit and removed from the critical path.

## WHAT I PRESERVED (do not remove next iteration)

- cand_0001's **Root Cause vs Contributing Factor** section and the `attributed_to`
  phrasing it teaches. Both forbidden facts are clean 5/5 *because* of it; Edit E's fifth
  line reinforces it rather than restating it.
- The **canonical repo table** and the `ansible/`-prefix AgnosticV/AgnosticD
  discriminator — Edit C step 4 depends on it to build `includes/<parent>.yaml` in the
  right repo.
- "Read a file you already have the path for" — the reason all 5 runs get graded leg 3.
- Rule 1's report-is-the-deliverable framing, no-tools-in-final-response, and
  never-end-by-asking.

## NON-OVERFITTING

Checked by grep over all 8 prompt files: **zero** occurrences of `ansible_control_plane`,
`ansible_controllers`, `ansible_controller_select_mode`, `babylon_anarchy_governor`,
`19034`, `90451`, `schema-compat`, `512MiB`. Every new rule is a placeholder pattern
(`<parent>`, `<old_field>`, `<new_field>`, `includes/<parent>.yaml`, `pr-<number>`,
`<consumer path>`). (`east` appears once in `aap2_agent.md`'s pre-existing controller
mapping table — baseline text, not loaded for this task, not touched.)

The two knowledge claims are conventions, not instance facts: (1) a shared top-level
variable in AgnosticV is defined in its own include under `includes/`, consumers live
under `roles/` — a repo-layout convention; (2) a migrated definition file's header comment
normally names the change that migrated it — a config-repo convention. Both generalise to
any renamed/removed-field outage, which is the failure class here.

## SKIPPED / NOT DONE

- **Cluster 3 (splunk empty terms, 2 pairs) is only partly addressed.** Edit D removes the
  composed-phrase failure mode, but the "omit `search_terms` entirely" fallback is
  **derived from `_build_aap2_query` and the simulator's own spec, never observed** — no
  run in the bundle ever tried it. The primary path (identifier as the term) *is* observed
  (`pr-<number>` returned both the OOM row and the override row in the one run that tried
  it), so the fallback being wrong costs nothing.
- No edits to the other 6 prompt files: not loaded for this task.
- `query_provisions_db`, `render_chart`, `generate_report` are in
  `parsecsim.routing.UNMODELLED` and return "not modelled" — I did not add guidance
  steering toward them.

## ESCALATION (genuinely needs code, not prose — not faked with prose here)

1. **`max_rounds=8` for `babylon` is too tight for its own documented chain**
   (`agents.py:113`). `aap2` and `security` get 20, `icinga` 15. This task's designed
   golden path is 3 calls, but any real investigation that also answers the
   "what did the tests do" sub-question needs 5 — leaving 3 rounds for every wrong turn.
   3 of 5 champion runs died on it. Prose can only make the agent thriftier; it cannot
   raise the cap.
2. **The fall-through text is appended to the graded answer, not substituted**
   (`agents.py:1108-1118` yields it as `sse_text`; `parsec_harbor_agent._answer_from_sse`
   concatenates every `event: text`). So an exhausted run is graded on its interim
   narration *plus* a question to the user. A code fix would emit a forced synthesis turn
   at the cap instead of a question.
3. **`search_agnosticv_prs` is unreliable under simulation** (non-deterministic, sometimes
   fabricating, sometimes returning harness errors) and **drops the `files` field** the
   scenario's own `provenance.md` says the chain depends on. Any task whose golden path
   routes a fact through it is testing the simulator, not the agent.
