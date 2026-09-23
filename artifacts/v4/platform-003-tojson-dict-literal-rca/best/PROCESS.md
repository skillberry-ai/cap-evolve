# PROCESS — iteration 2, candidate `cand_0002` (parent `cand_0001`, val 0.847)

Capability: **system-prompt**. Task: `platform-003-tojson-dict-literal-rca` (train == val == test == this one task).
Edit space: 8 `.md` files. **Files changed: `aap2_agent.md` only** (+116 lines, 10 hunks, 771 → 880).
The other seven are byte-identical to the parent — verified with `diff -q` per file.

---

## 1. Method, in the order I did it

1. **Read the handover set first**: `LEDGER.md`, `JOURNAL.md`, `INSIGHTS.md`, `META_INSIGHTS.md`,
   `FRAMEWORK_IMPROVEMENTS.md`, `RUNMAP.md`, `prior_iterations/cand_0001/{PROCESS.md,diff.patch}`.
   `rejected.jsonl` does not exist yet (no rejects this run), so nothing was off-limits as refuted.
2. **Took cand_0001's process advice literally** — its META_INSIGHTS §1 says to start from
   `reward-detail.json`, not from the trajectory summary. Did that. It is the reason this
   iteration's issue ranking is by measured frequency rather than by hunch.
3. **Re-derived the trace facts myself.** The trajectory JSONs in `trajectories/` carry only
   `output` + `score` (`trace` is `null`, `tool_calls` is `[]`), so every behavioural claim below
   comes from `rollout.metadata.trial_dir` → `**/agent/agent.jsonl` (the tool-use records) and
   `**/verifier/reward-detail.json` (the per-item misses).
4. **Diagnosed with subagents, concluded myself** — cand_0001's META_INSIGHTS §5: subagents are
   "reliable at locating evidence and unreliable at concluding from it". Held to that; see §7.
5. **Read `verify.py` before wording anything** (`_verdict_present`, `_word_present`, `TAXONOMY`,
   `TAXONOMY_EXCLUSIVE`) so the edits target what is actually scored.
6. Applied edits, then **audited every added line** for instance-specific values and for strings the
   rubric forbids.

## 2. What the data says (measured, not inferred)

Parent `cand_0001`, 5 trials, mean **0.8467**:

| seed | reward | tool_calls | answer misses | what the trace shows |
|---|---|---|---|---|
| t0 | **1.000** | clean | none | no-ref fetch → *fabricated* content; recovered via in-repo search on the **failing task name**, then re-read with **`ref=HEAD`** → real content |
| t1 | 0.767 | clean | `the-fix`, `category` | no-ref fetch → fabricated; then **14 calls, none of them back to the named repo** — all against the two monorepos |
| t2 | 0.700 | **0.000** | none | **9 calls, all errored.** Never called the pair the instruction named. Forbidden `agnosticd/agnosticd-v2` |
| t3 | 0.883 | clean | `category` | **1 call**, real content, correct analysis, wrong category token |
| t4 | 0.883 | clean | `category` | **1 call**, real content, correct analysis, no token at all |

`tool_calls` weight 0.3 (one forbidden call zeroes the whole component); `answer` weight 0.7 over a
denominator of 6.

### The `category` miss is two different failures, not one

Pulling the actual category text out of each final report was the pivotal step of this iteration:

| seed | prose category line | summary-table cell | outcome |
|---|---|---|---|
| t0 | `application_bug` | `application_bug` | pass |
| t2 | `application_bug` | `application_bug` — *gloss* | pass |
| t1 | `configuration` | **Type coercion / data serialization bug** | miss |
| t3 | `configuration` | **Data type mismatch** (YAML string vs. mapping) | miss |
| t4 | *(none)* | **Data-type mismatch** — YAML string mistaken for… | miss |

So:
- **(a) token replaced by a phrase** — t4 has no token anywhere. A *format* failure.
- **(b) a valid but wrong token** — t1 and t3 wrote `configuration`. A *discrimination* failure.

**This split matters because a format fix alone cannot repair (b).** t1 and t3 already believed
`configuration` was the token their evidence matched; telling them to "write the token" yields
`configuration` written correctly and still scores zero. (b) is worth **twice** what (a) is worth
(2 seeds vs 1), and I had nearly shipped only the (a) fix. The verifier's own `rationale` field names
the confusion outright: *"a wrong value committed in role source is an application bug, **not a
platform or configuration failure**"*.

## 3. Ranked issues

| # | issue | seeds | val at stake | class |
|---|---|---|---|---|
| 1 | `category`: wrong token (`configuration` for committed source) | t1, t3 | +0.047 | right domain, wrong action (reasoning) |
| 2 | `category`: token replaced by a self-authored phrase | t4 | +0.023 | output-contract compliance |
| 3 | tool_calls zeroed: never called the named `owner/repo`; built a forbidden pair | t2 | +0.060 | right domain, wrong action (parameters) |
| 4 | `the-fix`: left the named repo after one unpinned read, reported a fix from a monorepo | t1 | +0.023 | right domain, wrong action (recovery) |

