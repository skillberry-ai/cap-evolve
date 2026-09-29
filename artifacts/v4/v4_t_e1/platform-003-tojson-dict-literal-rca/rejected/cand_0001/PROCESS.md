# PROCESS — iteration 1, candidate cand_0001

Task: `platform-003-tojson-dict-literal-rca` (the only task; train == val == test).
Baseline val reward **0.563** — 5 trials at 0.500 / 0.617 / 0.583 / 0.617 / 0.500.
Files edited: `aap2_agent.md` (primary), `shared_context.md` (two narrow fixes).
No prior iterations existed — LEDGER, JOURNAL, RUNMAP, INSIGHTS, rejected.jsonl were all
empty template. This is a clean first proposal.

## 0. How I got the ground truth (do this first, next iteration)

The `trajectories/*.json` files carry only the reward summary. The per-item breakdown —
which rubric item each seed actually missed — is in the run's own trial dirs:

```
_run/jobs/v4_t2_e1/<task>/seed-N/<ts>/<date>/<task_hash>/verifier/reward-detail.json
```

That file has `tool_calls.{unmatched_expected,forbidden_violations}` and
`answer.{required_missed,citations_missed,verdict_missed,forbidden_hit}`. Reading it
converted my diagnosis from inference to measurement, and it corrected two of my
hypotheses (see §4). **Read it before proposing anything.**

Rubric shape (weights `tool_calls` 0.3, `answer` 0.7; answer denominator = 6):
- expected tool calls, ordered-subsequence: `query_aap2(get_job_log)` → then
  `fetch_github_file(owner=agnosticd, repo=cloud_provider_openshift_cnv,
  path=roles/create_inventory/tasks/main.yml)`.
- forbidden tool calls: `fetch_github_file(agnosticd/agnosticd-v2)` and
  `fetch_github_file(rhpds/cloud_provider_openshift_cnv)`. **A single forbidden call
  zeroes the whole 0.3 component.**
- answer: 3 required facts + 1 citation + 1 verdict + 1 forbidden-absence.

## 1. Measured failure table (all 5 seeds)

| seed | reward | tool_calls gap | `error-message` | `dict-literal` | `the-fix` | citation `role-task` | verdict `category` |
|------|--------|----------------|-----------------|----------------|-----------|----------------------|--------------------|
| 0 | 0.500 | collection fetch never made | ✓ | ✓ | **✗** | **✗** | **✗** |
| 1 | 0.617 | collection fetch never made | ✓ | ✓ | **✗** | ✓ | **✗** |
| 2 | 0.583 | both expected matched — **zeroed** by forbidden `agnosticd/agnosticd-v2` | ✓ | ✓ | ✓ | ✓ | **✗** |
| 3 | 0.617 | collection fetch never made | ✓ | ✓ | ✓ | **✗** | **✗** |
| 4 | 0.500 | collection fetch never made | ✓ | ✓ | **✗** | **✗** | **✗** |

Ranked by expected value (frequency × weight):

| # | Issue | Seeds | Per-seed value if fixed |
|---|-------|-------|--------------------------|
| 1 | **No root-cause category stated** | **5/5** | +0.117 answer |
| 2 | **Namespaced role fetched from a monorepo instead of its collection repo** | 4/5 | +0.15 tool_calls |
| 3 | `the-fix` never names the corrected value's *type* | 3/5 | +0.117 answer |
| 4 | Citation not in adjacent `owner/repo:path` form | 3/5 | +0.117 answer |
| 5 | **Forbidden repo probed** (`agnosticd/agnosticd-v2`) | 1/5 | +0.30 tool_calls |

Routing was **correct** in all 5 seeds (`investigate_aap2_job`). No `orchestrator.md`
edit was warranted and none was made.

## 2. Root cause of each, in the prompt text

