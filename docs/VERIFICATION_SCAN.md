# Verification scan of an evaluation run: procedure

A generic checklist, run on each assembled run folder before it is archived (`docs/BACKUP_BOX.md` §6).
It checks that the run's result can be trusted, that the folder is complete, and that the run can be
reproduced.

**Rules for the executing agent**
- **This document is read-only.** Never edit it. Write the findings for each run into
  `SCAN_RESULTS_<TS>.md` in **that run's folder** (it is uploaded with the folder). `<TS>` is the full
  UTC timestamp at which the scan started, `YYYYMMDDTHHMMSSZ`, and it is the same for every run in one
  scan.
- Check against **evidence**: transcripts, logs, run state, files. Never take a plan's or a post's
  statement on trust. When the evidence contradicts a published claim, that is a finding.
- Report every check, including the ones that pass, with the evidence: counts, file paths, the
  command used. A check that cannot be run is reported as **not run**, with the reason. It is not a
  pass.
- Do not change the run's data to make a check pass.

## Severity

| level | meaning |
|---|---|
| **INVALIDATES** | the run's result cannot be used as reported (an isolation breach, a broken comparability rule) |
| **QUALIFIES** | the result stands only with a stated caveat (a disclosed deviation, an estimated cost) |
| **INFO** | worth knowing; changes nothing |
| **PASS** | the check was run and found nothing |

The run's status (`docs/BACKUP_BOX.md` §2) follows from the worst finding.

---

## A. Isolation: did the method see what it must not?

1. **Answer and gold access.** Grep every optimizer and orchestrator transcript, subagent
   transcripts included, every workdir and every method store for:
   - the benchmark's gold paths and file names (ground truth, answers, solutions, evaluation code,
     private data);
   - task generators or any source that encodes solutions;
   - evaluator invocations.

   Read the **tool calls**, not just text matches: a path named in an instruction or a lint command
   is not access. List each real access with round, file and transcript.
2. **Test access.** Search the same places for held-out task ids and test-only files. Do not rely on a
   canary string unless it is unique to the test split: some benchmarks use one canary for every task.
3. **Copies.** Look for copies of data roots or gold that an agent made (`cp -r`, new directories in
   `/tmp`), and check whether anything read them.
4. **Beyond the intended context.** List any source the method read outside what the plan allowed,
   for example the benchmark's implementation code. Grade it: **INVALIDATES** if it encodes answers
   or solutions, **QUALIFIES** if it is environment code shared by every task.
5. **Isolation mechanism.** If a wrapper or sandbox was used, record:
   - its allowlist or denylist, and whether it was active for **every** optimizer call (from the
     guard logs);
   - whether its own pre-run check (a planted-secret test or similar) passed;
   - whether anything was reachable that should not have been.
6. **The agent under test.** Check that its own code (for example REPL code) did not touch gold
   paths, from per-episode flags or a grep of the trajectories.

## B. Comparability: was the comparison fair?

1. **Models as actually used.** From the transcripts, count assistant messages and tokens **by model
   and by role** (main loop, subagent, helper) for every optimizer call of every arm. Compare with the
   models the plan and the posts report.
   - A subagent or helper on a different model from the one stated is a finding: check the CLI's
     inherited settings, such as `CLAUDE_CODE_SUBAGENT_MODEL`.
   - Different optimizer models across the arms of one comparison is **INVALIDATES** for a
     same-model claim.
2. **CLI and tool versions** per run (from the transcripts), and the effort and thinking settings
   they inherited.
3. **Budgets.** For each arm: search episodes, optimizer calls, tokens and cost. Report unmatched
   budgets.
4. **One window.** Arms that are compared must have been scored in the same window, with frozen
   artifacts whose hashes match. Re-scored arms must be byte-identical to their earlier copies.
5. **Window-to-window drift.** If the same artifact was scored in two windows, report the difference
   between them. Compare any between-arm gap with that drift.

## B2. Intent versus actual: configuration as run

For **every item of the original plan's configuration**, compare what the plan intended with what
the evidence shows actually ran. Report it as a table (`item | intended (plan, with section) | actual
(evidence) | match?`), including the rows that match. At least:
- **agent model**: id, provider and endpoint, sampling parameters, seeds, step, token and context
  limits;
