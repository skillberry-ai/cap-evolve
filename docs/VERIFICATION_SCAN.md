# Verification scan of an evaluation run: procedure

**Procedure v2.0.** A generic checklist, run on each assembled run folder of `docs/BACKUP_BOX.md`
(v2.0, §9). It checks four things:
- the run's result can be trusted;
- the folder is complete, and its gaps are reported;
- the run can be reproduced;
- the published claims hold.

It applies to every benchmark. Benchmark differences come only from the benchmark's profile
(`docs/backup_profiles/<bench-id>.md`, as used for the run and copied into its folder as `PROFILE.md`;
`docs/BACKUP_BOX.md` §4).

**Rules for the executing agent**
- **This document is read-only.** Never edit it. Write the findings for each run into
  `SCAN_RESULTS_<TS>.md` and `SCAN_RESULTS_<TS>.json`, in **that run's folder**. The `.json` has the
  same content (`docs/BACKUP_BOX.md` Appendix A.8). `<TS>` is the full UTC timestamp at which the scan
  started, `YYYYMMDDTHHMMSSZ`, and it is the same for every run in one scan. If a rule here is wrong,
  say so in the results and propose the change in an issue.
- **Two stages.**
  - **Capture gate** (at backup time, `docs/BACKUP_BOX.md` §5.10): D1, D2, D3 and D5.
  - **Later**, from the captured copy: every other check. A check whose evidence is a live source
    (for example a transcript store) must have had that evidence captured. Otherwise the check is
    `not run (gap G<n>)`.
- **Check against evidence**: transcripts, logs, run state, files. Never take a plan's or a post's
  statement on trust. When the evidence contradicts a published claim, that is a finding.
- **Report every check**, including the ones that pass, with its evidence: counts, file paths, and
  the command used. Every check has exactly one result:
  - **`PASS`**, or a finding with its severity;
  - **`not run`**, with the reason; if the reason is missing data, cite the gap id from `GAPS.json`,
    as `not run (gap G<n>)`;
  - **`not applicable`**, when the run's design makes the check meaningless (for example a test-access
    check on a run with no held-out split). Take the reason from the profile or `runmeta`.

  `not run` and `not applicable` are never a pass.
- **Do not change the run's data to make a check pass.**
- **Use the profile's values** wherever a check names one: gold paths, allowed gold, isolation
  mechanism, agent-under-test evidence, models-as-used source, infra detectors, success criterion,
  group metric.

## Severity

| level | meaning |
|---|---|
| **INVALIDATES** | the run's result cannot be used as reported (an isolation breach, a broken comparability rule) |
| **QUALIFIES** | the result stands only with a stated caveat (a disclosed deviation, an estimated cost, no held-out split, a gap that leaves a claim unverifiable) |
| **INFO** | worth knowing; changes nothing |
| **PASS** | the check was run and found nothing |
| **not applicable** | the check does not apply to this run's design; reason stated |
| **not run** | the check could not be run; reason stated, with the gap id if data is missing |

**The run's status** (`docs/BACKUP_BOX.md` §2.4) follows from the worst finding:
- INVALIDATES → `invalid`;
- QUALIFIES → `qualified`;
- otherwise `scored`.

`discarded`, `superseded` and `smoke` are owner decisions, recorded with their reason. A run with no
held-out split is at best `qualified` (A2).

---

## A. Isolation: did the method see what it must not?