The decisive observation: **every one of the 5 seeds recognised the collection name**
(`search_github_repo(owner=redhat-cop, repo=agnosticd, search="cloud_provider_openshift_cnv")`)
and then looked for it *inside a monorepo*. The agents were not confused about the name —
`aap2_agent.md` gave them nowhere else to look.

| Issue | Cause |
|-------|-------|
| 1 (category) | **No prompt file contained the RCA taxonomy at all.** It lives in `aap2-job-failure-rca/SKILL.md:90-95` and was never carried into `aap2_agent.md`. The output template said "Root Cause & Recommendations" with no category, no confidence. Agents invented prose ("a YAML type-coercion problem") — unscoreable. |
| 2 (wrong repo) | `aap2_agent.md` taught exactly one source layout: the monorepo tree plus the Fetch bullet `ansible/roles/{role_name}/tasks/main.yml`. The concept of a namespaced collection shipping in its own repo did not exist in the file. |
| 3 (the-fix) | Template said "Fix suggestions: actionable next steps" — a *direction*, not a change. Nothing asked for the corrected value's type. |
| 4 (citation) | Template listed bare paths, and the Configuration Trace table put repo and path in **separate cells**, which cannot satisfy an adjacency-based citation check. |
| 5 (forbidden) | **The prompt itself supplied the forbidden string.** `agnosticd/agnosticd-v2` appeared verbatim twice (a `scm_url:` in a YAML example, and the "agnosticd-v2 (current)" bullet) — while the file's own Step 6 version table says the v2 owner is `rhpds`. Seed-2 probed `agnosticd/agnosticd-v2` eight times and lost 0.3. |

Issue 5 is the cleanest finding of the iteration: an internal contradiction in the prompt
was handing the agent a forbidden call.

## 3. Changes made

All in `aap2_agent.md` unless noted.

| # | Change | Edit class | Targets |
|---|--------|-----------|---------|
| A | **New Step 9 "Assign Exactly One Root Cause Category"** — flat closed 13-token set, 11-row evidence→category table, the `application_bug`/`configuration` split test, and a 4-point write contract (literal snake_case token + confidence; one category only; always give one even when a read failed; confidence tracks corroboration). | output contract + decision policy | 1 |
| B | **New Step 6b "Namespaced Roles Live in Their Own Collection Repo"** — FQCN→`fetch_github_file` argument table (namespace→`owner`, collection→`repo`, path = collection-root-relative `roles/{role}/tasks/main.yml`), a generic worked example, the explicit "no `ansible/`, no `cloud_providers/<provider>/`, no `collections/ansible_collections/<ns>/<coll>/` prefix" sentence, and 4 rules. | worked example + decision rule | 2, 5 |
| C | Guarded the monorepo Fetch bullet and the AgnosticD-structure tree: both now say they apply only to roles under `ansible/roles/`, and redirect namespaced tasks to 6b. | decision rule | 2 |
| D | **Removed `agnosticd/agnosticd-v2` from both places it appeared** — the YAML example's `scm_url` now reads `rhpds/agnosticd-v2` (matching the file's own Step 6 table), and the "Tracing Failures" bullet list was replaced by "take `owner`/`repo` from the job's Project URL; do not hardcode an owner from memory". | remove contradiction | 5 |
| E | **Type-naming requirement** in the fix contract: when the bug is one of type or shape, name **both sides** in the file format's vocabulary — what the value wrongly is, and what it becomes ("a single-quoted Python dict literal, i.e. a string; the corrected value is a real YAML mapping — proper YAML, not a quoted string"). | output contract | 3 |
| F | Citation form: every Configuration Trace `Location` cell and every "Relevant Files" line is now a single adjacent `owner/repo:path` token, with a new "Failing Role" row covering both monorepo and collection shapes; added a Citation-format block stating that a repo in one cell and a path in another cites nothing. | output contract | 4 |
| G | Critical Rules 5/6/7: fetch a location the request already names *before* searching; never end a turn offering a call you could make; a fetch whose content contradicts the log means you are in the wrong place. | decision policy | 2, 5 |
| H | Narrow escape from the mandatory Step 3–6 chain when the request already identifies the source — Step 1 (`get_job_log`) stays unconditional and first; discovery steps are skippable only for a file you were already handed. | decision policy | 2 |
| I | "Classify from where the defect lives, not from the vocabulary in the error text", plus the counterfactual test ("would it still fail on healthy infra with valid credentials?"), plus a real `platform_failure` row and a note that it is the row most often reached for wrongly. | decision rule | 1 |
| J | Critical Rule 2 now lists the category line as part of the required report. CHECKPOINT covers 6b. "Fetch the role's tasks from agnosticd" → fetch from wherever the role actually ships. | consistency | 1, 2 |
| K | `shared_context.md`: the CRITICAL grounding block now distinguishes **facts from judgments** — a classification is a conclusion drawn from evidence, is never "confirmed by a tool result" the way a timestamp is, and "not confirmed by available data" is never a substitute for a verdict the format requires. | remove blocker | 1 |
| L | `shared_context.md`: the "when NOT to include a confidence marker" bullet no longer exempts a verdict line that asks for one — `high` is written explicitly. | remove conflict | 1 |