- **optimizer model per role**: main loop, subagents, helpers. Take these from the transcripts,
  counting messages and output tokens per model and role;
- **optimizer CLI**: version, flags, permission mode, and the settings it **inherited** from user or
  global config (subagent model, effort, thinking, plugins). Settings applied without anyone choosing
  them count as findings when they differ from the intent;
- **other methods' models**: the library calls (for example litellm), embedding models and their
  revisions;
- **algorithm and gate**: iterations planned versus scored, trials, gate rule and threshold,
  budgets and caps;
- **data**: benchmark version, splits and counts, data hashes;
- **code**: the commit and patch intended versus the code actually run (§E);
- **isolation**: what the plan intended versus what was actually in force, per round;
- **tools and environment**: interpreter and package versions, and any tool installed during the run.

Also record checks done in passing that confirm the intent (for example "Claude Code version
identical in all sessions"). A confirmed match is evidence too.

## C. Validity of the measurement

1. **Splits.** Only the intended splits were used, and none overlap. Test ids appear in no
   search-time file.
2. **Search score versus held-out score.** Label the search score as a fit metric when it is
   measured on training tasks.
3. **Infrastructure errors.** Count missing cells, retries and episodes that hit a wall-time limit;
   check that errors were not scored as failures.
4. **Harness behaviour.** Check that the limits the plan relied on were enforced (token caps, step
   caps). Check for silent truncation, including the context window.
5. **Run interruptions.** Look for evaluation errors, resumes and iterations lost to harness faults.
   Check that the iteration counts in the results match what was actually scored.
6. **Gate decisions.** For each round, check that the accept/reject verdict follows from the logged
   scores and the gate rule.
7. **Determinism.** Measure trial-to-trial disagreement. Do not report a "deterministic" claim
   without that measurement.
8. **Feasibility.** Check whether any arm ran in a reduced mode (for example a context limit), and
   whether that is disclosed.

## D. Completeness of the folder

1. Every regular source file of the run has a byte-identical copy (sha256) in the folder.
2. Present, for every round and attempt: the ledger, journal and insights files, every round's
   workdir, the run state and events, and the candidates.
3. The posts are complete: every comment on the tracking issue(s) for this run, the full thread, and
   the linked issues and PRs. Each item has its URL and timestamps.
4. `data/metrics_full.jsonl` has reward, tokens, latency and cost for every episode, round and run
   total. Each cost names its source. Unpriced costs are `null` with a reason, never `0`. Episode
   rewards reproduce the published results.
   Once the file is verified, render it into the same folder as `data/metrics_full.md` and
   `data/metrics_full.html`. People reading the Box folder in a browser can then see the results
   without opening JSONL. Both files show the same content:
   - the run total, and a per-arm summary (reward, tokens, latency, cost), first;
   - one table per row level (round or step, optimizer call, episode). Every value keeps its source,
     and a `null` cost is shown with its reason, never as `0`;
   - a header naming the source file and its sha256.

   The HTML is one self-contained file: inline CSS, no scripts and no external resources, so that
   Box's preview shows it. Check that the totals and per-arm figures in the rendered files equal
   those computed from `metrics_full.jsonl`.

   Then write a high-level summary into the same folder as `data/metrics_summary.json` (pure JSON)
   and `data/metrics_summary.md`. Every run folder has one. Both files show the same content. It
   has one entry for the run's candidate and one for the **baseline** (the seed arm), and the
   baseline is reported like any other candidate. For each entry:
   1. **Train reward:** TGC and SGC of the candidate's champion at the end of the search, on the
      search split. Name the split, the number of tasks and the round it comes from. This is a fit
      metric (§C2).
   2. **Test reward:** TGC and SGC of the champion in the held-out window. Name the window and the
      number of tasks and trials.
   3. **Phase cost:** tokens (prompt and completion) and USD for the train phase and for the test
      phase, each with its source. The train phase is the optimizer calls plus the search episodes;
      show the two parts as well as their sum.
   4. **Task cost:** total and average agent cost (tokens and USD) per task, for all tasks,
      successful tasks and failed tasks. Give each one for train, for test and for train and test
      together, with the number of tasks next to each average. A task here is one episode (one task,
      one trial). It is successful when it meets the benchmark's success criterion (for AppWorld:
      every test passes, so it counts towards TGC). Optimizer cost is not a task cost.

   Any figure that was not measured is `null` with a reason. An average over zero tasks is `null`
   too, never `0`. When a case below applies, state in the entry which rule was used:
   - **Train reward of the candidate.** Use the method's own end-of-search score of the champion it
     froze (the score it selected on), on the split it searched. If the frozen champion was also
     re-scored inside the test window (for example a dev diagnostic), report that as well, beside it
     and labelled. Never put the re-score in its place.
   - **No end-of-search score.** Some methods never score the champion they froze (for example online
     adaptation that keeps the last state). Then use the earliest scoring of that frozen champion on
     a non-test split (for example a dev diagnostic), and name the split. Report the method's own
     running score (for example the mean reward over its adaptation episodes) beside it, labelled as
     a fit metric. If neither exists, train reward is `null` with the reason.
   - **Train reward of the baseline.** Use the seed's own scoring on the candidate's search split (for
     example a round-0 evaluation), if one exists. Otherwise use the seed's scoring on another non-test
     split in the same window (for example the dev diagnostic), and name the split. If neither exists,
     it is `null` with the reason. The baseline has no optimizer calls, so its optimizer cost is `null`
     with the reason "not applicable: no search".
   - **Infra-errored episodes.** Score them as failed in TGC and SGC, as the published results do.
     They have no usage, so leave them out of the token and cost totals and averages. Show their count
     next to each average.
   - **Unpriced endpoints.** If a model's calls are not priced (for example IBM RITS), its USD is
     `null` with the reason. You may add a separate `usd_estimated` at a named public rate, but never
     add it into a measured or reported USD. Totals show the known USD, and separately the known USD
     plus the estimates.
   - **What each phase includes.** Train = every search episode the method ran and every optimizer
     call. Test = the champion's episodes in the test window. Count reused episodes (for example a
     baseline reused from an earlier attempt) only in the entry that ran them, and say so in the
     entry that reuses them. Diagnostic episodes that belong to neither phase (for example a dev
     re-score inside the window) are reported apart, never added to train or test.
   - **Several attempts in one run** (`docs/BACKUP_BOX.md` §1). Each attempt is an entry of its own. An attempt
     never scored on test has a `null` test reward with the reason.

   The baseline is scored once for all candidates in a window. So compute its entry **once per
   window**, from that window's data, and put the identical entry into the summary of every run that
   the window scores. Each summary names the window and the source file and sha256 of each entry.
   Runs scored in different windows each get their own window's baseline (§B4).
   Check that each figure equals the value computed from `metrics_full.jsonl` (or from the baseline's
   source, for its entry). Check also that the baseline entry is byte-identical in every summary that
   shares a window.
