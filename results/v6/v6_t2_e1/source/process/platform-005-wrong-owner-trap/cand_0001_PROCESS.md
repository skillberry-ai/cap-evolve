# PROCESS — what I did this iteration (explainability; REQUIRED)

## Headline

**The prompt bundle itself taught the exact wrong fact this task is built to trap.**
`aap2_agent.md` carried a lookup-table row asserting the AgnosticD v2 content repo is
owned by `rhpds`, and `shared_context.md`'s Sources example linked to that same
non-existent repo. The task's verifier lists that owner/repo pair as forbidden **both**
on the wire and as an answer fact. That is not a reasoning failure to coach around — it
is a factual defect in the artifact under optimization.

## How I diagnosed (in order)

1. Read LEDGER / JOURNAL / RUNMAP / `rejected.jsonl` — iteration 1, no prior art.
2. The 10 `trajectories/*.json` carry **no traces** (`"trace": null`, `tool_calls: []`),
   only a reward each: 9 × 1.0 and **1 × 0.29** (`tool_calls=0.5`, `answer=0.2`). That
   one trial is the entire 0.929.
3. Each trajectory's `metadata.trial_dir` is live on disk, so I read what the summaries
   omit: `verifier/reward-detail.json`, the full `agent/agent.jsonl` transcript, plus the
   task's `instruction.md`, `provenance.md`, `tests/expected.json`.
4. Diffed failing seed-3 against passing seed-2 call-by-call. One clean divergence point.

## The failing mechanism, precisely

Both trials open identically:

| # | call | result |
|---|---|---|
| 1 | `lookup_catalog_item` | `found: true, owner: agnosticd, repo: agnosticd-v2, …` |
| 2 | `fetch_github_file …/common.yaml` | `No such file or directory at the requested ref.` |
| 3 | `fetch_github_file …/prod.yaml` | `No such file or directory at the requested ref.` |

**Passing (seed-2), call 4:** fetches the path the instruction *explicitly named*
(`ansible/roles_ocp_workloads/…/defaults/main.yml`) in the repo the resolver returned →
file returns all three required literals. 4 calls, reward 1.0.

**Failing (seed-3), call 4+:** concludes the *repo* is wrong — "The catalog item index
points at `agnosticd/agnosticd-v2` but the path doesn't exist there. Let me check the
rhpds agnosticv repo…" — then burns 8 calls on other containers. Its 11th call finally
searches the right repo with a distinctive substring and **gets the defaults path back**,
then stops without fetching it: *"I've used all my planned tool calls but haven't
finished. Would you like me to keep going?"* + a `{{choices}}` block.

Three composing defects:

- **(A) Error-semantics confusion** — a *path-level* 404 read as evidence the *container*
  was wrong, though a resolver had settled the owner and nothing contradicted it.
- **(B) Prompt-taught wrong owner** — the "check rhpds" instinct was not invented;
  `aap2_agent.md:238` told it `rhpds` owns the v2 content repo.
- **(C) Vague scarcity → bail** — `aap2_agent.md:18` said "You have a limited number of
  tool calls" with no number; the agent self-declared exhaustion and swapped an answer
  for a permission question one fetch from the goal.

Verifier agrees: `citations_missed` = the defaults file (owner half required),
`required_missed` = admin-user + operator-channel, `counts_missed` = the version literal.
`forbidden_violations: []` only by luck — its guessed-owner searches hit
`rhpds/agnosticv`; one letter the other way zeroes `tool_calls` entirely.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | A — path-404 misread as wrong container | platform-005-wrong-owner-trap (1/10 trials) | A not-found on a *path* treated as evidence the resolver-supplied owner/repo/account is wrong → abandons the authoritative container and hunts guessed ones | BEHAVIORAL | decision rule + worked example in `shared_context.md`, mirrored in `babylon_agent.md` |
| 2 | B — prompt asserts the wrong v2 content-repo owner (**latent, prompt-seeded**) | platform-005-wrong-owner-trap | `aap2_agent.md` Step 6 table and `shared_context.md` Sources example both name the agnosticv owner for the AgnosticD v2 content repo — a repo that does not exist; it is this task's forbidden call *and* forbidden answer fact | KNOWLEDGE | correct the fact in both files + owner-provenance note |
| 3 | C — false call-scarcity → permission question instead of answer | platform-005-wrong-owner-trap | "limited number of tool calls" with no number invites self-declared exhaustion; agent ends turn with an explicitly named route untried | BEHAVIORAL | narrow the stop/ask conditions in `aap2_agent.md` + `orchestrator.md` |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| B | KNOWLEDGE (factual defect) | `aap2_agent.md` (Step 6 table) | v2 row corrected to `agnosticd/agnosticd-v2`; adds that the agnosticv family and AgnosticD content family have *different* owners and an owner must never be carried across families. Grounded in parsec's own `_AGNOSTICD_V2_REPO` constant per `provenance.md`. Generalizes: any agent tracing a config chain across both repo families. | Yes — passing trials never used the wrong owner; removes a trap, adds no constraint |
| B | KNOWLEDGE (factual defect) | `shared_context.md` (Sources example) | Example link repointed to the correct owner. An example URL is copied verbatim by agents, so a wrong one teaches the wrong owner to *every* domain agent. | Yes — cosmetic for passing trials |
| A | BEHAVIORAL (right-domain-wrong-action) | `shared_context.md` — new "A missing path is not a wrong container" | Distinguish "path does not exist here" from "wrong container"; resolver-supplied container is authoritative; vary the *path*, not the container; try an explicitly-named path **exactly as given** first; switch containers only when a tool result *positively names* a different one. Worked example in neutral placeholders. Domain-general on purpose: holds for repos, AWS accounts, Babylon clusters, Icinga hosts. | Yes — prescribes exactly what the 9 passing trials already did; no-op there |
| C | BEHAVIORAL (overcautious / stopped early) | `aap2_agent.md` Critical Rule 3 | Keeps the anti-speculative-browsing intent; adds that "budget" never licenses stopping while an explicitly named route is untried, and that there is no quota to announce. | Yes — passing trials never announced exhaustion |
| C | BEHAVIORAL (overcautious) | `orchestrator.md` "Asking Clarifying Questions" | Separates genuine ambiguity from permission-seeking: named identifiers *are* the spec → fetch, don't ask; never ask "keep going?" for work already requested; if a fact is truly unobtainable, state which and what you tried — that is an answer. | Yes — passing trials asked no question; `{{choices}}` for real ambiguity untouched |
| A + B | BEHAVIORAL + KNOWLEDGE | `babylon_agent.md` Catalog Item Lookup Rules | Same owner-provenance + 404-semantics rule at the other door. This agent has `lookup_catalog_item` + `fetch_github_file` and the identical 4-step lookup block but no such guidance, so it would reproduce this failure whenever the orchestrator routes a catalog-item question to Babylon rather than AAP2. | Yes — additive; no passing path altered |