Issues 1+2 = the `category` cluster (3/5 seeds, +0.070) — the largest. Issue 3 is the largest
single-seed loss. Issues 3 and 4 share a root: **the agent does not treat a location it was handed
as authoritative**, so both are addressed by one family of rules.

## 4. Every edit, its class, and verify-the-fix

All in `aap2_agent.md`. "Verify" = the exact point in a real trace the text would have changed.

| # | edit | targets | class |
|---|---|---|---|
| A | Step 9 opening: closed set restated; **"naming the mechanism is not assigning a category"** | 2 | contract |
| B | `application_bug` table row: added **wrong type or shape** vocabulary (a string where a mapping was needed; a structure stringified before use) | 1 | missing knowledge |
| C | Step 9 contract item 1: the token rule holds **everywhere** the category appears, including a summary-table cell | 2 | contract |
| D | **NEW** Step 9 contract item 5: mechanical pre-send check — a space, hyphen, slash, or capital in the token's place means it is not from the set; repair by moving the phrase to Root cause. Carve-out: a gloss *after* the token is fine | 2 | code-enforcement-in-prose |
| E | **NEW** `application_bug`/`configuration` discriminator: settle it **by pointing at the line that sets the value**; from a repo file (incl. a `vars:` block or `defaults/main.yml`) → source; `configuration` **requires naming the outside source**; "config" in a name proves nothing | 1 | missing knowledge |
| F | Step 6 version table: owner and repo in a row belong together | 3 | missing knowledge |
| G | **NEW** Step 6b rule 5: an `owner`/`repo` pair travels together — name the single source that gave you **both** halves; switching `ref` will not rescue a wrong pair | 3 | wrong parameters |
| H | Critical Rule 5: **read a slash as coordinates** — `X/Y` already *is* `owner=X, repo=Y`; the noun beside it says what the thing is, not that you must go find it | 3 | wrong parameters |
| I | Critical Rule 7: the anchor is the **failing task's name**, not an incidental string; **recover inside the same repo**; pin the `ref`; never hunt the same filename across other repos; the fix must come from the repo the failing task named | 4 | wrong recovery |
| J | **NEW** Critical Rule 8: errors on a location you invented mean the **location** is wrong, not the tool; before declaring a tool unavailable, call it with a location you were *given*; never write "try again later" while a named target is untried | 3, 4 | overconfident diagnosis |

**Verify-the-fix, per issue:**

- **Issue 1 → E.** t3 fetched the real file and read the offending value inside a `vars:` block in
  that file, then wrote `configuration`. E says: the line that sets the value came from a file you
  fetched out of a repo → `application_bug`, **explicitly including when the block is called
  `vars`**, and `configuration` requires naming an outside supplier (agnosticv, `extra_vars`,
  survey) — which t3 could not have named. This flips t3 at its decision point. t1 leaned on a
  `defaults`-style file it had fetched from a repo; E names that case too.
  *Pre-existing text was not enough*: cand_0001 had already added the abstract form of this test
  ("committed in a repo's role source → `application_bug`") and t3 read it and still chose
  `configuration`. E's contribution is making it **operational** — point at a line — rather than a
  principle the reader can agree with and misapply.
- **Issue 2 → D (+A, C).** t4's cell holds `Data-type mismatch`: a capital, a hyphen, and spaces.
  D's check is mechanical and fires on it. C closes the loophole that the rule applied only to the
  prose line. **Safety check:** t2 *passes* with `application_bug` — *gloss*; D's carve-out
  explicitly protects that form, so D cannot convert a passing report into a "repair".
- **Issue 3 → H, G, J (+F).** t2's 9 calls were all on derived locations, and it twice retried a
  *different `ref`* on a wrong repo — the precise antipattern G and J name. H addresses why it never
  tried the right pair: the instruction handed it `owner/repo` in slash form and it read that as a
  name to resolve into a monorepo path. J addresses what it did instead of recovering: its report
  closes with *"the GitHub tool needs to be available. Would you like me to retry the file read?"*
  while the named pair sat untried. **Positive control:** a sibling baseline trial of the same seed
  made 11 wrong-repo calls that all errored, then called the named pair and got real content — so
  the tool was live throughout and this is promptable, not infrastructure.
- **Issue 4 → I.** t1's own words at the pivot: *"The role file doesn't contain a `to_json` filter…
  Let me read the template and also search the collection for `to_json` usage"* — it tested with an
  incidental string and then searched **two monorepos**. I says the anchor is the failing task's
  name and the recovery search runs on the *same* `owner`/`repo`. **Positive control inside the same
  task:** t0 — the only 1.0 rollout — did exactly that (in-repo search on the failing task name,
  then a `ref`-pinned re-read) and got the real content. I promotes the observed winning strategy to
  an explicit rule rather than inventing one.

## 5. Overfitting risks — declared

- **Zero instance-specific values in any added line**, verified mechanically over all 116 added
  lines (job id, repo names, role/task names, the filter name, the offending literal, `16Gi`,
  `inventory.j2`, both monorepo owners: no hits).