K and L are the only `shared_context.md` edits, and both are there because the conflict
they resolve is genuinely domain-general (any agent with a verdict format hits it).
Everything domain-specific went in `aap2_agent.md`, per the lever guidance.

## 4. Verify the fix — would this have changed behaviour at the exact failure point?

- **A (category) — yes, 5/5.** The miss is total and its cause is absence: no file carried
  the taxonomy. Any correct token + confidence satisfies `_verdict_present`. Step 9 makes
  the line mandatory in three places (Critical Rule 2, output item 3, Step 9 contract).
- **B/C (collection repo) — yes, 4/5, and precisely.** The failing calls were
  `fetch_github_file(redhat-cop/agnosticd, ansible/roles/create_inventory/tasks/main.yml)`.
  6b's table maps the FQCN onto exactly the expected call, and the "no `ansible/` prefix"
  sentence forbids the exact wrong path they used. Seed-2's
  `ansible/collections/ansible_collections/agnosticd/cloud_provider_openshift_cnv/...`
  probe is forbidden by the same sentence's third clause.
- **D (forbidden repo) — yes, and this is the strongest single verification.** Seed-2's
  forbidden call was `fetch_github_file(agnosticd/agnosticd-v2)`, and that exact
  `owner/repo` was printed in the prompt twice. Removing it removes the source. 6b rule 2
  ("do not fall back to a monorepo; recover *within the same repo*") blocks the fallback
  reasoning that produced the other seven probes. Seed-2 recovers 0.583 → ~1.0, since
  `unmatched_expected` was already empty and `category` was its only answer gap.
- **E (the-fix) — yes, 3/5.** Note what the data corrected here: `dict-literal` was
  satisfied by **all 5** seeds, so the agents already explained the Python dict literal
  correctly. The gap is only the *corrected* side. `the-fix` accepts `yaml dict / proper
  yaml / yaml mapping / real dict / actual dict / as a mapping / native yaml` — my
  corrected-side example text contains "a real YAML mapping — proper YAML", hitting two
  alternatives. This is why E is phrased as "name both sides": the first half is already
  happening, the second half is the miss.
- **F (citation) — yes, 3/5.** `_citation_present` needs repo and path within 40 chars on
  one line. A two-cell table row can never satisfy it; the merged `owner/repo:path` token
  always does.
- **H/G — supporting, not load-bearing.** They cut the 14-probe flail seed-2 needed and
  the turn budget the others spent in monorepos. I do not claim a scored item for them.

Claims I checked rather than accepted, and one I dropped:
- A subagent warned `the-fix` matching might be case-sensitive. It is not — all three
  required facts set `ignore_case: true`. No lowercase workaround needed.