## Verify-the-fix
- **Cluster A → seed-3 call 4** (the exact divergence): the 404s were path-level, the repo came from a resolver, and the instruction named an untried path. The new rule's step 1 prescribes precisely the call passing seed-2 made. ✅ changes the decision.
- **Cluster B → seed-3's own words:** it *named rhpds* while reasoning. Removing the table row that asserts it removes the belief that made the detour attractive. ✅
- **Cluster C → seed-3's terminal turn:** even on the detour path, call 11 had returned the defaults path; the new rules forbid both ending with a named route untried and the "used all my planned tool calls" framing it literally emitted. ✅ recovers even if the detour recurs.
- **Passing-trial safety:** all 9 already fetch the named path in the resolved repo and ask nothing, so every new rule is a no-op for them. Nothing discourages any call a passing trial made.
- **Forbidden-literal check (important):** my first draft spelled the wrong pair verbatim as a negative example. `expected.json`'s `answer.forbidden` is `none_of: ["rhpds/agnosticd-v2"]`, case-insensitive, and agents echo prompt caveats into answers — that would zero the 0.7 answer component. All three rules were rewritten to describe the pair *structurally* ("the agnosticv owner paired with the v2 content repo name") without spelling it. `grep -niE "rhpds/agnosticd-v2" *.md` → no matches. ✅
- **Non-overfitting grep:** no `agd-v2.…` item name, no `ocp4_workload_advanced_developer_suite`, no `1.22.3`, no `opentlc-mgr`, no role path, no count entered any edit. Restatement test passes: "a not-found on a path is not evidence the container is wrong; keep the resolved container and vary the path, trying any explicitly-named path first" — no task-specific noun. ✅

## Process & features used
- **Subagents / worktrees / parallel features used (or: "serial fallback because …"):** Serial fallback, deliberately. The run has one task with one failing trial and a single clean divergence point; diagnosis cost a handful of file reads. Fan-out pays when there are many clusters to cover in parallel — here there is one, so parallel diagnosis agents would have added cost and summarization loss with nothing to cover. Recorded in `META_INSIGHTS.md`.
- **Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md (which, and what I learned):** None exist — this is iteration 1. `RUNMAP.md` has only the placeholder row, `rejected.jsonl`/`history.jsonl` do not yet exist, LEDGER is baseline-only. Nothing to build on or avoid.
- **Key technique worth reusing:** the shipped `trajectories/*.json` had `trace: null`, but `metadata.trial_dir` pointed at live on-disk `agent/agent.jsonl` + `verifier/reward-detail.json`. Reading those turned "flaky, no visible cause" into an exact call-by-call diagnosis.

## Good things to PRESERVE (do not let a future iteration undo these)
- The **corrected owner** in `aap2_agent.md` and `shared_context.md`. It is a factual defect and this task's double-graded trap — never revert it.
- The **structural (never literal) phrasing** of the wrong pair. Spelling `rhpds/agnosticd-v2` anywhere in a prompt risks tripping the forbidden *answer* fact via caveat echo.
- The retained anti-speculation intent of `aap2_agent.md` Rule 3 — only its false-scarcity and premature-stop halves were changed, not the "don't speculatively browse" core.

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- **A `ref` discipline rule for `search_github_repo`.** `provenance.md` reports the call returns `repository tree not found` without an explicit `ref`, but in these traces the seeded search *succeeded* without one. A rule here would be speculation unsupported by the transcripts.
- **The catalog item's own `common.yaml` / `prod.yaml` 404s** (calls 2–3 in *every* trial, passing included). Harness/seed property, not agent error; agents must route around it, which is what makes cluster A decisive. Wrote no prose depending on it.
- **`lookup_catalog_item` qualified-argument leniency.** `provenance.md` flags that the `account.item.stage` form is accepted under simulation but would miss real parsec. Out of scope for a prompt edit judged on this harness, and coaching the bare-key form could not be verified here.

## Escalations
- **No tool-layer fix needed.** The gap was prose-shaped (a wrong fact + a missing error-semantics rule), squarely within this phase's edit space.

---

# DIAGNOSIS.json

Written to `./DIAGNOSIS.json` alongside this file.