- Both **forbidden `owner/repo` pairs are described by shape only** ("a collection's namespace as
  the `owner` while keeping a monorepo's name as the `repo`", and its mirror). Neither pair appears
  as a string anywhere in the 8 prompt files — confirmed; cand_0001's fix D still holds. They occur
  only in these handover docs, which the runtime agent never reads.
- The four strings the rubric forbids in the answer (`InvalidClientTokenId`, `--private-data-dir`,
  `was not found`, `worker stream`) appear nowhere in `aap2_agent.md`. Note that **`was not found`
  is a latent trap**: any future edit that teaches the agent to report an unreachable file in that
  phrasing would zero the answer's forbidden-absence item. No seed has hit it yet.
- **D introduces no new copyable token** and adds nothing to `TAXONOMY_EXCLUSIVE`; I checked the
  space/hyphen/slash/capital test against all 13 tokens (all lowercase snake_case, so the test has
  no false positives within the set).
- **Honest note on I's "pin the `ref`" clause.** Pinning demonstrably flips this mock from
  fabricated to real content (t0). I kept the clause because it is independently correct — you are
  diagnosing the commit that ran — and because cand_0001's Step 6 already required a `ref` for
  monorepo reads while Step 6b said nothing for collection reads, so this is a consolidation, not a
  new trick. But a future iteration should know the clause has a scoreboard-shaped side effect and
  should not read a gain on it as proof the *reasoning* improved. See FRAMEWORK_IMPROVEMENTS §6.

## 6. What to preserve / what I deliberately did not touch

**Preserve from cand_0001** (it went 0.564 → 0.847): the Step 9 taxonomy table and its
"classify from where the defect lives, not from the error vocabulary" rule; the removal of
`agnosticd/agnosticd-v2` from the prompt body; Step 6b's FQCN→collection-repo rules.

**Not edited, on purpose:**
- **`shared_context.md`** — highest blast radius in the edit space (read by all 6 domain agents).
  cand_0001's META_INSIGHTS asked whether its K/L edits were even necessary. My evidence says the
  category failures are *reasoning and formatting inside `aap2_agent.md`*, not a shared-context
  conflict, so touching it would add risk to tasks I cannot see for no expected gain. Leaving it
  byte-identical also means that if this candidate is accepted, the next iteration gets a clean
  answer to cand_0001's open question: K/L were sufficient and needed no follow-up.
- **`orchestrator.md`** — routing was correct in 5/5 trials; nothing to fix.
- **The five other domain agents** — out of this task's prompt footprint.
- **Cutting legacy sections.** cand_0001's META_INSIGHTS flagged file growth (+48%) as a suspect if
  this iteration came back flat. I did not cut, because cutting and adding in the same candidate
  makes the result uninterpretable — if it is accepted you cannot tell which half did it. If
  `cand_0002` is **rejected**, growth is now the leading suspect and cutting should be iteration 3's
  measured edit, on its own.

## 7. Subagents and tooling used

- Parallel read-only diagnosis subagents, one per trajectory group, to locate evidence in the trial
  dirs (the traces are large and outside the worktree).
- One adversarial self-verification pass aimed specifically at "does this edit push the reader
  toward or away from what the verifier rewards" — cand_0001's META_INSIGHTS §4. **It earned its
  cost again:** it caught that my first draft of D would have flagged t2's *passing* token-plus-gloss
  form as needing repair. The carve-out in D exists because of that pass.
- **Every load-bearing subagent claim was re-checked against the artifact before use.** One claim
  I did not take on trust was the "the tool was unavailable" reading of t2 — see §4, issue 3, where
  the positive control overturned it (and with it a belief recorded in cand_0001's PROCESS §7).
- `git` is not the interface here: the repo root is the run dir and `.gitignore` excludes `work/`,
  so `git diff` shows nothing after real edits. Diffed against `../cand_0001/` instead.

## 8. What I skipped, and what I could not fix from this phase

- **t1's fabricated-content problem is only half promptable.** The mock returned invented content,
  `is_error: false`, for a *correctly addressed* unpinned read of a **seeded** path — and
  nondeterministically: t0/t1 got a 620-byte fabrication from the same call that gave t3/t4 the real
  435-byte file. No prompt rule can make an agent detect a successful tool result that lies. What I
  *could* fix is the part that is genuinely the agent's: testing with the wrong anchor, and leaving
  the named repo. Escalated as FRAMEWORK_IMPROVEMENTS §6 — and it **corrects** cand_0001's
  escalation §2, which reported the path as nonexistent.
- **Seed-miss errors are worded like infrastructure faults.** t2's 9 errors arrive in the vocabulary
  of schemas and responses, which is what lured it into "the GitHub tool needs to be available".
  Rule J is the honest prose-level mitigation; the wording itself is a framework issue (§7).
- **No new tool was invented or implied.** There is no tools/code layer in this phase and none of
  these edits pretends otherwise.