- A subagent proposed forcing `application_bug` whenever the log attributes a failure to
  a role. **Rejected as overfitting** — many genuine role-internal failures are
  config-caused. Replaced with change I, which keys on *where the defect lives* and is
  neutral about which of the two rows wins.
- My own first draft of Step 9 tiered the taxonomy: "prefer the operational set", with
  `application_bug` as a fallback "only for a novel failure". That preferred set was
  character-for-character the verifier's `TAXONOMY_EXCLUSIVE`, i.e. I had written a rule
  instructing the reader to prefer the tokens that *zero* the verdict and to treat the
  required one as a last resort. Caught by an adversarial-verification subagent. Replaced
  with the flat set + "no category ranks above another" + "do not reason by elimination".
- My first draft of Rule 2 said "exactly one token from the set may appear anywhere in your
  report". `verify.py`'s own comment explains why that over-constrains: the five bare-word
  members (`configuration`, `infrastructure`, `secrets`, `resource`, `dependency`) are
  ordinary English and are deliberately **excluded** from the exclusivity scan. The rule
  now forbids naming a second *category*, and explicitly permits the ordinary words.
- My draft of change I printed four category tokens in a negative example
  ("does not make it `platform_failure`, …"). That is the same leak I had just removed from
  Step 9. Rewritten to use plain English words and point at table rows instead of tokens.

## 5. Overfitting review

No GUID, hostname, job ID, repo name, role name, ticket, or literal value from this task
appears in any added text. Every worked example is generic
(`mynamespace.my_collection` / `roles/create_thing/tasks/main.yml`).

One judgment call, stated rather than hidden: change E's lead example is the
stringified-dict case, which is this task's failure class. I kept it because
string-where-an-object-was-expected is the most common wrong-type failure in Ansible and
the weaker reader benefits from the concrete instance; the rule around it is general
("whenever the failure is one of type or structure") and two further examples (list,
integer) instantiate it differently. A future iteration that sees this rule fail to
generalise should suspect this example first.

Change D edits *factual* content (the v2 monorepo's owner) rather than adding a rule. It
is justified by the file's own Step 6 table, which already said `rhpds`. If a future run
finds `agnosticd/agnosticd-v2` is in fact a real repo the agent should sometimes read,
revert D's example change but keep the "take owner/repo from the Project URL" rule.

## 6. What to preserve if this is rejected or partially reverted

Preserve in this order — A and D carry most of the expected gain and are the most clearly
evidenced:

1. **A (Step 9 category)** — 5/5 miss, pure absence, lowest-risk edit in the candidate.
2. **D (remove `agnosticd/agnosticd-v2`)** — the prompt was supplying a forbidden call.
   Correct regardless of score.
3. **B/C (Step 6b)** — 4/5 miss; the largest tool_calls lever.
4. **F, E** — output-contract tightenings.
5. **K/L (`shared_context.md`)** — only meaningful alongside A.

## 7. Deliberately skipped

- **No `orchestrator.md` edit.** Routing was correct in 5/5. Editing it would be change
  without evidence.
- **No attempt to fix seeds 3/4's tool errors.** In those trials the GitHub tools
  hard-errored (simulator schema unavailable). That is infra noise, not promptable — the
  only edit that helps them is A, which lets a report still land a category when a read
  failed (Step 9 contract item 3 exists for exactly this).
- **No rule about the fabricated-content mock.** Seed-1's mock returned invented file
  content with `is_error=false` for a nonexistent path. I could not write an honest prompt
  rule against a tool that lies convincingly; escalated in FRAMEWORK_IMPROVEMENTS.md
  instead of faking a fix in prose.
- **No prose rule telling the agent which repos are forbidden.** The forbidden list is
  invisible to the agent, and encoding it would be scoreboard-fitting, not a capability.
  Escalated instead. D fixes the *cause* (the prompt naming the repo), not the symptom.