5. Symlinks are listed in `SYMLINKS.txt` with their targets.
6. The cap-evolve tools load the copy: `cap-evolve tail --from-start` exits 0, and the dashboard
   renders in memory.
7. Secret scan: 0 hits.
8. Licence: data under a redistribution rule is marked in `NOTICE.md`, and its handling was decided
   by the owner.

## E. Reproducibility

1. The code bundle verifies, and every commit in `code_commits.json` checks out.
2. The commit in effect for each run is shown by its start time and by byte comparison of the run's
   own code copies. Code that was never committed was recovered and matches every surviving copy.
3. Data identity, environment freezes, model list (as used), inherited config, host facts and
   `REPRODUCE.md` are present, and their hashes match.
4. Anything a repeat needs that could not be captured (for example an endpoint's backend version)
   is listed as a known gap.

## F. Published claims

List every claim in the run's posts and result pages (numbers, models, isolation, budgets). Check
each one against the evidence. Report any that is contradicted, with the correct value, and whether a
correction has been posted.

---

## `SCAN_RESULTS_<TS>.md` format

```
# Verification scan: <run folder name>
Scan started: <TS>   ·   Procedure: docs/VERIFICATION_SCAN.md @ <commit>
Status: <scored | qualified | invalid | discarded> — <one line why>

## Summary
| check | result | severity |
| A1 … | … | PASS / INFO / QUALIFIES / INVALIDATES / not run |

## Intent versus actual (B2)
| item | intended | actual | match? |

## Findings
### <id>. <title>  (severity)
Evidence: <counts, paths, commands>
Effect on the result: <…>
Already disclosed: <where, or "no">

## Known gaps
## Open decisions (for the owner)
```