1. **Answer and gold access.** Grep every optimizer and orchestrator transcript (subagent transcripts
   included), every workdir and every method store. Look for:
   - the profile's `gold.paths` and the file names in them: ground truth, answers, solutions,
     evaluation code, private data;
   - gold carried inside records (the profile's `gold.in_records`, for example gold actions inside
     rollout metadata copied into the optimizer's trajectories);
   - task generators, or any source that encodes solutions;
   - evaluator invocations.

   Exclude the profile's `false_positive_terms`.

   Read the **tool calls**, not just text matches: a path named in an instruction or a lint command
   is not access. List each real access with round, file and transcript, and grade it against the
   profile:
   - access to gold the profile lists under `allowed_to_optimizer` (for example train-task gold in a
     design that grants it) is **INFO**;
   - access to `forbidden` gold (for example any test-split task's gold) is **INVALIDATES**.

   **A1b. Hardcoding.** In designs that give the optimizer gold, check the champion and every accepted
   candidate for test-task ids, gold values or gold-derived literals written into the capability. Any
   test-task material is INVALIDATES. Train-task material is QUALIFIES, with the extent.
2. **Test access.** Search the same places for held-out task ids and test-only files.
   - Do not rely on a canary string unless it is unique to the test split. Some benchmarks use one
     canary for every task.
   - If `runmeta.splits.holdout` is false, A2 is **not applicable**. The run's status is then at best
     `qualified`, with the reason "no held-out split: the test score is a fit metric".
3. **Copies.** Look for copies of data roots or gold that an agent made (`cp -r`, new directories in
   `/tmp`; captured in `isolation/agent_copies/`), and check whether anything read them.
4. **Beyond the intended context.** List any source the method read outside what the plan allowed,
   for example the benchmark's implementation code. Grade it:
   - **INVALIDATES** if it encodes answers or solutions;
   - **QUALIFIES** if it is environment code shared by every task.
5. **Isolation mechanism.** If the profile's `isolation_mechanism` names one, record:
   - its allowlist or denylist, and whether it was active for **every** optimizer call (from the
     guard logs);
   - whether its own pre-run check (a planted-secret test or similar) passed;
   - whether anything was reachable that should not have been.

   If the profile says `none`, record **QUALIFIES**: "no isolation mechanism: isolation rests on the
   A1–A3 evidence alone". A1–A3 must then have been run on every transcript, with none `not run`.
6. **The agent under test.** Check that its own code did not touch gold, using the profile's
   `agent_under_test_evidence`:
   - per-episode flags (for example a file-system probe);
   - the gold-mount flag;
   - the contents of the agent's worktree;
   - whether the grader was supplied by the candidate (packaged graders);
   - the network mode;
   - otherwise, a grep of the trajectories.

## B. Comparability: was the comparison fair?

1. **Models as actually used.** From the transcripts of **every CLI involved** (optimizer, an agent
   under test that is itself a CLI, judges), count assistant messages and tokens **by model and by
   role** (main loop, subagent, helper), for every optimizer call of every arm. Take the agent's and
   the user simulator's models from the profile's `models_as_used_source`. Compare with the models the
   plan and the posts report.
   - A subagent or helper on a different model from the one stated is a finding. Check the settings
     the CLI inherited (for Claude Code, for example, `CLAUDE_CODE_SUBAGENT_MODEL`; for other CLIs,
     their own config).
   - Different optimizer models across the arms of one comparison is **INVALIDATES** for a same-model
     claim.
2. **CLI and tool versions** per run, taken from the transcripts and the live-state snapshot, together
   with the effort and thinking settings each CLI inherited.
3. **Budgets.** For each arm: search episodes, optimizer calls, tokens and cost, per cost category.
   Report unmatched budgets.
4. **One window.** Arms that are compared must have been scored in the same window, with frozen
   artifacts whose hashes match. Re-scored arms must be byte-identical to their earlier copies.
   Copies of a shared window in different run folders must be identical.
5. **Window-to-window drift.** If the same artifact was scored in two windows, report the difference
   between them, and compare any between-arm gap with that drift. **Not applicable** when only one
   window exists.

## B2. Intent versus actual: configuration as run

For **every item of the original plan's configuration**, compare what the plan intended with what
the evidence shows actually ran. Report it as a table (`item | intended (plan, with section) | actual
(evidence) | match?`), including the rows that match. At least:
- **agent model:** id, provider and endpoint, sampling parameters, seeds, and step, token and context
  limits;
- **user-simulator, judge and simulator models**, where the profile lists them;
- **optimizer model per role:** main loop, subagents, helpers. Take these from the transcripts,
  counting messages and output tokens per model and role;
- **optimizer CLI:** version, flags, permission mode, and the settings it **inherited** from user or
  global config (subagent model, effort, thinking, plugins, hooks, MCP servers). Settings applied
  without anyone choosing them count as findings when they differ from the intent;
- **other methods' models:** the library calls (for example litellm), embedding models and their
  revisions;
- **algorithm and gate:** iterations planned versus scored, trials, gate rule and threshold, budgets
  and caps;
- **capability as delivered:** the seed variant, and what the agent actually received. For example, a
  harness that delivers only one file of a skill package;
- **baselines:** which baseline arms were run, and where each came from (fresh, reused, from another
  run);
- **data:** benchmark version from every source that records it (they may disagree), splits and
  counts, data hashes;
- **code:** the commit and patch intended versus the code actually run (§E);
- **isolation:** what the plan intended versus what was actually in force, per round;
- **tools and environment:** interpreter and package versions, and any tool installed during the run.

Also record checks done in passing that confirm the intent (for example "CLI version identical in all
sessions"). A confirmed match is evidence too.

## C. Validity of the measurement

1. **Splits.** Only the intended splits were used, and none overlap. Test ids appear in no search-time
   file. If there is no held-out split, say so: C1 then confirms only that train, val and test are
   the declared set.
2. **Search score versus held-out score.** Label the search score a fit metric when it is measured on
   training tasks. Label the "test" score a fit metric when there is no held-out split.
3. **Infra errors.** Use the profile's `infra_error.detectors`. Count missing cells, retries and
   episodes that hit a wall-time limit. Check that the published numbers handled errors the way the
   profile's `published_rule` says, and that the summary reports both ways of scoring them
   (`as_published` and `errors_as_failures`).
4. **Harness behaviour.** Check that the limits the plan relied on were enforced (token caps, step
   caps). Check for silent truncation, including the context window.
5. **Run interruptions.** Look for evaluation errors, resumes and iterations lost to harness faults.
   Check that the iteration counts in the results match what was actually scored.
6. **Gate decisions.** For each round, check that the accept/reject verdict follows from the logged
   scores and the gate rule.
7. **Determinism.** Measure trial-to-trial disagreement. Do not report a "deterministic" claim
   without that measurement. **Not applicable** when there is one trial per task.
8. **Feasibility.** Check whether any arm ran in a reduced mode (for example a context limit), and
   whether that is disclosed.

## D. Completeness of the folder

D1, D2, D3 and D5 run in the capture gate. The rest may run later.

1. **Source copies.** Every source file of the run has a copy in the folder whose sha256 equals the
   `source_sha256` taken on the source at capture. A file without such a copy is listed in
   `REDACTIONS.json` or `GAPS.json`.
2. **Required items.** These must be present for every round, attempt and unit: the ledger, journal
   and insights files, every round's workdir, the run state and events, the candidates, and every
   item of the requirement list (`docs/BACKUP_BOX.md` §6.1). Anything missing is a gap, with its class
   and fetch attempts.
3. **Posts.** The posts must be complete: every comment on the tracking issue(s) and PRs for this run,
   the full threads, the linked issues and PRs, and the workflow runs. Each item has its URL and
   timestamps.
4. **Metrics.** `data/metrics_full.jsonl`, `data/metrics_summary.json` / `.md` and
   `data/reward_check.json` follow `docs/BACKUP_BOX.md` Appendix A.3–A.5.
   - Every value names its source.
   - Unpriced costs are `null` with a reason, never `0`. A recorded 0 counts as $0 only where the
     profile says `zero_means: zero`.
   - The published metric named in `runmeta.reward_metric` is reproduced from the episode records.
     Where it is not, that is a finding, with both values.
   - `metrics_full.html` is one self-contained file (inline CSS, no scripts, no external resources).
     Its totals and per-arm figures equal those computed from `metrics_full.jsonl`.
   - **Summary entries:** one entry for each candidate and attempt, and one for each baseline id.
     Each baseline entry is computed once per window and is byte-identical in every summary that
     shares the window. The case rules of Appendix A.4 were applied, and every rule used is named in
     `rules_applied`.
5. **Symlinks.** Every symlink is listed in `SYMLINKS.txt` with its target.
6. **cap-evolve tools.** The cap-evolve tools load the copy. `cap-evolve tail --from-start` exits 0,
   or exits 3 after reading at least one event. The dashboard renders in memory. **Not applicable**
   to partial exports, other methods and test windows.
7. **Secrets.** The secret scan finds 0 hits. Every redaction and every excluded secret store is
   listed in `REDACTIONS.json`.
8. **Licences.** The data is present in full. `NOTICE.md` lists the profile's licence, restrictions
   and protected paths, with a do-not-publish note. A missing licence entry is INFO, never a reason
   to leave data out.
9. **Gap report.**
   - `GAPS.json` and `GAPS.md` exist and are consistent: every item of the requirement list is
     present or listed as a gap; coverage figures recompute from `MANIFEST.json`; every check
     reported `not run (gap …)` points to an existing gap entry.
   - Each gap has a class, `expected` with how it was derived, `may_exist_at`, `fetch_attempts`, and
     `impact`.
   - Coverage is reported by item type, in items and bytes. Where other copies are known, it is
     reported per source and for their union, with what is unique to each.
   - Grading:
     - a gap that leaves a published claim unverifiable is **QUALIFIES**;
     - a `snapshot-incomplete` or `lost` gap in data the result depends on is **QUALIFIES**;
     - a `not-produced` gap is **INFO**.

## E. Reproducibility

These checks are static, from hashes and checkouts. No repeat run is made.

1. **Code bundles.**
   - The cap-evolve code bundle verifies, and every commit in `code_commits.json` checks out.
   - Every `reproduce/code/upstream/*.bundle` verifies and checks out at its recorded commit.
   - Where the profile names a constraint on the commit, it holds (for example parsec: the in-effect
     commit predates `aeee7126d`).
2. **The commit in effect.** For each run, it is shown by the run's start time and by byte comparison
   of the run's own code copies. Code that was never committed was recovered and matches every
   surviving copy. Where two sources of a version disagree (for example two different benchmark
   commits recorded by one run), that is a finding, with both recorded.
3. **Inputs.** Data identity, environment freezes, the model list (as used), inherited config, host
   facts and `REPRODUCE.md` are present, and their hashes match.
   - The hashes of `reproduce/data/` equal the split and tree hashes the run itself recorded.
   - Every saved image matches its digest.
4. **Known gaps.**
   - Anything a repeat needs that could not be captured is listed as a known gap: every one of the
     profile's `unpinnable` items, and every `reproduce/` slot that is not filled.
   - `runmeta.reproducibility` equals the level that `docs/BACKUP_BOX.md` §8.2 computes from the
     filled slots.
   - A folder whose README claims a higher level than this is **QUALIFIES**. `record-only` is INFO
     when disclosed.
5. **Smoke test, only on user request.** Without a request, report `not run (not requested)`. That is
   not a finding.

   When requested:
   - From the backed-up folder only, restore code, data and environment as `REPRODUCE.md` says.
   - Check that each component reports its recorded version: commit, package freeze, image digest,
     CLI version.
   - Then run the profile's smoke command: `cap-evolve check`, plus at most one task × one trial with
     the seed capability.
   - Record the versions found against the versions recorded, whether the run starts, scores and
     writes a rollout in the same shape, and the cost.
   - A version mismatch or a failure to start is **QUALIFIES**: the level is overstated.

## F. Published claims

List every claim in the run's published material: posts, result pages, and the results repo or
branch at its captured commit (README tables, full results tables, reports, decision logs). Claims
cover numbers, models, isolation and budgets.
- Check each claim against the evidence.
- Report any that is contradicted, with the correct value, and whether a correction has been
  posted.
- A deviation recorded in the results repo's own decision log counts as "already disclosed".
- A claim that cannot be checked because of a gap is `not run (gap G<n>)`, and it raises D9 to
  QUALIFIES.

---

## `SCAN_RESULTS_<TS>.md` format

The `.json` file holds the same content (`docs/BACKUP_BOX.md` Appendix A.8).

```
# Verification scan: <run folder name>
Scan started: <TS>   ·   Procedure: VERIFICATION_SCAN v2.0 @ <commit>   ·   Profile: <bench-id> (<source>)
Holdout: <yes | no>   ·   Coverage: <items %, by main type> (<source kind>)   ·   Reproducibility: <level>
Status: <scored | qualified | invalid | discarded | superseded | smoke> — <one line why>

## Summary
| check | stage | result | severity |
| A1 … | later | … | PASS / INFO / QUALIFIES / INVALIDATES / not applicable / not run (gap G<n>) |

## Intent versus actual (B2)
| item | intended | actual | match? |

## Findings
### <id>. <title>  (severity)
Evidence: <counts, paths, commands>
Effect on the result: <…>
Already disclosed: <where, or "no">

## Gaps that affected this scan
| gap | class | checks not run | effect |

## Known gaps (reproducibility)
## Open decisions (for the owner)
```
