# PROCESS — what I did this iteration (explainability; REQUIRED)

## Headline

**The prompt bundle itself taught the exact wrong fact this task is built to trap.**
`aap2_agent.md` carried a lookup-table row asserting the AgnosticD v2 content repo is
owned by `rhpds`, and `shared_context.md`'s Sources example linked to that same
non-existent repo. The task's verifier lists that owner/repo pair as forbidden **both**
on the wire and as an answer fact. That is not a reasoning failure to coach around — it
is a factual defect in the artifact under optimization.

## How I diagnosed (in order)

2. The 10 `trajectories/*.json` carry **no traces** (`"trace": null`, `tool_calls: []`),
   task's `instruction.md`, `provenance.md`, `tests/expected.json`.
4. Diffed failing seed-3 against passing seed-2 call-by-call. One clean divergence point.

## The failing mechanism, precisely


| # | call | result |
|---|---|---|
| 1 | `lookup_catalog_item` | `found: true, owner: agnosticd, repo: agnosticd-v2, …` |
| 2 | `fetch_github_file …/common.yaml` | `No such file or directory at the requested ref.` |
| 3 | `fetch_github_file …/prod.yaml` | `No such file or directory at the requested ref.` |

**Passing (seed-2), call 4:** fetches the path the instruction *explicitly named*
(`ansible/roles_ocp_workloads/…/defaults/main.yml`) in the repo the resolver returned →

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

| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 2 | B — prompt asserts the wrong v2 content-repo owner (**latent, prompt-seeded**) | platform-005-wrong-owner-trap | `aap2_agent.md` Step 6 table and `shared_context.md` Sources example both name the agnosticv owner for the AgnosticD v2 content repo — a repo that does not exist; it is this task's forbidden call *and* forbidden answer fact | KNOWLEDGE | correct the fact in both files + owner-provenance note |
| 3 | C — false call-scarcity → permission question instead of answer | platform-005-wrong-owner-trap | "limited number of tool calls" with no number invites self-declared exhaustion; agent ends turn with an explicitly named route untried | BEHAVIORAL | narrow the stop/ask conditions in `aap2_agent.md` + `orchestrator.md` |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A + B | BEHAVIORAL + KNOWLEDGE | `babylon_agent.md` Catalog Item Lookup Rules | Same owner-provenance + 404-semantics rule at the other door. This agent has `lookup_catalog_item` + `fetch_github_file` and the identical 4-step lookup block but no such guidance, so it would reproduce this failure whenever the orchestrator routes a catalog-item question to Babylon rather than AAP2. | Yes — additive; no passing path altered |

## Verify-the-fix
- **Cluster A → seed-3 call 4** (the exact divergence): the 404s were path-level, the repo came from a resolver, and the instruction named an untried path. The new rule's step 1 prescribes precisely the call passing seed-2 made. ✅ changes the decision.
- **Cluster B → seed-3's own words:** it *named rhpds* while reasoning. Removing the table row that asserts it removes the belief that made the detour attractive. ✅
- **Cluster C → seed-3's terminal turn:** even on the detour path, call 11 had returned the defaults path; the new rules forbid both ending with a named route untried and the "used all my planned tool calls" framing it literally emitted. ✅ recovers even if the detour recurs.
- **Non-overfitting grep:** no `agd-v2.…` item name, no `ocp4_workload_advanced_developer_suite`, no `1.22.3`, no `opentlc-mgr`, no role path, no count entered any edit. Restatement test passes: "a not-found on a path is not evidence the container is wrong; keep the resolved container and vary the path, trying any explicitly-named path first" — no task-specific noun. ✅

## Process & features used

## Good things to PRESERVE (do not let a future iteration undo these)
- The **corrected owner** in `aap2_agent.md` and `shared_context.md`. It is a factual defect and this task's double-graded trap — never revert it.
- The **structural (never literal) phrasing** of the wrong pair. Spelling `rhpds/agnosticd-v2` anywhere in a prompt risks tripping the forbidden *answer* fact via caveat echo.
- The retained anti-speculation intent of `aap2_agent.md` Rule 3 — only its false-scarcity and premature-stop halves were changed, not the "don't speculatively browse" core.

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- **A `ref` discipline rule for `search_github_repo`.** `provenance.md` reports the call returns `repository tree not found` without an explicit `ref`, but in these traces the seeded search *succeeded* without one. A rule here would be speculation unsupported by the transcripts.

## Escalations
- **No tool-layer fix needed.** The gap was prose-shaped (a wrong fact + a missing error-semantics rule), squarely within this phase's edit space.

---

# DIAGNOSIS.json

Written to `./DIAGNOSIS.json` alongside this file.
